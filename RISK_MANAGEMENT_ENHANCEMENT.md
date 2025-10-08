# Risk Management Enhancement - Stop-Loss & Take-Profit

## ✅ Enhancement Complete (October 8, 2025)

The Capital.com MCP Server has been enhanced to support risk management parameters on all order types.

---

## 🎯 What Was Added

### **New Parameters for `place_market_order`:**
- `stop_loss` (optional): Stop-loss price level
- `take_profit` (optional): Take-profit price level  
- `trailing_stop` (optional): Trailing stop distance

### **New Parameters for `place_limit_order`:**
- `stop_loss` (optional): Stop-loss price level
- `take_profit` (optional): Take-profit price level
- `trailing_stop` (optional): Trailing stop distance

---

## 📖 Usage Examples

### **Example 1: Market Order with Stop-Loss and Take-Profit**

**Current Price:** 0.86664 (EURGBP)

```python
place_market_order(
    epic="EURGBP",
    direction="BUY",
    size="100",
    stop_loss="0.86364",      # -30 pips (max $35 loss)
    take_profit="0.87164",    # +50 pips (~$58 profit)
    confirm_live_trade=""     # Not needed for demo
)
```

**Result:**
- Entry: 0.86664
- Stop-Loss: 0.86364 (automatic close if price drops)
- Take-Profit: 0.87164 (automatic close if target reached)
- Risk/Reward: 1:1.67

---

### **Example 2: Limit Order with Trailing Stop**

```python
place_limit_order(
    epic="EURUSD",
    direction="BUY",
    size="50",
    limit_level="1.1000",     # Order triggers at this price
    stop_loss="1.0950",       # -50 pips protection
    trailing_stop="30",       # Follows price by 30 pips
    confirm_live_trade=""
)
```

**Result:**
- Order waits until EURUSD reaches 1.1000
- When filled, stop-loss is placed at 1.0950
- Trailing stop follows price movements

---

### **Example 3: Market Order with Only Take-Profit**

```python
place_market_order(
    epic="US500",
    direction="SELL",
    size="1",
    take_profit="4500",       # Target level
    confirm_live_trade=""
)
```

**Result:**
- Immediate execution at current market price
- Position auto-closes when US500 reaches 4500

---

## 🔧 Technical Details

### **API Payload Changes:**

**Before:**
```json
{
  "epic": "EURGBP",
  "direction": "BUY",
  "size": 100
}
```

**After (with risk management):**
```json
{
  "epic": "EURGBP",
  "direction": "BUY",
  "size": 100,
  "stopLevel": 0.86364,
  "profitLevel": 0.87164,
  "trailingStop": 30
}
```

---

## 📊 Benefits

### **1. Risk Management**
- ✅ Automatic loss protection
- ✅ Guaranteed profit taking
- ✅ Emotional discipline

### **2. No Manual Monitoring**
- ✅ Orders manage themselves
- ✅ Works 24/7 automatically
- ✅ No need to watch positions

### **3. Better Trading Psychology**
- ✅ Pre-defined exit strategy
- ✅ Reduces stress
- ✅ Consistent approach

---

## 🎓 Trading Tips

### **Stop-Loss Placement:**
1. **Support/Resistance**: Place beyond key levels
2. **Percentage**: 1-2% of account balance
3. **Volatility**: Use ATR (Average True Range)

### **Take-Profit Strategies:**
1. **Risk/Reward Ratio**: Minimum 1:2 (risk $1 to make $2)
2. **Technical Targets**: Fibonacci levels, resistance zones
3. **Trailing Stops**: Lock in profits as price moves

### **Example Risk Management:**

**Account:** $1,000  
**Risk Per Trade:** 2% = $20  
**Position Size:** Calculate based on stop-loss distance

If stop-loss is 30 pips away:
- Position size = $20 / 30 pips = 0.67 per pip
- This automatically limits your loss to $20

---

## 🔄 How to Use (Restart Required)

### **Step 1: Quit Cursor**
```bash
# Quit Cursor completely (Cmd+Q)
```

### **Step 2: Restart Cursor**
```bash
# Reopen Cursor to load updated MCP server
```

### **Step 3: Test the New Features**
Try placing an order with stop-loss:

> "Place a buy order for 100 units of EURGBP with stop-loss at 0.86364 and take-profit at 0.87164"

---

## ⚠️ Important Notes

### **Parameter Validation:**
- All price levels must be positive numbers
- Stop-loss should be below entry for BUY orders
- Stop-loss should be above entry for SELL orders
- Take-profit should be above entry for BUY orders
- Take-profit should be below entry for SELL orders

### **Optional Parameters:**
- You can use only stop-loss: `stop_loss="0.86364"`
- You can use only take-profit: `take_profit="0.87164"`
- You can use both or neither
- Trailing stop works independently

### **Live Trading:**
- Still requires `confirm_live_trade="yes"` for live mode
- Risk management doesn't bypass safety checks
- Always test in demo first!

---

## 📝 Changes Made to Codebase

### **Files Modified:**
1. `capital_server.py`:
   - Enhanced `place_market_order()` function
   - Enhanced `place_limit_order()` function
   - Added validation for new parameters
   - Updated payload construction
   - Improved success messages

2. `~/.docker/mcp/catalogs/my-servers.yaml`:
   - Updated tool descriptions

3. Docker image rebuilt with new functionality

---

## 🎉 Ready to Use!

Your Capital.com MCP server now supports professional-grade risk management!

**Next Steps:**
1. ✅ Quit and restart Cursor
2. ✅ Try the enhanced order tools
3. ✅ Practice with sensible stop-loss/take-profit levels
4. ✅ Always test in demo mode first!

---

## 📚 Additional Resources

- [Capital.com Risk Management Guide](https://capital.com/risk-management)
- [Position Sizing Calculator](https://www.myfxbook.com/forex-calculators/position-size)
- [Risk/Reward Ratio Explained](https://www.investopedia.com/terms/r/riskrewardratio.asp)

---

**Version:** 1.1.0  
**Enhancement Date:** 2025-10-08  
**Status:** ✅ Complete and Ready


