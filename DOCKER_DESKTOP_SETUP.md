# Adding Capital.com MCP Server to Docker Desktop MCP Toolkit

## Step-by-Step Guide

### Method 1: Using the Docker Desktop MCP Toolkit UI (Recommended)

1. **Open Docker Desktop** and go to the **MCP Toolkit** tab (you should already be there)

2. **Click the blue "Add a server" button** in the top right

3. **Fill in the Server Configuration Form:**

   **Server Name:**
   ```
   Capital.com Trading
   ```

   **Description:** (if there's a field for it)
   ```
   MCP server for Capital.com trading API - market data, positions, and trade execution
   ```

   **Command/Script Path:**
   ```
   /Users/jacqueskruger/Documents/Code Projects/Capital-MCP-Server/run-mcp-server.sh
   ```

   **OR if it asks for Docker command:**
   
   - **Type:** `Docker Command`
   - **Image:** `capital-mcp-server`
   - **Environment Variables** (add each):
     - `CAP_ENVIRONMENT` = `demo`
     - `CAP_API_KEY` = `your_demo_api_key_here`
     - `CAP_IDENTIFIER` = `your_demo_identifier_here`
     - `CAP_PASSWORD` = `your_demo_password_here`

4. **Click "Save" or "Add Server"**

5. **Your server should now appear** in the "My servers" list

6. **Click on it to connect** and test the 11 available tools!

---

### Method 2: If UI Requires JSON Configuration

If Docker Desktop allows importing a JSON config, use this:

**File Location:** Create a file anywhere with this content:

```json
{
  "name": "capital-trading",
  "displayName": "Capital.com Trading",
  "description": "MCP server for Capital.com trading API",
  "command": "/Users/jacqueskruger/Documents/Code Projects/Capital-MCP-Server/run-mcp-server.sh",
  "args": []
}
```

Then import it through the UI.

---

### Method 3: Direct Docker Command (Alternative)

If the form asks for a complete command:

**Command:**
```
docker
```

**Args** (add each as separate line):
```
run
--rm
-i
--env-file
/Users/jacqueskruger/Documents/Code Projects/Capital-MCP-Server/secrets/.env.demo
capital-mcp-server
```

---

## Before Testing: Add Your Credentials!

**IMPORTANT:** Edit your credentials file:

```bash
nano /Users/jacqueskruger/Documents/Code\ Projects/Capital-MCP-Server/secrets/.env.demo
```

Replace placeholders with your actual Capital.com demo credentials:
- `CAP_API_KEY=your_actual_demo_api_key`
- `CAP_IDENTIFIER=your_actual_demo_identifier`
- `CAP_PASSWORD=your_actual_demo_password`

Get credentials at: **https://capital.com** → Settings → API Access

---

## After Adding the Server

Once your server appears in "My servers" list:

1. **Click on the server name** to connect
2. **You should see 11 tools** listed
3. **Test a few tools:**
   - `check_status` - No credentials needed
   - `list_instruments` - Search for "EUR"
   - `get_quote` - Get price for "EURUSD"
   - `get_account_balance` - See your demo account

---

## Troubleshooting

### "Server won't connect" or "Connection error"
- Ensure Docker image is built: `docker images | grep capital`
- Test manually: `./run-mcp-server.sh`
- Check credentials in `secrets/.env.demo`

### "Authentication failed"
- Verify Capital.com credentials are correct
- Ensure you're using DEMO credentials (not live)
- Check API access is enabled in Capital.com settings

### Server doesn't appear after adding
- Refresh the page
- Restart Docker Desktop
- Check Docker logs for errors

---

## Testing Without Docker Desktop UI

You can also test directly:

```bash
# Test the wrapper script
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}' | ./run-mcp-server.sh 2>/dev/null
```

Expected: JSON response with server info

---

## Available Tools (11 total)

Once connected, you'll see these tools:

1. ✅ **check_status** - Server status and environment
2. ✅ **authenticate** - Establish Capital.com session  
3. ✅ **list_instruments** - Search trading instruments
4. ✅ **get_quote** - Current price quotes
5. ✅ **get_account_balance** - Account balance info
6. ✅ **get_positions** - Open positions
7. ✅ **place_market_order** - Execute market order
8. ✅ **place_limit_order** - Place limit order  
9. ✅ **get_order_status** - Check order confirmation
10. ✅ **cancel_order** - Cancel/close position
11. ✅ **poll_prices** - Poll multiple instruments

---

## Security Reminder

- ✅ Currently in DEMO mode (safe for testing)
- ⚠️ Never commit credentials to Git
- ⚠️ Only use LIVE mode when ready for real trading
- ⚠️ Live orders require `confirm_live_trade="yes"` parameter

---

Good luck! Let me know if you encounter any issues. 🚀



