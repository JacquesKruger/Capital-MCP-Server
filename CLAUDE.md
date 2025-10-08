# Capital.com MCP Server - Implementation Notes

## Overview

This document provides technical implementation details for developers working with or extending the Capital.com MCP Server.

## Architecture

### Technology Stack

- **Python 3.11**: Core runtime environment
- **FastMCP**: Model Context Protocol server framework
- **httpx**: HTTP client for API communication (chosen for async support and modern API)
- **python-dotenv**: Optional environment variable management
- **Docker**: Containerization with security-first approach

### Design Philosophy

1. **Security First**: Non-root Docker user (UID 1000), explicit live trading confirmations, credential isolation
2. **Simplicity**: Single-file server implementation, minimal dependencies
3. **GitHub Safety**: Credentials in gitignored directories, example files only in repo
4. **MCP Compliance**: Strict adherence to FastMCP patterns and constraints

## MCP Implementation Details

### Framework: FastMCP

The server uses `mcp.server.fastmcp.FastMCP` with specific constraints:

```python
mcp = FastMCP("Capital.com Trading")
```

**Important Constraints:**
- **NO** `prompt` parameter passed to FastMCP constructor
- **NO** `@mcp.prompt()` decorators (per requirements)
- **ONLY** `@mcp.tool()` decorators for exposed functionality

### Tool Function Requirements

All MCP tool functions follow strict patterns:

1. **Return Type**: Always `-> str` (string only, never complex types)
2. **Parameters**: Only primitive types with empty string defaults:
   ```python
   def tool_name(param1: str = "", param2: str = "") -> str:
   ```
3. **Docstrings**: Single-line only (MCP limitation)
4. **Input Validation**: All inputs `.strip()` checked and validated
5. **Output Format**: Human-readable strings with emoji prefixes for UX:
   - ✅ Success
   - ❌ Error
   - ⚠️  Warning
   - 📊 Data/Info
   - 💹 Market data
   - 💰 Financial info
   - 🔴 Live mode
   - 🟢 Demo mode

### No Complex Types

The implementation avoids `typing` module complex types per requirements:
- NO `Optional[str]`
- NO `Union[str, int]`
- NO `List[str]`
- All parameters are simple: `str`, defaults to `""`

## API Integration

### Capital.com API Architecture

The server integrates with Capital.com's REST API v1:

**Base URLs:**
- Demo: `https://demo-api-capital.backend-capital.com`
- Live: `https://api-capital.backend-capital.com`

### Authentication Flow

Capital.com uses session-based authentication with dual tokens:

1. **Initial Authentication** (`POST /api/v1/session`):
   - Headers: `X-CAP-API-KEY`
   - Body: `identifier`, `password` (JSON)
   - Response Headers: `CST` and `X-SECURITY-TOKEN`

2. **Authenticated Requests**:
   - All subsequent requests include three headers:
     - `X-CAP-API-KEY`: API key
     - `CST`: Session client token
     - `X-SECURITY-TOKEN`: Security token

3. **Session Management**:
   - Sessions typically valid for 6 hours
   - Server maintains `_session_token`, `_session_cst`, `_session_expiry`
   - Automatic re-authentication with 5-minute buffer before expiry

### API Endpoints Used

| Tool | Method | Endpoint | Purpose |
|------|--------|----------|---------|
| authenticate | POST | `/api/v1/session` | Establish session |
| list_instruments | GET | `/api/v1/markets` | List/search instruments |
| get_quote | GET | `/api/v1/markets/{epic}` | Get price quote |
| get_account_balance | GET | `/api/v1/accounts` | Account balance |
| get_positions | GET | `/api/v1/positions` | Open positions |
| place_market_order | POST | `/api/v1/positions` | Create market order |
| place_limit_order | POST | `/api/v1/workingorders` | Create limit order |
| get_order_status | GET | `/api/v1/confirms/{dealReference}` | Order confirmation status |
| cancel_order | DELETE | `/api/v1/positions/{dealId}` | Close position/cancel order |
| poll_prices | GET | `/api/v1/markets/{epic}` (loop) | Price polling |

## Security Implementation

### Credential Management

