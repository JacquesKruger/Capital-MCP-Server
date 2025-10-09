# n8n Workflow Import & Execution Guide

## 📋 Import Order

Import the workflows in this order (recommended for dependencies):

### 1️⃣ **Data Collection & Signals** (ALREADY IMPORTED & WORKING ✅)
**File:** `n8n/workflows/data_signals.json`  
**Status:** ✅ Tested and operational  
**Purpose:** Collects market data, calculates indicators, generates signals  
**Dependencies:** None - this is the foundation workflow

---

### 2️⃣ **Telegram Notifications** (Import Second)
**File:** `n8n/workflows/telegram_notifications.json`  
**Status:** Ready to import  
**Purpose:** Sends Telegram alerts for signals, trades, errors  
**Dependencies:** Telegram bot token configured in `.env`

**Import Steps:**
1. In n8n, click **Workflows** → **Import from File**
2. Select `automation/n8n/workflows/telegram_notifications.json`
3. Click **Import**
4. Configure credentials if needed

---

### 3️⃣ **Telegram Approval Handler** (Import Third)
**File:** `n8n/workflows/telegram_approval_handler.json`  
**Status:** Ready to import  
**Purpose:** Handles trade approvals via Telegram  
**Dependencies:** Telegram bot, Telegram Notifications workflow

**Import Steps:**
1. Import from `automation/n8n/workflows/telegram_approval_handler.json`
2. Set up Telegram webhook (instructions in workflow)

---

### 4️⃣ **Risk & Order Routing** (Import Fourth)
**File:** `n8n/workflows/risk_order_routing.json`  
**Status:** Ready to import  
**Purpose:** Evaluates signals, checks risk limits, routes orders  
**Dependencies:** Data Signals workflow, Telegram workflows

**Import Steps:**
1. Import from `automation/n8n/workflows/risk_order_routing.json`
2. Verify database credentials
3. Test with DEMO mode only

---

### 5️⃣ **Post-Trade Management** (Import Fifth)
**File:** `n8n/workflows/post_trade_management.json`  
**Status:** Ready to import  
**Purpose:** Monitors open positions, manages stops/targets  
**Dependencies:** Risk & Order Routing workflow

**Import Steps:**
1. Import from `automation/n8n/workflows/post_trade_management.json`
2. Review position management rules

---

### 6️⃣ **Nightly Evaluation** (Import Last)
**File:** `n8n/workflows/nightly_evaluation.json`  
**Status:** Ready to import  
**Purpose:** Daily performance analysis, bandit updates  
**Dependencies:** All other workflows

**Import Steps:**
1. Import from `automation/n8n/workflows/nightly_evaluation.json`
2. Set execution time (default: 23:59)

---

## ⚙️ Workflow Activation Order

After importing, activate them in this order:

### Step 1: Activate Foundation Workflows
```
✅ 1. Data Collection & Signals (already active)
```

### Step 2: Activate Notification System
```
2. Telegram Notifications
3. Telegram Approval Handler
```

### Step 3: Activate Trading Workflows (DEMO MODE ONLY!)
```
4. Risk & Order Routing
5. Post-Trade Management
```

### Step 4: Activate Analysis
```
6. Nightly Evaluation
```

---

## 🔄 Execution Flow & Schedule

### Automated Schedule (via Cron Triggers)

**Every 15 Minutes:**
```
Data Collection & Signals
├─ Fetches latest quotes
├─ Calculates indicators
├─ Generates signals
└─ Stores in database
```

**Every 1 Minute (when signals exist):**
```
Risk & Order Routing
├─ Checks for new signals
├─ Applies risk filters
├─ Bandit selects strategy/sizing
├─ Requests approval (Telegram)
└─ Places orders (if approved)
```

**Every 1 Minute (when positions open):**
```
Post-Trade Management
├─ Checks open positions
├─ Updates stop losses
├─ Checks take profit levels
├─ Closes positions when triggered
└─ Records trade results
```

