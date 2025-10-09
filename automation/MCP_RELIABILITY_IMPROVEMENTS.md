# MCP Server Reliability Improvements

## Problem
The MCP server would frequently hang or timeout after making many consecutive API calls to Capital.com, requiring manual restarts.

## Solution Implemented
Added automatic timeout handling, health checking, and self-healing capabilities to the MCP server wrapper.

### New Features

#### 1. **Call Timeouts** (30 seconds)
- Each MCP tool call now has a 30-second timeout
- If a call doesn't respond within 30 seconds, it's automatically terminated
- Prevents indefinite hangs

#### 2. **Health Checking**
The server monitors its own health using three metrics:
- **Process alive**: Checks if the subprocess is still running
- **Idle time**: Restarts if idle for > 5 minutes (prevents stale connections)
- **Failed calls**: Tracks consecutive failures (restarts after 3 failures)

#### 3. **Automatic Restart & Retry**
When a call fails or server becomes unhealthy:
1. Logs the error
2. Stops the old MCP process
3. Waits 2 seconds
4. Starts a fresh MCP process
5. Re-initializes the protocol
6. Retries the failed call (once)

#### 4. **Activity Tracking**
- Tracks last successful API call timestamp
- Updates on every successful call
- Used to detect stale connections

### Configuration Parameters

```python
self.max_failed_calls = 3      # Restart after 3 consecutive failures
self.call_timeout = 30          # 30 second timeout per API call  
self.max_idle_time = 300        # 5 minutes max idle before restart
```

These can be adjusted in `mcp_server_wrapper.py` if needed.

### Code Changes

**File**: `automation/scripts/mcp_server_wrapper.py`

**Added Methods:**
- `is_healthy()` - Health check logic
- `restart()` - Clean restart procedure  
- Enhanced `call_tool()` - Now includes timeout, retry, and health check

**Added Properties:**
- `last_activity` - Timestamp of last successful call
- `failed_calls` - Counter for consecutive failures
- `call_timeout` - Timeout per call
- `max_idle_time` - Max idle time before restart
- `max_failed_calls` - Max failures before restart

### Benefits

✅ **No more manual restarts** - Server self-heals automatically  
✅ **Graceful degradation** - Retries failed calls once  
✅ **Fresh connections** - Restarts on idle/stale connections  
✅ **Better logging** - Clear visibility into health issues  
✅ **LLM-friendly** - Maintains MCP protocol for future integrations  

### Testing

Test the improvements:

```bash
# The server should automatically recover from timeouts
curl http://localhost:8000/mcp/get_account_balance

# Even if it hangs, the next call will auto-restart
curl http://localhost:8000/mcp/get_positions

# Check logs to see auto-restart behavior
docker logs trading-mcp-caller --tail 50
```

### Monitoring

Watch for these log messages:
- `Server unhealthy, attempting restart...` - Auto-restart triggered
- `Restarting MCP server...` - Restart in progress
- `MCP server initialized successfully` - Restart complete
- `Timeout waiting for response` - Call timed out (will retry)
- `Retrying {tool} after restart...` - Retry attempt

### Workflow Integration

The workflows will now be more reliable:
1. **Data & Signals** - Won't hang on batch quote calls
2. **Risk & Order Routing** - Account balance/positions won't timeout
3. **Trade Management** - Position monitoring won't stall
4. **Telegram** - All workflows complete successfully

### Future Enhancements

If issues persist, consider:
1. Reduce `call_timeout` to 15 seconds for faster recovery
2. Decrease `max_idle_time` to 120 seconds for more frequent refreshes
3. Add exponential backoff for retries
4. Implement connection pooling
5. Cache frequently-requested data (quotes, balances)

---

**Status**: ✅ **DEPLOYED**

The MCP server will now automatically recover from timeouts and connection issues, providing a much more reliable experience for your trading workflows.


