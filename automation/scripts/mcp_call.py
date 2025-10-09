#!/usr/bin/env python3
"""
MCP Caller - stdio JSON-RPC wrapper for Capital.com MCP Server
Calls the MCP server container via Docker and stdio JSON-RPC protocol.
"""

import json
import subprocess
import sys
import os
import time
import hmac
import hashlib
from typing import Dict, Any, Optional
import logging

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mcp_call')


class MCPError(Exception):
    """MCP-specific error"""
    pass


class MCPCaller:
    """Handles stdio JSON-RPC calls to Capital.com MCP server"""
    
    def __init__(self):
        self.mcp_image = os.getenv('MCP_IMAGE', 'capital-mcp-server:latest')
        self.mcp_container = os.getenv('MCP_CONTAINER', 'cool_hopper')  # Use actual container name
        self.approval_secret = os.getenv('APPROVAL_SECRET', '')
        self.trading_halted = os.getenv('TRADING_HALTED', '0') == '1'
        
        # Rate limiting
        self.last_call_time = 0
        self.min_call_interval = 0.1  # 100ms between calls
        self.request_count = 0
        self.rate_limit_window_start = time.time()
        self.max_requests_per_minute = 100
        
        # Session tracking
        self.session_id = 0
    
    def _rate_limit(self):
        """Enforce rate limiting with backoff"""
        current_time = time.time()
        
        # Reset window if needed
        if current_time - self.rate_limit_window_start > 60:
            self.request_count = 0
            self.rate_limit_window_start = current_time
        
        # Check rate limit
        if self.request_count >= self.max_requests_per_minute:
            wait_time = 60 - (current_time - self.rate_limit_window_start)
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
                time.sleep(wait_time)
                self.request_count = 0
                self.rate_limit_window_start = time.time()
        
        # Minimum interval between calls
        time_since_last = current_time - self.last_call_time
        if time_since_last < self.min_call_interval:
            time.sleep(self.min_call_interval - time_since_last)
        
        self.last_call_time = time.time()
        self.request_count += 1
    
    def _build_env_args(self) -> list:
        """Build Docker environment arguments for MCP server"""
        env_args = []
        
        # Pass through required env vars
        env_vars = [
            'CAP_ENVIRONMENT',
            'CAP_API_KEY',
            'CAP_IDENTIFIER',
            'CAP_PASSWORD'
        ]
        
        for var in env_vars:
            value = os.getenv(var)
            if value:
                env_args.extend(['-e', f'{var}={value}'])
        
        return env_args
    
    def call_mcp(self, tool_name: str, arguments: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Call an MCP tool via stdio JSON-RPC
        
        Args:
            tool_name: Name of the MCP tool to call
            arguments: Tool arguments
            
        Returns:
            Tool result as dict
            
        Raises:
            MCPError: If the call fails
        """
        if arguments is None:
            arguments = {}
        
        # Check trading halt
        if self.trading_halted and tool_name in ['place_market_order', 'place_limit_order']:
            raise MCPError("Trading is currently halted (TRADING_HALTED=1)")
        
        # Apply rate limiting
        self._rate_limit()
        
        # Generate request ID
        self.session_id += 1
        request_id = self.session_id
        
        try:
            # Build Docker command to exec into existing container
            docker_cmd = [
                'docker', 'exec', '-i', self.mcp_container,
                'python', 'capital_server.py'
            ]
            
            # Build JSON-RPC requests (initialize + initialized notification + tool call)
            initialize_request = {
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "automation", "version": "1.0.0"}
                },
                # Use a distinct id so we don't confuse this with the tool call response
                "id": 0
            }
            
            # MCP protocol requires an "initialized" notification after initialize response
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {}
            }
            
            tool_request = {
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                },
                "id": request_id
            }
            
            # Prepare input - note: we send initialize, then initialized, then tool call
            # The initialized notification doesn't have an id (it's a notification, not a request)
            input_data = json.dumps(initialize_request) + '\n' + json.dumps(initialized_notification) + '\n' + json.dumps(tool_request) + '\n'
            
            logger.info(f"Calling MCP tool: {tool_name}")
            logger.debug(f"Arguments: {json.dumps(arguments, indent=2)}")
            
            # Execute Docker command
            process = subprocess.run(
                docker_cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if process.returncode != 0:
                logger.error(f"Docker command failed: {process.stderr}")
                raise MCPError(f"Docker execution failed: {process.stderr}")
            
            # Parse responses (skip initialize response, get tool response)
            responses = []
            for line in process.stdout.strip().split('\n'):
                if line.strip():
                    try:
                        resp = json.loads(line)
                        responses.append(resp)
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse line: {line[:100]}")
            
            # Find our tool response
            tool_response = None
            for resp in responses:
                if resp.get('id') == request_id:
                    tool_response = resp
                    break
            
            if not tool_response:
                raise MCPError("No tool response received")
            
            # Check for errors
            if 'error' in tool_response:
                error = tool_response['error']
                raise MCPError(f"MCP error: {error.get('message', 'Unknown error')}")
            
            # Extract result
            result = tool_response.get('result', {})
            
            # Parse content if it's MCP content format
            if isinstance(result, dict) and 'content' in result:
                content_items = result['content']
                if content_items and isinstance(content_items, list):
                    # Get text from first content item
                    text_content = content_items[0].get('text', '')
                    logger.info(f"MCP tool {tool_name} completed")
                    logger.debug(f"Result: {text_content[:200]}")
                    return {
                        'success': True,
                        'tool': tool_name,
                        'result': text_content,
                        'raw': result
                    }
            
            # Return raw result if not in content format
            logger.info(f"MCP tool {tool_name} completed")
            return {
                'success': True,
                'tool': tool_name,
                'result': result,
                'raw': result
            }
            
        except subprocess.TimeoutExpired:
            logger.error(f"MCP call timed out: {tool_name}")
            raise MCPError(f"MCP call timed out after 30 seconds")
        except Exception as e:
            logger.error(f"MCP call failed: {tool_name} - {str(e)}")
            raise MCPError(f"MCP call failed: {str(e)}")
    
    def check_status(self) -> Dict[str, Any]:
        """Check MCP server status"""
        return self.call_mcp('check_status')
    
    def authenticate(self) -> Dict[str, Any]:
        """Authenticate with Capital.com"""
        return self.call_mcp('authenticate')
    
    def list_instruments(self, search_term: str = "", limit: int = 50) -> Dict[str, Any]:
        """List available instruments"""
        return self.call_mcp('list_instruments', {
            'search_term': search_term,
            'limit': str(limit)
        })
    
    def get_quote(self, epic: str) -> Dict[str, Any]:
        """Get current quote for instrument"""
        return self.call_mcp('get_quote', {'epic': epic})
    
    def get_account_balance(self) -> Dict[str, Any]:
        """Get account balance"""
        return self.call_mcp('get_account_balance')
    
    def get_positions(self) -> Dict[str, Any]:
        """Get open positions"""
        return self.call_mcp('get_positions')
    
    def place_market_order(
        self,
        epic: str,
        direction: str,
        size: str,
        stop_loss: str = "",
        take_profit: str = "",
        trailing_stop: str = "",
        approval_token: str = "",
        confirm_live_trade: str = ""
    ) -> Dict[str, Any]:
        """
        Place market order
        
        Requires approval_token if not in demo mode
        """
        # Verify approval token if required
        if os.getenv('CAP_ENVIRONMENT', 'demo') == 'live' and not approval_token:
            raise MCPError("Approval token required for live trading")
        
        if approval_token:
            # Verify HMAC token
            if not self._verify_approval_token(approval_token, epic, direction, size):
                raise MCPError("Invalid approval token")
        
        return self.call_mcp('place_market_order', {
            'epic': epic,
            'direction': direction,
            'size': size,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'trailing_stop': trailing_stop,
            'confirm_live_trade': confirm_live_trade
        })
    
    def place_limit_order(
        self,
        epic: str,
        direction: str,
        size: str,
        limit_level: str,
        stop_loss: str = "",
        take_profit: str = "",
        trailing_stop: str = "",
        approval_token: str = "",
        confirm_live_trade: str = ""
    ) -> Dict[str, Any]:
        """Place limit order"""
        if os.getenv('CAP_ENVIRONMENT', 'demo') == 'live' and not approval_token:
            raise MCPError("Approval token required for live trading")
        
        if approval_token:
            if not self._verify_approval_token(approval_token, epic, direction, size):
                raise MCPError("Invalid approval token")
        
        return self.call_mcp('place_limit_order', {
            'epic': epic,
            'direction': direction,
            'size': size,
            'limit_level': limit_level,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'trailing_stop': trailing_stop,
            'confirm_live_trade': confirm_live_trade
        })
    
    def get_order_status(self, deal_reference: str) -> Dict[str, Any]:
        """Get order status"""
        return self.call_mcp('get_order_status', {'deal_reference': deal_reference})
    
    def cancel_order(self, deal_id: str) -> Dict[str, Any]:
        """Cancel order or close position"""
        return self.call_mcp('cancel_order', {'deal_id': deal_id})
    
    def poll_prices(
        self,
        epic_list: str,
        interval_seconds: int = 5,
        iterations: int = 10
    ) -> Dict[str, Any]:
        """Poll prices for multiple instruments"""
        return self.call_mcp('poll_prices', {
            'epic_list': epic_list,
            'interval_seconds': str(interval_seconds),
            'iterations': str(iterations)
        })
    
    def _verify_approval_token(self, token: str, epic: str, direction: str, size: str) -> bool:
        """Verify HMAC approval token"""
        if not self.approval_secret:
            logger.warning("No approval secret configured, skipping token verification")
            return True
        
        # Reconstruct expected token
        message = f"{epic}:{direction}:{size}"
        expected_token = hmac.new(
            self.approval_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(token, expected_token)
    
    def generate_approval_token(self, epic: str, direction: str, size: str) -> str:
        """Generate HMAC approval token for trade"""
        if not self.approval_secret:
            raise MCPError("No approval secret configured")
        
        message = f"{epic}:{direction}:{size}"
        token = hmac.new(
            self.approval_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return token


def main():
    """CLI interface for MCP caller"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Call Capital.com MCP server tools')
    parser.add_argument('tool', help='MCP tool name')
    parser.add_argument('--args', type=json.loads, default={}, help='Tool arguments as JSON')
    parser.add_argument('--output', choices=['json', 'text'], default='json', help='Output format')
    
    args = parser.parse_args()
    
    try:
        caller = MCPCaller()
        result = caller.call_mcp(args.tool, args.args)
        
        if args.output == 'json':
            print(json.dumps(result, indent=2))
        else:
            print(result.get('result', ''))
        
        sys.exit(0)
    except MCPError as e:
        logger.error(f"MCP error: {e}")
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(json.dumps({'error': str(e)}), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()

