-- Capital.com MCP Automation - Database Schema
-- PostgreSQL 16+

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================================
-- INSTRUMENTS & WATCHLIST
-- ============================================================================

CREATE TABLE instruments (
    id SERIAL PRIMARY KEY,
    epic VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    instrument_type VARCHAR(50) NOT NULL,  -- CURRENCIES, CRYPTOCURRENCIES, INDICES, COMMODITIES, etc.
    market_status VARCHAR(20),
    tradeable BOOLEAN DEFAULT true,
    
    -- Metadata
    lot_size DECIMAL(20, 8),
    min_size DECIMAL(20, 8),
    max_size DECIMAL(20, 8),
    pip_value DECIMAL(20, 8),
    
    -- Ranking factors
    avg_daily_volume DECIMAL(20, 2),
    avg_spread DECIMAL(20, 8),
    volatility_atr DECIMAL(20, 8),
    
    -- Tracking
    added_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_traded_at TIMESTAMP,
    
    CONSTRAINT chk_market_status CHECK (market_status IN ('TRADEABLE', 'CLOSED', 'SUSPENDED'))
);

CREATE INDEX idx_instruments_epic ON instruments(epic);
CREATE INDEX idx_instruments_tradeable ON instruments(tradeable) WHERE tradeable = true;
CREATE INDEX idx_instruments_type ON instruments(instrument_type);


-- ============================================================================
-- MARKET DATA - CANDLES
-- ============================================================================

CREATE TABLE candles (
    id BIGSERIAL PRIMARY KEY,
    epic VARCHAR(50) NOT NULL REFERENCES instruments(epic) ON DELETE CASCADE,
    timeframe VARCHAR(10) NOT NULL,  -- 15m, 1h, 4h, 1d
    timestamp TIMESTAMP NOT NULL,
    
    -- OHLCV
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(20, 2),
    
    -- Additional fields
    spread DECIMAL(20, 8),
    num_trades INTEGER,
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(epic, timeframe, timestamp)
);

CREATE INDEX idx_candles_epic_timeframe_timestamp ON candles(epic, timeframe, timestamp DESC);
CREATE INDEX idx_candles_timestamp ON candles(timestamp DESC);


-- ============================================================================
-- SIGNALS
-- ============================================================================

CREATE TABLE signals (
    id SERIAL PRIMARY KEY,
    epic VARCHAR(50) NOT NULL REFERENCES instruments(epic),
    strategy_name VARCHAR(100) NOT NULL,  -- ORB_VWAP, SMA_RSI_ATR, DONCHIAN_BREAKOUT
    timeframe VARCHAR(10) NOT NULL,
    
    signal_type VARCHAR(10) NOT NULL,  -- BUY, SELL, NEUTRAL
    strength DECIMAL(5, 4),  -- 0.0 to 1.0
    confidence DECIMAL(5, 4),  -- 0.0 to 1.0
    
    -- Signal details (JSON)
    indicators JSONB,  -- {sma_20: 1.2345, rsi: 65.4, atr: 0.0023, ...}
    conditions JSONB,  -- {rsi_oversold: true, volume_breakout: false, ...}
    
    -- Metadata
    generated_at TIMESTAMP DEFAULT NOW(),
    valid_until TIMESTAMP,
    acted_upon BOOLEAN DEFAULT false,
    
    CONSTRAINT chk_signal_type CHECK (signal_type IN ('BUY', 'SELL', 'NEUTRAL'))
);

CREATE INDEX idx_signals_epic_strategy ON signals(epic, strategy_name);
CREATE INDEX idx_signals_generated_at ON signals(generated_at DESC);
CREATE INDEX idx_signals_acted_upon ON signals(acted_upon) WHERE acted_upon = false;


-- ============================================================================
-- TRADE INTENTS (Pre-Order Stage)
-- ============================================================================

