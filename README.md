# Capital.com MCP Server

A production-ready [Model Context Protocol](https://modelcontextprotocol.io) (MCP) server for integrating with the Capital.com trading API. Trade currencies, indices, commodities, and more through Claude Desktop, Cursor, or any MCP-compatible client.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)

---

## ⚠️ Important Disclaimer

**Trading involves significant financial risk.** This software is provided "AS IS" without warranty. You are responsible for:
- Understanding Capital.com's Terms of Service
- Complying with financial regulations in your jurisdiction  
- Any losses incurred through trading
- Proper risk management of your trading account

**Always start with Capital.com's demo environment before using live trading.**

---

## 🎯 Features

### Market Data & Analysis
- 📊 **Search instruments** - Find trading pairs, indices, commodities
- 💹 **Real-time quotes** - Get current bid/offer prices
- 📈 **Price polling** - Monitor multiple instruments simultaneously

### Account Management
- 💰 **Account balance** - View available funds and P&L
- 📋 **Open positions** - Monitor active trades
- 🔍 **Order status** - Track order execution

### Trading Operations
- 🚀 **Market orders** - Execute at current market price
- 🎯 **Limit orders** - Execute at specific price levels
- 🛡️ **Risk management** - Stop-loss, take-profit, trailing stops
- ❌ **Cancel orders** - Close positions or cancel pending orders

### Safety Features
- 🟢 **Demo mode** by default - Practice without risk
- 🔐 **Live trading protection** - Requires explicit confirmation
- ⏱️ **Rate limiting** - Automatic backoff (100 requests/60s)
- 🔒 **Credential security** - Environment-based, never hardcoded

---

## 🚀 Quick Start

### Prerequisites

- **Capital.com Account** - Get API credentials from [Capital.com Developer Portal](https://capital.com)
- **Docker** (recommended) or Python 3.11+
- **MCP-compatible client** - Claude Desktop, Cursor, or similar

### Installation

#### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/Capital-MCP-Server.git
cd Capital-MCP-Server

# Build the Docker image
docker build -t capital-mcp-server .

# Create credentials file
cp .env.example secrets/.env.demo
nano secrets/.env.demo  # Add your Capital.com credentials

# Test the server
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}' | \
  docker run --rm -i --env-file secrets/.env.demo capital-mcp-server
```

#### Option 2: Local Python

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export CAP_ENVIRONMENT=demo
export CAP_API_KEY=your_demo_api_key
export CAP_IDENTIFIER=your_demo_identifier
export CAP_PASSWORD=your_demo_password

# Run the server
python capital_server.py
```

---

## 🔧 Configuration

### For Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

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
        "/absolute/path/to/secrets/.env.demo",
        "capital-mcp-server"
      ]
    }
  }
}
```

### For Cursor

Edit `~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "capital-trading": {
      "command": "/bin/bash",
      "args": [
        "/absolute/path/to/Capital-MCP-Server/run-mcp-server.sh"
      ],
      "env": {
        "CAP_ENVIRONMENT": "demo"
      }
    }
  }
}
```

### For Docker Desktop MCP Toolkit

The server is compatible with Docker Desktop's MCP Toolkit. See [DOCKER_DESKTOP_SETUP.md](DOCKER_DESKTOP_SETUP.md) for detailed instructions.

---

## 📖 Available Tools

| Tool | Description | Parameters |
|------|-------------|------------|
| `check_status` | Server status and environment info | None |
| `authenticate` | Manual authentication (auto-handled) | None |
| `list_instruments` | Search trading instruments | `search_term`, `limit` |
| `get_quote` | Get current price quote | `epic` |
| `get_account_balance` | Account balance and funds | None |
| `get_positions` | View open positions | None |
| `place_market_order` | Execute market order | `epic`, `direction`, `size`, `stop_loss`*, `take_profit`*, `trailing_stop`*, `confirm_live_trade`** |
| `place_limit_order` | Place limit order | `epic`, `direction`, `size`, `limit_level`, `stop_loss`*, `take_profit`*, `trailing_stop`*, `confirm_live_trade`** |
| `get_order_status` | Check order confirmation | `deal_reference` |
| `cancel_order` | Close position/cancel order | `deal_id` |
| `poll_prices` | Poll multiple instruments | `epic_list`, `interval_seconds`, `iterations` |

*Optional risk management parameters  
**Required for live trading

---

## 💡 Usage Examples

### Market Data
```
# In Claude/Cursor, use natural language:
"Search for EUR currency pairs"
"Get the current quote for EURUSD"
"Poll prices for EURUSD,US500,GOLD every 5 seconds"
```

### Trading (Demo Mode)
```
"Place a buy order for 100 units of EURGBP"
"Buy 50 EURUSD with stop-loss at 1.0950 and take-profit at 1.1050"
"Show my open positions"
"Close position with deal ID 12345"
```

### Risk Management
```python
# Market order with protection
place_market_order(
    epic="EURGBP",
    direction="BUY",
    size="100",
    stop_loss="0.86364",      # 30 pips protection
    take_profit="0.87164"     # 50 pips target
)
```

---

## 🔐 Security

### Credential Management

**✅ DO:**
- Store credentials in `secrets/.env.demo` or `secrets/.env.live`
- Use `chmod 600` on credential files
- Rotate API keys regularly
- Use demo mode for testing

**❌ DON'T:**
- Commit credentials to Git
- Share API keys publicly
- Use live credentials in development
- Skip the `confirm_live_trade` check

### Live Trading Safety

Live trading requires explicit confirmation:
```python
place_market_order(
    epic="EURUSD",
    direction="BUY",
    size="1",
    confirm_live_trade="yes"  # Required for live mode
)
```

---

## 📚 Documentation

- **[readme.txt](readme.txt)** - Complete user guide with examples
- **[CLAUDE.md](CLAUDE.md)** - Technical implementation details
- **[DOCKER_DESKTOP_SETUP.md](DOCKER_DESKTOP_SETUP.md)** - Docker Desktop integration
- **[RISK_MANAGEMENT_ENHANCEMENT.md](RISK_MANAGEMENT_ENHANCEMENT.md)** - Stop-loss/take-profit guide
- **[SERVER_STATUS.md](SERVER_STATUS.md)** - Current server status

---

## 🛠️ Development

### Project Structure

```
Capital-MCP-Server/
├── capital_server.py          # Main MCP server
├── Dockerfile                 # Docker container config
├── requirements.txt           # Python dependencies
├── run-mcp-server.sh         # Server launcher script
├── secrets/                   # Credentials (gitignored)
│   ├── .env.demo             # Demo credentials
│   └── .env.live             # Live credentials
├── .gitignore                # Git exclusions
└── README.md                 # This file
```

### Running Tests

```bash
# Test MCP protocol
./test_server.py

