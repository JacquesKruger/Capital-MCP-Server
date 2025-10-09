# Capital.com API Limitation: Stop-Loss & Take-Profit

## 🔴 **CRITICAL ISSUE DISCOVERED**

Capital.com's **demo API** does **NOT honor** the `stopLevel` and `profitLevel` parameters when placing market orders via `POST /api/v1/positions`.

---

## 📊 Evidence

### 1. **Parameters ARE being sent correctly**:
```json
POST /api/v1/positions
{
  "epic": "BTCUSD",
  "direction": "BUY",
  "size": 0.01,
  "stopLevel": 119713.32,    ← Sent ✅
  "profitLevel": 127042.71   ← Sent ✅
}
```

### 2. **API returns 200 OK**:
- No error message
- Deal reference returned
- Position created successfully

### 3. **BUT: Position has NO stop-loss or take-profit**:
- Verified in Capital.com web platform
- `get_positions` API doesn't return SL/TP data
- Manual inspection shows toggles are OFF

---

## 🔍 Root Cause

Capital.com's **demo environment** likely:
1. Accepts `stopLevel` and `profitLevel` parameters (no validation error)
2. Silently ignores them (no error, no application)
3. Creates position without risk management levels

This is common with broker demo APIs to simplify testing.

---

## ✅ Solutions

### **Option A: Update Stop-Loss/Take-Profit After Order Placement** (Recommended)

1. Place the market order (without SL/TP)
2. Get the `dealId` from the opened position
3. Use Capital.com's **update position endpoint** to add SL/TP:
   ```
   PUT /api/v1/positions/{dealId}
   {
     "stopLevel": 119713.32,
     "profitLevel": 127042.71
   }
   ```

**Implementation**:
- Add new MCP tool: `update_position_risk_levels(deal_id, stop_loss, take_profit)`
- Modify approval handler workflow to:
  1. Place order
  2. Wait for execution
  3. Get deal ID
  4. Update risk levels

---

### **Option B: Manual Risk Management in Capital.com Platform**

User manually sets stop-loss and take-profit after receiving notification.

**Pros**: Simple, no code changes  
**Cons**: Defeats automation purpose, prone to human error

---

### **Option C: Accept Demo Limitation, Enable for Live Trading**

The **live API** likely honors `stopLevel` and `profitLevel` correctly.

**Approach**:
- Test in demo without SL/TP
- Enable SL/TP only for live trading
- Add warning in demo mode

---

## 🎯 Recommended Implementation

**Use Option A** - Update positions after placement.

### New MCP Tool

Add to `capital_server.py`:

```python
@mcp.tool()
def update_position_risk_levels(deal_id: str = "", stop_loss: str = "", take_profit: str = "") -> str:
    """Update stop-loss and take-profit for an existing position."""
    deal_id = deal_id.strip()
    stop_loss = stop_loss.strip()
    take_profit = take_profit.strip()
    
    if not deal_id:
        return "❌ Deal ID is required"
    
    payload = {}
    
    if stop_loss:
        try:
            payload["stopLevel"] = float(stop_loss)
        except ValueError:
            return f"❌ Invalid stop-loss value: {stop_loss}"
    
    if take_profit:
        try:
            payload["profitLevel"] = float(take_profit)
        except ValueError:
            return f"❌ Invalid take-profit value: {take_profit}"
    
    if not payload:
        return "❌ At least one of stop_loss or take_profit must be provided"
    
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    try:
        _rate_limit()
        
        response = _client.put(
            f"{BASE_URL}/api/v1/positions/{deal_id}",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            result = f"✅ Position Risk Levels Updated\n"
            result += f"Deal ID: {deal_id}\n"
            if stop_loss:
                result += f"Stop Loss: {stop_loss}\n"
            if take_profit:
                result += f"Take Profit: {take_profit}\n"
            return result
        else:
            return f"❌ Failed to update position: {response.status_code} - {response.text[:200]}"
    
    except Exception as e:
        return f"❌ Error updating position: {str(e)}"
```

### Updated Workflow

Modify `telegram_approval_handler.json`:

1. **After "Place Order" node**, add new nodes:
   - "Wait for Execution" (Wait 2 seconds)
   - "Get Position Deal ID" (Code node to extract from positions)
   - "Update Risk Levels" (HTTP Request to new MCP endpoint)
   - "Log Risk Update" (Postgres node)

---

## 📝 Testing Plan

1. Create the `update_position_risk_levels` tool
2. Test manually:
   ```bash
   curl -X POST http://localhost:8000/mcp/update_position_risk_levels \
     -H "Content-Type: application/json" \
     -d '{
       "deal_id": "000940dd-0055-311e-0000-000082e8bf10",
       "stop_loss": "119713.32",
       "take_profit": "127042.71"
     }'
   ```
3. Verify in Capital.com platform
4. If successful, integrate into workflow

---

## 🚨 Current Status

**Stop-loss and take-profit are NOT being applied to positions** despite being:
- ✅ Calculated correctly
- ✅ Stored in database
- ✅ Sent to Capital.com API
- ❌ **Applied to actual positions** ← ISSUE

**Action Required**: Implement Option A (update after placement)

---

## 📚 References

- Capital.com API Docs: https://open-api.capital.com/
- MCP Server: `capital_server.py`
- Approval Handler: `telegram_approval_handler.json`
- Debug logs: `docker logs trading-mcp-caller | grep "place_market_order"`


