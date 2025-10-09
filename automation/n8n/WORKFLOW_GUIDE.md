# n8n Workflow Building Guide

This guide explains how to build the four core workflows for the trading automation stack.

## 📋 Prerequisites

1. n8n running and accessible at http://localhost:5678
2. PostgreSQL connection configured
3. Environment variables available to n8n workflows
4. `mcp-caller` container running

## 🔌 Initial n8n Setup

### 1. Configure PostgreSQL Credential

1. Go to Settings → Credentials
2. Click "Add Credential"
3. Search for "Postgres"
4. Fill in:
   - **Host:** `db` (Docker service name)
   - **Database:** `trading` (or value from `POSTGRES_DB`)
   - **User:** `trader` (or value from `POSTGRES_USER`)
   - **Password:** Your `POSTGRES_PASSWORD`
   - **Port:** `5432`
   - **SSL:** Off (internal network)
5. Test connection and save

### 2. Test Execute Command Node

Create a test workflow to verify `mcp-caller` access:

1. Add "Execute Command" node
2. Command: `docker exec trading-mcp-caller python /app/scripts/mcp_call.py check_status --output json`
3. Execute manually
4. Verify output shows MCP server status

---

## 🔄 Workflow A: Data Collection & Signal Generation

**Purpose:** Fetch price data, calculate indicators, generate signals

### Nodes

#### 1. Schedule Trigger
- **Type:** Cron
- **Cron Expression:** `*/15 * * * *` (every 15 minutes)
- **Description:** Triggers data collection

#### 2. Get Top Instruments
- **Type:** Postgres
- **Operation:** Execute Query
- **Query:**
  ```sql
  SELECT epic, name, tradeable
  FROM instruments
  WHERE tradeable = true
  ORDER BY volatility_atr DESC
  LIMIT 5;
  ```
- **Description:** Fetch tradeable instruments

#### 3. Split Out (Item Loop)
- **Type:** Split Out
- **Description:** Process each instrument individually

#### 4. Get Current Quote
- **Type:** Execute Command
- **Command:**
  ```bash
  docker exec trading-mcp-caller python /app/scripts/mcp_call.py get_quote --args '{"epic":"{{ $json.epic }}"}' --output json
  ```
- **Description:** Fetch latest price from Capital.com

#### 5. Parse Quote JSON
- **Type:** Code (JavaScript)
- **Code:**
  ```javascript
  const result = JSON.parse($input.first().json.stdout);
  const quote = JSON.parse(result.result);
  
  return {
    epic: $('Get Top Instruments').item.json.epic,
    bid: parseFloat(quote.bid),
    ask: parseFloat(quote.ask),
    timestamp: new Date().toISOString()
  };
  ```

#### 6. Store Candle
- **Type:** Postgres
- **Operation:** Insert
- **Table:** `candles`
- **Columns:**
  - `epic`: `{{ $json.epic }}`
  - `timeframe`: `15m`
  - `timestamp`: `{{ $json.timestamp }}`
  - `open`: `{{ $json.ask }}`
  - `high`: `{{ $json.ask }}`
  - `low`: `{{ $json.bid }}`
  - `close`: `{{ ($json.bid + $json.ask) / 2 }}`
  - `spread`: `{{ $json.ask - $json.bid }}`

#### 7. Get Historical Candles
- **Type:** Postgres
- **Operation:** Execute Query
- **Query:**
  ```sql
  SELECT timestamp, open, high, low, close, COALESCE(volume, 1000) as volume
  FROM candles
  WHERE epic = '{{ $json.epic }}'
    AND timeframe = '15m'
    AND timestamp > NOW() - INTERVAL '7 days'
  ORDER BY timestamp ASC
  LIMIT 100;
  ```

#### 8. Calculate Indicators
- **Type:** Execute Command
- **Command:**
  ```bash
  docker exec trading-mcp-caller python /app/scripts/indicators.py \
    --epic '{{ $json.epic }}' \
    --candles '{{ $json.candles | jsonStringify }}'
  ```
- **Description:** Run technical indicator calculations

#### 9. Store Signals
- **Type:** Postgres
- **Operation:** Insert
- **Table:** `signals`
- **Columns:**
  - `epic`: From previous node
  - `strategy_name`: From indicator output
  - `timeframe`: `15m`
  - `signal_type`: `BUY`, `SELL`, or `NEUTRAL`
  - `strength`: Indicator strength score
  - `confidence`: Indicator confidence
  - `indicators`: JSON object with all indicator values
  - `conditions`: JSON object with boolean conditions
  - `generated_at`: `NOW()`
  - `valid_until`: `NOW() + INTERVAL '30 minutes'`

#### 10. Filter Strong Signals
- **Type:** IF
- **Condition:** `{{ $json.strength >= 0.7 && $json.signal_type !== 'NEUTRAL' }}`