**Daily at 23:59:**
```
Nightly Evaluation
├─ Calculates daily performance
├─ Updates bandit with rewards
├─ Generates performance report
└─ Sends summary to Telegram
```

**On Demand (Telegram trigger):**
```
Telegram Approval Handler
├─ Receives approval/rejection
├─ Validates token
├─ Executes or cancels trade
└─ Confirms to user
```

---

## 🧪 Testing Order

**Test each workflow individually before moving to the next:**

### Test 1: Data Collection ✅
**Status:** Already tested and working

**Verify:**
```sql
SELECT * FROM signals ORDER BY id DESC LIMIT 5;
```

---

### Test 2: Telegram Notifications

**Steps:**
1. Activate workflow
2. Manually trigger: Click **Execute Workflow**
3. Check Telegram for test message

**Expected:** Receive Telegram notification

---

### Test 3: Telegram Approval Handler

**Steps:**
1. Activate workflow
2. Send test approval via Telegram: `/approve test`
3. Check workflow execution log

**Expected:** Workflow processes approval command

---

### Test 4: Risk & Order Routing (CRITICAL - DEMO ONLY!)

**⚠️ IMPORTANT:** Ensure `.env` has `CAP_ENVIRONMENT=demo`

**Steps:**
1. Wait for Data Signals to generate signals
2. Risk workflow should trigger automatically
3. Check for Telegram approval request
4. Approve via Telegram
5. Verify order placed in Capital.com DEMO account

**Verify:**
```sql
SELECT * FROM intents ORDER BY created_at DESC LIMIT 5;
SELECT * FROM orders ORDER BY placed_at DESC LIMIT 5;
```

---

### Test 5: Post-Trade Management

**Steps:**
1. Ensure you have open positions (from Test 4)
2. Wait 1 minute for workflow to run
3. Check workflow logs

**Verify:**
```sql
SELECT * FROM trades ORDER BY opened_at DESC LIMIT 5;
```

---

### Test 6: Nightly Evaluation

**Steps:**
1. Manually trigger: Click **Execute Workflow**
2. Check execution log
3. Check Telegram for daily report

**Verify:**
```sql
SELECT * FROM performance ORDER BY day DESC LIMIT 5;
SELECT * FROM bandit_policy ORDER BY id DESC LIMIT 1;
```

---

## 📊 Monitoring Dashboard

### Quick Health Check
```bash
# Check workflow executions
docker-compose logs -f n8n | grep -E "(SUCCESS|ERROR)"

# Check database activity
docker-compose exec db psql -U trader -d trading -c "
  SELECT 
    event_type, 
    COUNT(*) as count,
    MAX(occurred_at) as last_seen
  FROM system_events
  GROUP BY event_type
  ORDER BY last_seen DESC;
"
```

### Check Latest Activity
```sql
-- Latest signals
SELECT symbol, strategy, signal, score, 
       to_timestamp(ts) as time
FROM signals 
ORDER BY id DESC LIMIT 10;

-- Latest intents
SELECT symbol, side, strategy, status, created_at
FROM intents
ORDER BY created_at DESC LIMIT 10;

-- Latest orders
SELECT symbol, side, status, placed_at
FROM orders
ORDER BY placed_at DESC LIMIT 10;

-- Latest trades
SELECT symbol, side, pnl, closed_at
FROM trades
WHERE closed_at IS NOT NULL
ORDER BY closed_at DESC LIMIT 10;
```

---

## 🚨 Troubleshooting

### Workflow Won't Import
**Problem:** JSON parse error  
**Solution:** Ensure the JSON file is valid. Try importing `00_starter_template.json` first as a test.