**Environment Variables (Required):**
```bash
CAP_ENVIRONMENT=demo          # or "live"
CAP_API_KEY=xxx
CAP_IDENTIFIER=xxx
CAP_PASSWORD=xxx
```

**Optional Overrides:**
```bash
CAP_DEMO_API_URL=https://demo-api-capital.backend-capital.com
CAP_LIVE_API_URL=https://api-capital.backend-capital.com
```

**Storage Strategy:**
- Credentials stored in `secrets/` directory (gitignored)
- Example files (`.env.example`) committed to repo
- Actual files (`.env.demo`, `.env.live`) NEVER committed

### Live Trading Safety

Multi-layer protection against accidental live trading:

1. **Environment Variable**: `CAP_ENVIRONMENT=demo` by default
2. **Explicit Confirmation Parameter**: `confirm_live_trade="yes"` required for live orders
3. **Warning Messages**: Clear warnings before execution
4. **Logging**: All live trades logged with 🔴 marker

Example protection flow:
```python
if _is_live_environment() and confirm_live_trade != "yes":
    return "⚠️ LIVE TRADING BLOCKED - requires confirmation"
```

### Docker Security

The Dockerfile implements security best practices:

```dockerfile
# Create non-root user (uid 1000)
RUN groupadd -g 1000 mcpuser && \
    useradd -r -u 1000 -g mcpuser mcpuser

# Switch to non-root user
USER mcpuser
```

Benefits:
- Prevents container breakout escalation
- Limits filesystem access
- Standard UID 1000 matches typical developer user
- Group isolation

## Rate Limiting

### Implementation

Simple sliding window rate limiter:

```python
_rate_limit_window = 60  # seconds
_max_requests_per_window = 100
```

**Algorithm:**
1. Track request count and window start time
2. Reset counter when window expires
3. If limit exceeded, calculate wait time and sleep
4. Log warnings at INFO level

**Per-Request Overhead:**
- ~0.1ms for check (negligible)
- Automatic backoff with `time.sleep()` when limit hit

### Capital.com API Limits

Capital.com enforces their own rate limits (not documented in public API). The server's conservative 100/60s limit should stay well within their bounds.

**Recommended Approach:**
- Monitor Capital.com responses for `429 Too Many Requests`
- Adjust `_max_requests_per_window` if needed
- Consider implementing exponential backoff for 429 responses

## Error Handling

### HTTP Error Categories

1. **Authentication Errors (401, 403)**:
   - Trigger re-authentication attempt
   - Log detailed error
   - Return user-friendly message

2. **Not Found (404)**:
   - Clear error: "Instrument/order not found"
   - Don't retry (permanent failure)

3. **Rate Limit (429)**:
   - Currently handled by client-side rate limiter
   - Future: implement exponential backoff

4. **Server Errors (500, 502, 503)**:
   - Log full error
   - Return sanitized message to user
   - Don't expose internal details

5. **Timeout**:
   - 30-second timeout configured
   - Caught with `httpx.TimeoutException`
   - User-friendly retry message

### Exception Hierarchy

```python
try:
    # API call
except httpx.TimeoutException:
    # Specific timeout handling
except Exception as e:
    # Catch-all with logging
    logger.error(f"Operation error: {str(e)}")
    return f"❌ Error: {str(e)}"
```

## Logging

### Configuration

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
```

**Format Example:**
```
2025-10-08 10:15:32,123 - capital-mcp-server - INFO - Authenticating to Capital.com (demo environment)
```

### Log Levels Used

- **INFO**: Normal operations (auth, orders placed)
- **WARNING**: Rate limits, session expiry warnings
- **ERROR**: API failures, authentication errors

### Log Output

- All logs to `stderr` (per requirements)
- Docker captures to container logs
- MCP clients typically display in their debug/console views

**Viewing Docker logs:**
```bash
docker logs <container_id>
```

## Testing

### Local Testing Without MCP Client

Test tool listing:
```bash
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python capital_server.py
```

Expected output: JSON with all 11 tools listed.

### Integration Testing

**Prerequisites:**
1. Capital.com demo account
2. API credentials
3. Environment variables set

**Test Sequence:**
1. `check_status` - verify configuration
2. `authenticate` - establish session
3. `list_instruments` - test market data
4. `get_quote` - test specific instrument
5. `get_account_balance` - test account access
6. `place_market_order` (demo, small size) - test order execution
7. `get_order_status` - verify order placed
8. `cancel_order` - test order cancellation

### Unit Testing (Future Enhancement)

The codebase is structured for easy unit testing:

```python
# Mock httpx client
def test_authenticate():
    mock_client = Mock()
    mock_client.post.return_value.status_code = 200
    mock_client.post.return_value.headers = {
        "CST": "test-cst",
        "X-SECURITY-TOKEN": "test-token"
    }
    # Test authentication logic
