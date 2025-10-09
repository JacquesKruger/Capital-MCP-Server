# Dynamic Watchlist - Symbol Management Guide

## Overview

The watchlist screener only analyzes symbols that exist in the `instruments` table. This guide explains how to manage your symbol universe.

## Current Symbols

Check what symbols are currently enabled:

```sql
SELECT symbol, name, exchange, enabled, priority 
FROM instruments 
ORDER BY priority DESC, symbol;
```

## Adding New Symbols

### Method 1: Manual Addition (Quick)

```sql
INSERT INTO instruments (symbol, epic, name, exchange, enabled, priority) VALUES
-- Forex pairs
('AUDUSD', 'AUDUSD', 'Australian Dollar vs USD', 'FX', true, 80),
('USDJPY', 'USDJPY', 'USD vs Japanese Yen', 'FX', true, 79),
('NZDUSD', 'NZDUSD', 'New Zealand Dollar vs USD', 'FX', true, 78),
('USDCAD', 'USDCAD', 'USD vs Canadian Dollar', 'FX', true, 77),
('USDCHF', 'USDCHF', 'USD vs Swiss Franc', 'FX', true, 76),

-- Major stocks
('AAPL', 'AAPL', 'Apple Inc', 'NASDAQ', true, 95),
('MSFT', 'MSFT', 'Microsoft Corp', 'NASDAQ', true, 94),
('GOOGL', 'GOOGL', 'Alphabet Inc', 'NASDAQ', true, 93),
('AMZN', 'AMZN', 'Amazon.com Inc', 'NASDAQ', true, 92),
('TSLA', 'TSLA', 'Tesla Inc', 'NASDAQ', true, 91),
('NVDA', 'NVDA', 'NVIDIA Corp', 'NASDAQ', true, 90),
('META', 'META', 'Meta Platforms Inc', 'NASDAQ', true, 89),

-- Crypto
('ETHUSD', 'ETHUSD', 'Ethereum vs USD', 'CRYPTO', true, 85),
('SOLUSD', 'SOLUSD', 'Solana vs USD', 'CRYPTO', true, 84),
('ADAUSD', 'ADAUSD', 'Cardano vs USD', 'CRYPTO', true, 83),

-- Metals
('XAGUSD', 'XAGUSD', 'Silver vs USD', 'METALS', true, 75),

-- Indices
('NDX', 'NDX', 'NASDAQ 100', 'INDICES', true, 70),
('DJI', 'DJI', 'Dow Jones Industrial', 'INDICES', true, 69)

ON CONFLICT (symbol) DO NOTHING;
```

### Method 2: Discover from Capital.com API

Use the MCP server's `list_instruments` tool to fetch available instruments:

```bash
# List all EUR instruments
curl -X POST http://localhost:8000/mcp/call \
  -H "Content-Type: application/json" \
  -d '{
    "tool": "list_instruments",
    "args": {
      "search_term": "EUR",
      "limit": "50"
    }
  }'
```

Then insert the results into the database.

### Method 3: Automated Discovery Script

Create `automation/scripts/discover_instruments.py`:

```python
#!/usr/bin/env python3
"""
Discover and add instruments from Capital.com API
"""
import requests
import psycopg2
import os

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'trading-db'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trading'),
        user=os.getenv('POSTGRES_USER', 'trader'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )

def discover_instruments(search_term="", limit=100):
    """Fetch instruments from MCP API"""
    response = requests.post(
        'http://localhost:8000/mcp/call',
        json={
            'tool': 'list_instruments',
            'args': {
                'search_term': search_term,
                'limit': str(limit)
            }
        }
    )
    return response.json()

def add_to_database(instruments):
    """Add discovered instruments to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    added = 0
    for inst in instruments:
        try:
            cursor.execute("""
                INSERT INTO instruments (symbol, epic, name, exchange, enabled, priority)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (symbol) DO UPDATE
                SET name = EXCLUDED.name,
                    epic = EXCLUDED.epic
            """, (
                inst['symbol'],
                inst.get('epic', inst['symbol']),
                inst['name'],
                inst.get('exchange', 'UNKNOWN'),
                True,
                50  # Default priority
            ))
            added += 1
        except Exception as e:
            print(f"Error adding {inst.get('symbol')}: {e}")
    
    conn.commit()
    conn.close()
    return added

if __name__ == '__main__':
    # Discover major forex pairs
    print("Discovering forex instruments...")
    forex = discover_instruments("USD", 50)
    added = add_to_database(forex.get('instruments', []))
    print(f"Added {added} forex instruments")
    
    # Discover major indices
    print("Discovering indices...")
    indices = discover_instruments("500", 20)
    added = add_to_database(indices.get('instruments', []))
    print(f"Added {added} index instruments")
    
    # Discover crypto
    print("Discovering crypto...")
    crypto = discover_instruments("BTC", 20)
    added = add_to_database(crypto.get('instruments', []))
    print(f"Added {added} crypto instruments")
```

