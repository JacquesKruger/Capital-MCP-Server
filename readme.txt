═══════════════════════════════════════════════════════════════════════════════
CAPITAL.COM MCP SERVER - README
═══════════════════════════════════════════════════════════════════════════════

A Model Context Protocol (MCP) server for secure integration with Capital.com
trading API. Exposes tools for viewing market data, account information, and
executing trades through Claude or other MCP-compatible clients.

═══════════════════════════════════════════════════════════════════════════════
⚠️  CRITICAL WARNINGS - READ BEFORE USE
═══════════════════════════════════════════════════════════════════════════════

1. FINANCIAL RISK:
   • Live trading involves REAL money and REAL financial risk
   • You can lose more than your initial investment
   • Past performance does not guarantee future results
   • Trading leveraged products like CFDs carries high risk

2. LEGAL & REGULATORY:
   • You are responsible for compliance with Capital.com Terms of Service
   • Review Capital.com API Terms: https://capital.com/terms-and-policies
   • Ensure you have appropriate permissions and licenses for automated trading
   • Comply with all applicable financial regulations in your jurisdiction

3. SECURITY:
   • NEVER commit credentials to GitHub or share them publicly
   • Use Docker secrets or secure environment variable management
   • Rotate API keys regularly
   • Monitor account activity for unauthorized access

4. NO WARRANTY:
   • This software is provided "AS IS" without warranty of any kind
   • The authors assume NO liability for financial losses or damages
   • Use at your own risk

═══════════════════════════════════════════════════════════════════════════════
PREREQUISITES
═══════════════════════════════════════════════════════════════════════════════

1. Capital.com Account:
   • Sign up at: https://capital.com
   • Get API credentials from developer portal
   • Demo account recommended for testing

2. System Requirements:
   • Docker (recommended) or Python 3.11+
   • MCP-compatible client (Claude Desktop, Cline, etc.)

3. API Access:
   • API Key (X-CAP-API-KEY)
   • Account Identifier
   • Account Password

   Demo Postman Collection:
   https://github.com/capital-com-sv/capital-api-postman

═══════════════════════════════════════════════════════════════════════════════
INSTALLATION
═══════════════════════════════════════════════════════════════════════════════

METHOD 1: Docker (Recommended for Production)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Build the Docker image
──────────────────────────────
$ cd /path/to/Capital-MCP-Server
$ docker build -t capital-mcp-server .

Step 2: Create secrets directory (if not exists)
─────────────────────────────────────────────────
$ mkdir -p secrets

Step 3: Create environment file
────────────────────────────────
Copy .env.example to secrets/.env.demo:
$ cp .env.example secrets/.env.demo

Edit secrets/.env.demo and add your credentials:
CAP_ENVIRONMENT=demo
CAP_API_KEY=your_actual_demo_api_key
CAP_IDENTIFIER=your_actual_demo_identifier
CAP_PASSWORD=your_actual_demo_password

Step 4: Run the container
──────────────────────────
$ docker run --rm \
  --env-file secrets/.env.demo \
  -i capital-mcp-server

For live trading (⚠️  USE WITH EXTREME CAUTION):
$ docker run --rm \
  --env-file secrets/.env.live \
  -i capital-mcp-server


METHOD 2: Local Python (Development)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Step 1: Install dependencies
─────────────────────────────
$ python3 -m venv venv
$ source venv/bin/activate  # On Windows: venv\Scripts\activate
$ pip install -r requirements.txt

Step 2: Set environment variables
──────────────────────────────────
$ export CAP_ENVIRONMENT=demo
$ export CAP_API_KEY=your_demo_api_key
$ export CAP_IDENTIFIER=your_demo_identifier
$ export CAP_PASSWORD=your_demo_password

Step 3: Run the server
──────────────────────
$ python capital_server.py

═══════════════════════════════════════════════════════════════════════════════
MCP CLIENT CONFIGURATION
═══════════════════════════════════════════════════════════════════════════════

CLAUDE DESKTOP (macOS)
━━━━━━━━━━━━━━━━━━━━━━

Configuration file location:
~/Library/Application Support/Claude/claude_desktop_config.json

Add this to your configuration:

{
  "mcpServers": {
    "capital-trading": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--env-file",
        "/absolute/path/to/secrets/.env.demo",
        "capital-mcp-server"
      ]
    }
  }
}

