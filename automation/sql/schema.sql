-- =============================================================================
-- TRADING AUTOMATION STACK - COMPREHENSIVE DATABASE SCHEMA
-- =============================================================================
-- This schema supports:
-- - Market data (instruments, candles)
-- - Technical analysis signals
-- - BSM options analysis (analysis-only mode)
-- - Contextual bandit learning
-- - Order management and trade tracking
-- - Telegram approvals and notifications
-- - Performance analytics

-- =============================================================================
-- CORE MARKET DATA TABLES
-- =============================================================================

-- Trading instruments (CFDs, spot, futures)
CREATE TABLE IF NOT EXISTS instruments (
    symbol TEXT PRIMARY KEY,
    epic TEXT,  -- Capital.com epic identifier
    name TEXT NOT NULL,
    exchange TEXT,
    tick_size REAL DEFAULT 0.0001,
    lot_size REAL DEFAULT 1.0,
    enabled BOOLEAN DEFAULT true,
    priority INTEGER DEFAULT 0,
    meta_json TEXT,  -- Additional metadata as JSON
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- OHLCV candle data
CREATE TABLE IF NOT EXISTS candles (
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,  -- timeframe: 1m, 5m, 15m, 1h, 4h, 1d
    ts INTEGER NOT NULL,  -- timestamp
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL DEFAULT 0,
    PRIMARY KEY (symbol, tf, ts)
);

-- Index for efficient time-series queries
CREATE INDEX IF NOT EXISTS candles_ts_idx ON candles(symbol, tf, ts);
CREATE INDEX IF NOT EXISTS candles_symbol_idx ON candles(symbol);

-- =============================================================================
-- AUTOMATION STATE TABLES
-- =============================================================================

-- Generic key/value store for workflow state (e.g., Telegram polling offsets)
CREATE TABLE IF NOT EXISTS bot_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- SIGNALS AND ANALYSIS TABLES
-- =============================================================================

-- Technical analysis signals from rule-based strategies
CREATE TABLE IF NOT EXISTS signals (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    tf TEXT NOT NULL,
    ts INTEGER NOT NULL,
    strategy TEXT NOT NULL,  -- ORB, SMA_RSI_ATR, Donchian, etc.
    signal TEXT NOT NULL,    -- BUY, SELL, HOLD
    score REAL NOT NULL,     -- Signal strength 0-1
    features_json TEXT,      -- Technical indicators as JSON
    context_json TEXT,       -- Bandit context features
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS signals_ts_idx ON signals(symbol, tf, ts);
CREATE INDEX IF NOT EXISTS signals_strategy_idx ON signals(strategy);
CREATE INDEX IF NOT EXISTS signals_created_idx ON signals(created_at);

-- =============================================================================
-- INTENTS AND ORDER MANAGEMENT
-- =============================================================================

-- Trading intents (before execution)
CREATE TABLE IF NOT EXISTS intents (
    id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,      -- BUY, SELL
    type TEXT NOT NULL,       -- MARKET, LIMIT
    price REAL,
    qty REAL NOT NULL,
    tif TEXT DEFAULT 'GTC',  -- Good Till Cancel
    strategy TEXT NOT NULL,
    rationale TEXT,
    env_mode TEXT NOT NULL,   -- demo, live
    status TEXT DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED, EXECUTED
    risk_json TEXT,          -- Risk parameters
    news_json TEXT,          -- News context
    ai_json TEXT,            -- AI analysis
    context_json TEXT,       -- Bandit context
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notified_at TIMESTAMP,
    -- Position sizing columns (added for trade management)
    position_size_usd REAL,
    position_size_units REAL,
    stop_loss_price REAL,
    take_profit_price REAL,
    risk_amount_usd REAL,
    stop_loss_pct REAL,
    take_profit_pct REAL
);

CREATE INDEX IF NOT EXISTS intents_status_idx ON intents(status);
CREATE INDEX IF NOT EXISTS intents_symbol_idx ON intents(symbol);
CREATE INDEX IF NOT EXISTS intents_created_idx ON intents(created_at);

-- Executed orders
CREATE TABLE IF NOT EXISTS orders (
    id TEXT PRIMARY KEY,
    client_id TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    type TEXT NOT NULL,
    price REAL,
    qty REAL NOT NULL,
    status TEXT NOT NULL,    -- PENDING, FILLED, CANCELLED, REJECTED
    tif TEXT DEFAULT 'GTC',
    env_mode TEXT NOT NULL,
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    raw_json TEXT            -- Full API response
);

CREATE INDEX IF NOT EXISTS orders_status_idx ON orders(status);
CREATE INDEX IF NOT EXISTS orders_symbol_idx ON orders(symbol);
CREATE INDEX IF NOT EXISTS orders_placed_idx ON orders(placed_at);

-- Completed trades
CREATE TABLE IF NOT EXISTS trades (
    trade_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    intent_id TEXT,           -- Link to original intent
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    strategy TEXT,            -- Trading strategy used
    avg_price REAL NOT NULL,
    qty REAL NOT NULL,
    pnl REAL DEFAULT 0,
    fees REAL DEFAULT 0,
    opened_at TIMESTAMP NOT NULL,
    closed_at TIMESTAMP,
    holding_secs INTEGER,
    notes TEXT,
    FOREIGN KEY (intent_id) REFERENCES intents(id)
);

CREATE INDEX IF NOT EXISTS trades_symbol_idx ON trades(symbol);
CREATE INDEX IF NOT EXISTS trades_opened_idx ON trades(opened_at);
CREATE INDEX IF NOT EXISTS trades_closed_idx ON trades(closed_at);

-- =============================================================================
-- NEWS AND REVIEWS
-- =============================================================================

-- News articles and sentiment
CREATE TABLE IF NOT EXISTS news (
    id TEXT PRIMARY KEY,
    symbol TEXT,
    published_at TIMESTAMP NOT NULL,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT,
    summary TEXT,
    sentiment REAL,  -- -1 to 1
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS news_symbol_idx ON news(symbol);
CREATE INDEX IF NOT EXISTS news_published_idx ON news(published_at);

-- Trade reviews and analysis
CREATE TABLE IF NOT EXISTS reviews (
    id SERIAL PRIMARY KEY,
    trade_id TEXT NOT NULL,
    reviewer TEXT NOT NULL,  -- human, ai, system
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    rationale TEXT,
    verdict TEXT,            -- GOOD, BAD, NEUTRAL
    suggestions TEXT
);

CREATE INDEX IF NOT EXISTS reviews_trade_idx ON reviews(trade_id);

-- =============================================================================
-- BSM OPTIONS ANALYSIS (ANALYSIS-ONLY MODE)
-- =============================================================================

-- Options market data (if available)
CREATE TABLE IF NOT EXISTS options_quotes (
    symbol TEXT NOT NULL,
    ts INTEGER NOT NULL,
    K REAL NOT NULL,         -- Strike price
    T REAL NOT NULL,         -- Time to expiration (years)
    type TEXT NOT NULL,      -- call, put
    bid REAL,
    ask REAL,
    mid REAL,
    r REAL,                  -- Risk-free rate
    iv_market REAL,          -- Market implied volatility
    src TEXT,                -- Data source
    PRIMARY KEY (symbol, ts, K, T, type)
);

-- BSM calculations and Greeks
CREATE TABLE IF NOT EXISTS bsm_evals (
    id SERIAL PRIMARY KEY,
    symbol TEXT NOT NULL,
    ts INTEGER NOT NULL,
    K REAL NOT NULL,
    T REAL NOT NULL,
    type TEXT NOT NULL,
    theo REAL,               -- Theoretical price
    iv REAL,                 -- Implied volatility
    delta REAL,
    gamma REAL,
    vega REAL,
    theta REAL,
    rho REAL,
    mispricing REAL,         -- Market vs theoretical
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS bsm_evals_symbol_idx ON bsm_evals(symbol);
CREATE INDEX IF NOT EXISTS bsm_evals_ts_idx ON bsm_evals(ts);

-- =============================================================================
-- APPROVALS AND SECURITY
-- =============================================================================

-- Human/Telegram approvals for trades
CREATE TABLE IF NOT EXISTS approvals (
    id SERIAL PRIMARY KEY,
    intent_id TEXT NOT NULL,
    approver TEXT NOT NULL,   -- username, telegram_id, etc.
    source TEXT NOT NULL,     -- telegram, claude, manual
    approved_at TIMESTAMP NOT NULL,
    token_preview TEXT,      -- First 8 chars of approval token
    env_mode TEXT NOT NULL,
    expires_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS approvals_intent_idx ON approvals(intent_id);
CREATE INDEX IF NOT EXISTS approvals_approver_idx ON approvals(approver);
CREATE INDEX IF NOT EXISTS approvals_approved_idx ON approvals(approved_at);

-- =============================================================================
-- CONTEXTUAL BANDIT LEARNING
-- =============================================================================

-- Bandit policy state
CREATE TABLE IF NOT EXISTS bandit_policy (
    id SERIAL PRIMARY KEY,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    algorithm TEXT NOT NULL,  -- linucb, logistic
    policy_json TEXT NOT NULL, -- Serialized policy weights/parameters
    performance_summary TEXT  -- Recent performance metrics
);

-- Performance tracking by strategy and context
CREATE TABLE IF NOT EXISTS performance (
    id SERIAL PRIMARY KEY,
    day DATE NOT NULL,
    strategy TEXT NOT NULL,
    action TEXT NOT NULL,     -- ORB_base, SMA_tight, etc.
    context_hash TEXT,        -- Hash of context features
    trades_count INTEGER DEFAULT 0,
    wins_count INTEGER DEFAULT 0,
    total_pnl REAL DEFAULT 0,
    avg_r_multiple REAL DEFAULT 0,
    max_drawdown REAL DEFAULT 0,
    metrics_json TEXT,        -- Detailed metrics
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS performance_day_idx ON performance(day);
CREATE INDEX IF NOT EXISTS performance_strategy_idx ON performance(strategy);

-- =============================================================================
-- DYNAMIC WATCHLIST AND RESEARCH
-- =============================================================================

-- Daily watchlist generated by screener
CREATE TABLE IF NOT EXISTS watchlist_daily (
    id SERIAL PRIMARY KEY,
    day TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    symbol TEXT NOT NULL,
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    reasons TEXT,           -- comma-separated tags
    metrics_json TEXT,      -- atr%, spread, liquidity, gap, compression, sentiment
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS wld_day_class_idx ON watchlist_daily(day, asset_class);
CREATE INDEX IF NOT EXISTS wld_symbol_idx ON watchlist_daily(symbol);
CREATE INDEX IF NOT EXISTS wld_created_idx ON watchlist_daily(created_at);

-- Research notes for symbols
CREATE TABLE IF NOT EXISTS research_notes (
    id SERIAL PRIMARY KEY,
    day TEXT NOT NULL,
    symbol TEXT NOT NULL,
    note TEXT NOT NULL,
    source TEXT,            -- 'telegram','ai','manual'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS research_symbol_idx ON research_notes(symbol);
CREATE INDEX IF NOT EXISTS research_day_idx ON research_notes(day);

-- =============================================================================
-- SYSTEM EVENTS AND LOGGING
-- =============================================================================

-- System events and health checks
CREATE TABLE IF NOT EXISTS system_events (
    id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,   -- INFO, WARN, ERROR
    message TEXT NOT NULL,
    details TEXT,             -- JSON details
    epic TEXT,                 -- Related instrument
    strategy_name TEXT,        -- Related strategy
    trade_id TEXT,             -- Related trade
    order_id TEXT,             -- Related order
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source TEXT DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS system_events_type_idx ON system_events(event_type);
CREATE INDEX IF NOT EXISTS system_events_severity_idx ON system_events(severity);
CREATE INDEX IF NOT EXISTS system_events_occurred_idx ON system_events(occurred_at);

-- =============================================================================
-- UTILITY FUNCTIONS AND TRIGGERS
-- =============================================================================

-- Function to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for intents table
CREATE TRIGGER update_intents_updated_at 
    BEFORE UPDATE ON intents 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger for orders table
CREATE TRIGGER update_orders_updated_at 
    BEFORE UPDATE ON orders 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- INITIAL DATA AND SEQUENCES
-- =============================================================================

-- Initialize bandit policy with default settings
INSERT INTO bandit_policy (algorithm, policy_json, performance_summary) 
VALUES ('linucb', '{"weights": {}, "exploration_rate": 0.08}', '{"initialized": true}')
ON CONFLICT DO NOTHING;

-- Initialize some demo instruments
INSERT INTO instruments (symbol, epic, name, exchange, enabled, priority) VALUES
('BTCUSD', 'BTCUSD', 'Bitcoin vs US Dollar', 'CRYPTO', true, 100),
('EURUSD', 'EURUSD', 'Euro vs US Dollar', 'FX', true, 90),
('GBPUSD', 'GBPUSD', 'British Pound vs US Dollar', 'FX', true, 80),
('XAUUSD', 'XAUUSD', 'Gold vs US Dollar', 'METALS', true, 70),
('SPX500', 'SPX500', 'S&P 500 Index', 'INDICES', true, 60)
ON CONFLICT (symbol) DO NOTHING;

-- Initialize system events sequence to allow ID 0
ALTER SEQUENCE system_events_id_seq MINVALUE 0 RESTART WITH 0;

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- Active positions view
CREATE OR REPLACE VIEW active_positions AS
SELECT 
    t.trade_id,
    t.symbol,
    t.side,
    t.avg_price,
    t.qty,
    t.pnl,
    t.opened_at,
    EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - t.opened_at)) as holding_seconds
FROM trades t
WHERE t.closed_at IS NULL;

-- Performance summary view
CREATE OR REPLACE VIEW performance_summary AS
SELECT 
    'ALL' as strategy,
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
    AVG(pnl) as avg_pnl,
    SUM(pnl) as total_pnl,
    MAX(pnl) as best_trade,
    MIN(pnl) as worst_trade
FROM trades
WHERE closed_at IS NOT NULL;

-- =============================================================================
-- CLEANUP AND MAINTENANCE
-- =============================================================================

-- Function to clean old data (run periodically)
CREATE OR REPLACE FUNCTION cleanup_old_data()
RETURNS void AS $$
BEGIN
    -- Delete system events older than 30 days
    DELETE FROM system_events 
    WHERE occurred_at < CURRENT_TIMESTAMP - INTERVAL '30 days';
    
    -- Delete old news articles (keep last 90 days)
    DELETE FROM news 
    WHERE published_at < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    -- Delete old BSM evaluations (keep last 7 days)
    DELETE FROM bsm_evals 
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- SCHEMA COMPLETION
-- =============================================================================

-- Log schema creation
INSERT INTO system_events (event_type, severity, message, details, source) 
VALUES (
    'SCHEMA_INIT', 
    'INFO', 
    'Trading automation schema initialized successfully',
    '{"version": "1.0", "tables_created": 15, "indexes_created": 20}',
    'schema_init'
);

COMMIT;