Run it:
```bash
docker exec trading-mcp-caller python3 /app/scripts/discover_instruments.py
```

## Symbol Filtering

### Disable Low-Priority Symbols

```sql
-- Disable symbols with low priority
UPDATE instruments SET enabled = false WHERE priority < 50;
```

### Enable Only Specific Asset Classes

```sql
-- Enable only forex and crypto
UPDATE instruments SET enabled = false;
UPDATE instruments SET enabled = true WHERE exchange IN ('FX', 'CRYPTO');
```

### Prioritize by Liquidity

Once you have candle data, prioritize by average volume:

```sql
UPDATE instruments i
SET priority = (
    SELECT AVG(volume)::INTEGER / 10000
    FROM candles c
    WHERE c.symbol = i.symbol AND c.tf = '1d'
    LIMIT 100
)
WHERE enabled = true;
```

## Symbol Lifecycle

### Weekly Symbol Refresh

Create an n8n workflow that runs weekly:
1. Discover new instruments from Capital.com
2. Update `instruments` table
3. Disable symbols with no recent data
4. Adjust priorities based on volume

### Automatic Cleanup

Remove symbols with no data:

```sql
DELETE FROM instruments
WHERE symbol NOT IN (
    SELECT DISTINCT symbol FROM candles
)
AND enabled = false;
```

## Best Practices

1. **Start Small**: Begin with 10-20 high-quality symbols
2. **Monitor Performance**: Track which symbols appear in watchlist most
3. **Regular Review**: Weekly review of enabled symbols
4. **Volume Matters**: Prioritize liquid instruments
5. **Asset Class Balance**: Don't over-weight one class

## Recommended Starting Universe

### Conservative (20 symbols)
- **Forex (8)**: EURUSD, GBPUSD, USDJPY, AUDUSD, NZDUSD, USDCAD, USDCHF, EURGBP
- **Indices (5)**: SPX500, NDX, DJI, DAX, FTSE
- **Crypto (3)**: BTCUSD, ETHUSD, SOLUSD
- **Metals (2)**: XAUUSD, XAGUSD
- **Stocks (2)**: AAPL, TSLA

### Aggressive (50+ symbols)
- All major forex pairs
- Top 20 stocks by market cap
- All major indices
- Top 10 crypto by market cap
- Commodities (oil, gold, silver)

## Integration with Watchlist

The screener will automatically:
1. Query all `enabled = true` instruments
2. Fetch their candle data
3. Calculate metrics
4. Rank and filter
5. Return top N per asset class

No code changes needed - just manage the `instruments` table!

## Troubleshooting

### Symbol Not Appearing in Watchlist

Check:
1. **Is it enabled?** `SELECT * FROM instruments WHERE symbol = 'AAPL';`
2. **Has candle data?** `SELECT COUNT(*) FROM candles WHERE symbol = 'AAPL' AND tf = '1d';`
3. **Meets thresholds?** Check `config/watchlist_rules.yaml`

### Too Many/Few Symbols

Adjust in `config/watchlist_rules.yaml`:
```yaml
classes:
  forex:
    top_n: 15  # Increase from 10
```

Or adjust thresholds:
```yaml
classes:
  forex:
    atr_pct_min: 0.001  # Lower = more symbols qualify
```

## Future Enhancements

- [ ] Auto-discovery workflow (weekly)
- [ ] Dynamic priority based on performance
- [ ] Symbol health monitoring
- [ ] Correlation-based filtering
- [ ] Market cap weighting
- [ ] Sector/industry grouping