For local Python installation:

{
  "mcpServers": {
    "capital-trading": {
      "command": "/absolute/path/to/venv/bin/python",
      "args": ["/absolute/path/to/capital_server.py"],
      "env": {
        "CAP_ENVIRONMENT": "demo",
        "CAP_API_KEY": "your_demo_api_key",
        "CAP_IDENTIFIER": "your_demo_identifier",
        "CAP_PASSWORD": "your_demo_password"
      }
    }
  }
}


CLINE (VS Code Extension)
━━━━━━━━━━━━━━━━━━━━━━━

Settings → MCP Servers → Add Server:

Name: Capital.com Trading
Command: docker
Args: ["run", "--rm", "-i", "--env-file", "/path/to/secrets/.env.demo", "capital-mcp-server"]


TESTING LOCALLY
━━━━━━━━━━━━━━

Test the server responds to MCP protocol:

$ echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python capital_server.py

You should see a JSON response listing all available tools.

═══════════════════════════════════════════════════════════════════════════════
AVAILABLE TOOLS
═══════════════════════════════════════════════════════════════════════════════

1. check_status
   ────────────
   Check server status and environment configuration.
   
   Example:
   "Use the check_status tool"
   
   Output: Shows environment (demo/live), credentials status, session status


2. authenticate
   ────────────
   Authenticate to Capital.com API and establish a session.
   
   Example:
   "Authenticate to Capital.com"
   
   Output: Success/failure message with session details


3. list_instruments
   ────────────────
   Search and list available trading instruments.
   
   Parameters:
   • search_term: Optional search string (e.g., "EUR", "Gold", "US500")
   • limit: Maximum results to return (default: 50, max: 1000)
   
   Examples:
   "List available instruments"
   "Search for EUR currency pairs with limit 10"
   "Find instruments matching 'Gold'"
   
   Output: List of instruments with epic, name, type, and status


4. get_quote
   ─────────
   Get current price quote for a specific instrument.
   
   Parameters:
   • epic: Instrument epic code (e.g., "EURUSD", "US500", "GOLD")
   
   Examples:
   "Get quote for EURUSD"
   "What's the current price of US500?"
   
   Output: Bid, offer, status, change%, and update time


5. get_account_balance
   ───────────────────
   Get current account balance and available funds.
   
   Example:
   "Show my account balance"
   
   Output: Balance, available funds, deposit, and P&L


6. get_positions
   ─────────────
   Get all current open positions.
   
   Example:
   "Show my open positions"
   
   Output: List of positions with deal ID, instrument, direction, size, and P&L


7. place_market_order
   ──────────────────
   Place a market order (executes immediately at current market price).
   
   Parameters:
   • epic: Instrument epic (e.g., "EURUSD")
   • direction: "BUY" or "SELL"
   • size: Position size (e.g., "1", "0.5")
   • confirm_live_trade: Must be "yes" for live environment (safety check)
   
   Examples (Demo):
   "Place a market order to BUY 1 unit of EURUSD"
   "Sell 0.5 US500 at market"
   
   Examples (Live - requires confirmation):
   "Place a market order to BUY 1 EURUSD with confirm_live_trade yes"
   
   Output: Deal reference for tracking order status
   
   ⚠️  LIVE MODE: Requires confirm_live_trade="yes" parameter to execute


8. place_limit_order
   ─────────────────
   Place a limit order (executes when market reaches specified price).
   
   Parameters:
   • epic: Instrument epic (e.g., "EURUSD")
   • direction: "BUY" or "SELL"
   • size: Position size (e.g., "1", "0.5")
   • limit_level: Price level to execute at (e.g., "1.1000")
   • confirm_live_trade: Must be "yes" for live environment (safety check)
   
   Examples (Demo):
   "Place a limit order to BUY 1 EURUSD at 1.1000"
   "Sell 0.5 US500 at limit level 4500.0"
   
   Examples (Live - requires confirmation):
   "Place limit order to BUY 1 EURUSD at 1.1000 with confirm_live_trade yes"
   
   Output: Deal reference for tracking order status
   
   ⚠️  LIVE MODE: Requires confirm_live_trade="yes" parameter to execute