CREATE TABLE intents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    epic VARCHAR(50) NOT NULL REFERENCES instruments(epic),
    signal_id INTEGER REFERENCES signals(id),
    strategy_name VARCHAR(100) NOT NULL,
    
    -- Intent details
    direction VARCHAR(10) NOT NULL,  -- BUY, SELL
    size DECIMAL(20, 8) NOT NULL,
    entry_price DECIMAL(20, 8),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    trailing_stop DECIMAL(20, 8),
    
    -- Risk calculation
    risk_usd DECIMAL(20, 2),
    reward_usd DECIMAL(20, 2),
    risk_reward_ratio DECIMAL(10, 4),
    
    -- AI Review
    ai_review_status VARCHAR(20) DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED
    ai_review_text TEXT,
    ai_review_score DECIMAL(5, 4),
    
    -- Approval
    approval_status VARCHAR(20) DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED, EXECUTED
    approval_token VARCHAR(200),  -- HMAC token for execution
    approval_token_expires_at TIMESTAMP,
    approved_by VARCHAR(100),  -- human, auto, ai
    approved_at TIMESTAMP,
    
    -- Execution
    executed BOOLEAN DEFAULT false,
    executed_at TIMESTAMP,
    order_id UUID,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    notes TEXT,
    
    CONSTRAINT chk_intent_direction CHECK (direction IN ('BUY', 'SELL')),
    CONSTRAINT chk_intent_ai_review CHECK (ai_review_status IN ('PENDING', 'APPROVED', 'REJECTED', 'SKIPPED')),
    CONSTRAINT chk_intent_approval CHECK (approval_status IN ('PENDING', 'APPROVED', 'REJECTED', 'EXECUTED', 'EXPIRED'))
);

CREATE INDEX idx_intents_approval_status ON intents(approval_status);
CREATE INDEX idx_intents_created_at ON intents(created_at DESC);
CREATE INDEX idx_intents_epic ON intents(epic);


-- ============================================================================
-- ORDERS
-- ============================================================================

CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    intent_id UUID REFERENCES intents(id),
    
    -- Capital.com identifiers
    deal_reference VARCHAR(100),
    deal_id VARCHAR(100),
    
    -- Order details
    epic VARCHAR(50) NOT NULL REFERENCES instruments(epic),
    direction VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,  -- MARKET, LIMIT
    size DECIMAL(20, 8) NOT NULL,
    
    -- Prices
    requested_price DECIMAL(20, 8),
    executed_price DECIMAL(20, 8),
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    trailing_stop DECIMAL(20, 8),
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING, ACCEPTED, REJECTED, FILLED, CANCELLED
    status_reason TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    submitted_at TIMESTAMP,
    filled_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Metadata
    notes TEXT,
    
    CONSTRAINT chk_order_direction CHECK (direction IN ('BUY', 'SELL')),
    CONSTRAINT chk_order_type CHECK (order_type IN ('MARKET', 'LIMIT')),
    CONSTRAINT chk_order_status CHECK (status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'FILLED', 'CANCELLED', 'EXPIRED'))
);

CREATE INDEX idx_orders_deal_reference ON orders(deal_reference);
CREATE INDEX idx_orders_deal_id ON orders(deal_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_created_at ON orders(created_at DESC);


-- ============================================================================
-- TRADES (Filled Orders)
-- ============================================================================

CREATE TABLE trades (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID REFERENCES orders(id),
    
    -- Capital.com identifiers
    deal_id VARCHAR(100),
    position_id VARCHAR(100),
    
    -- Trade details
    epic VARCHAR(50) NOT NULL REFERENCES instruments(epic),
    direction VARCHAR(10) NOT NULL,
    size DECIMAL(20, 8) NOT NULL,
    
    -- Entry
    entry_price DECIMAL(20, 8) NOT NULL,
    entry_time TIMESTAMP NOT NULL,
    
    -- Exit (NULL if still open)
    exit_price DECIMAL(20, 8),
    exit_time TIMESTAMP,
    exit_reason VARCHAR(50),  -- TAKE_PROFIT, STOP_LOSS, MANUAL, TRAILING_STOP
    
    -- P&L
    gross_pnl DECIMAL(20, 2),
    net_pnl DECIMAL(20, 2),
    fees DECIMAL(20, 2),
    
    -- Risk management
    stop_loss DECIMAL(20, 8),
    take_profit DECIMAL(20, 8),
    trailing_stop DECIMAL(20, 8),
    
    -- Status
    status VARCHAR(20) DEFAULT 'OPEN',  -- OPEN, CLOSED
    
    -- Metadata
    strategy_name VARCHAR(100),
    holding_time_minutes INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT chk_trade_direction CHECK (direction IN ('BUY', 'SELL')),
    CONSTRAINT chk_trade_status CHECK (status IN ('OPEN', 'CLOSED'))
);

CREATE INDEX idx_trades_deal_id ON trades(deal_id);
CREATE INDEX idx_trades_position_id ON trades(position_id);
CREATE INDEX idx_trades_status ON trades(status);
CREATE INDEX idx_trades_entry_time ON trades(entry_time DESC);
CREATE INDEX idx_trades_epic ON trades(epic);


-- ============================================================================
-- NEWS & SENTIMENT
-- ============================================================================

CREATE TABLE news (
    id SERIAL PRIMARY KEY,
    epic VARCHAR(50) REFERENCES instruments(epic),
    
    -- News details
    title TEXT NOT NULL,
    summary TEXT,
    full_text TEXT,
    source VARCHAR(255),
    url TEXT,
    
    -- Sentiment analysis (from AI)
    sentiment VARCHAR(20),  -- BULLISH, BEARISH, NEUTRAL
    sentiment_score DECIMAL(5, 4),  -- -1.0 to 1.0
    ai_analysis TEXT,
    
    -- Impact assessment
    impact_level VARCHAR(20),  -- HIGH, MEDIUM, LOW
    relevance_score DECIMAL(5, 4),  -- 0.0 to 1.0
    
    -- Timestamps
    published_at TIMESTAMP,
    analyzed_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT chk_news_sentiment CHECK (sentiment IN ('BULLISH', 'BEARISH', 'NEUTRAL', 'MIXED')),
    CONSTRAINT chk_news_impact CHECK (impact_level IN ('HIGH', 'MEDIUM', 'LOW'))
);

CREATE INDEX idx_news_epic ON news(epic);
CREATE INDEX idx_news_published_at ON news(published_at DESC);
CREATE INDEX idx_news_sentiment ON news(sentiment);


-- ============================================================================
-- TRADE REVIEWS (Post-Trade Analysis)
-- ============================================================================

CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    trade_id UUID REFERENCES trades(id),
    
    -- Review details
    review_type VARCHAR(20) NOT NULL,  -- AUTOMATED, MANUAL, AI
    reviewer VARCHAR(100),  -- system, human_name, gpt-4o, claude-3.5
    
    -- Assessment
    execution_quality DECIMAL(5, 4),  -- 0.0 to 1.0
    timing_score DECIMAL(5, 4),
    risk_management_score DECIMAL(5, 4),
    overall_score DECIMAL(5, 4),
    
    -- Analysis
    what_went_well TEXT,
    what_went_wrong TEXT,
    lessons_learned TEXT,
    recommendations TEXT,
    
    -- Metadata
    reviewed_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT chk_review_type CHECK (review_type IN ('AUTOMATED', 'MANUAL', 'AI'))
);

