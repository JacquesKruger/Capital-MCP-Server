# MCP API Updates - Structured Data Response

## Overview
Updated the MCP API endpoints to return **structured, parsed data** instead of raw text responses. This eliminates the need for n8n workflows to parse text with regex and `JSON.parse()`.

## Changes Made

### 1. `/mcp/get_account_balance` (GET)

**Before:**
```json
{
  "success": true,
  "result": "💰 Account Balance (DEMO mode)\n...",
  "text": "..."
}
```

**After:**
```json
{
  "success": true,
  "data": {
    "balance": 1000.27,
    "available": 989.29,
    "currency": "USDd",
    "deposit": 999.95,
    "pnl": 0.32,
    "raw_text": "..."
  },
  "raw": { ... }
}
```

### 2. `/mcp/get_positions` (GET)

**Before:**
```json
{
  "success": true,
  "result": "📊 Open Positions (2 total)\n...",
  "text": "..."
}
```

**After:**
```json
{
  "success": true,
  "data": {
    "count": 2,
    "positions": [
      {
        "dealId": "00005552-001c-241e-0000-0000808c0911",
        "direction": "BUY",
        "epic": "EURGBP",
        "instrumentName": "EUR/GBP",
        "level": 0.8665,
        "profit": 0,
        "size": 100.0
      }
    ],
    "totalExposure": 282.71136,
    "totalPnL": 0,
    "raw_text": "..."
  },
  "raw": { ... }
}
```

## Workflow Updates

### Updated Nodes

#### 1. **Parse Balance** (risk_order_routing.json)
- **Old:** `JSON.parse(data.result)`
- **New:** Direct access to `data.data` (already parsed)

```javascript
// Before
const balance = JSON.parse(data.result);

// After
const balance = data.data;
```

#### 2. **Parse Positions** (risk_order_routing.json)
- **Old:** `JSON.parse(data.result)` + manual calculation of totals
- **New:** Direct access to `data.data` with pre-calculated totals

```javascript
// Before
const positions = JSON.parse(data.result);
// ... manual totalExposure calculation ...

// After
const positionsData = data.data;
// totalExposure, count, totalPnL already calculated
```

#### 3. **Parse Balance** (02_risk_order_routing.json)
- **Old:** `result.result.available`
- **New:** `result.data.available`

## Benefits

1. ✅ **No more parsing errors** - No `JSON.parse()` failures
2. ✅ **Cleaner workflow code** - Less regex, less error handling
3. ✅ **Pre-calculated metrics** - API does the heavy lifting
4. ✅ **Consistent structure** - All endpoints follow same pattern
5. ✅ **Better debugging** - Structured data is easier to inspect

## Testing

```bash
# Test balance endpoint
curl http://localhost:8000/mcp/get_account_balance | jq '.data'

# Test positions endpoint
curl http://localhost:8000/mcp/get_positions | jq '.data'
```

## Migration Checklist

- [x] Update `mcp_api.py` - `/mcp/get_account_balance` endpoint
- [x] Update `mcp_api.py` - `/mcp/get_positions` endpoint
- [x] Update `risk_order_routing.json` - Parse Balance node
- [x] Update `risk_order_routing.json` - Parse Positions node
- [x] Update `02_risk_order_routing.json` - Parse Balance node
- [x] Restart mcp-caller service
- [x] Test both endpoints
- [ ] Re-import workflows in n8n
- [ ] Test full workflow execution

## Next Steps

1. **Re-import workflows** in n8n UI:
   - Delete old "Risk & Order Routing" workflow
   - Import updated `risk_order_routing.json`
   - Configure database credentials

2. **Test nodes individually**:
   - Execute "Get Account Balance" → should return structured data
   - Execute "Parse Balance" → should return clean balance object
   - Execute "Get Positions" → should return structured positions
   - Execute "Parse Positions" → should return risk metrics

3. **Test full workflow**:
   - Run workflow end-to-end
   - Check all nodes produce output
   - Verify data flows correctly to database

## Rollback Plan

If issues occur, the old text parsing logic can be restored by reverting the `mcp_api.py` changes and using the original workflow JSON files.

---

**Status:** ✅ Complete - Ready for testing in n8n
**Date:** 2025-10-08
**Version:** 1.1.0