9. get_order_status
   ────────────────
   Get the status of an order by deal reference.
   
   Parameters:
   • deal_reference: Deal reference from place_market_order or place_limit_order
   
   Example:
   "Check order status for deal reference ABC123XYZ"
   
   Output: Status, deal ID, epic, direction, size, level, P&L


10. cancel_order
    ───────────
    Cancel an open position or working order.
    
    Parameters:
    • deal_id: Deal ID from get_positions or get_order_status
    
    Example:
    "Cancel order with deal ID 12345"
    
    Output: Confirmation with deal reference


11. poll_prices
    ───────────
    Poll prices for multiple instruments at regular intervals.
    (Alternative to websocket streaming)
    
    Parameters:
    • epic_list: Comma-separated list of epics (e.g., "EURUSD,US500,GOLD")
    • interval_seconds: Seconds between polls (default: 5, range: 1-60)
    • iterations: Number of times to poll (default: 10, max: 100)
    
    Example:
    "Poll prices for EURUSD,US500 every 10 seconds for 5 iterations"
    
    Output: Price updates for each iteration
    
    Note: Max 10 instruments per poll request

═══════════════════════════════════════════════════════════════════════════════
USAGE EXAMPLES
═══════════════════════════════════════════════════════════════════════════════

SCENARIO 1: Check Status and View Market Data
──────────────────────────────────────────────

You: "Check the Capital.com server status"
Assistant: [Uses check_status tool]

You: "Search for EUR currency pairs"
Assistant: [Uses list_instruments with search_term="EUR"]

You: "Get the current quote for EURUSD"
Assistant: [Uses get_quote with epic="EURUSD"]


SCENARIO 2: View Account Information
─────────────────────────────────────

You: "Show my account balance"
Assistant: [Uses get_account_balance]

You: "What positions do I have open?"
Assistant: [Uses get_positions]


SCENARIO 3: Place and Monitor an Order (Demo Mode)
───────────────────────────────────────────────────

You: "Place a market order to buy 1 unit of EURUSD"
Assistant: [Uses place_market_order - no confirmation needed in demo]
Result: Deal reference ABC123

You: "Check the status of deal reference ABC123"
Assistant: [Uses get_order_status with deal_reference="ABC123"]


SCENARIO 4: Live Trading (⚠️  Real Money)
─────────────────────────────────────────

You: "Place a market order to buy 0.5 US500"
Assistant: [Uses place_market_order]
Result: ⚠️ LIVE TRADING BLOCKED - requires confirmation

You: "Place a market order to buy 0.5 US500 with confirm_live_trade yes"
Assistant: [Executes live order with confirmation]
Result: ✅ Order placed with real money

═══════════════════════════════════════════════════════════════════════════════
ENVIRONMENT VARIABLES
═══════════════════════════════════════════════════════════════════════════════

Required:
─────────
CAP_ENVIRONMENT     "demo" or "live" (default: demo)
CAP_API_KEY         Your Capital.com API key
CAP_IDENTIFIER      Your account identifier
CAP_PASSWORD        Your account password