#### 11. Create Intent (if strong signal)
- **Type:** HTTP Request
- **Method:** POST
- **URL:** `http://n8n:5678/webhook/create-intent`
- **Body:**
  ```json
  {
    "signal_id": "{{ $json.signal_id }}",
    "epic": "{{ $json.epic }}",
    "signal_type": "{{ $json.signal_type }}",
    "strength": "{{ $json.strength }}"
  }
  ```
- **Description:** Trigger Workflow B

### Workflow Configuration

- **Settings → Execution:** Allow manual execution + schedule
- **Settings → Error Workflow:** Create error handler (logs to system_events)

---

## 🛡️ Workflow B: Risk Management & Order Routing

**Purpose:** Validate signals, calculate risk, create intents, route to approval

### Nodes

#### 1. Webhook Trigger
- **Type:** Webhook
- **Path:** `create-intent`
- **HTTP Method:** POST
- **Authentication:** None (internal)

#### 2. Get Signal Details
- **Type:** Postgres
- **Query:**
  ```sql
  SELECT s.*, i.name AS instrument_name, i.volatility_atr
  FROM signals s
  JOIN instruments i ON s.epic = i.epic
  WHERE s.id = {{ $json.body.signal_id }};
  ```

#### 3. Get Account Balance
- **Type:** Execute Command
- **Command:**
  ```bash
  docker exec trading-mcp-caller python /app/scripts/mcp_call.py get_account_balance --output json
  ```

#### 4. Parse Balance
- **Type:** Code (JavaScript)
- **Code:**
  ```javascript
  const result = JSON.parse($input.first().json.stdout);
  const balance_text = result.result;
  
  // Parse balance from text (adjust based on actual format)
  const match = balance_text.match(/Available:\s*\$?([\d,]+\.\d+)/);
  const available = match ? parseFloat(match[1].replace(/,/g, '')) : 10000;
  
  return { available_balance: available };
  ```

#### 5. Check Risk Capacity
- **Type:** Postgres
- **Query:**
  ```sql
  SELECT check_risk_capacity(
    '{{ $('Get Signal Details').item.json.epic }}',
    {{ $('Get Signal Details').item.json.volatility_atr * 2 * 100 }},
    5.0  -- max portfolio risk %
  ) AS has_capacity;
  ```

#### 6. IF: Has Risk Capacity
- **Type:** IF
- **Condition:** `{{ $json.has_capacity === true }}`

#### 7. Calculate Position Size
- **Type:** Function
- **JavaScript Code:**
  ```javascript
  const signal = $('Get Signal Details').item.json;
  const balance = $('Parse Balance').item.json.available_balance;
  const risk_pct = 1.0;  // 1% risk per trade
  
  const risk_amount = balance * (risk_pct / 100);
  const atr = signal.volatility_atr;
  const stop_distance_pct = (atr * 2) / signal.indicators.current_price;
  
  const position_size_usd = risk_amount / stop_distance_pct;
  const position_size = position_size_usd / signal.indicators.current_price;
  
  // Calculate stop loss and take profit
  const entry_price = signal.indicators.current_price;
  const stop_loss = signal.signal_type === 'BUY' 
    ? entry_price - (atr * 2)
    : entry_price + (atr * 2);
  const take_profit = signal.signal_type === 'BUY'
    ? entry_price + (atr * 4)
    : entry_price - (atr * 4);
  
  return {
    epic: signal.epic,
    direction: signal.signal_type,
    size: position_size.toFixed(4),
    entry_price: entry_price,
    stop_loss: stop_loss.toFixed(4),
    take_profit: take_profit.toFixed(4),
    risk_usd: risk_amount,
    reward_usd: risk_amount * 2,  // 2:1 RR
    risk_reward_ratio: 2.0
  };
  ```

#### 8. AI Review (Optional)
- **Type:** HTTP Request
- **Method:** POST
- **URL:** `{{ $env.AI_BASE_URL }}/chat/completions`
- **Headers:**
  - `Authorization`: `Bearer {{ $env.AI_API_KEY }}`
  - `Content-Type`: `application/json`
- **Body:**
  ```json
  {
    "model": "{{ $env.AI_MODEL }}",
    "messages": [
      {
        "role": "system",
        "content": "You are a trading risk analyst. Review this trade setup and provide a brief sanity check. Is this a reasonable trade? Any red flags?"
      },
      {
        "role": "user",
        "content": "Trade Setup:\nInstrument: {{ $json.epic }}\nDirection: {{ $json.direction }}\nEntry: {{ $json.entry_price }}\nStop Loss: {{ $json.stop_loss }}\nTake Profit: {{ $json.take_profit }}\nRisk: ${{ $json.risk_usd }}\nReward: ${{ $json.reward_usd }}\nRisk/Reward: {{ $json.risk_reward_ratio }}:1"
      }
    ],
    "max_tokens": 200
  }
  ```

