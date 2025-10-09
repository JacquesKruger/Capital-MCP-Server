# Trading Automation Stack

Dockerized trading automation system that orchestrates strategies via **n8n**, stores data in **PostgreSQL**, calls the **Capital.com MCP server** via stdio JSON-RPC, and uses **AI** (ChatGPT/Claude) for analysis.

---

## 🏗️ Architecture

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   n8n       │────▶│  mcp-caller  │────▶│ Capital MCP │
│ Orchestrator│     │  (HTTP API)  │     │   Server    │
└─────────────┘     └──────────────┘     └─────────────┘
       │                    │
       │                    │
       ▼                    ▼
┌─────────────┐     ┌──────────────┐
│  PostgreSQL │     │   Scripts    │
│   Database  │     │  (TA/BSM/    │
└─────────────┘     │   Bandit)    │
                    └──────────────┘
```

### Components

1. **PostgreSQL 16** - Stores candles, signals, orders, trades, BSM analysis, bandit policy
2. **n8n** - Workflow automation engine (data collection, risk routing, trade management)
3. **MCP Caller** - HTTP API wrapper for Capital.com MCP server (persistent session)
4. **Capital MCP Server** - Production MCP server for Capital.com Public API
5. **Python Scripts** - Technical analysis, BSM pricing, contextual bandit, context builder

---

## 🚀 Quick Start

### 1. Setup Environment

```bash
cd automation
cp .env.example .env
# Edit .env with your credentials
```

**Required variables:**
- `CAP_API_KEY`, `CAP_IDENTIFIER`, `CAP_PASSWORD` - Capital.com API credentials
- `AI_API_KEY` - OpenAI or Anthropic API key
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` - Telegram bot (optional)

### 2. Start Services

```bash
docker-compose up -d
```

This starts:
- `db` - PostgreSQL on port 5433
- `n8n` - n8n on port 5678
- `mcp-caller` - HTTP API on port 8000
- `db-init` - One-shot schema initialization

### 3. Access n8n

```
http://localhost:5678
```

**Default credentials** (change in `.env`):
- Username: `admin`
- Password: `change_me`

### 4. Import Workflows

In n8n, import these workflows:
- `n8n/workflows/data_signals.json` - Data collection & signal generation (✅ READY)
- `n8n/workflows/risk_order_routing.json` - Risk checks & order routing (🚧 TODO)
- `n8n/workflows/post_trade_management.json` - Position management (🚧 TODO)
- `n8n/workflows/nightly_evaluation.json` - Performance analysis (🚧 TODO)
- `n8n/workflows/telegram_notifications.json` - Telegram alerts (🚧 TODO)
- `n8n/workflows/telegram_approval_handler.json` - Telegram approvals (🚧 TODO)

### 5. Configure Database Connection

In n8n:
1. Go to **Credentials** → **Postgres account**
2. Set:
   - Host: `db`
   - Port: `5432`
   - Database: `trading`
   - User: `trader`
   - Password: `traderpass` (from `.env`)

---

## 📊 Data Flow

### Workflow A: Data Collection & Signals (Every 15 minutes)

```
Cron Trigger (15m)
  ↓
Get Watchlist (DB: instruments)
  ↓
Process Watchlist (normalize data)
  ↓
Batch Get Quotes (MCP: batch_quotes API) ← ✅ Persistent session, no rate limits
  ↓
Parse Quote (extract bid/ask)
  ↓
Get Candles (DB: historical data)
  ↓
Prepare Candles (aggregate per symbol)
  ↓
Calculate Indicators (Python: SMA/RSI/ATR/VWAP/Donchian)
  ↓
Parse Indicators
  ↓
Generate Signals (ORB_VWAP, SMA_RSI_ATR, DONCHIAN_BREAKOUT)
  ↓
Store Signals (DB: signals table)
  ↓
Log Completion (DB: system_events)
```

**Status:** ✅ **WORKING** (tested successfully)

---

## 🧠 Strategy Engine

### Default Strategies

1. **ORB + VWAP**
   - Opening Range Breakout combined with VWAP
   - BUY: Price > VWAP && Price > SMA20
   - SELL: Price < VWAP && Price < SMA20

