-- Capital.com MCP Automation - Seed Data
-- Initial data for testing and development

-- ============================================================================
-- INSTRUMENTS
-- ============================================================================

INSERT INTO instruments (epic, name, instrument_type, tradeable, lot_size, min_size, max_size) VALUES
-- Forex
('EURUSD', 'EUR/USD', 'CURRENCIES', true, 1000, 0.01, 100),
('GBPUSD', 'GBP/USD', 'CURRENCIES', true, 1000, 0.01, 100),
('USDJPY', 'USD/JPY', 'CURRENCIES', true, 1000, 0.01, 100),
('AUDUSD', 'AUD/USD', 'CURRENCIES', true, 1000, 0.01, 100),

-- Cryptocurrencies
('BTCUSD', 'Bitcoin', 'CRYPTOCURRENCIES', true, 1, 0.001, 10),
('ETHUSD', 'Ethereum', 'CRYPTOCURRENCIES', true, 1, 0.01, 100),

-- Indices
('US500', 'S&P 500', 'INDICES', true, 1, 0.1, 100),
('US30', 'Dow Jones 30', 'INDICES', true, 1, 0.1, 100),
('GER40', 'DAX 40', 'INDICES', true, 1, 0.1, 100),
('UK100', 'FTSE 100', 'INDICES', true, 1, 0.1, 100),

-- Commodities
('GOLD', 'Gold', 'COMMODITIES', true, 1, 0.01, 100),
('SILVER', 'Silver', 'COMMODITIES', true, 1, 0.1, 1000),
('OIL_CRUDE', 'Crude Oil WTI', 'COMMODITIES', true, 1, 0.1, 100)

ON CONFLICT (epic) DO NOTHING;

-- Update instrument metadata with realistic values
UPDATE instruments SET
    avg_daily_volume = CASE epic
        WHEN 'EURUSD' THEN 5000000
        WHEN 'GBPUSD' THEN 3000000
        WHEN 'BTCUSD' THEN 1000000
        WHEN 'ETHUSD' THEN 500000
        WHEN 'US500' THEN 2000000
        WHEN 'GOLD' THEN 1500000
        ELSE 100000
    END,
    avg_spread = CASE epic
        WHEN 'EURUSD' THEN 0.00008
        WHEN 'GBPUSD' THEN 0.00010
        WHEN 'BTCUSD' THEN 5.0
        WHEN 'ETHUSD' THEN 0.50
        ELSE 0.001
    END,
    volatility_atr = CASE epic
        WHEN 'EURUSD' THEN 0.0012
        WHEN 'GBPUSD' THEN 0.0015
        WHEN 'BTCUSD' THEN 500.0
        WHEN 'ETHUSD' THEN 30.0
        ELSE 0.01
    END,
    updated_at = NOW()
WHERE epic IN ('EURUSD', 'GBPUSD', 'BTCUSD', 'ETHUSD', 'US500', 'GOLD');


-- ============================================================================
-- BANDIT STATE INITIALIZATION
-- ============================================================================

INSERT INTO bandit_state (strategy_name, pulls, wins, total_reward, win_rate, avg_reward, enabled) VALUES
('ORB_VWAP', 0, 0, 0, 0.5, 0, true),
('SMA_RSI_ATR', 0, 0, 0, 0.5, 0, true),
('DONCHIAN_BREAKOUT', 0, 0, 0, 0.5, 0, true)
ON CONFLICT (strategy_name) DO NOTHING;


-- ============================================================================
-- SYSTEM EVENTS - STARTUP
-- ============================================================================

INSERT INTO system_events (event_type, severity, message, source) VALUES
('SYSTEM_INITIALIZED', 'INFO', 'Database initialized with seed data', 'seed_script');


-- ============================================================================
-- SAMPLE DATA (for development/testing only)
-- ============================================================================

-- Uncomment below to add sample trades for testing performance calculations

/*
-- Sample historical trades for testing
INSERT INTO trades (
    epic, direction, size, entry_price, entry_time,
    exit_price, exit_time, exit_reason,
    gross_pnl, net_pnl, fees, status, strategy_name
) VALUES
-- Winning trades
('EURUSD', 'BUY', 0.1, 1.1000, NOW() - INTERVAL '5 days', 1.1050, NOW() - INTERVAL '4 days', 'TAKE_PROFIT', 50, 48, 2, 'CLOSED', 'ORB_VWAP'),
('BTCUSD', 'BUY', 0.01, 40000, NOW() - INTERVAL '4 days', 41000, NOW() - INTERVAL '3 days', 'TAKE_PROFIT', 100, 98, 2, 'CLOSED', 'SMA_RSI_ATR'),
('GOLD', 'BUY', 1, 1900, NOW() - INTERVAL '3 days', 1920, NOW() - INTERVAL '2 days', 'TAKE_PROFIT', 20, 19, 1, 'CLOSED', 'DONCHIAN_BREAKOUT'),

-- Losing trades
('GBPUSD', 'SELL', 0.1, 1.2500, NOW() - INTERVAL '2 days', 1.2530, NOW() - INTERVAL '1 day', 'STOP_LOSS', -30, -32, 2, 'CLOSED', 'ORB_VWAP'),
('ETHUSD', 'BUY', 0.1, 2500, NOW() - INTERVAL '1 day', 2480, NOW() - INTERVAL '12 hours', 'STOP_LOSS', -20, -22, 2, 'CLOSED', 'SMA_RSI_ATR');

-- Update bandit state based on sample trades
SELECT update_bandit_state('ORB_VWAP', 18);  -- 50 - 32 = 18
SELECT update_bandit_state('SMA_RSI_ATR', 76);  -- 98 - 22 = 76
SELECT update_bandit_state('DONCHIAN_BREAKOUT', 19);
*/


-- ============================================================================
-- VERIFY INSTALLATION
-- ============================================================================

DO $$
DECLARE
    v_instrument_count INTEGER;
    v_bandit_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO v_instrument_count FROM instruments;
    SELECT COUNT(*) INTO v_bandit_count FROM bandit_state;
    
    RAISE NOTICE 'Database seed completed:';
    RAISE NOTICE '  - % instruments loaded', v_instrument_count;
    RAISE NOTICE '  - % strategies initialized', v_bandit_count;
    
    IF v_instrument_count = 0 THEN
        RAISE WARNING 'No instruments loaded! Check seed data.';
    END IF;
END $$;

