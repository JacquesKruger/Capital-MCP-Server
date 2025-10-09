# Trade Management System - Complete Implementation

## 🎯 Overview

Comprehensive trade management system with:
1. **Intelligent Position Sizing** - USD-based with 60% reserve rule
2. **Automatic Trade Management** - Monitors and closes positions
3. **Stop-Loss & Take-Profit** - Integrated with Capital.com
4. **Telegram Notifications** - Real-time position updates

---

## 📊 Position Sizing System

### Philosophy: 60% Reserve Rule

**Your capital allocation:**
- **Maximum at Risk**: 40% of available capital
- **Minimum Reserve**: 60% always available
- **Per-Trade Risk**: 2% of total capital (customizable)

### Example with $1,000 Capital

```
Available Capital: $1,000
Max Deployable: $400 (40%)
Reserved: $600 (60%)

For EURUSD trade with 1.5% stop:
- Position Size: $400 USD
- Risk if Stop Hit: $6 (0.6% of capital)
- Units: 368.66 lots @ 1.0850
- Take Profit Target: $12 (2:1 R:R)
```

### Position Sizer Script

**Location**: `automation/scripts/position_sizer.py`

**Usage**:
```bash
echo '{
  "available_capital": 1000,
  "current_price": 1.0850,
  "stop_loss_pct": 0.015,
  "instrument_type": "forex"
}' | docker exec -i trading-mcp-caller python3 /app/scripts/position_sizer.py
```

**Parameters**:
- `available_capital`: Your current USD balance
- `current_price`: Entry price for instrument
- `stop_loss_pct`: Stop distance as decimal (0.015 = 1.5%)
- `instrument_type`: forex|crypto|stocks|indices|metals
- `max_risk_pct`: Optional, default 0.02 (2%)
- `min_reserve_pct`: Optional, default 0.60 (60%)

**Output**:
```json
{
  "position_size_usd": 400.0,
  "position_size_units": 368.66,
  "risk_amount_usd": 6.0,
  "risk_pct_of_capital": 0.6,
  "stop_loss_pct": 1.5,
  "take_profit_pct": 3.0,
  "reserve_after_entry": 600.0,
  "reserve_pct_after_entry": 60.0,
  "meets_reserve_requirement": true,
  "warnings": []
}
```

---

## 🔄 Trade Management Workflow

### Overview

**File**: `automation/n8n/workflows/trade_management.json`

**Trigger**: Every 5 minutes (cron: `*/5 * * * *`)

**Purpose**: Monitor open positions and close based on exit rules

### Exit Rules

1. **Stop-Loss Hit** ✅
   - Closes immediately if price hits stop level
   - Protects capital from excessive losses

2. **Take-Profit Hit** ✅
   - Closes when target profit reached
   - Default: 2:1 risk-reward ratio

3. **Maximum Hold Time** ⏱️
   - Auto-close after 24 hours
   - Prevents overnight risk accumulation

4. **Loss Limit Fallback** 🛡️
   - Closes if loss > 3% (emergency backup)
   - In case stop wasn't set/triggered

### Workflow Nodes

1. **Cron Trigger** → Runs every 5 minutes
2. **Get Open Positions** → Fetches from Capital.com
3. **Parse Positions** → Extracts position data
4. **Has Positions?** → Check if any open
5. **Evaluate Positions** → Apply exit rules
6. **Should Close?** → Decision point
7. **Close Position** → Calls Capital.com API
8. **Log Position Close** → Database logging
9. **Notify Close** → Telegram alert
10. **Log Completion** → Workflow completion

### Telegram Notifications

When a position closes, you receive:
```
🔴 POSITION CLOSED

Symbol: EURUSD
Reason: TAKE_PROFIT_HIT
P&L: $12.45

take-profit reached
```

---

## 🔧 Integration with Existing Workflows

### Step 1: Update Risk & Order Routing

The "Create Intent" node needs to:
1. Call `position_sizer.py` to calculate size
2. Store position size in USD
3. Calculate stop-loss and take-profit levels
4. Store these in intents table