Optional:
─────────
CAP_DEMO_API_URL    Override demo API URL
                    (default: https://demo-api-capital.backend-capital.com)

CAP_LIVE_API_URL    Override live API URL
                    (default: https://api-capital.backend-capital.com)

═══════════════════════════════════════════════════════════════════════════════
SECURITY BEST PRACTICES
═══════════════════════════════════════════════════════════════════════════════

1. Credential Management:
   • Store credentials in secrets/ directory (gitignored)
   • Use separate .env.demo and .env.live files
   • NEVER commit credentials to version control
   • Use Docker secrets in production environments

2. Access Control:
   • Limit file permissions: chmod 600 secrets/.env.*
   • Use read-only API keys if available
   • Implement IP whitelist on Capital.com account settings

3. Monitoring:
   • Regularly review account activity on Capital.com
   • Check server logs for suspicious activity
   • Set up alerts for large trades or losses

4. Development vs Production:
   • Always test in DEMO mode first
   • Use minimal position sizes in live testing
   • Implement additional confirmation layers for production

5. Key Rotation:
   • Rotate API keys periodically (e.g., every 90 days)
   • Immediately rotate if credentials are compromised
   • Update .env files and restart containers after rotation

═══════════════════════════════════════════════════════════════════════════════
RATE LIMITING
═══════════════════════════════════════════════════════════════════════════════

The server implements automatic rate limiting:
• Maximum 100 requests per 60-second window
• Automatic backoff when limit is reached
• Logged warnings when rate limit is approached

Capital.com may enforce additional API rate limits. Monitor your account for
rate limit notifications and adjust usage accordingly.

═══════════════════════════════════════════════════════════════════════════════
TROUBLESHOOTING
═══════════════════════════════════════════════════════════════════════════════

Problem: "Missing credentials" error
Solution: Ensure all environment variables are set correctly:
          - CAP_API_KEY
          - CAP_IDENTIFIER
          - CAP_PASSWORD

Problem: "Authentication failed" error
Solution: 1. Verify credentials are correct
          2. Check if using correct environment (demo vs live)
          3. Ensure API key is active on Capital.com portal
          4. Check network connectivity

Problem: "Rate limit reached" warning
Solution: The server automatically handles rate limiting with backoff.
          Wait for the window to reset, or reduce request frequency.

Problem: Docker container won't start
Solution: 1. Check Docker daemon is running
          2. Verify .env file path is correct (absolute path required)
          3. Check .env file has correct format (no quotes around values)
          4. Rebuild image: docker build -t capital-mcp-server .

Problem: MCP client can't connect
Solution: 1. Verify MCP client configuration (absolute paths required)
          2. Test server directly: echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python capital_server.py
          3. Check client logs for connection errors
          4. Restart MCP client application

Problem: "Live trading blocked" when trying to trade
Solution: This is a safety feature. For live trading, you must:
          1. Set CAP_ENVIRONMENT=live in your .env file
          2. Include confirm_live_trade="yes" parameter in order tools
          ⚠️  Only proceed if you accept financial risk

═══════════════════════════════════════════════════════════════════════════════
API REFERENCE
═══════════════════════════════════════════════════════════════════════════════

Capital.com Public API Documentation:
https://github.com/capital-com-sv/capital-api-postman

Postman Collection:
https://github.com/capital-com-sv/capital-api-postman

Capital.com Terms & Conditions:
https://capital.com/terms-and-policies

Model Context Protocol (MCP) Specification:
https://modelcontextprotocol.io/

═══════════════════════════════════════════════════════════════════════════════
CONTRIBUTING
═══════════════════════════════════════════════════════════════════════════════

This project is open source. Contributions are welcome via GitHub pull requests.

Repository: https://github.com/yourusername/Capital-MCP-Server

When contributing:
• Follow existing code style and conventions
• Add tests for new features
• Update documentation
• Never commit credentials or secrets
• Test in demo mode before submitting PRs

═══════════════════════════════════════════════════════════════════════════════
LICENSE
═══════════════════════════════════════════════════════════════════════════════

See LICENSE file for full license terms.

THIS SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.
The authors assume NO liability for financial losses or damages resulting from
use of this software.

═══════════════════════════════════════════════════════════════════════════════
SUPPORT
═══════════════════════════════════════════════════════════════════════════════

• GitHub Issues: Report bugs and feature requests
• Capital.com Support: For API access and account issues
• MCP Community: For MCP protocol questions

═══════════════════════════════════════════════════════════════════════════════
VERSION HISTORY
═══════════════════════════════════════════════════════════════════════════════

v1.0.0 (2025-10-08)
• Initial release
• Market data tools (instruments, quotes, polling)
• Account tools (balance, positions)
• Trading tools (market orders, limit orders, cancel, status)
• Docker containerization
• Demo/live environment switching
• Live trading safety confirmations
• Rate limiting and error handling

═══════════════════════════════════════════════════════════════════════════════
DISCLAIMER
═══════════════════════════════════════════════════════════════════════════════

Trading involves significant risk. CFDs are complex instruments and come with
a high risk of losing money rapidly due to leverage. You should consider whether
you understand how CFDs work and whether you can afford to take the high risk of
losing your money.

This software is a third-party integration tool and is not affiliated with,
endorsed by, or supported by Capital.com. Use at your own risk.

Always:
• Start with demo mode
• Understand the instruments you're trading
• Never trade with money you cannot afford to lose
• Seek independent financial advice if needed
• Comply with all applicable laws and regulations

═══════════════════════════════════════════════════════════════════════════════