```

## Extension Points

### Adding New Tools

To add a new MCP tool:

1. Define function with constraints:
```python
@mcp.tool()
def new_tool(param: str = "") -> str:
    """Single-line description of tool purpose."""
    param = param.strip()
    
    if not param:
        return "❌ Param required"
    
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    # Implementation
    try:
        _rate_limit()
        headers = _get_headers()
        # Make API call
        # Return user-friendly string
    except Exception as e:
        return f"❌ Error: {str(e)}"
```

2. Follow patterns:
   - Input validation
   - Authentication check
   - Rate limiting
   - Error handling
   - String return with emoji

### Adding Streaming (WebSocket)

Capital.com API supports WebSocket streaming. To add:

1. Add `websockets` to `requirements.txt`
2. Create background task for WebSocket connection
3. Implement price update streaming tool
4. Handle connection lifecycle and reconnection

**Challenge**: MCP tools are synchronous. Streaming requires:
- Background thread/task
- Message queue for updates
- Tool to start/stop streaming
- Tool to fetch queued updates

### Adding Strategy Execution

The server intentionally exposes **primitive operations only**. For automated trading strategies:

1. **External Orchestrator** (Recommended):
   - MCP client (Claude, custom script) calls tools
   - Strategy logic lives outside the MCP server
   - Maintains separation of concerns

2. **Internal Strategy Tool** (Not Recommended):
   - Would require adding complex logic to server
   - Harder to test and modify
   - Less flexible for different strategies

## Performance Considerations

### Memory

- **Session State**: Minimal (3 string variables for tokens)
- **HTTP Client**: Single persistent `httpx.Client` instance
- **No Caching**: Every request hits API (ensures fresh data)

**Optimization Opportunity**: Implement quote caching with TTL for frequently accessed instruments.

### Latency

Typical request latency breakdown:
- Rate limit check: <1ms
- Network round-trip to Capital.com: 50-200ms (depends on geography)
- JSON parsing: 1-5ms
- Total: ~50-210ms per request

**Optimization Opportunity**: Parallel requests for multi-instrument operations.

### Concurrency

Current implementation:
- Single `httpx.Client` (not async)
- Sequential request processing
- No concurrent API calls

**For High Throughput**: 
- Switch to `httpx.AsyncClient`
- Use `asyncio` for concurrent operations
- Requires refactoring all tool functions to `async def`

## Common Pitfalls & Solutions

### Pitfall 1: Hardcoded Credentials

❌ **Don't:**
```python
CAP_API_KEY = "12345abcde"
```

✅ **Do:**
```python
CAP_API_KEY = os.getenv("CAP_API_KEY", "").strip()
```

### Pitfall 2: Complex Return Types

❌ **Don't:**
```python
def get_quote(epic: str) -> dict:
    return {"bid": 1.1000, "offer": 1.1002}
```

✅ **Do:**
```python
def get_quote(epic: str = "") -> str:
    return f"Bid: 1.1000\nOffer: 1.1002"
```

### Pitfall 3: Missing Input Validation

❌ **Don't:**
```python
def place_order(epic: str = "", size: str = "") -> str:
    size_float = float(size)  # Crashes on empty string!
```

✅ **Do:**
```python
def place_order(epic: str = "", size: str = "") -> str:
    size = size.strip()
    if not size:
        return "❌ Size required"
    try:
        size_float = float(size)
    except ValueError:
        return f"❌ Invalid size: {size}"
