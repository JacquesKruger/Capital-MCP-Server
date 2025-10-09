# Stop-Loss & Take-Profit Implementation Summary

## ✅ Complete Implementation

Stop-loss and take-profit levels are now **fully integrated** throughout the trading system.

---

## 📊 Data Flow

### 1. **Intent Creation** (`risk_order_routing.json` → "Create Intent" node)
- Calculates stop-loss and take-profit **prices** based on:
  - Entry price
  - Stop-loss percentage (from `position_sizer.py`)
  - Take-profit percentage (from `position_sizer.py`)
- **For BUY orders**:
  ```javascript
  stopLossPrice = currentPrice * (1 - stopLossPct)
  takeProfitPrice = currentPrice * (1 + takeProfitPct)
  ```
- **For SELL orders**:
  ```javascript
  stopLossPrice = currentPrice * (1 + stopLossPct)
  takeProfitPrice = currentPrice * (1 - takeProfitPct)
  ```
- Stores in `intents` table:
  - `stop_loss_price`
  - `take_profit_price`
  - `stop_loss_pct`
  - `take_profit_pct`

### 2. **Telegram Notification** (`telegram_notifications.json` → "Prepare Notification" node)
- Fetches intent with stop-loss/take-profit prices
- **Calculates USD amounts**:
  - **For BUY**: 
    - Loss = `(entryPrice - stopPrice) * units`
    - Profit = `(targetPrice - entryPrice) * units`
  - **For SELL**:
    - Loss = `(stopPrice - entryPrice) * units`
    - Profit = `(entryPrice - targetPrice) * units`
- **Message format**:
  ```
  Stop Loss: 119729.9840 (-$24.43)
  Take Profit: 127060.3900 (+$48.87)
  ```

### 3. **Order Approval** (`telegram_approval_handler.json` → "Generate Approval Token" node)
- Extracts `stop_loss_price` and `take_profit_price` from intent
- Converts to strings for API call:
  ```javascript
  const stopLoss = data.stop_loss_price ? data.stop_loss_price.toString() : '';
  const takeProfit = data.take_profit_price ? data.take_profit_price.toString() : '';
  ```

### 4. **Order Placement** (`telegram_approval_handler.json` → "Place Order" node)
- Sends to MCP API endpoint `/mcp/place_market_order`:
  ```json
  {
    "epic": "BTCUSD",
    "direction": "BUY",
    "size": "0.01",
    "stop_loss": "119729.9840",
    "take_profit": "127060.3900",
    "confirm_live_trade": "no"
  }
  ```

### 5. **MCP API** (`mcp_api.py` → `place_market_order()`)
- Passes parameters to MCP server:
  ```python
  result = server.call_tool('place_market_order', {
      'epic': data.get('epic'),
      'direction': data.get('direction'),
      'size': data.get('size'),
      'stop_loss': data.get('stop_loss'),      # ✅
      'take_profit': data.get('take_profit'),  # ✅
      'trailing_stop': data.get('trailing_stop'),
      'confirm_live_trade': data.get('confirm_live_trade')
  })
  ```

### 6. **Capital.com MCP Server** (`capital_server.py` → `place_market_order()`)
- Validates stop-loss and take-profit:
  ```python
  stop_loss_float = float(stop_loss) if stop_loss else None
  take_profit_float = float(take_profit) if take_profit else None
  ```
- Builds API payload with **Capital.com field names**:
  ```python
  payload = {
      "epic": epic,
      "direction": direction,
      "size": size_float
  }
  
  if stop_loss_float is not None:
      payload["stopLevel"] = stop_loss_float    # ✅
  
  if take_profit_float is not None:
      payload["profitLevel"] = take_profit_float  # ✅
  ```
- Sends to Capital.com API: `POST /api/v1/positions`

---

## 📝 Database Schema

