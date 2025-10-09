# Dynamic Daily Watchlist Guide

## Overview

The **Dynamic Daily Watchlist** feature automatically screens and ranks trading symbols each day based on technical metrics and sentiment. It runs before market open and publishes results to Telegram.

## Components

### 1. Screener Script (`scripts/screener.py`)

**Purpose**: Analyzes all enabled instruments and generates a ranked watchlist per asset class.

**Metrics Calculated**:
- **ATR%**: Average True Range as percentage of price (volatility measure)
- **Gap%**: Overnight gap from previous close
- **Compression**: Range compression (Bollinger-like squeeze detection)
- **Liquidity**: Volume consistency and average volume
- **Sentiment**: News sentiment with time decay

**Process**:
1. Load configuration from `config/watchlist_rules.yaml`
2. Fetch candle data from database (no internet required)
3. Calculate metrics for each symbol
4. Normalize scores within asset class
5. Apply weighted scoring based on asset class rules
6. Filter by thresholds (min ATR, min liquidity, max spread)
7. Rank and select top N per class
8. Save to `watchlist_daily` table
9. Output JSON for n8n workflow

**Usage**:
```bash
# Run manually
docker exec -it trading-mcp-caller python3 /app/scripts/screener.py

# Via API
curl -X POST http://localhost:8000/screener
```

### 2. Configuration (`config/watchlist_rules.yaml`)

**Asset Classes**:
- `stocks`: Equities with gap analysis
- `forex`: Currency pairs (24h markets)
- `crypto`: Cryptocurrencies (high volatility)
- `metals`: Gold, silver, etc.
- `indices`: Stock indices

**Key Parameters**:
```yaml
classes:
  stocks:
    min_liquidity_score: 0.60    # Minimum liquidity to qualify
    max_spread_bps: 12           # Maximum spread in basis points
    atr_pct_min: 0.008           # Minimum 0.8% ATR
    gap_abs_min_pct: 0.5         # Minimum 0.5% gap
    weights:                     # Scoring weights (must sum to 1.0)
      atr_pct: 0.35
      gap: 0.25
      compression: 0.15
      liquidity: 0.15
      sentiment: 0.10
    top_n: 12                    # Max symbols in watchlist
```

**Customization**:
- Edit `config/watchlist_rules.yaml`
- Adjust weights per asset class
- Change filtering thresholds
- Modify scoring lookback periods

### 3. Database Tables

**`watchlist_daily`**:
Stores daily watchlist results.

