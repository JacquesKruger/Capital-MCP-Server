#!/usr/bin/env python3
"""
MCP Proxy - Simple proxy to maintain persistent connection to MCP server
"""

import json
import subprocess
import sys
import os
import time
import threading
import queue
from typing import Dict, Any

class MCPProxy:
    """Maintains a persistent connection to the MCP server"""
    
    def __init__(self):
        self.mcp_container = os.getenv('MCP_CONTAINER', 'cool_hopper')
        self.process = None
        self.initialized = False
        self.request_id = 0
        self.responses = {}
        self.response_lock = threading.Lock()
        
    def start(self):
        """Start the MCP server process"""
        if self.process is None:
            docker_cmd = [
                'docker', 'exec', '-i', self.mcp_container,
                'python', 'capital_server.py'
            ]
            
            self.process = subprocess.Popen(
                docker_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Start response reader thread
            self.response_thread = threading.Thread(target=self._read_responses)
            self.response_thread.daemon = True
            self.response_thread.start()
            
            # Initialize the connection
            self._initialize()
    
    def _initialize(self):
        """Initialize the MCP connection"""
        if not self.initialized:
            initialize_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "mcp-proxy", "version": "1.0.0"}
                },
                "id": 1
            }
            
            self.process.stdin.write(json.dumps(initialize_request) + '\n')
            self.process.stdin.flush()
            
            # Wait for initialization response
            time.sleep(0.5)
            self.initialized = True
    
    def _read_responses(self):
        """Read responses from MCP server"""
        while True:
            try:
                line = self.process.stdout.readline()
                if line:
                    response = json.loads(line.strip())
                    with self.response_lock:
                        self.responses[response.get('id')] = response
                else:
                    break
            except Exception as e:
                print(f"Error reading response: {e}", file=sys.stderr)
                break
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """Call an MCP tool"""
        if not self.initialized:
            self.start()
        
        self.request_id += 1
        request_id = self.request_id
        
        tool_request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments or {}
            },
            "id": request_id
        }
        
        # Send request
        self.process.stdin.write(json.dumps(tool_request) + '\n')
        self.process.stdin.flush()
        
        # Wait for response
        timeout = 10
        start_time = time.time()
        while time.time() - start_time < timeout:
            with self.response_lock:
                if request_id in self.responses:
                    response = self.responses.pop(request_id)
                    if 'error' in response:
                        raise Exception(f"MCP error: {response['error']}")
                    return response
            time.sleep(0.1)
        
        raise Exception("Timeout waiting for MCP response")

# Global proxy instance
_proxy = None

def get_proxy():
    global _proxy
    if _proxy is None:
        _proxy = MCPProxy()
    return _proxy

if __name__ == "__main__":
    # Test the proxy
    proxy = get_proxy()
    result = proxy.call_tool('check_status')
    print(json.dumps(result, indent=2))