#### 9. Parse AI Response
- **Type:** Code
- **Code:**
  ```javascript
  const ai_response = $input.first().json;
  const review_text = ai_response.choices[0].message.content;
  
  // Simple sentiment analysis (approve if no "don't", "risky", "bad" keywords)
  const negative_keywords = ['don\'t', 'risky', 'bad', 'avoid', 'dangerous'];
  const is_negative = negative_keywords.some(kw => review_text.toLowerCase().includes(kw));
  
  return {
    ai_review_status: is_negative ? 'REJECTED' : 'APPROVED',
    ai_review_text: review_text,
    ai_review_score: is_negative ? 0.3 : 0.8
  };
  ```

#### 10. Create Intent Record
- **Type:** Postgres
- **Operation:** Insert
- **Table:** `intents`
- **Columns:**
  - `epic`, `direction`, `size`, `entry_price`, `stop_loss`, `take_profit`
  - `risk_usd`, `reward_usd`, `risk_reward_ratio`
  - `ai_review_status`, `ai_review_text`, `ai_review_score`
  - `approval_status`: `PENDING`
  - `signal_id`: From webhook input
  - `strategy_name`: From signal

#### 11. Generate Approval Token
- **Type:** Code
- **Code:**
  ```javascript
  const crypto = require('crypto');
  const intent = $input.first().json;
  const secret = process.env.APPROVAL_SECRET;
  
  const message = `${intent.epic}:${intent.direction}:${intent.size}`;
  const token = crypto.createHmac('sha256', secret).update(message).digest('hex');
  
  const expires_at = new Date(Date.now() + 5 * 60 * 1000);  // 5 minutes
  
  return {
    approval_token: token,
    approval_token_expires_at: expires_at.toISOString()
  };
  ```

#### 12. Update Intent with Token
- **Type:** Postgres
- **Operation:** Update
- **Where:** `id = {{ $('Create Intent Record').item.json.id }}`
- **Set:**
  - `approval_token`: `{{ $json.approval_token }}`
  - `approval_token_expires_at`: `{{ $json.approval_token_expires_at }}`

#### 13. Check Auto-Approval
- **Type:** IF
- **Condition:**
  ```
  {{ $env.AUTO_TRADING_ENABLED === 'true' && 
     $('Parse AI Response').item.json.ai_review_status === 'APPROVED' }}
  ```

#### 14A. If Auto-Approved: Execute Order
- **Type:** HTTP Request
- **URL:** `http://n8n:5678/webhook/execute-order`
- **Body:** Intent details + approval token

#### 14B. If Manual Approval: Send Notification
- **Type:** Email / Slack / SMS
- **Message:** "Trade approval required: [intent details]"

---

## 🚀 Workflow C: Order Execution & Position Management

**Purpose:** Execute approved orders, monitor positions

### Nodes

#### 1. Webhook or Schedule Trigger
- **Webhook:** `execute-order` (from Workflow B)
- **Schedule:** Every 5 minutes (check pending orders)

#### 2. Get Approved Intents
- **Type:** Postgres
- **Query:**
  ```sql
  SELECT * FROM intents
  WHERE approval_status = 'APPROVED'
    AND executed = false
    AND approval_token_expires_at > NOW()
  ORDER BY created_at ASC
  LIMIT 10;
  ```

#### 3. Loop Intents
- **Type:** Split Out

#### 4. Verify Trading Not Halted
- **Type:** IF
- **Condition:** `{{ $env.TRADING_HALTED !== '1' }}`

#### 5. Place Market Order
- **Type:** Execute Command
- **Command:**
  ```bash
  docker exec trading-mcp-caller python /app/scripts/mcp_call.py place_market_order \
    --args '{
      "epic": "{{ $json.epic }}",
      "direction": "{{ $json.direction }}",
      "size": "{{ $json.size }}",
      "stop_loss": "{{ $json.stop_loss }}",
      "take_profit": "{{ $json.take_profit }}",
      "approval_token": "{{ $json.approval_token }}",
      "confirm_live_trade": "{{ $env.CAP_ENVIRONMENT === "live" ? "yes" : "no" }}"
    }' --output json
  ```

#### 6. Parse Order Result
- **Type:** Code
- **Code:**
  ```javascript
  const result = JSON.parse($input.first().json.stdout);
  const order_text = result.result;
  
  // Parse deal reference from result text
  const match = order_text.match(/Deal Reference:\s*([A-Z0-9]+)/);
  const deal_reference = match ? match[1] : null;
  
  return {
    deal_reference: deal_reference,
    status: deal_reference ? 'SUBMITTED' : 'FAILED',
    response_text: order_text
  };
  ```

