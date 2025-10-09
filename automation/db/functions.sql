-- Capital.com MCP Automation - Database Functions & Triggers
-- PostgreSQL 16+

-- ============================================================================
-- UTILITY FUNCTIONS
-- ============================================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to relevant tables
CREATE TRIGGER update_instruments_updated_at BEFORE UPDATE ON instruments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_intents_updated_at BEFORE UPDATE ON intents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trades_updated_at BEFORE UPDATE ON trades
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_bandit_state_updated_at BEFORE UPDATE ON bandit_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();


-- ============================================================================
-- RISK CALCULATION FUNCTIONS
-- ============================================================================

-- Calculate position size based on risk parameters
CREATE OR REPLACE FUNCTION calculate_position_size(
    p_account_balance DECIMAL,
    p_risk_pct DECIMAL,
    p_entry_price DECIMAL,
    p_stop_loss DECIMAL
) RETURNS DECIMAL AS $$
DECLARE
    v_risk_amount DECIMAL;
    v_price_distance DECIMAL;
    v_position_size DECIMAL;
BEGIN
    -- Calculate risk amount
    v_risk_amount := p_account_balance * (p_risk_pct / 100.0);
    
    -- Calculate price distance (percentage)
    v_price_distance := ABS(p_entry_price - p_stop_loss) / p_entry_price;
    
    -- Calculate position size
    v_position_size := v_risk_amount / (p_entry_price * v_price_distance);
    
    RETURN v_position_size;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- Calculate risk-reward ratio
CREATE OR REPLACE FUNCTION calculate_risk_reward(
    p_entry_price DECIMAL,
    p_stop_loss DECIMAL,
    p_take_profit DECIMAL
) RETURNS DECIMAL AS $$
DECLARE
    v_risk DECIMAL;
    v_reward DECIMAL;
BEGIN
    v_risk := ABS(p_entry_price - p_stop_loss);
    v_reward := ABS(p_take_profit - p_entry_price);
    
    IF v_risk = 0 THEN
        RETURN NULL;
    END IF;
    
    RETURN v_reward / v_risk;
END;
$$ LANGUAGE plpgsql IMMUTABLE;


-- Check if account has sufficient risk capacity
CREATE OR REPLACE FUNCTION check_risk_capacity(
    p_epic VARCHAR,
    p_new_risk_usd DECIMAL,
    p_max_portfolio_risk_pct DECIMAL DEFAULT 5.0
) RETURNS BOOLEAN AS $$
DECLARE
    v_current_risk DECIMAL;
    v_account_balance DECIMAL;
    v_max_risk DECIMAL;
BEGIN
    -- Get current account balance (from most recent balance check)
    -- In production, this would query account balance
    v_account_balance := 10000;  -- Placeholder
    
    -- Calculate current risk from open trades
    SELECT COALESCE(SUM(ABS(entry_price - stop_loss) * size), 0)
    INTO v_current_risk
    FROM trades
    WHERE status = 'OPEN';
    
    -- Calculate maximum allowed risk
    v_max_risk := v_account_balance * (p_max_portfolio_risk_pct / 100.0);
    
    -- Check if new trade would exceed limit
    RETURN (v_current_risk + p_new_risk_usd) <= v_max_risk;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- PERFORMANCE CALCULATION FUNCTIONS
-- ============================================================================

-- Calculate win rate for a strategy/instrument
CREATE OR REPLACE FUNCTION calculate_win_rate(
    p_strategy_name VARCHAR DEFAULT NULL,
    p_epic VARCHAR DEFAULT NULL,
    p_days INTEGER DEFAULT 20
) RETURNS DECIMAL AS $$
DECLARE
    v_total_trades INTEGER;
    v_winning_trades INTEGER;
    v_win_rate DECIMAL;
BEGIN
    SELECT 
        COUNT(*),
        SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END)
    INTO v_total_trades, v_winning_trades
    FROM trades
    WHERE status = 'CLOSED'
        AND entry_time > NOW() - (p_days || ' days')::INTERVAL
        AND (p_strategy_name IS NULL OR strategy_name = p_strategy_name)
        AND (p_epic IS NULL OR epic = p_epic);
    
    IF v_total_trades = 0 THEN
        RETURN 0.5;  -- Default to 50% if no trades
    END IF;
    
    v_win_rate := v_winning_trades::DECIMAL / v_total_trades::DECIMAL;
    RETURN v_win_rate;
END;
$$ LANGUAGE plpgsql;


-- Calculate profit factor
CREATE OR REPLACE FUNCTION calculate_profit_factor(
    p_strategy_name VARCHAR DEFAULT NULL,
    p_epic VARCHAR DEFAULT NULL,
    p_days INTEGER DEFAULT 20
) RETURNS DECIMAL AS $$
DECLARE
    v_gross_profit DECIMAL;
    v_gross_loss DECIMAL;
    v_profit_factor DECIMAL;