2. **SMA + RSI + ATR**
   - Trend following with momentum filter
   - BUY: Price > SMA20 > SMA50, RSI < 70
   - SELL: Price < SMA20 < SMA50, RSI > 30

3. **Donchian Breakout**
   - Channel breakout system (20-period)
   - BUY: Price >= Upper band
   - SELL: Price <= Lower band

### Contextual Bandit (LinUCB)

**Purpose:** Learn which strategy/sizing/stop combo works best in different contexts

**Action Space:** 10 actions
- 3 strategies × 3 variants (tight/base/wide stop, 0.5x/1.0x/1.5x size) + SKIP

**Context Features:** 28 dimensions
- TA features (8): SMA gaps, RSI, ATR, VWAP, Donchian position
- BSM features (7): IV rank, regime flags, vega, delta, mispricing
- Regime features (8): Time bucket, day of week
- Risk features (5): Drawdown, exposure, open positions, daily loss

**Update:** After each trade, reward = R-multiple (PnL / initial risk)

---

## 🔒 Safety & Risk Management

### DEMO by Default
- All trading defaults to **DEMO** environment
- LIVE requires:
  1. `CAP_ENVIRONMENT=live` in `.env`
  2. `env_mode="live"` in trade intent
  3. `confirm_live_trade="yes"` in MCP call
  4. Valid approval token from `approve_trade`

### Kill Switch
```bash
# In .env
TRADING_HALTED=1
```
Prevents ALL new orders (demo or live)

### Rate Limits (Capital.com)
- ✅ **1 auth/second** - Solved with persistent MCP session
- ✅ **10 requests/second** - Enforced in `mcp_call.py`
- ✅ **1 position/0.1s** - Rate limiting in place
- Session expires after 10 minutes inactivity

### Approval Flow
1. Strategy generates intent → stored in `intents` table
2. AI sanity check (ChatGPT/Claude)
3. Human approval via Telegram or n8n UI
4. `approve_trade` generates short-lived HMAC token
5. `place_order_from_intent` requires valid token

---

## 📁 File Structure

```
automation/
├── docker-compose.yml          # Service definitions
├── .env.example                # Environment template
├── README_AUTOMATION.md        # This file
├── SECURITY.md                 # Security guidelines
│
├── sql/
│   └── schema.sql              # PostgreSQL schema (candles, signals, orders, etc.)
│
├── scripts/
│   ├── mcp_api.py              # HTTP API for MCP server
│   ├── mcp_call.py             # Stdio JSON-RPC wrapper
│   ├── mcp_server_wrapper.py   # Persistent MCP process manager
│   ├── batch_quotes.py         # Batch quote fetcher
│   ├── indicators.py           # ✅ Technical analysis (SMA/RSI/ATR/VWAP/Donchian)
│   ├── bsm.py                  # ✅ Black-Scholes-Merton pricing + Greeks
│   ├── bsm_signals.py          # ✅ BSM → context features
│   ├── bandit.py               # ✅ LinUCB contextual bandit
│   └── context_builder.py      # ✅ Merge TA/BSM/regime/risk features
│
├── config/
│   ├── watchlist.yaml          # 🚧 Symbols to trade
│   ├── strategy.yaml           # 🚧 Strategy parameters
│   ├── risk.yaml               # 🚧 Risk limits
│   ├── schedule.yaml           # 🚧 Cron schedules
│   ├── bsm.yaml                # 🚧 BSM configuration
│   └── bandit.yaml             # 🚧 Bandit parameters
│
└── n8n/
    └── workflows/
        ├── data_signals.json                  # ✅ Data & Signals (READY)
        ├── risk_order_routing.json            # 🚧 Risk & Order Routing
        ├── post_trade_management.json         # 🚧 Post-Trade Management
        ├── nightly_evaluation.json            # 🚧 Nightly Evaluation
        ├── telegram_notifications.json        # 🚧 Telegram Notifications
        └── telegram_approval_handler.json     # 🚧 Telegram Approval Handler
```

---

## 🧪 Testing

### Test MCP API

