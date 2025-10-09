#!/usr/bin/env python3
"""
Simple HTTP API for MCP calls
Allows n8n to call MCP functions via HTTP with persistent session reuse
"""

from flask import Flask, request, jsonify
import json
import sys
import os

# Add the scripts directory to Python path
sys.path.append('/app/scripts')

from mcp_server_wrapper import get_server

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "mcp-api"})

@app.route('/mcp/call', methods=['POST'])
def mcp_call():
    """Generic MCP tool caller"""
    try:
        data = request.get_json()
        tool_name = data.get('tool')
        arguments = data.get('args', {})
        
        if not tool_name:
            return jsonify({"error": "Missing 'tool' parameter"}), 400
        
        result = MCPCaller().call_mcp(tool_name, arguments)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mcp/check_status', methods=['GET'])
def check_status():
    """Check MCP server status"""
    try:
        server = get_server()
        return jsonify({"status": "ok", "initialized": server.initialized})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mcp/authenticate', methods=['POST'])
def authenticate():
    """Authenticate to Capital.com API"""
    try:
        server = get_server()
        result = server.call_tool('authenticate', {})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mcp/get_quote', methods=['POST'])
def get_quote():
    """Get quote for an instrument"""
    try:
        data = request.get_json()
        
        if data is None:
            return jsonify({"error": "Invalid JSON body"}), 400
            
        epic = data.get('epic')
        if not epic:
            return jsonify({"error": "Missing 'epic' parameter"}), 400
        
        server = get_server()
        result = server.call_tool('get_quote', {'epic': epic})
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mcp/batch_quotes', methods=['POST'])
def batch_quotes():
    """Get quotes for multiple instruments using persistent session (no rate limiting)"""
    try:
        data = request.get_json()
        
        if data is None:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        epics = data.get('epics', [])
        if not epics or not isinstance(epics, list):
            return jsonify({"error": "Missing or invalid 'epics' parameter (must be array)"}), 400
        
        # Use persistent MCP server
        server = get_server()
        results = {}
        
        for epic in epics:
            try:
                result = server.call_tool('get_quote', {'epic': epic})
                results[epic] = result
            except Exception as e:
                results[epic] = {"error": str(e)}
        
        return jsonify(results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/indicators', methods=['POST'])
def calculate_indicators():
    """Calculate technical indicators from candle data"""
    try:
        data = request.get_json()
        
        if data is None:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        # Call indicators.py script
        import subprocess
        result = subprocess.run(
            ['python3', '/app/scripts/indicators.py'],
            input=json.dumps(data),
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return jsonify({"error": f"Indicators calculation failed: {result.stderr}"}), 500
        
        return jsonify(json.loads(result.stdout))
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mcp/get_account_balance', methods=['GET'])
def get_account_balance():
    """Get account balance - returns structured data"""
    try:
        server = get_server()
        
        # Check if server is initialized
        if not server.initialized:
            return jsonify({"success": False, "error": "MCP server not initialized"}), 500
        
        result = server.call_tool('get_account_balance', {})
        
        # Parse the text response to extract structured data
        text = result.get('result', '') or result.get('text', '')
        
        if not text:
            return jsonify({"success": False, "error": "Empty response from MCP server", "raw": result}), 500
        
        import re
        balance_match = re.search(r'Balance:\s*([\d.]+)', text)
        available_match = re.search(r'Available:\s*([\d.]+)', text)
        deposit_match = re.search(r'Deposit:\s*([\d.]+)', text)
        pnl_match = re.search(r'P&L:\s*([-\d.]+)', text)
        currency_match = re.search(r'Currency:\s*(\w+)', text)
        
        structured_data = {
            'balance': float(balance_match.group(1)) if balance_match else 0,
            'available': float(available_match.group(1)) if available_match else 0,
            'deposit': float(deposit_match.group(1)) if deposit_match else 0,
            'pnl': float(pnl_match.group(1)) if pnl_match else 0,
            'currency': currency_match.group(1) if currency_match else 'USD',
            'raw_text': text
        }
        
        return jsonify({
            'success': True,
            'data': structured_data,
            'raw': result
        })
    except TimeoutError as e:
        return jsonify({"success": False, "error": f"Request timeout: {e}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/mcp/get_positions', methods=['GET'])
def get_positions():
    """Get open positions - returns structured data"""
    try:
        server = get_server()
        result = server.call_tool('get_positions', {})
        
        # Parse the text response to extract structured data
        text = result.get('result', '') or result.get('text', '')
        
        import re
        
        # Extract positions from text
        positions = []
        
        # Split by position blocks (each starts with "Deal ID:")
        position_blocks = re.split(r'\n(?=Deal ID:)', text)
        
        for block in position_blocks:
            if 'Deal ID:' not in block:
                continue
                
            deal_id_match = re.search(r'Deal ID:\s*(\S+)', block)
            instrument_match = re.search(r'Instrument:\s*([^(]+)\(([^)]+)\)', block)
            direction_match = re.search(r'Direction:\s*(\w+)', block)
            size_match = re.search(r'Size:\s*([\d.]+)', block)
            level_match = re.search(r'Level:\s*([\d.]+)', block)
            pnl_match = re.search(r'P&L:\s*([-\d.]+|N/A)', block)
            
            if deal_id_match and instrument_match:
                position = {
                    'dealId': deal_id_match.group(1),
                    'instrumentName': instrument_match.group(1).strip(),
                    'epic': instrument_match.group(2),
                    'direction': direction_match.group(1) if direction_match else '',
                    'size': float(size_match.group(1)) if size_match else 0,
                    'level': float(level_match.group(1)) if level_match else 0,
                    'profit': 0 if not pnl_match or pnl_match.group(1) == 'N/A' else float(pnl_match.group(1))
                }
                positions.append(position)
        
        # Calculate totals
        total_exposure = sum(abs(p['size'] * p['level']) for p in positions)
        total_pnl = sum(p['profit'] for p in positions)
        
        structured_data = {
            'positions': positions,
            'count': len(positions),
            'totalExposure': total_exposure,
            'totalPnL': total_pnl,
            'raw_text': text
        }
        
        return jsonify({
            'success': True,
            'data': structured_data,
            'raw': result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/mcp/place_market_order', methods=['POST'])
def place_market_order():
    """Place a market order"""
    try:
        data = request.get_json()
        server = get_server()
        
        # Extract parameters
        params = {
            'epic': data.get('epic', ''),
            'direction': data.get('direction', ''),
            'size': data.get('size', ''),
            'stop_loss': data.get('stop_loss', ''),
            'take_profit': data.get('take_profit', ''),
            'trailing_stop': data.get('trailing_stop', ''),
            'confirm_live_trade': data.get('confirm_live_trade', '')
        }
        
        # Log the parameters being sent
        print(f"[DEBUG] place_market_order called with params: {params}", flush=True)
        
        result = server.call_tool('place_market_order', params)
        return jsonify(result)
    except Exception as e:
        print(f"[ERROR] place_market_order failed: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 500

@app.route('/mcp/place_limit_order', methods=['POST'])
def place_limit_order():
    """Place a limit order"""
    try:
        data = request.get_json()
        server = get_server()
        
        # Extract parameters
        result = server.call_tool('place_limit_order', {
            'epic': data.get('epic', ''),
            'direction': data.get('direction', ''),
            'size': data.get('size', ''),
            'limit_level': data.get('limit_level', ''),
            'stop_loss': data.get('stop_loss', ''),
            'take_profit': data.get('take_profit', ''),
            'trailing_stop': data.get('trailing_stop', ''),
            'confirm_live_trade': data.get('confirm_live_trade', '')
        })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/screener', methods=['POST'])
def run_screener():
    """Run the daily watchlist screener"""
    try:
        import subprocess
        result = subprocess.run(
            ['python3', '/app/scripts/screener.py'],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            return jsonify({
                "success": False,
                "error": f"Screener failed: {result.stderr}"
            }), 500
        
        # Parse JSON output from screener
        # Look for JSON block in output
        lines = result.stdout.strip().split('\n')
        json_output = None
        
        # Try each line from the end
        for line in reversed(lines):
            line = line.strip()
            if not line or not (line.startswith('{') or line.startswith('[')):
                continue
            try:
                json_output = json.loads(line)
                # If we found valid JSON with expected structure, use it
                if isinstance(json_output, dict) and 'watchlist' in json_output:
                    break
            except:
                continue
        
        if json_output and isinstance(json_output, dict) and 'watchlist' in json_output:
            return jsonify(json_output)
        else:
            # Return the output even if empty, it's still valid
            try:
                # Try parsing entire output as JSON
                json_output = json.loads(result.stdout.strip())
                return jsonify(json_output)
            except:
                return jsonify({
                    "success": False,
                    "error": "Could not parse screener output",
                    "output": result.stdout
                }), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/position_sizer', methods=['POST'])
def calculate_position_size():
    """Calculate position size based on risk parameters"""
    try:
        data = request.get_json()
        
        if data is None:
            return jsonify({"error": "Invalid JSON body"}), 400
        
        # Call position_sizer.py script
        import subprocess
        result = subprocess.run(
            ['python3', '/app/scripts/position_sizer.py'],
            input=json.dumps(data),
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return jsonify({
                "success": False,
                "error": f"Position sizer failed: {result.stderr}"
            }), 500
        
        # Parse output
        sizing_result = json.loads(result.stdout.strip())
        return jsonify({
            "success": True,
            "data": sizing_result
        })
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