```sql
CREATE TABLE watchlist_daily (
    id SERIAL PRIMARY KEY,
    day TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    symbol TEXT NOT NULL,
    rank INTEGER NOT NULL,
    score REAL NOT NULL,
    reasons TEXT,           -- e.g., "high_volatility,gap_up,compressed_range"
    metrics_json TEXT,      -- Full metrics as JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**`research_notes`**:
Manual or AI-generated notes about symbols.

```sql
CREATE TABLE research_notes (
    id SERIAL PRIMARY KEY,
    day TEXT NOT NULL,
    symbol TEXT NOT NULL,
    note TEXT NOT NULL,
    source TEXT,            -- 'telegram','ai','manual'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4. n8n Workflow (`n8n/workflows/pre_open_watchlist.json`)

**Trigger**: Cron at 06:00 AM Monday-Friday (before market open)

**Flow**:
1. **Cron Trigger** → Runs at 6 AM daily
2. **Run Screener** → Calls `/screener` API endpoint
3. **Parse Watchlist** → Extracts watchlist data
4. **Format Telegram Message** → Creates markdown message
5. **Send Telegram Notification** → Publishes to Telegram
6. **Log Completion** → Records event in system_events

**Import**:
```bash
# In n8n UI:
# Settings → Import from File → pre_open_watchlist.json
```

## Scoring Algorithm

### Step 1: Calculate Raw Metrics

For each symbol:
- `atr_pct = ATR / current_price * 100`
- `gap_pct = (today_open - yesterday_close) / yesterday_close * 100`
- `compression = 1 - (recent_range / historical_ATR)`
- `liquidity = volume_consistency_score`
- `sentiment = time_weighted_news_sentiment`

### Step 2: Normalize Within Asset Class

- Use `minmax_clip` or `zscore_clip` method
- Ensures fair comparison within each asset class
- Prevents outliers from dominating

### Step 3: Apply Weighted Scoring

```python
composite_score = (
    weights['atr_pct'] * atr_norm +
    weights['gap'] * gap_norm +
    weights['compression'] * compression +
    weights['liquidity'] * liquidity +
    weights['sentiment'] * (sentiment + 1) / 2
)
```

### Step 4: Filter and Rank

- Apply minimum thresholds
- Sort by composite score (descending)
- Take top N symbols per class

### Step 5: Generate Reasons

Tags added based on metrics:
- `high_volatility`: ATR score > 0.7
- `gap_up` / `gap_down`: Significant overnight gap
- `compressed_range`: Compression score > 0.7
- `high_liquidity`: Liquidity score > 0.8
- `positive_sentiment` / `negative_sentiment`: Strong sentiment signal

## Usage Examples

### 1. View Today's Watchlist

```sql
SELECT asset_class, symbol, rank, score, reasons
FROM watchlist_daily
WHERE day = CURRENT_DATE::text
ORDER BY asset_class, rank;
```

### 2. Compare Symbol Rankings Over Time

```sql
SELECT day, rank, score, reasons
FROM watchlist_daily
WHERE symbol = 'EURUSD' AND day >= (CURRENT_DATE - 7)::text
ORDER BY day DESC;
```

### 3. Find High-Volatility Opportunities

```sql
SELECT symbol, score, metrics_json->>'atr_pct' as atr_pct
FROM watchlist_daily
WHERE day = CURRENT_DATE::text
  AND reasons LIKE '%high_volatility%'
ORDER BY score DESC
LIMIT 10;
```

### 4. Add Research Note

```sql
INSERT INTO research_notes (day, symbol, note, source, created_at)
VALUES (
    CURRENT_DATE::text,
    'BTCUSD',
    'Strong support at 62000, watching for breakout above 65000',
    'manual',
    NOW()
);
```

## Customization

### Adjust Cron Schedule

Edit `pre_open_watchlist.json`:
```json
{
  "cronExpression": "0 6 * * 1-5"  // 6 AM Mon-Fri
}
```

Common schedules:
- `0 6 * * 1-5`: 6 AM weekdays
- `30 5 * * *`: 5:30 AM daily
- `0 8,12,16 * * *`: 8 AM, noon, 4 PM daily

### Change Asset Class Weights

Edit `config/watchlist_rules.yaml`:
```yaml
classes:
  forex:
    weights:
      atr_pct: 0.50      # Increase volatility importance
      compression: 0.30  # Increase compression importance
      liquidity: 0.15
      sentiment: 0.05    # Decrease sentiment importance
```

### Add New Asset Class

```yaml
classes:
  commodities:
    min_liquidity_score: 0.70
    max_spread_bps: 10
    atr_pct_min: 0.006
    gap_abs_min_pct: 0.00
    weights:
      atr_pct: 0.40
      compression: 0.25
      liquidity: 0.20
      sentiment: 0.15
    top_n: 8
```

Update `screener.py` classification logic if needed.

## Integration with Trading Workflows

### Use Watchlist in Signal Generation

```sql
-- In data_signals workflow, prioritize watchlist symbols
SELECT s.*
FROM signals s
INNER JOIN watchlist_daily w ON s.symbol = w.symbol
WHERE w.day = CURRENT_DATE::text
  AND s.signal IN ('BUY', 'SELL')
  AND s.created_at > NOW() - INTERVAL '1 hour'
ORDER BY w.rank, s.score DESC;
```

### Dynamic Position Sizing

```python
# In risk calculation
watchlist_rank = get_symbol_rank(symbol)  # 1-12
base_size = 1.0

if watchlist_rank <= 3:
    # Top 3 symbols: increase size
    size = base_size * 1.5
elif watchlist_rank <= 6:
    # Top 6: standard size
    size = base_size
else:
    # Lower ranked: reduce size
    size = base_size * 0.5
```

## Monitoring

### Check Screener Status

```sql
SELECT event_type, message, details, occurred_at
FROM system_events
WHERE event_type = 'WATCHLIST_GENERATED'
ORDER BY occurred_at DESC
LIMIT 10;
```

### Verify Data Freshness

```sql
SELECT asset_class, COUNT(*) as symbol_count, MAX(created_at) as last_updated
FROM watchlist_daily
WHERE day = CURRENT_DATE::text
GROUP BY asset_class;
```

## Troubleshooting

### No Symbols in Watchlist

**Causes**:
- Insufficient candle data (need 50+ bars)
- Thresholds too strict
- All symbols filtered out

**Solution**:
```yaml
# Lower thresholds temporarily
classes:
  forex:
    min_liquidity_score: 0.50  # was 0.80
    atr_pct_min: 0.001         # was 0.003
```

### Screener Timeout

**Causes**:
- Too many symbols
- Database slow

**Solution**:
- Increase timeout in `mcp_api.py` (currently 120s)
- Optimize database with indexes
- Reduce `require_min_candles` in config

### Telegram Message Too Long

**Causes**:
- Too many symbols per class

**Solution**:
- Reduce `top_n` in config
- Limit display in workflow (already capped at 10 per class)

## Advanced Features

### Multi-Timeframe Analysis

Extend screener to analyze multiple timeframes:
```python
# In screener.py
for tf in ['1d', '4h', '1h']:
    candles = fetch_candles(symbol, tf)
    scores[tf] = calculate_metrics(candles)

# Combine scores
final_score = (
    scores['1d'] * 0.5 +
    scores['4h'] * 0.3 +
    scores['1h'] * 0.2
)
```

### Sentiment Integration

Add news scraping or use research notes:
```sql
-- Aggregate manual research notes into sentiment
SELECT symbol, 
       COUNT(*) as note_count,
       AVG(CASE 
           WHEN note ILIKE '%bullish%' THEN 1
           WHEN note ILIKE '%bearish%' THEN -1
           ELSE 0
       END) as manual_sentiment
FROM research_notes
WHERE day >= (CURRENT_DATE - 3)::text
GROUP BY symbol;
```

### Backtesting Watchlist Quality

```sql
-- Compare watchlist ranking vs actual performance
WITH watchlist AS (
    SELECT symbol, rank, score, day
    FROM watchlist_daily
    WHERE day >= '2025-01-01'
),
performance AS (
    SELECT symbol, day, 
           (close - open) / open * 100 as intraday_return
    FROM candles
    WHERE tf = '1d' AND day >= '2025-01-01'
)
SELECT w.rank, 
       AVG(p.intraday_return) as avg_return,
       COUNT(*) as days
FROM watchlist w
JOIN performance p ON w.symbol = p.symbol AND w.day = p.day
GROUP BY w.rank
ORDER BY w.rank;
```

## Best Practices

1. **Review Watchlist Daily**: Don't blindly follow - use as a starting point
2. **Combine with Other Signals**: Watchlist + technical signals + news
3. **Adjust Seasonally**: Market volatility changes throughout the year
4. **Monitor Performance**: Track which ranked symbols perform best
5. **Customize Weights**: Adjust based on your trading style
6. **Add Manual Notes**: Use `research_notes` to supplement automated screening
7. **Backtest Changes**: Test config changes on historical data before deploying

## Future Enhancements

- [ ] Multi-timeframe scoring
- [ ] Correlation analysis (avoid correlated symbols)
- [ ] Sector/industry classification
- [ ] Machine learning for weight optimization
- [ ] Real-time watchlist updates (intraday)
- [ ] Performance tracking per watchlist rank
- [ ] Integration with external sentiment APIs
- [ ] Automated backtesting on config changes

