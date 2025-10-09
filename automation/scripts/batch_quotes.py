#!/usr/bin/env python3
"""
Batch quote fetcher - gets quotes for multiple epics in a single MCP session
This solves the rate-limiting issue by reusing the same authentication session
"""

import json
import subprocess
import sys
import os

def batch_get_quotes(epics: list) -> dict:
    """Get quotes for multiple epics in a single MCP session"""
    
    mcp_container = os.getenv('MCP_CONTAINER', 'cool_hopper')
    
    # Build JSON-RPC requests for a single session
    initialize_request = {
        "jsonrpc": "2.0",
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "batch_quotes", "version": "1.0.0"}
        },
        "id": 0
    }
    
    initialized_notification = {
        "jsonrpc": "2.0",
        "method": "notifications/initialized",
        "params": {}
    }
    
    # Create a tool request for each epic
    tool_requests = []
    for i, epic in enumerate(epics, start=1):
        tool_requests.append({
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": "get_quote",
                "arguments": {"epic": epic}
            },
            "id": i
        })
    
    # Build input: initialize + initialized + all tool calls
    input_lines = [
        json.dumps(initialize_request),
        json.dumps(initialized_notification)
    ]
    input_lines.extend([json.dumps(req) for req in tool_requests])
    input_data = '\n'.join(input_lines) + '\n'
    
    # Execute in a single Docker exec session
    docker_cmd = [
        'docker', 'exec', '-i', mcp_container,
        'python', 'capital_server.py'
    ]
    
    try:
        process = subprocess.run(
            docker_cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if process.returncode != 0:
            return {"error": f"Docker execution failed: {process.stderr}"}
        
        # Parse all responses
        responses = []
        for line in process.stdout.strip().split('\n'):
            if line.strip():
                try:
                    responses.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        
        # Extract results for each epic (skip initialize response)
        results = {}
        for i, epic in enumerate(epics, start=1):
            for resp in responses:
                if resp.get('id') == i:
                    if 'error' in resp:
                        results[epic] = {"error": resp['error']['message']}
                    else:
                        result = resp.get('result', {})
                        if isinstance(result, dict) and 'content' in result:
                            text = result['content'][0].get('text', '')
                            results[epic] = {"text": text}
                        else:
                            results[epic] = {"result": result}
                    break
        
        return results
        
    except subprocess.TimeoutExpired:
        return {"error": "Request timed out"}
    except Exception as e:
        return {"error": str(e)}


if __name__ == '__main__':
    # Read epics from stdin (one per line) or args
    if len(sys.argv) > 1:
        epics = sys.argv[1:]
    else:
        epics = [line.strip() for line in sys.stdin if line.strip()]
    
    if not epics:
        print(json.dumps({"error": "No epics provided"}))
        sys.exit(1)
    
    results = batch_get_quotes(epics)
    print(json.dumps(results, indent=2))


