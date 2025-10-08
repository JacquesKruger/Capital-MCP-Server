# Using Capital.com MCP Server with MCP Inspector

## Quick Start with MCP Inspector

The MCP Inspector is a web-based tool that lets you interactively test your MCP server before integrating it with Claude Desktop or other clients.

---

## Option 1: Test with MCP Inspector (Recommended)

### Step 1: Install MCP Inspector (if not already installed)

```bash
npx @modelcontextprotocol/inspector docker run --rm -i --env-file /absolute/path/to/secrets/.env.demo capital-mcp-server
```

Or if you have it installed globally:

```bash
mcp-inspector docker run --rm -i --env-file /absolute/path/to/secrets/.env.demo capital-mcp-server
```

**Replace `/absolute/path/to/` with your actual project path!**

For this project, use:
```bash
npx @modelcontextprotocol/inspector docker run --rm -i --env-file "/Users/jacqueskruger/Documents/Code Projects/Capital-MCP-Server/secrets/.env.demo" capital-mcp-server
```

### Step 2: Open the Inspector

The MCP Inspector will:
1. Start a web server (usually at http://localhost:5173)
2. Connect to your Capital.com MCP server
3. Open your browser automatically

### Step 3: Test Your Tools

In the MCP Inspector interface, you can:

1. **View All Tools** - See all 11 available tools
2. **Test Tools** - Click any tool to see its parameters
3. **Call Tools** - Fill in parameters and execute
4. **See Results** - View responses in real-time

### Example Tests to Run:

#### Test 1: Check Status
- Tool: `check_status`
- Parameters: None
- Expected: Server status with environment info

#### Test 2: List Instruments
- Tool: `list_instruments`
- Parameters:
  - `search_term`: "EUR"
  - `limit`: "10"
- Expected: List of EUR currency pairs

#### Test 3: Get Quote
- Tool: `get_quote`
- Parameters:
  - `epic`: "EURUSD"
- Expected: Current bid/offer prices for EUR/USD

---

## Option 2: Direct Docker Testing (Command Line)

### Test Without Credentials (Status Check)

```bash
docker run --rm -i capital-mcp-server << 'EOF'
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"check_status","arguments":{}},"id":2}
EOF
```

### Test With Credentials (List Instruments)

First, add your actual Capital.com demo credentials to `secrets/.env.demo`:

```bash
nano secrets/.env.demo
# Edit CAP_API_KEY, CAP_IDENTIFIER, CAP_PASSWORD
```

Then test:

```bash
docker run --rm -i --env-file secrets/.env.demo capital-mcp-server << 'EOF'
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"authenticate","arguments":{}},"id":2}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_instruments","arguments":{"search_term":"EUR","limit":"5"}},"id":3}
EOF
```

---

## Option 3: Local Python Testing (Without Docker)

If you prefer to test without Docker:

```bash
# Activate virtual environment
source venv/bin/activate

# Export credentials
export CAP_ENVIRONMENT=demo
export CAP_API_KEY=your_demo_api_key
export CAP_IDENTIFIER=your_demo_identifier
export CAP_PASSWORD=your_demo_password

# Run server
python capital_server.py << 'EOF'
{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"check_status","arguments":{}},"id":2}
EOF
```

---

## Troubleshooting MCP Inspector

### Inspector won't connect
- Ensure Docker is running
- Check that the env file path is absolute (no `~/` or relative paths)
- Verify credentials in `secrets/.env.demo`

### "Authentication failed" error
- Verify your Capital.com credentials are correct
- Ensure you're using demo credentials (not live)
- Check that you have API access enabled in Capital.com settings

### Tools not showing up
- Wait a few seconds for initialization
- Refresh the browser
- Check Docker logs: `docker ps` then `docker logs <container_id>`

---

## Next Steps After Testing

Once you've verified everything works in MCP Inspector:

### 1. Configure Claude Desktop

Edit: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "capital-trading": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--env-file",
        "/Users/jacqueskruger/Documents/Code Projects/Capital-MCP-Server/secrets/.env.demo",
        "capital-mcp-server"
      ]
    }
  }
}
```

### 2. Restart Claude Desktop

Quit completely (Cmd+Q) and restart.

### 3. Use in Claude

You can now use natural language:

> "Check the Capital.com server status"
> "Search for EUR currency pairs"  
> "Get a quote for EURUSD"
> "Show my account balance"

---

## Security Reminders

- ✅ Start with DEMO mode (default)
- ✅ Never commit `secrets/.env.demo` or `.env.live` to git
- ⚠️  Only switch to live mode when ready for real trading
- ⚠️  Live trading requires `confirm_live_trade="yes"` parameter

---

## Getting Capital.com Credentials

1. Sign up at https://capital.com
2. Go to Settings → API Access
3. Generate API Key
4. Copy:
   - API Key (X-CAP-API-KEY header)
   - Identifier
   - Password
5. Paste into `secrets/.env.demo`

---

## Tools Available

1. `check_status` - Server and environment status
2. `authenticate` - Manual auth (auto-handled internally)
3. `list_instruments` - Search trading instruments
4. `get_quote` - Current price quote
5. `get_account_balance` - Account balance
6. `get_positions` - Open positions
7. `place_market_order` - Market order (immediate execution)
8. `place_limit_order` - Limit order (at specific price)
9. `get_order_status` - Check order confirmation
10. `cancel_order` - Cancel/close position
11. `poll_prices` - Poll multiple instruments

---

Happy testing! 🚀