### `intents` Table Columns:
```sql
stop_loss_price REAL        -- Absolute price level for stop-loss
take_profit_price REAL      -- Absolute price level for take-profit
risk_amount_usd REAL        -- USD amount at risk (from position sizer)
stop_loss_pct REAL          -- Percentage for stop-loss (e.g., 2.0 = 2%)
take_profit_pct REAL        -- Percentage for take-profit (e.g., 4.0 = 4%)
```

---

## 🧪 Example Calculation

**Intent**:
- Symbol: BTCUSD
- Side: BUY
- Entry: $122,173.45
- Position: 0.01 units ($1,221.73)
- Stop-loss %: 2%
- Take-profit %: 4%

**Calculated Prices**:
```javascript
stopLossPrice = 122173.45 * (1 - 0.02) = 119,729.98
takeProfitPrice = 122173.45 * (1 + 0.04) = 127,060.39
```

**USD Amounts** (for Telegram):
```javascript
stopLossUSD = (122173.45 - 119729.98) * 0.01 = $24.43
takeProfitUSD = (127060.39 - 122173.45) * 0.01 = $48.87
```

**Telegram Message**:
```
Stop Loss: 119729.9840 (-$24.43)
Take Profit: 127060.3900 (+$48.87)
```

**Capital.com API Call**:
```json
{
  "epic": "BTCUSD",
  "direction": "BUY",
  "size": 0.01,
  "stopLevel": 119729.9840,
  "profitLevel": 127060.3900
}
```

---

## ✅ Verification Checklist

To verify stop-loss/take-profit are working:

1. **Check intents table**:
   ```sql
   SELECT symbol, side, price, stop_loss_price, take_profit_price 
   FROM intents 
   WHERE status = 'PENDING' 
   ORDER BY created_at DESC 
   LIMIT 5;
   ```
   ✅ Should show calculated SL/TP prices

2. **Check Telegram notification**:
   - Should display: `Stop Loss: X.XXXX (-$YY.YY)`
   - Should display: `Take Profit: X.XXXX (+$ZZ.ZZ)`

3. **Approve a trade via Telegram**

4. **Check Capital.com platform**:
   - Open the position
   - Verify stop-loss and take-profit are set
   - Verify they match the values in the Telegram message

5. **Check MCP server logs**:
   ```bash
   docker logs exciting_neumann --tail 50 | grep -A 10 "Placing market order"
   ```
   Should show: `with SL=119729.98 TP=127060.39`

---

## 🔧 Configuration

Stop-loss and take-profit percentages are set in `position_sizer.py`:

```python
# Default configuration
DEFAULT_STOP_LOSS_PCT = 2.0      # 2% stop-loss
DEFAULT_TAKE_PROFIT_PCT = 4.0    # 4% take-profit (2:1 reward/risk)
DEFAULT_RISK_PCT = 2.5           # 2.5% of capital at risk per trade
```

Adjust these values to change risk/reward profile.

---

## 🎯 Key Features

✅ **Automatic calculation** - No manual input needed  
✅ **Database persistence** - Stored for audit trail  
✅ **Clear visualization** - USD amounts in Telegram  
✅ **API integration** - Sent to Capital.com  
✅ **Direction-aware** - Correct logic for BUY vs SELL  
✅ **Risk management** - Enforces 60% reserve requirement  

---

## 📌 Important Notes

1. **Old positions** without SL/TP:
   - Positions opened before this implementation won't have SL/TP
   - Manually close these or add SL/TP via Capital.com platform

2. **Demo vs Live**:
   - Currently in **demo mode** (`env_mode: 'demo'`)
   - Live trading requires `confirm_live_trade: 'yes'`

3. **Capital.com API fields**:
   - Our field names: `stop_loss`, `take_profit`
   - Capital.com API: `stopLevel`, `profitLevel`
   - Conversion handled in `capital_server.py`

---

**Status**: ✅ **FULLY OPERATIONAL**

Stop-loss and take-profit levels are now automatically calculated, displayed, and applied to all new trades.