BEGIN
    SELECT 
        COALESCE(SUM(CASE WHEN net_pnl > 0 THEN net_pnl ELSE 0 END), 0),
        COALESCE(ABS(SUM(CASE WHEN net_pnl < 0 THEN net_pnl ELSE 0 END)), 1)
    INTO v_gross_profit, v_gross_loss
    FROM trades
    WHERE status = 'CLOSED'
        AND entry_time > NOW() - (p_days || ' days')::INTERVAL
        AND (p_strategy_name IS NULL OR strategy_name = p_strategy_name)
        AND (p_epic IS NULL OR epic = p_epic);
    
    IF v_gross_loss = 0 THEN
        RETURN NULL;  -- Undefined if no losses
    END IF;
    
    v_profit_factor := v_gross_profit / v_gross_loss;
    RETURN v_profit_factor;
END;
$$ LANGUAGE plpgsql;


-- Calculate Sharpe ratio (simplified)
CREATE OR REPLACE FUNCTION calculate_sharpe_ratio(
    p_strategy_name VARCHAR DEFAULT NULL,
    p_days INTEGER DEFAULT 20
) RETURNS DECIMAL AS $$
DECLARE
    v_avg_return DECIMAL;
    v_std_dev DECIMAL;
    v_sharpe DECIMAL;
BEGIN
    -- Calculate average return and standard deviation of returns
    SELECT 
        AVG(net_pnl),
        STDDEV(net_pnl)
    INTO v_avg_return, v_std_dev
    FROM trades
    WHERE status = 'CLOSED'
        AND entry_time > NOW() - (p_days || ' days')::INTERVAL
        AND (p_strategy_name IS NULL OR strategy_name = p_strategy_name);
    
    IF v_std_dev IS NULL OR v_std_dev = 0 THEN
        RETURN NULL;
    END IF;
    
    -- Simplified Sharpe (assuming risk-free rate = 0)
    v_sharpe := v_avg_return / v_std_dev;
    RETURN v_sharpe;
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- BANDIT FUNCTIONS
-- ============================================================================

-- Calculate UCB (Upper Confidence Bound) score for a strategy
CREATE OR REPLACE FUNCTION calculate_ucb_score(
    p_strategy_name VARCHAR,
    p_total_pulls INTEGER,
    p_confidence_level DECIMAL DEFAULT 1.96
) RETURNS DECIMAL AS $$
DECLARE
    v_pulls INTEGER;
    v_avg_reward DECIMAL;
    v_exploration_bonus DECIMAL;
    v_ucb_score DECIMAL;
BEGIN
    -- Get strategy metrics
    SELECT pulls, avg_reward
    INTO v_pulls, v_avg_reward
    FROM bandit_state
    WHERE strategy_name = p_strategy_name;
    
    IF v_pulls = 0 THEN
        RETURN 999999;  -- Prioritize unexplored strategies
    END IF;
    
    -- Calculate exploration bonus
    v_exploration_bonus := p_confidence_level * SQRT(LN(p_total_pulls) / v_pulls);
    
    -- UCB score = exploitation + exploration
    v_ucb_score := COALESCE(v_avg_reward, 0) + v_exploration_bonus;
    
    RETURN v_ucb_score;
END;
$$ LANGUAGE plpgsql;


-- Update bandit state after trade completion
CREATE OR REPLACE FUNCTION update_bandit_state(
    p_strategy_name VARCHAR,
    p_reward DECIMAL
) RETURNS VOID AS $$
DECLARE
    v_window_start TIMESTAMP;
BEGIN
    -- Define 20-day rolling window
    v_window_start := NOW() - INTERVAL '20 days';
    
    -- Upsert bandit state
    INSERT INTO bandit_state (strategy_name, pulls, wins, total_reward, last_selected_at, selection_count, window_start, window_end)
    VALUES (
        p_strategy_name,
        1,
        CASE WHEN p_reward > 0 THEN 1 ELSE 0 END,
        p_reward,
        NOW(),
        1,
        v_window_start,
        NOW()
    )
    ON CONFLICT (strategy_name) DO UPDATE SET
        pulls = (
            SELECT COUNT(*)
            FROM trades
            WHERE strategy_name = p_strategy_name
                AND entry_time > v_window_start
                AND status = 'CLOSED'
        ),
        wins = (
            SELECT COUNT(*)
            FROM trades
            WHERE strategy_name = p_strategy_name
                AND entry_time > v_window_start
                AND status = 'CLOSED'
                AND net_pnl > 0
        ),
        total_reward = (
            SELECT COALESCE(SUM(net_pnl), 0)
            FROM trades
            WHERE strategy_name = p_strategy_name
                AND entry_time > v_window_start
                AND status = 'CLOSED'
        ),
        win_rate = (
            SELECT COUNT(*)::DECIMAL / NULLIF(COUNT(*), 0)
            FROM trades
            WHERE strategy_name = p_strategy_name
                AND entry_time > v_window_start
                AND status = 'CLOSED'
                AND net_pnl > 0
        ),
        avg_reward = (
            SELECT AVG(net_pnl)
            FROM trades
            WHERE strategy_name = p_strategy_name
                AND entry_time > v_window_start
                AND status = 'CLOSED'
        ),
        window_start = v_window_start,
        window_end = NOW(),
        updated_at = NOW();