```

### Pitfall 4: Committing Secrets

❌ **Don't:**
```bash
git add secrets/.env.demo
```

✅ **Do:**
```bash
# Ensure .gitignore covers secrets/
# Only commit example files
git add .env.example
```

## Deployment Considerations

### Docker Production Best Practices

1. **Use Docker Secrets** (Swarm/Kubernetes):
```bash
echo "my_api_key" | docker secret create cap_api_key -
docker service create --secret cap_api_key ...
```

2. **Multi-Stage Builds** (Future Enhancement):
```dockerfile
FROM python:3.11-slim AS builder
# Install dependencies
FROM python:3.11-slim
# Copy only necessary files
```

3. **Health Checks**:
```dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import httpx; httpx.get('http://localhost:8080/health')" || exit 1
```

### Kubernetes Deployment

Example deployment manifest:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: capital-api-creds
type: Opaque
stringData:
  CAP_API_KEY: "xxx"
  CAP_IDENTIFIER: "xxx"
  CAP_PASSWORD: "xxx"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: capital-mcp-server
spec:
  replicas: 1
  selector:
    matchLabels:
      app: capital-mcp
  template:
    metadata:
      labels:
        app: capital-mcp
    spec:
      containers:
      - name: capital-mcp
        image: capital-mcp-server:latest
        envFrom:
        - secretRef:
            name: capital-api-creds
        securityContext:
          runAsUser: 1000
          runAsNonRoot: true
```

### Monitoring & Observability

**Recommended Additions:**

1. **Metrics** (Prometheus):
   - Request count by tool
   - Error rate
   - API latency percentiles
   - Rate limit hits

2. **Distributed Tracing** (OpenTelemetry):
   - Trace API calls end-to-end
   - Identify slow endpoints

3. **Alerting**:
   - Authentication failures
   - Sustained errors
   - Rate limit threshold

## Compliance & Legal

### Terms of Service

**Capital.com API Terms**: Review at https://capital.com/terms-and-policies

Key points:
- Automated trading requires appropriate permissions
- Rate limits must be respected
- Liability for trades rests with account holder

### Financial Regulations

Automated trading may be subject to:
- MiFID II (Europe)
- SEC regulations (USA)
- Local financial authority rules

**Disclaimer**: This software does not provide financial advice. Users are responsible for regulatory compliance.

### Data Privacy

- API credentials are sensitive PII
- Trade data may be subject to GDPR (Europe)
- Implement data retention policies

## Support & Resources

### Capital.com Resources

- API Postman Collection: https://github.com/capital-com-sv/capital-api-postman
- Developer Portal: https://capital.com (login required)
- Support: Contact Capital.com directly for API issues

### MCP Resources

- FastMCP Documentation: https://github.com/jlowin/fastmcp
- MCP Specification: https://modelcontextprotocol.io/
- MCP Community: https://discord.gg/mcp (example)

### Development Tools

- **httpx**: https://www.python-httpx.org/
- **Docker**: https://docs.docker.com/
- **Python Logging**: https://docs.python.org/3/library/logging.html

## Changelog & Roadmap

### v1.0.0 (Current)

- [x] Core MCP server with FastMCP
- [x] All 11 trading tools
- [x] Docker containerization
- [x] Demo/live environment switching
- [x] Live trading safety confirmations
- [x] Rate limiting
- [x] Comprehensive error handling
- [x] Full documentation

### Future Enhancements

- [ ] WebSocket streaming support
- [ ] Async/await for better concurrency
- [ ] Quote caching with TTL
- [ ] Advanced order types (stop-loss, take-profit)
- [ ] Historical data tools
- [ ] Performance metrics and monitoring
- [ ] Unit test suite
- [ ] Multi-account support

## Contributing Guidelines

When contributing to this project:

1. **Code Style**: Follow existing patterns and PEP 8
2. **Testing**: Test in demo mode; include test cases
3. **Documentation**: Update README and CLAUDE.md
4. **Security**: Never commit credentials; follow security best practices
5. **Commits**: Clear, descriptive commit messages
6. **PRs**: One feature/fix per PR; include rationale

## License

See LICENSE file. Key points:
- Open source, free to use and modify
- No warranty or liability
- Attribution appreciated

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-10-08  
**Maintainer**: See GitHub repository