# Test Docker container
./test_mcp.sh

# Manual test
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python capital_server.py
```

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Test in demo mode
4. Submit a pull request

**Never commit:**
- Credentials or API keys
- Trading strategies
- Personal account information

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## ⚠️ Regulatory Compliance

Users are responsible for:
- Compliance with Capital.com Terms of Service
- Adherence to financial regulations in their jurisdiction
- Proper authorization for automated trading
- Risk management and position sizing

**CFD Trading Risk Warning:** CFDs are complex instruments and come with a high risk of losing money rapidly due to leverage. Ensure you understand how CFDs work and whether you can afford the high risk of losing money.

---

## 🔗 Resources

- **Capital.com API**: https://github.com/capital-com-sv/capital-api-postman
- **MCP Protocol**: https://modelcontextprotocol.io/
- **FastMCP Framework**: https://github.com/jlowin/fastmcp
- **Risk Management Guide**: See [RISK_MANAGEMENT_ENHANCEMENT.md](RISK_MANAGEMENT_ENHANCEMENT.md)

---

## 📞 Support

- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Capital.com API**: Contact Capital.com support for API-related questions
- **MCP Protocol**: See MCP community resources

---

## 🙏 Acknowledgments

- Capital.com for providing the trading API
- The MCP community for protocol development
- FastMCP framework by Jeff Lowin

---

**Built with ❤️ for the MCP community**

*Remember: Past performance is not indicative of future results. Trade responsibly.*
