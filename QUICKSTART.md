# Quick Start Guide - Capital.com MCP Server

**Get up and running in 5 minutes!** ⚡

---

## Step 1: Install (30 seconds)

Copy and paste this into your terminal:

```bash
git clone https://github.com/JacquesKruger/Capital-MCP-Server.git && cd Capital-MCP-Server && ./install.sh
```

The installer does everything automatically! ✨

---

## Step 2: Get Capital.com Credentials (2 minutes)

1. Go to https://capital.com
2. Sign up for a **demo account** (it's free!)
3. Navigate to: **Settings → API Access**
4. Generate an API key
5. Copy these three values:
   - API Key
   - Identifier
   - Password

---

## Step 3: Add Your Credentials (1 minute)

Edit the credentials file:

```bash
nano secrets/.env.demo
```

Replace the placeholders:

```bash
CAP_ENVIRONMENT=demo
CAP_API_KEY=paste_your_api_key_here
CAP_IDENTIFIER=paste_your_identifier_here
CAP_PASSWORD=paste_your_password_here
```

Save and exit (Ctrl+X, then Y, then Enter)

---

## Step 4: Configure Your MCP Client (1 minute)

### For Claude Desktop

Edit this file:
```bash
nano ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Add this configuration (the installer showed you the exact path):

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
        "/absolute/path/to/Capital-MCP-Server/secrets/.env.demo",
        "capital-mcp-server"
      ]
    }
  }
}
```

**Replace `/absolute/path/to/` with your actual path!**

### For Cursor

Edit this file:
```bash
nano ~/.cursor/mcp.json
```

Add:

```json
{
  "mcpServers": {
    "capital-trading": {
      "command": "/bin/bash",
      "args": ["/absolute/path/to/Capital-MCP-Server/run-mcp-server.sh"],
      "env": {"CAP_ENVIRONMENT": "demo"}
    }
  }
}
```

---

## Step 5: Restart & Test (30 seconds)

1. **Quit your MCP client completely** (Cmd+Q on Mac)
2. **Reopen it**
3. Try these commands:

```
"Check the Capital.com server status"
"Search for EUR currency pairs"
"Get a quote for EURUSD"
"Show my account balance"
```

---

## 🎉 You're Done!

That's it! You now have a fully functional trading integration.

---

## What Can You Do Now?

### View Market Data
```
"Search for Gold instruments"
"Get the current price of US500"
"Poll EURUSD,GBPUSD,USDJPY prices every 5 seconds"
```

### Check Your Account
```
"What's my account balance?"
"Show my open positions"
```

### Practice Trading (Demo Mode - No Real Money!)
```
"Buy 100 units of EURGBP"
"Place a buy order for 50 EURUSD with stop-loss at 1.0950"
"Close position with deal ID 12345"
```

---

## Safety Reminders

✅ You're in **DEMO mode** - All trades are simulated  
✅ No real money is at risk  
✅ Perfect for learning and testing  

⚠️ **To use live trading:**
1. Change `CAP_ENVIRONMENT` to `live` in your config
2. Use live Capital.com credentials
3. Orders require `confirm_live_trade="yes"` parameter
4. **Only use live mode when you're ready and understand the risks!**

---

## Need Help?

- **Full Documentation**: See [readme.txt](readme.txt)
- **Technical Details**: See [CLAUDE.md](CLAUDE.md)
- **Issues**: https://github.com/JacquesKruger/Capital-MCP-Server/issues

---

## Pro Tips

1. **Always test in demo first** - It's free and safe
2. **Use stop-losses** - Protect your trades automatically
3. **Start small** - Practice with small position sizes
4. **Read the docs** - `readme.txt` has detailed examples

---

**Happy Trading!** 📈

*Remember: This is demo mode - perfect for learning without risk!*

