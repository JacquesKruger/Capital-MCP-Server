#!/usr/bin/env python3
"""
MCP Server Wrapper - Keeps a persistent MCP server process alive
Handles stdin/stdout communication with the MCP server
"""

import os
import sys
import json
import subprocess
import threading
import time
import logging
from typing import Optional, Dict, Any
from queue import Queue, Empty

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('mcp_wrapper')


class PersistentMCPServer:
    """Manages a persistent MCP server process with session reuse"""
    
    def __init__(self):
        # Auto-detect the Capital MCP server container
        self.container = self._find_capital_container()
        self.process: Optional[subprocess.Popen] = None
        self.request_id = 0
        self.response_queue = Queue()
        self.lock = threading.Lock()
        self.initialized = False
        self.reader_thread = None
        self.last_activity = time.time()
        self.failed_calls = 0
        self.max_failed_calls = 3  # Restart after 3 consecutive failures
        self.call_timeout = 30  # 30 second timeout per call
        self.max_idle_time = 300  # 5 minutes max idle time before restart
    
    def _find_capital_container(self) -> str:
        """Find the Capital MCP server container by image name"""
        try:
            result = subprocess.run(
                ['docker', 'ps', '--filter', 'ancestor=capital-mcp-server', '--format', '{{.Names}}'],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0 and result.stdout.strip():
                container_name = result.stdout.strip()
                logger.info(f"Found Capital MCP container: {container_name}")
                return container_name
        except Exception as e:
            logger.warning(f"Failed to find Capital container: {e}")
        
        # Fallback to environment variable or default
        fallback = os.getenv('MCP_CONTAINER', 'capital-mcp-server')
        logger.warning(f"Using fallback container name: {fallback}")
        return fallback
        
    def start(self):
        """Start the persistent MCP server process"""
        if self.process:
            logger.warning("Process already running")
            return
        
        cmd = ['docker', 'exec', '-i', self.container, 'python', 'capital_server.py']
        
        logger.info(f"Starting MCP server: {' '.join(cmd)}")
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        # Start reader thread
        self.reader_thread = threading.Thread(target=self._read_responses, daemon=True)
        self.reader_thread.start()
        
        # Initialize MCP protocol
        self._initialize()
        
    def _read_responses(self):
        """Background thread to read responses from MCP server"""
        while self.process and self.process.poll() is None:
            try:
                line = self.process.stdout.readline()
                if not line:
                    break
                
                line = line.strip()
                if line:
                    try:
                        resp = json.loads(line)
                        self.response_queue.put(resp)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse response: {line[:100]}")
            except Exception as e:
                logger.error(f"Reader error: {e}")
                break
    
    def _initialize(self):
        """Initialize MCP protocol"""
        with self.lock:
            # Send initialize request
            init_req = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "persistent_wrapper", "version": "1.0.0"}
                },
                "id": 0
            }
            
            self._write(init_req)
            
            # Wait for initialize response
            init_resp = self._wait_for_response(0, timeout=10)
            if not init_resp or 'error' in init_resp:
                raise Exception(f"Initialization failed: {init_resp}")
            
            # Send initialized notification
            init_notif = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            self._write(init_notif)
            
            self.initialized = True
            logger.info("MCP server initialized successfully")
    
    def _write(self, data: dict):
        """Write JSON-RPC request to server"""
        if not self.process or not self.process.stdin:
            raise Exception("Process not running")
        
        line = json.dumps(data) + '\n'
        self.process.stdin.write(line)
        self.process.stdin.flush()
    
    def _wait_for_response(self, request_id: int, timeout: float = 30) -> Optional[Dict]:
        """Wait for a specific response by ID"""
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                resp = self.response_queue.get(timeout=0.5)
                if resp.get('id') == request_id:
                    return resp
                else:
                    # Put it back if it's not ours (shouldn't happen with locking)
                    self.response_queue.put(resp)
            except Empty:
                continue
        
        return None
    
    def is_healthy(self) -> bool:
        """Check if the server process is healthy"""
        if not self.process or self.process.poll() is not None:
            return False
        
        # Check for excessive idle time
        idle_time = time.time() - self.last_activity
        if idle_time > self.max_idle_time:
            logger.warning(f"Server idle for {idle_time:.1f}s, marking unhealthy")
            return False
        
        # Check for too many failures
        if self.failed_calls >= self.max_failed_calls:
            logger.warning(f"Too many failed calls ({self.failed_calls}), marking unhealthy")
            return False
        
        return True
    
    def restart(self):
        """Restart the MCP server process"""
        logger.info("Restarting MCP server...")
        self.stop()
        time.sleep(2)  # Brief pause
        self.failed_calls = 0
        self.start()
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any], retry: bool = True) -> Dict[str, Any]:
        """Call an MCP tool with session reuse, timeout, and auto-retry"""
        
        # Health check before call
        if not self.is_healthy():
            if retry:
                logger.warning("Server unhealthy, attempting restart...")
                self.restart()
            else:
                raise Exception("Server unhealthy and retry disabled")
        
        if not self.initialized:
            raise Exception("Server not initialized")
        
        try:
            with self.lock:
                self.request_id += 1
                req_id = self.request_id
                
                request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    },
                    "id": req_id
                }
                
                logger.info(f"Calling tool: {tool_name} (id={req_id})")
                self._write(request)
                
                # Wait for response with timeout
                response = self._wait_for_response(req_id, timeout=self.call_timeout)
                
                if not response:
                    self.failed_calls += 1
                    raise Exception(f"Timeout waiting for response to {tool_name} ({self.call_timeout}s)")
                
                if 'error' in response:
                    self.failed_calls += 1
                    error_msg = response['error'].get('message', 'Unknown error')
                    raise Exception(f"MCP error: {error_msg}")
                
                # Success - reset failure counter and update activity
                self.failed_calls = 0
                self.last_activity = time.time()
                
                result = response.get('result', {})
                
                # Extract text from content format
                if isinstance(result, dict) and 'content' in result:
                    content_items = result['content']
                    if content_items and isinstance(content_items, list):
                        text = content_items[0].get('text', '')
                        return {'text': text, 'raw': result}
                
                return {'result': result, 'raw': result}
                
        except Exception as e:
            logger.error(f"Tool call failed: {tool_name} - {str(e)}")
            
            # If retry enabled and this is first attempt, restart and retry
            if retry and self.failed_calls < self.max_failed_calls:
                logger.info(f"Retrying {tool_name} after restart...")
                self.restart()
                return self.call_tool(tool_name, arguments, retry=False)  # No retry on second attempt
            
            raise
    
    def stop(self):
        """Stop the MCP server process"""
        if self.process:
            self.process.terminate()
            self.process.wait(timeout=5)
            self.process = None
            self.initialized = False


# Global singleton
_server: Optional[PersistentMCPServer] = None

def get_server() -> PersistentMCPServer:
    """Get or create the global MCP server instance"""
    global _server
    if _server is None or not _server.initialized:
        _server = PersistentMCPServer()
        _server.start()
    return _server


if __name__ == '__main__':
    # Test the wrapper
    server = get_server()
    
    # Test with a simple call
    result = server.call_tool('get_quote', {'epic': 'EURUSD'})
    print(json.dumps(result, indent=2))


