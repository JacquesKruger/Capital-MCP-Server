#!/bin/bash
# MCP Server Test Script
# Tests the Capital.com MCP server with various requests

set -e

PYTHON="python"
if [ -d "venv" ]; then
    source venv/bin/activate
    PYTHON="python"
fi

echo "═══════════════════════════════════════════════════════════════"
echo "Testing Capital.com MCP Server"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Test 1: Initialize
echo "✓ Test 1: Initialize Protocol"
echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}' | \
  $PYTHON capital_server.py 2>/dev/null | jq -r '.result.serverInfo.name' || echo "FAIL"
echo ""

# Test 2: List Tools
echo "✓ Test 2: List Available Tools"
(
  echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}'
  echo '{"jsonrpc":"2.0","method":"tools/list","id":2}'
) | $PYTHON capital_server.py 2>/dev/null | grep -o '"name":"[^"]*"' | cut -d':' -f2 | tr -d '"' || echo "FAIL"
echo ""

# Test 3: Check Server Status (without credentials)
echo "✓ Test 3: Call check_status Tool"
(
  echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0.0"}},"id":1}'
  echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"check_status","arguments":{}},"id":2}'
) | $PYTHON capital_server.py 2>/dev/null | grep -A 20 '"content"' | head -15 || echo "FAIL"
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo "Basic MCP protocol tests complete!"
echo ""
echo "Next steps:"
echo "1. Add your Capital.com credentials to secrets/.env.demo"
echo "2. Run with credentials: export \$(cat secrets/.env.demo | xargs) && ./test_mcp.sh"
echo "3. Or configure in Claude Desktop for full integration"
echo "═══════════════════════════════════════════════════════════════"