END;
$$ LANGUAGE plpgsql;


-- ============================================================================
-- TRADE LIFECYCLE TRIGGERS
-- ============================================================================

-- Auto-update bandit state when trade is closed
CREATE OR REPLACE FUNCTION trigger_update_bandit_on_trade_close()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.status = 'CLOSED' AND OLD.status = 'OPEN' THEN
        PERFORM update_bandit_state(NEW.strategy_name, NEW.net_pnl);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trade_closed_update_bandit
    AFTER UPDATE ON trades
    FOR EACH ROW
    WHEN (NEW.status = 'CLOSED' AND OLD.status = 'OPEN')
    EXECUTE FUNCTION trigger_update_bandit_on_trade_close();


-- Log system events on critical actions
CREATE OR REPLACE FUNCTION log_critical_event()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_TABLE_NAME = 'orders' AND NEW.status = 'FILLED' THEN
        INSERT INTO system_events (event_type, severity, message, epic, order_id, source)
        VALUES ('ORDER_FILLED', 'INFO', 'Order ' || NEW.deal_reference || ' filled', NEW.epic, NEW.id, 'db_trigger');
    ELSIF TG_TABLE_NAME = 'trades' AND NEW.status = 'CLOSED' THEN
        INSERT INTO system_events (event_type, severity, message, epic, trade_id, details, source)
        VALUES (
            'TRADE_CLOSED',
            CASE WHEN NEW.net_pnl > 0 THEN 'INFO' ELSE 'WARNING' END,
            'Trade closed with P&L: ' || NEW.net_pnl,
            NEW.epic,
            NEW.id,
            jsonb_build_object('pnl', NEW.net_pnl, 'holding_time', NEW.holding_time_minutes, 'exit_reason', NEW.exit_reason),
            'db_trigger'
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_order_filled
    AFTER UPDATE ON orders
    FOR EACH ROW
    WHEN (NEW.status = 'FILLED')
    EXECUTE FUNCTION log_critical_event();

CREATE TRIGGER log_trade_closed
    AFTER UPDATE ON trades
    FOR EACH ROW
    WHEN (NEW.status = 'CLOSED')
    EXECUTE FUNCTION log_critical_event();


-- ============================================================================
-- HELPER VIEWS FUNCTIONS
-- ============================================================================

-- Get current portfolio summary
CREATE OR REPLACE FUNCTION get_portfolio_summary()
RETURNS TABLE (
    total_positions INTEGER,
    total_exposure_usd DECIMAL,
    unrealized_pnl DECIMAL,
    daily_pnl DECIMAL,
    weekly_pnl DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(*)::INTEGER AS total_positions,
        SUM(entry_price * size)::DECIMAL AS total_exposure_usd,
        SUM(gross_pnl)::DECIMAL AS unrealized_pnl,
        (SELECT SUM(net_pnl) FROM trades WHERE entry_time >= CURRENT_DATE)::DECIMAL AS daily_pnl,
        (SELECT SUM(net_pnl) FROM trades WHERE entry_time >= CURRENT_DATE - INTERVAL '7 days')::DECIMAL AS weekly_pnl
    FROM trades
    WHERE status = 'OPEN';
END;
$$ LANGUAGE plpgsql;


-- Get top ranked instruments for trading
CREATE OR REPLACE FUNCTION get_top_ranked_instruments(p_limit INTEGER DEFAULT 3)
RETURNS TABLE (
    epic VARCHAR,
    name VARCHAR,
    rank_score DECIMAL,
    volatility_atr DECIMAL,
    avg_daily_volume DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        i.epic,
        i.name,
        (COALESCE(i.volatility_atr, 0) * 0.3 + 
         COALESCE(i.avg_daily_volume, 0) / 1000000 * 0.25)::DECIMAL AS rank_score,
        i.volatility_atr,
        i.avg_daily_volume
    FROM instruments i
    WHERE i.tradeable = true
    ORDER BY rank_score DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