```bash
# Health check
curl http://localhost:8000/health

# Batch quotes (persistent session - no rate limit!)
curl -X POST http://localhost:8000/mcp/batch_quotes \
  -H "Content-Type: application/json" \
  -d '{"epics":["BTCUSD","EURUSD","GBPUSD","GOLD","US500"]}'

# Account balance
curl http://localhost:8000/mcp/get_account_balance

# Open positions
curl http://localhost:8000/mcp/get_positions
```

### Test Scripts

```bash
# Technical indicators
docker-compose exec mcp-caller bash -c 'echo '\''{"symbol":"BTCUSD","candles":[...]}'\'' | python3 /app/scripts/indicators.py'

# BSM pricing
docker-compose exec mcp-caller bash -c 'echo '\''{"S":100,"K":105,"T":0.25,"r":0.04,"sigma":0.2,"type":"call","mode":"full"}'\'' | python3 /app/scripts/bsm.py'

# Bandit selection
docker-compose exec mcp-caller bash -c 'echo '\''{"mode":"select","feature_vector":[0.1,0.2,...]}'\'' | python3 /app/scripts/bandit.py'
```

### Test Workflow

1. In n8n, open **Data Collection & Signals**
2. Click **Execute Workflow**
3. Check outputs at each step
4. Verify signals in database:

```sql
SELECT * FROM signals ORDER BY id DESC LIMIT 10;
```

---

## 📈 Monitoring

### Database

```bash
# Connect to Postgres
docker-compose exec db psql -U trader -d trading

# View latest signals
SELECT symbol, strategy, signal, score, 
       to_timestamp(ts) as signal_time 
FROM signals 
ORDER BY ts DESC LIMIT 20;

# View system events
SELECT * FROM system_events ORDER BY created_at DESC LIMIT 10;
```

### Logs

```bash
# n8n logs
docker-compose logs -f n8n

# MCP caller logs
docker-compose logs -f mcp-caller

# Database logs
docker-compose logs -f db
```

---

## ⚙️ Configuration

### Watchlist Management

```sql
-- Add instrument
INSERT INTO instruments (symbol, epic, enabled, priority)
VALUES ('AAPL', 'AAPL', true, 50);

-- Disable instrument
UPDATE instruments SET enabled = false WHERE symbol = 'BTCUSD';

-- Change priority
UPDATE instruments SET priority = 95 WHERE symbol = 'GOLD';
```

### Bandit Tuning

Edit `config/bandit.yaml`:
- `epsilon.base` - Base exploration rate (default 0.08)
- `epsilon.high_iv` - Exploration during high volatility
- `alpha` - UCB exploration parameter

---

## 🔧 Troubleshooting

### Rate Limit 429 Errors

**Cause:** Too many authentication attempts (1/second limit)

**Solution:** ✅ Already fixed with persistent MCP session wrapper

The `mcp_server_wrapper.py` keeps a single MCP process alive, authenticates once, and reuses the session for 10 minutes.

### Workflow Stops at "Get Candles"

**Cause:** Empty `candles` table

**Solution:** Populate with sample data (already done) or wait for real candle data collection

### MCP Connection Errors

**Check:**
```bash
# Is MCP server container running?
docker ps | grep cool_hopper

# Test direct MCP call
docker exec -i cool_hopper python capital_server.py <<EOF
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":0}
{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"check_status","arguments":{}},"id":1}
EOF
```

---

## 📚 Next Steps

### Immediate (Building Now)
1. ✅ Fix data_signals workflow (DONE)
2. ✅ Create all core scripts (DONE)
3. 🚧 Create remaining workflows
4. 🚧 Create YAML config files
5. 🚧 Write SECURITY.md

### Phase 2
- Add real-time candle collection (websocket or polling)
- Implement complete risk routing workflow
- Add Telegram integration
- Create nightly evaluation & reporting

### Phase 3
- Backtest engine
- Paper trading mode
- Live trading (with extreme caution)

---

## 📜 License

Same as parent project (see root LICENSE)

## ⚠️ Disclaimer

**FOR EDUCATIONAL PURPOSES ONLY.** Trading involves substantial risk. Always test in DEMO mode first. Never risk more than you can afford to lose.