CREATE INDEX idx_reviews_trade_id ON reviews(trade_id);
CREATE INDEX idx_reviews_reviewed_at ON reviews(reviewed_at DESC);


-- ============================================================================
-- PERFORMANCE METRICS
-- ============================================================================

CREATE TABLE performance (
    id SERIAL PRIMARY KEY,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    
    -- Aggregation level
    epic VARCHAR(50) REFERENCES instruments(epic),  -- NULL for overall
    strategy_name VARCHAR(100),  -- NULL for overall
    
    -- Trade statistics
    total_trades INTEGER DEFAULT 0,
    winning_trades INTEGER DEFAULT 0,
    losing_trades INTEGER DEFAULT 0,
    win_rate DECIMAL(5, 4),
    
    -- P&L
    gross_profit DECIMAL(20, 2),
    gross_loss DECIMAL(20, 2),
    net_profit DECIMAL(20, 2),
    total_fees DECIMAL(20, 2),
    
    -- Risk metrics
    avg_win DECIMAL(20, 2),
    avg_loss DECIMAL(20, 2),
    profit_factor DECIMAL(10, 4),
    expectancy DECIMAL(20, 2),
    max_drawdown DECIMAL(20, 2),
    max_drawdown_pct DECIMAL(5, 4),
    
    -- Sharpe & Sortino
    sharpe_ratio DECIMAL(10, 4),
    sortino_ratio DECIMAL(10, 4),
    
    -- Timing
    avg_holding_time_minutes INTEGER,
    
    -- Metadata
    calculated_at TIMESTAMP DEFAULT NOW()
);

-- Create unique index with coalesce for nullable columns
CREATE UNIQUE INDEX idx_performance_unique ON performance(
    period_start, 
    period_end, 
    COALESCE(epic, ''), 
    COALESCE(strategy_name, '')
);

CREATE INDEX idx_performance_period ON performance(period_start, period_end);
CREATE INDEX idx_performance_epic ON performance(epic);
CREATE INDEX idx_performance_strategy ON performance(strategy_name);


-- ============================================================================
-- MULTI-ARMED BANDIT STATE
-- ============================================================================

CREATE TABLE bandit_state (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) UNIQUE NOT NULL,
    
    -- Bandit metrics (20-day rolling window)
    pulls INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    total_reward DECIMAL(20, 2) DEFAULT 0,
    
    -- Calculated metrics
    win_rate DECIMAL(5, 4),
    avg_reward DECIMAL(20, 2),
    ucb_score DECIMAL(20, 8),  -- Upper Confidence Bound
    
    -- Selection tracking
    last_selected_at TIMESTAMP,
    selection_count INTEGER DEFAULT 0,
    
    -- Status
    enabled BOOLEAN DEFAULT true,
    
    -- Metadata
    updated_at TIMESTAMP DEFAULT NOW(),
    window_start TIMESTAMP,
    window_end TIMESTAMP
);