#### 7. Create Order Record
- **Type:** Postgres
- **Insert into `orders` table**

#### 8. Mark Intent as Executed
- **Type:** Postgres
- **Update `intents` SET executed = true, executed_at = NOW()**

#### 9. Poll Order Status (Loop)
- **Type:** Wait** (10 seconds)
- **Then Execute Command:**
  ```bash
  docker exec trading-mcp-caller python /app/scripts/mcp_call.py get_order_status \
    --args '{"deal_reference": "{{ $json.deal_reference }}"}' --output json
  ```

#### 10. Check if Filled
- **Type:** IF
- **Condition:** Parse status from response, check if "FILLED"

#### 11. Create Trade Record
- **Type:** Postgres
- **Insert into `trades` table with status 'OPEN'**

---

## 📊 Workflow D: Nightly Evaluation & Bandit Update

**Purpose:** Daily performance review and strategy rebalancing

### Nodes

#### 1. Schedule Trigger
- **Cron:** `0 0 * * *` (daily at midnight UTC)

#### 2. Calculate Daily Performance
- **Type:** Postgres
- **Query:**
  ```sql
  SELECT * FROM v_today_performance;
  ```

#### 3. Update Performance Table
- **Type:** Postgres
- **Insert aggregated metrics into `performance` table**

#### 4. Get All Strategies
- **Type:** Postgres
- **Query:**
  ```sql
  SELECT strategy_name FROM bandit_state WHERE enabled = true;
  ```

#### 5. Loop Strategies
- **Type:** Split Out

#### 6. Calculate Strategy Metrics
- **Type:** Postgres
- **Query:**
  ```sql
  SELECT 
    calculate_win_rate('{{ $json.strategy_name }}', NULL, 20) AS win_rate,
    calculate_profit_factor('{{ $json.strategy_name }}', NULL, 20) AS profit_factor,
    calculate_sharpe_ratio('{{ $json.strategy_name }}', 20) AS sharpe_ratio;
  ```

#### 7. Update Bandit State
- **Type:** Postgres
- **Execute stored procedure `update_bandit_state`**

#### 8. Calculate UCB Scores
- **Type:** Postgres
- **Update UCB scores for all strategies**

#### 9. Generate Performance Report
- **Type:** Code
- **Create summary report text**

#### 10. AI Trade Review (Optional)
- **Type:** HTTP Request to AI**
- **Prompt:** "Analyze today's trades and provide insights"

#### 11. Send Daily Email
- **Type:** Email
- **To:** Admin email
- **Subject:** `Trading Report - {{ $now.format('YYYY-MM-DD') }}`
- **Body:** Performance summary + AI insights

---

## 🔧 Testing Workflows

### Unit Testing

Test each node independently:
1. Use manual execution
2. Provide sample data
3. Verify output format
4. Check error handling

### Integration Testing

1. **Test Data Collection:**
   - Manually trigger Workflow A
   - Check `candles` table for new entries
   - Check `signals` table for generated signals

2. **Test Intent Creation:**
   - Manually trigger with sample signal
   - Verify intent created in DB
   - Verify AI review (if enabled)
   - Check approval token generated

3. **Test Order Execution:**
   - Use demo environment
   - Manually approve an intent
   - Trigger Workflow C
   - Verify order placed via Capital.com
   - Check `orders` and `trades` tables

4. **Test Nightly Evaluation:**
   - Run Workflow D manually
   - Check `performance` table updated
   - Check `bandit_state` updated
   - Verify email sent

### Error Handling

Each workflow should have error workflow configured:
1. Settings → Error Workflow
2. Create generic error handler workflow:
   - Log error to `system_events`
   - Send alert if critical
   - Optionally retry

---

## 📦 Exporting Workflows

Once built, export workflows:
1. Click workflow name → Settings
2. Download → JSON
3. Save to `n8n/workflows/01_data_collection_signals.json`
4. Commit to Git

---

## 🎯 Quick Start Template

A simplified starter workflow is provided in:
`n8n/workflows/00_starter_template.json`

This demonstrates:
- MCP call via Execute Command
- PostgreSQL query
- Error handling
- Basic data flow

Import this first to verify your setup works.

---

## 📚 Additional Resources

- [n8n Documentation](https://docs.n8n.io/)
- [n8n Community](https://community.n8n.io/)
- [Workflow Templates](https://n8n.io/workflows/)
- [Execute Command Node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.executecommand/)
- [PostgreSQL Node](https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.postgres/)

---

**Pro Tip:** Build workflows incrementally. Start with Workflow A (data collection), verify it works, then add Workflow B, etc. Don't try to build all four at once!