### Workflow Executes But Fails
**Problem:** Node errors  
**Solution:** 
1. Check database credentials in each Postgres node
2. Verify HTTP endpoints are accessible (http://mcp-caller:8000)
3. Check logs: `docker-compose logs -f mcp-caller`

### No Signals Generated
**Problem:** Empty candles table  
**Solution:**
```sql
-- Check candle count
SELECT symbol, COUNT(*) FROM candles GROUP BY symbol;

-- If empty, wait 15 min for Data Signals workflow
-- Or manually populate (see COMPLETION_SUMMARY.txt)
```

### Rate Limit Errors
**Problem:** 429 errors from Capital.com  
**Solution:** 
1. Restart mcp-caller: `docker-compose restart mcp-caller`
2. Wait 10 minutes before testing again
3. The persistent session should prevent this

### Telegram Not Working
**Problem:** No messages received  
**Solution:**
1. Verify `TELEGRAM_BOT_TOKEN` in `.env`
2. Verify `TELEGRAM_CHAT_ID` in `.env`
3. Test bot: Send `/start` to your bot
4. Check n8n logs for Telegram API errors

---

## 🎯 Recommended Testing Schedule

### Week 1: Foundation Testing
- ✅ Day 1: Data Collection (done)
- Day 2: Telegram Notifications
- Day 3: Telegram Approvals
- Day 4-7: Monitor data collection stability

### Week 2: Trading Logic Testing (DEMO ONLY)
- Day 8-9: Risk & Order Routing
- Day 10-11: Post-Trade Management
- Day 12-14: Full stack integration

### Week 3-4: Performance Validation
- Day 15-21: Nightly Evaluation
- Day 22-28: Bandit learning validation
- Review all signals and outcomes

### Month 2+: Live Trading Consideration
- Review all DEMO results
- Verify risk management working
- Start with minimum position sizes
- Increase gradually

---

## ✅ Pre-Activation Checklist

Before activating any workflow for the first time:

- [ ] Database credentials configured
- [ ] Environment variables set (`.env`)
- [ ] MCP server running (`docker ps | grep cool_hopper`)
- [ ] mcp-caller API healthy (`curl http://localhost:8000/health`)
- [ ] Database accessible (`docker-compose exec db psql -U trader -d trading -c "\dt"`)
- [ ] Telegram bot configured (if using Telegram workflows)
- [ ] Review workflow nodes for hardcoded values
- [ ] Test execution on sample data
- [ ] Monitor logs during first execution

---

## 🔐 Security Reminders

**Before activating Risk & Order Routing:**

1. ✅ Verify `CAP_ENVIRONMENT=demo` in `.env`
2. ✅ Verify `TRADING_HALTED=0` (or set to 1 to disable all trading)
3. ✅ Review risk limits in `config/risk.yaml`
4. ✅ Test approval flow thoroughly
5. ✅ Never leave approval tokens hardcoded
6. ✅ Monitor all executions closely

**For Live Trading (Future):**
1. ⚠️ Change `CAP_ENVIRONMENT=live` ONLY when ready
2. ⚠️ Require approval for ALL live trades
3. ⚠️ Start with minimum position sizes
4. ⚠️ Set strict risk limits
5. ⚠️ Monitor 24/7 for first week
6. ⚠️ Have kill switch ready (`TRADING_HALTED=1`)

---

## 📞 Support

If you encounter issues:

1. **Check logs:** `docker-compose logs -f n8n`
2. **Check database:** Query `system_events` table
3. **Check MCP API:** `curl http://localhost:8000/health`
4. **Restart services:** `docker-compose restart`
5. **Review documentation:** `README_AUTOMATION.md`, `SECURITY.md`

---

## 🎓 Learning Path

**Beginner:**
1. Start with Data Collection only
2. Understand signals being generated
3. Add Telegram notifications
4. Review signals daily manually

**Intermediate:**
5. Add Risk & Order Routing (DEMO)
6. Manually approve each trade
7. Understand why trades are proposed
8. Review outcomes

**Advanced:**
9. Add Post-Trade Management
10. Add Nightly Evaluation
11. Let bandit optimize
12. Consider live trading (with extreme caution)

---

**Good luck! Start slow, test thoroughly, and trade responsibly.** 🚀