CREATE INDEX idx_bandit_enabled ON bandit_state(enabled) WHERE enabled = true;
CREATE INDEX idx_bandit_ucb_score ON bandit_state(ucb_score DESC);


-- ============================================================================
-- SYSTEM EVENTS & AUDIT LOG
-- ============================================================================

CREATE TABLE system_events (
    id BIGSERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,  -- ORDER_PLACED, TRADE_CLOSED, ERROR, WARNING, etc.
    severity VARCHAR(20) NOT NULL,  -- INFO, WARNING, ERROR, CRITICAL
    
    -- Event details
    message TEXT NOT NULL,
    details JSONB,
    
    -- Context
    epic VARCHAR(50),
    strategy_name VARCHAR(100),
    trade_id UUID,
    order_id UUID,
    
    -- Metadata
    occurred_at TIMESTAMP DEFAULT NOW(),
    source VARCHAR(100),  -- n8n, mcp_caller, db_trigger, etc.
    
    CONSTRAINT chk_event_severity CHECK (severity IN ('INFO', 'WARNING', 'ERROR', 'CRITICAL'))
);

CREATE INDEX idx_system_events_occurred_at ON system_events(occurred_at DESC);
CREATE INDEX idx_system_events_severity ON system_events(severity);
CREATE INDEX idx_system_events_event_type ON system_events(event_type);


-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Open positions summary
CREATE VIEW v_open_positions AS
SELECT 
    t.id,
    t.epic,
    i.name AS instrument_name,
    t.direction,
    t.size,
    t.entry_price,
    t.stop_loss,
    t.take_profit,
    t.entry_time,
    t.strategy_name,
    EXTRACT(EPOCH FROM (NOW() - t.entry_time))/60 AS holding_time_minutes,
    t.gross_pnl,
    t.net_pnl
FROM trades t
JOIN instruments i ON t.epic = i.epic
WHERE t.status = 'OPEN'
ORDER BY t.entry_time DESC;


-- View: Recent signals with instrument info
CREATE VIEW v_recent_signals AS
SELECT 
    s.id,
    s.epic,
    i.name AS instrument_name,
    s.strategy_name,
    s.timeframe,
    s.signal_type,
    s.strength,
    s.confidence,
    s.indicators,
    s.generated_at,
    s.acted_upon
FROM signals s
JOIN instruments i ON s.epic = i.epic
WHERE s.generated_at > NOW() - INTERVAL '24 hours'
ORDER BY s.generated_at DESC;


-- View: Pending intents
CREATE VIEW v_pending_intents AS
SELECT 
    i.id,
    i.epic,
    inst.name AS instrument_name,
    i.strategy_name,
    i.direction,
    i.size,
    i.entry_price,
    i.stop_loss,
    i.take_profit,
    i.risk_usd,
    i.reward_usd,
    i.risk_reward_ratio,
    i.ai_review_status,
    i.approval_status,
    i.created_at
FROM intents i
JOIN instruments inst ON i.epic = inst.epic
WHERE i.approval_status IN ('PENDING', 'APPROVED')
    AND i.executed = false
ORDER BY i.created_at DESC;


-- View: Today's performance
CREATE VIEW v_today_performance AS
SELECT 
    COUNT(*) AS total_trades,
    SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END) AS losing_trades,
    ROUND(SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END)::NUMERIC / NULLIF(COUNT(*), 0) * 100, 2) AS win_rate_pct,
    SUM(net_pnl) AS net_pnl,
    AVG(CASE WHEN net_pnl > 0 THEN net_pnl END) AS avg_win,
    AVG(CASE WHEN net_pnl < 0 THEN net_pnl END) AS avg_loss
FROM trades
WHERE entry_time >= CURRENT_DATE;


-- ============================================================================
-- INDEXES for Performance
-- ============================================================================

-- Composite indexes for common queries
CREATE INDEX idx_signals_epic_timeframe_generated ON signals(epic, timeframe, generated_at DESC);
CREATE INDEX idx_candles_epic_timestamp ON candles(epic, timestamp DESC) WHERE timeframe = '15m';
CREATE INDEX idx_trades_status_entry_time ON trades(status, entry_time DESC);


-- ============================================================================
-- GRANTS (for application user)
-- ============================================================================

-- These grants are applied after database initialization
-- Grants are handled in functions.sql and seed.sql

