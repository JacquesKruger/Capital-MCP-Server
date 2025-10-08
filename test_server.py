#!/usr/bin/env python3
"""
Simple test script for Capital.com MCP Server
Tests basic MCP protocol functionality
"""

import json
import subprocess
import sys

def send_mcp_requests(requests):
    """Send multiple MCP requests to the server in one session."""
    try:
        # Prepare all requests as newline-delimited JSON
        input_data = "\n".join(json.dumps(req) for req in requests) + "\n"
        
        # Send to server
        result = subprocess.run(
            [sys.executable, "capital_server.py"],
            input=input_data,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.stdout:
            # Parse multiple JSON responses
            responses = []
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    try:
                        responses.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
            return responses
        return []
    except Exception as e:
        return [{"error": str(e)}]

def test_initialize():
    """Test server initialization."""
    print("Test 1: Initialize MCP Server")
    print("-" * 60)
    
    response = send_mcp_request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0.0"}
    })
    
    if response and "result" in response:
        server_info = response["result"].get("serverInfo", {})
        print(f"✅ Server: {server_info.get('name')}")
        print(f"✅ Version: {server_info.get('version')}")
        print(f"✅ Protocol: {response['result'].get('protocolVersion')}")
        return True
    else:
        print(f"❌ Failed: {response}")
        return False

def test_list_tools():
    """Test listing available tools."""
    print("\nTest 2: List Available Tools")
    print("-" * 60)
    
    # Initialize first
    send_mcp_request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0.0"}
    }, 1)
    
    # List tools
    response = send_mcp_request("tools/list", {}, 2)
    
    if response and "result" in response:
        tools = response["result"].get("tools", [])
        print(f"✅ Found {len(tools)} tools:\n")
        
        for i, tool in enumerate(tools, 1):
            name = tool.get("name", "unknown")
            description = tool.get("description", "No description")
            print(f"{i:2d}. {name}")
            print(f"    {description}")
        
        return True
    else:
        print(f"❌ Failed: {response}")
        return False

def test_check_status():
    """Test calling the check_status tool."""
    print("\nTest 3: Call check_status Tool")
    print("-" * 60)
    
    # Initialize
    send_mcp_request("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "test-client", "version": "1.0.0"}
    }, 1)
    
    # Call tool
    response = send_mcp_request("tools/call", {
        "name": "check_status",
        "arguments": {}
    }, 2)
    
    if response and "result" in response:
        content = response["result"].get("content", [])
        if content and len(content) > 0:
            text = content[0].get("text", "")
            print(text)
            return True
    
    print(f"❌ Failed: {response}")
    return False

def main():
    """Run all tests."""
    print("═" * 60)
    print("Capital.com MCP Server - Test Suite")
    print("═" * 60)
    print()
    
    tests = [
        test_initialize,
        test_list_tools,
        test_check_status
    ]
    
    results = []
    for test in tests:
        try:
            success = test()
            results.append(success)
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
            results.append(False)
        print()
    
    print("═" * 60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("═" * 60)
    print()
    
    if all(results):
        print("✅ All tests passed! Server is working correctly.")
        print()
        print("Next steps:")
        print("1. Add Capital.com credentials to secrets/.env.demo")
        print("2. Test with credentials:")
        print("   $ export $(cat secrets/.env.demo | xargs)")
        print("   $ python capital_server.py")
        print("3. Configure in Claude Desktop for full integration")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()