**Next Steps** (I'll implement):
- Add position sizer call to risk workflow
- Update intents table schema for USD sizing
- Pass stops to approval handler

### Step 2: Update Approval Handler

The "Place Order" node needs to:
1. Use USD position size (not arbitrary units)
2. Include `stop_loss` parameter
3. Include `take_profit` parameter

**Current**:
```json
{
  "epic": "EURUSD",
  "direction": "BUY",
  "size": "100"  // ❌ Arbitrary units
}
```

**After Update**:
```json
{
  "epic": "EURUSD",
  "direction": "BUY",
  "size": "368.66",  // ✅ Calculated from position sizer
  "stop_loss": "1.0687",  // ✅ 1.5% below entry
  "take_profit": "1.1013"  // ✅ 3% above entry (2:1 R:R)
}
```

### Step 3: Activate Trade Management

Simply import and activate the workflow:
```
1. Import trade_management.json in n8n
2. Activate workflow
3. It runs every 5 minutes automatically
```

---

## 📈 Complete Trading Flow

### Phase 1: Signal Generation
**Workflow**: `data_signals.json` (every 5 min)
1. Fetch market data
2. Calculate indicators
3. Generate BUY/SELL signals
4. Store in database

### Phase 2: Risk Assessment & Intent Creation
**Workflow**: `risk_order_routing.json` (every 5 min)
1. Fetch signals from database
2. Get account balance
3. Get open positions
4. Check risk limits
5. **Calculate position size** (NEW!)
6. **Calculate stop-loss/take-profit** (NEW!)
7. Filter signals (skip existing positions)
8. Create trading intent with sizing
9. Store in database

### Phase 3: Human Approval
**Workflow**: `telegram_notifications.json` (every 1 min)
1. Find pending intents
2. Send Telegram notification with:
   - Symbol, side, strategy
   - **Position size in USD** (NEW!)
   - **Risk amount** (NEW!)
   - **Stop-loss price** (NEW!)
   - Approve/Reject buttons

### Phase 4: Order Execution
**Workflow**: `telegram_approval_handler.json` (long polling)
1. Receive approval/rejection
2. If approved:
   - Place order with Capital.com
   - **Include stop-loss** (NEW!)
   - **Include take-profit** (NEW!)
3. Update database
4. Send confirmation

### Phase 5: Trade Management
**Workflow**: `trade_management.json` (every 5 min) ✨ **NEW**
1. Check all open positions
2. Evaluate exit rules
3. Close positions if:
   - Stop-loss hit
   - Take-profit hit
   - Max hold time reached
   - Emergency loss limit
4. Send Telegram notification
5. Log to database

---

## 🎛️ Configuration

### Risk Parameters

Edit `scripts/position_sizer.py`:

```python
max_risk_pct = 0.02  # 2% risk per trade
min_reserve_pct = 0.60  # 60% minimum reserve
```

### Trade Management Rules

Edit `trade_management.json`, "Evaluate Positions" node:

```javascript
// Maximum hold time
if (age_hours > 24) {  // Change 24 to desired hours
  should_close = true;
}

// Loss limit
if (pnl_pct_abs > 3) {  // Change 3 to desired %
  should_close = true;
}
```

### Monitoring Frequency

Edit `trade_management.json`, "Cron Trigger":

```
*/5 * * * *  // Every 5 minutes (current)
*/15 * * * * // Every 15 minutes (less aggressive)
*/1 * * * *  // Every minute (very aggressive)
```

---

## 🚀 Next Steps to Complete

### Priority 1: Integrate Position Sizing (I'll do this now)

1. ✅ Create `position_sizer.py`
2. ✅ Create `trade_management.json` workflow
3. ⏳ Update `risk_order_routing.json` to call position sizer
4. ⏳ Update `telegram_approval_handler.json` to include stops
5. ⏳ Update `telegram_notifications.json` to show sizing info

### Priority 2: Database Schema Updates

Add columns to `intents` table:
```sql
ALTER TABLE intents ADD COLUMN position_size_usd REAL;
ALTER TABLE intents ADD COLUMN position_size_units REAL;
ALTER TABLE intents ADD COLUMN stop_loss_price REAL;
ALTER TABLE intents ADD COLUMN take_profit_price REAL;
ALTER TABLE intents ADD COLUMN risk_amount_usd REAL;
```

### Priority 3: Testing

1. Run position sizer with your current balance
2. Import trade management workflow
3. Test with one small position
4. Verify stop-loss and take-profit work
5. Activate for live trading

---

## 💡 Benefits of This System

### 1. Capital Preservation
- **60% always in reserve** - never over-leverage
- **2% risk per trade** - survive losing streaks
- **Automatic stops** - limit losses

### 2. Professional Risk Management
- **Position sizing based on stop distance**
- **Consistent risk across all trades**
- **No emotional sizing decisions**

### 3. Automated Execution
- **Monitors 24/7** (every 5 minutes)
- **Closes positions automatically**
- **No manual intervention needed**

### 4. Transparency
- **Telegram notifications** for all actions
- **Database logging** of all decisions
- **Clear reasoning** for each close

---

## 📊 Example Scenarios

### Scenario 1: Small Account ($1,000)

**Trade**: EURUSD @ 1.0850, Stop 1.5%, Target 3%

```
Max Deployable: $400 (40% of $1,000)
Risk if Stop Hit: $6 (0.6% of capital)
Position Size: 368.66 units
Stop-Loss: 1.0687 (-$6)
Take-Profit: 1.1013 (+$12)
Reserve After Entry: $600 (60%)
```

### Scenario 2: Larger Account ($10,000)

**Trade**: BTCUSD @ 65,000, Stop 2%, Target 4%

```
Max Deployable: $4,000 (40% of $10,000)
Risk if Stop Hit: $80 (0.8% of capital)
Position Size: 0.0615 BTC
Stop-Loss: 63,700 (-$80)
Take-Profit: 67,600 (+$160)
Reserve After Entry: $6,000 (60%)
```

### Scenario 3: Multiple Positions

With $10,000 capital and 3 positions:
- Each position: $1,333 max
- Total deployed: $4,000
- Reserve: $6,000 (60%)
- Max risk per trade: $200 (2%)

---

## ⚠️ Important Notes

1. **Stop-Loss is Critical**
   - Position sizer assumes stops will be hit
   - Without stops, you risk more than calculated
   - Always verify stop is set on broker

2. **Slippage Considerations**
   - Actual fills may differ from calculated
   - Add 0.1-0.2% buffer to stops
   - More important for crypto/volatile assets

3. **Capital.com Minimums**
   - Each instrument has minimum size
   - Position sizer respects these
   - Very small accounts may hit minimums

4. **Reserve is Not Static**
   - 60% of *available* capital
   - As capital grows, deployable grows
   - As capital shrinks, deployable shrinks

---

## 🎓 Best Practices

1. **Start Small**
   - Test with minimum position sizes
   - Verify all workflows work
   - Gradually increase as confident

2. **Monitor Initially**
   - Watch trade management workflow
   - Verify positions close correctly
   - Check Telegram notifications

3. **Review Weekly**
   - Check database for closed trades
   - Analyze which exit rules triggered
   - Adjust parameters if needed

4. **Emergency Procedures**
   - Know how to deactivate workflows
   - Have Capital.com app ready
   - Can manually close positions

---

**Status**: Ready to integrate! 

Shall I proceed with updating the workflows to include position sizing and stop-loss/take-profit?

