#!/usr/bin/env python3
"""
Capital.com MCP Server
Provides secure access to Capital.com trading API via MCP tools.
Demo environment by default. Live trading requires explicit confirmation.
"""

import os
import sys
import logging
import time
from mcp.server.fastmcp import FastMCP
import httpx

# Configure logging to stderr with required format
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("capital-mcp-server")

# Initialize FastMCP server (NO prompt parameter)
mcp = FastMCP("Capital.com Trading")

# Global session state
_session_token = None
_session_cst = None
_session_expiry = 0
_client = httpx.Client(timeout=30.0)

# API Configuration
CAP_ENVIRONMENT = os.getenv("CAP_ENVIRONMENT", "demo").strip().lower()
CAP_API_KEY = os.getenv("CAP_API_KEY", "").strip()
CAP_IDENTIFIER = os.getenv("CAP_IDENTIFIER", "").strip()
CAP_PASSWORD = os.getenv("CAP_PASSWORD", "").strip()

CAP_DEMO_API_URL = os.getenv("CAP_DEMO_API_URL", "https://demo-api-capital.backend-capital.com").strip()
CAP_LIVE_API_URL = os.getenv("CAP_LIVE_API_URL", "https://api-capital.backend-capital.com").strip()

# Determine base URL based on environment
BASE_URL = CAP_DEMO_API_URL if CAP_ENVIRONMENT == "demo" else CAP_LIVE_API_URL

# Rate limiting state
_last_request_time = 0
_request_count = 0
_rate_limit_window = 60  # seconds
_max_requests_per_window = 100


def _check_credentials():
    """Check if required credentials are configured."""
    if not CAP_API_KEY or not CAP_IDENTIFIER or not CAP_PASSWORD:
        return False
    return True


def _rate_limit():
    """Simple rate limiting with backoff."""
    global _last_request_time, _request_count
    current_time = time.time()
    
    if current_time - _last_request_time > _rate_limit_window:
        _request_count = 0
        _last_request_time = current_time
    
    _request_count += 1
    
    if _request_count > _max_requests_per_window:
        wait_time = _rate_limit_window - (current_time - _last_request_time)
        if wait_time > 0:
            logger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            _request_count = 0
            _last_request_time = time.time()


def _authenticate():
    """Internal authentication helper that maintains session state."""
    global _session_token, _session_cst, _session_expiry
    
    if not _check_credentials():
        return False, "❌ Missing credentials. Set CAP_API_KEY, CAP_IDENTIFIER, and CAP_PASSWORD environment variables."
    
    # Check if existing session is still valid (with 5 minute buffer)
    if _session_token and time.time() < (_session_expiry - 300):
        return True, "✅ Using existing valid session"
    
    try:
        _rate_limit()
        
        payload = {
            "identifier": CAP_IDENTIFIER,
            "password": CAP_PASSWORD
        }
        
        headers = {
            "X-CAP-API-KEY": CAP_API_KEY,
            "Content-Type": "application/json"
        }
        
        logger.info(f"Authenticating to Capital.com ({CAP_ENVIRONMENT} environment)")
        response = _client.post(
            f"{BASE_URL}/api/v1/session",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            _session_cst = response.headers.get("CST")
            _session_token = response.headers.get("X-SECURITY-TOKEN")
            
            if not _session_cst or not _session_token:
                return False, "❌ Authentication succeeded but missing session headers"
            
            # Set expiry to 6 hours from now (typical Capital.com session length)
            _session_expiry = time.time() + (6 * 3600)
            
            logger.info("Authentication successful")
            return True, f"✅ Authenticated successfully ({CAP_ENVIRONMENT} mode)"
        else:
            logger.error(f"Authentication failed: {response.status_code} - {response.text}")
            return False, f"❌ Authentication failed: {response.status_code} - {response.text[:200]}"
            
    except httpx.TimeoutException:
        logger.error("Authentication timeout")
        return False, "❌ Authentication timeout. Please try again."
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return False, f"❌ Authentication error: {str(e)}"


def _get_headers():
    """Get authenticated request headers."""
    if not _session_token or not _session_cst:
        return None
    
    return {
        "X-CAP-API-KEY": CAP_API_KEY,
        "CST": _session_cst,
        "X-SECURITY-TOKEN": _session_token,
        "Content-Type": "application/json"
    }


def _is_live_environment():
    """Check if running in live environment."""
    return CAP_ENVIRONMENT == "live"


@mcp.tool()
def check_status() -> str:
    """Check MCP server status and current environment configuration."""
    env_status = "🔴 LIVE" if _is_live_environment() else "🟢 DEMO"
    creds_status = "✅ Configured" if _check_credentials() else "❌ Missing"
    session_status = "✅ Active" if _session_token else "❌ Not authenticated"
    
    return f"""📊 Capital.com MCP Server Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Environment: {env_status} ({CAP_ENVIRONMENT})
API URL: {BASE_URL}
Credentials: {creds_status}
Session: {session_status}

⚠️  Remember: LIVE trading involves REAL money and REAL financial risk!
"""


@mcp.tool()
def authenticate() -> str:
    """Authenticate to Capital.com API and establish a session."""
    success, message = _authenticate()
    return message


@mcp.tool()
def list_instruments(search_term: str = "", limit: str = "50") -> str:
    """Search and list available trading instruments by name or epic."""
    search_term = search_term.strip()
    limit = limit.strip()
    
    if not limit:
        limit = "50"
    
    try:
        limit_int = int(limit)
        if limit_int < 1 or limit_int > 1000:
            return "❌ Limit must be between 1 and 1000"
    except ValueError:
        return f"❌ Invalid limit value: {limit}"
    
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    try:
        _rate_limit()
        
        # Use markets endpoint with optional search
        params = {}
        if search_term:
            params["searchTerm"] = search_term
        
        response = _client.get(
            f"{BASE_URL}/api/v1/markets",
            headers=headers,
            params=params
        )
        
        if response.status_code == 200:
            data = response.json()
            markets = data.get("markets", [])
            
            if not markets:
                return f"📋 No instruments found" + (f" matching '{search_term}'" if search_term else "")
            
            # Limit results
            markets = markets[:limit_int]
            
            result = f"📋 Found {len(markets)} instruments" + (f" matching '{search_term}'" if search_term else "") + ":\n\n"
            
            for market in markets:
                epic = market.get("epic", "N/A")
                name = market.get("instrumentName", "N/A")
                instrument_type = market.get("instrumentType", "N/A")
                market_status = market.get("marketStatus", "N/A")
                
                result += f"• {epic}\n"
                result += f"  Name: {name}\n"
                result += f"  Type: {instrument_type} | Status: {market_status}\n\n"
            
            return result
        else:
            logger.error(f"List instruments failed: {response.status_code}")
            return f"❌ Failed to list instruments: {response.status_code} - {response.text[:200]}"
            
    except httpx.TimeoutException:
        return "❌ Request timeout. Please try again."
    except Exception as e:
        logger.error(f"List instruments error: {str(e)}")
        return f"❌ Error listing instruments: {str(e)}"


@mcp.tool()
def get_quote(epic: str = "") -> str:
    """Get current price quote for a specific instrument by epic."""
    epic = epic.strip()
    
    if not epic:
        return "❌ Epic parameter is required (e.g., 'EURUSD', 'US500')"
    
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    try:
        _rate_limit()
        
        response = _client.get(
            f"{BASE_URL}/api/v1/markets/{epic}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            snapshot = data.get("snapshot", {})
            instrument = data.get("instrument", {})
            
            name = instrument.get("name", "N/A")
            bid = snapshot.get("bid", "N/A")
            offer = snapshot.get("offer", "N/A")
            market_status = snapshot.get("marketStatus", "N/A")
            net_change = snapshot.get("netChange", "N/A")
            percent_change = snapshot.get("percentageChange", "N/A")
            update_time = snapshot.get("updateTime", "N/A")
            
            return f"""💹 Quote for {epic}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name: {name}
Bid: {bid}
Offer: {offer}
Status: {market_status}
Change: {net_change} ({percent_change}%)
Updated: {update_time}
"""
        elif response.status_code == 404:
            return f"❌ Instrument not found: {epic}"
        else:
            logger.error(f"Get quote failed: {response.status_code}")
            return f"❌ Failed to get quote: {response.status_code} - {response.text[:200]}"
            
    except httpx.TimeoutException:
        return "❌ Request timeout. Please try again."
    except Exception as e:
        logger.error(f"Get quote error: {str(e)}")
        return f"❌ Error getting quote: {str(e)}"


@mcp.tool()
def get_account_balance() -> str:
    """Get current account balance and available funds."""
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    try:
        _rate_limit()
        
        response = _client.get(
            f"{BASE_URL}/api/v1/accounts",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            accounts = data.get("accounts", [])
            
            if not accounts:
                return "📊 No accounts found"
            
            result = f"💰 Account Balance ({CAP_ENVIRONMENT.upper()} mode)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for account in accounts:
                account_id = account.get("accountId", "N/A")
                account_name = account.get("accountName", "N/A")
                currency = account.get("currency", "N/A")
                balance = account.get("balance", {})
                
                total_balance = balance.get("balance", "N/A")
                available = balance.get("available", "N/A")
                deposit = balance.get("deposit", "N/A")
                profit_loss = balance.get("profitLoss", "N/A")
                
                result += f"Account: {account_name} ({account_id})\n"
                result += f"Currency: {currency}\n"
                result += f"Balance: {total_balance}\n"
                result += f"Available: {available}\n"
                result += f"Deposit: {deposit}\n"
                result += f"P&L: {profit_loss}\n\n"
            
            return result
        else:
            logger.error(f"Get balance failed: {response.status_code}")
            return f"❌ Failed to get balance: {response.status_code} - {response.text[:200]}"
            
    except httpx.TimeoutException:
        return "❌ Request timeout. Please try again."
    except Exception as e:
        logger.error(f"Get balance error: {str(e)}")
        return f"❌ Error getting balance: {str(e)}"


@mcp.tool()
def get_positions() -> str:
    """Get all current open positions."""
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    try:
        _rate_limit()
        
        response = _client.get(
            f"{BASE_URL}/api/v1/positions",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            positions = data.get("positions", [])
            
            if not positions:
                return "📊 No open positions"
            
            result = f"📊 Open Positions ({len(positions)} total)\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            
            for position in positions:
                position_data = position.get("position", {})
                market = position.get("market", {})
                
                deal_id = position_data.get("dealId", "N/A")
                epic = market.get("epic", "N/A")
                instrument_name = market.get("instrumentName", "N/A")
                direction = position_data.get("direction", "N/A")
                size = position_data.get("size", "N/A")
                level = position_data.get("level", "N/A")
                currency = position_data.get("currency", "N/A")
                profit_loss = position_data.get("profit", "N/A")
                
                result += f"Deal ID: {deal_id}\n"
                result += f"Instrument: {instrument_name} ({epic})\n"
                result += f"Direction: {direction}\n"
                result += f"Size: {size}\n"
                result += f"Level: {level} {currency}\n"
                result += f"P&L: {profit_loss}\n\n"
            
            return result
        else:
            logger.error(f"Get positions failed: {response.status_code}")
            return f"❌ Failed to get positions: {response.status_code} - {response.text[:200]}"
            
    except httpx.TimeoutException:
        return "❌ Request timeout. Please try again."
    except Exception as e:
        logger.error(f"Get positions error: {str(e)}")
        return f"❌ Error getting positions: {str(e)}"


@mcp.tool()
def place_market_order(epic: str = "", direction: str = "", size: str = "", stop_loss: str = "", take_profit: str = "", trailing_stop: str = "", confirm_live_trade: str = "") -> str:
    """Place a market order with optional stop-loss and take-profit levels."""
    epic = epic.strip()
    direction = direction.strip().upper()
    size = size.strip()
    stop_loss = stop_loss.strip()
    take_profit = take_profit.strip()
    trailing_stop = trailing_stop.strip()
    confirm_live_trade = confirm_live_trade.strip().lower()
    
    # Validate parameters
    if not epic:
        return "❌ Epic parameter is required (e.g., 'EURUSD', 'US500')"
    
    if direction not in ["BUY", "SELL"]:
        return "❌ Direction must be 'BUY' or 'SELL'"
    
    if not size:
        return "❌ Size parameter is required (e.g., '1', '0.5')"
    
    try:
        size_float = float(size)
        if size_float <= 0:
            return "❌ Size must be greater than 0"
    except ValueError:
        return f"❌ Invalid size value: {size}"
    
    # Validate stop_loss if provided
    stop_loss_float = None
    if stop_loss:
        try:
            stop_loss_float = float(stop_loss)
            if stop_loss_float <= 0:
                return "❌ Stop loss must be greater than 0"
        except ValueError:
            return f"❌ Invalid stop loss value: {stop_loss}"
    
    # Validate take_profit if provided
    take_profit_float = None
    if take_profit:
        try:
            take_profit_float = float(take_profit)
            if take_profit_float <= 0:
                return "❌ Take profit must be greater than 0"
        except ValueError:
            return f"❌ Invalid take profit value: {take_profit}"
    
    # Validate trailing_stop if provided
    trailing_stop_float = None
    if trailing_stop:
        try:
            trailing_stop_float = float(trailing_stop)
            if trailing_stop_float <= 0:
                return "❌ Trailing stop must be greater than 0"
        except ValueError:
            return f"❌ Invalid trailing stop value: {trailing_stop}"
    
    # Live trading safety check
    if _is_live_environment() and confirm_live_trade != "yes":
        return f"""⚠️  LIVE TRADING BLOCKED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You are attempting to place a LIVE trade with REAL money:
• Epic: {epic}
• Direction: {direction}
• Size: {size}

This involves REAL FINANCIAL RISK!

To proceed, call this tool again with parameter:
confirm_live_trade="yes"

Stay in demo mode to practice without risk.
"""
    
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    try:
        _rate_limit()
        
        payload = {
            "epic": epic,
            "direction": direction,
            "size": size_float
        }
        
        # Add stop-loss if provided
        if stop_loss_float is not None:
            payload["stopLevel"] = stop_loss_float
        
        # Add take-profit if provided
        if take_profit_float is not None:
            payload["profitLevel"] = take_profit_float
        
        # Add trailing stop if provided
        if trailing_stop_float is not None:
            payload["trailingStop"] = trailing_stop_float
        
        env_warning = "🔴 LIVE" if _is_live_environment() else "🟢 DEMO"
        risk_mgmt = f" with SL={stop_loss}" if stop_loss else ""
        risk_mgmt += f" TP={take_profit}" if take_profit else ""
        risk_mgmt += f" TS={trailing_stop}" if trailing_stop else ""
        logger.info(f"{env_warning} Placing market order: {direction} {size} {epic}{risk_mgmt}")
        
        response = _client.post(
            f"{BASE_URL}/api/v1/positions",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            deal_reference = data.get("dealReference", "N/A")
            
            result = f"""✅ Market Order Placed ({env_warning})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Deal Reference: {deal_reference}
Epic: {epic}
Direction: {direction}
Size: {size}"""
            
            if stop_loss_float is not None:
                result += f"\nStop Loss: {stop_loss}"
            if take_profit_float is not None:
                result += f"\nTake Profit: {take_profit}"
            if trailing_stop_float is not None:
                result += f"\nTrailing Stop: {trailing_stop}"
            
            result += "\n\nUse get_order_status with this deal reference to check execution status.\n"
            return result
        else:
            logger.error(f"Place order failed: {response.status_code}")
            return f"❌ Failed to place order: {response.status_code} - {response.text[:200]}"
            
    except httpx.TimeoutException:
        return "❌ Request timeout. Please try again."
    except Exception as e:
        logger.error(f"Place order error: {str(e)}")
        return f"❌ Error placing order: {str(e)}"


@mcp.tool()
def place_limit_order(epic: str = "", direction: str = "", size: str = "", limit_level: str = "", stop_loss: str = "", take_profit: str = "", trailing_stop: str = "", confirm_live_trade: str = "") -> str:
    """Place a limit order with optional stop-loss and take-profit levels."""
    epic = epic.strip()
    direction = direction.strip().upper()
    size = size.strip()
    limit_level = limit_level.strip()
    stop_loss = stop_loss.strip()
    take_profit = take_profit.strip()
    trailing_stop = trailing_stop.strip()
    confirm_live_trade = confirm_live_trade.strip().lower()
    
    # Validate parameters
    if not epic:
        return "❌ Epic parameter is required (e.g., 'EURUSD', 'US500')"
    
    if direction not in ["BUY", "SELL"]:
        return "❌ Direction must be 'BUY' or 'SELL'"
    
    if not size:
        return "❌ Size parameter is required (e.g., '1', '0.5')"
    
    if not limit_level:
        return "❌ Limit level (price) is required (e.g., '1.1000')"
    
    try:
        size_float = float(size)
        if size_float <= 0:
            return "❌ Size must be greater than 0"
    except ValueError:
        return f"❌ Invalid size value: {size}"
    
    try:
        limit_float = float(limit_level)
        if limit_float <= 0:
            return "❌ Limit level must be greater than 0"
    except ValueError:
        return f"❌ Invalid limit level value: {limit_level}"
    
    # Validate stop_loss if provided
    stop_loss_float = None
    if stop_loss:
        try:
            stop_loss_float = float(stop_loss)
            if stop_loss_float <= 0:
                return "❌ Stop loss must be greater than 0"
        except ValueError:
            return f"❌ Invalid stop loss value: {stop_loss}"
    
    # Validate take_profit if provided
    take_profit_float = None
    if take_profit:
        try:
            take_profit_float = float(take_profit)
            if take_profit_float <= 0:
                return "❌ Take profit must be greater than 0"
        except ValueError:
            return f"❌ Invalid take profit value: {take_profit}"
    
    # Validate trailing_stop if provided
    trailing_stop_float = None
    if trailing_stop:
        try:
            trailing_stop_float = float(trailing_stop)
            if trailing_stop_float <= 0:
                return "❌ Trailing stop must be greater than 0"
        except ValueError:
            return f"❌ Invalid trailing stop value: {trailing_stop}"
    
    # Live trading safety check
    if _is_live_environment() and confirm_live_trade != "yes":
        return f"""⚠️  LIVE TRADING BLOCKED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You are attempting to place a LIVE limit order with REAL money:
• Epic: {epic}
• Direction: {direction}
• Size: {size}
• Limit Level: {limit_level}

This involves REAL FINANCIAL RISK!

To proceed, call this tool again with parameter:
confirm_live_trade="yes"

Stay in demo mode to practice without risk.
"""
    
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    try:
        _rate_limit()
        
        payload = {
            "epic": epic,
            "direction": direction,
            "size": size_float,
            "level": limit_float,
            "type": "LIMIT"
        }
        
        # Add stop-loss if provided
        if stop_loss_float is not None:
            payload["stopLevel"] = stop_loss_float
        
        # Add take-profit if provided
        if take_profit_float is not None:
            payload["profitLevel"] = take_profit_float
        
        # Add trailing stop if provided
        if trailing_stop_float is not None:
            payload["trailingStop"] = trailing_stop_float
        
        env_warning = "🔴 LIVE" if _is_live_environment() else "🟢 DEMO"
        risk_mgmt = f" with SL={stop_loss}" if stop_loss else ""
        risk_mgmt += f" TP={take_profit}" if take_profit else ""
        risk_mgmt += f" TS={trailing_stop}" if trailing_stop else ""
        logger.info(f"{env_warning} Placing limit order: {direction} {size} {epic} @ {limit_level}{risk_mgmt}")
        
        response = _client.post(
            f"{BASE_URL}/api/v1/workingorders",
            json=payload,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            deal_reference = data.get("dealReference", "N/A")
            
            result = f"""✅ Limit Order Placed ({env_warning})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Deal Reference: {deal_reference}
Epic: {epic}
Direction: {direction}
Size: {size}
Limit Level: {limit_level}"""
            
            if stop_loss_float is not None:
                result += f"\nStop Loss: {stop_loss}"
            if take_profit_float is not None:
                result += f"\nTake Profit: {take_profit}"
            if trailing_stop_float is not None:
                result += f"\nTrailing Stop: {trailing_stop}"
            
            result += f"\n\nOrder will execute when market reaches {limit_level}.\nUse get_order_status with this deal reference to check status.\n"
            return result
        else:
            logger.error(f"Place limit order failed: {response.status_code}")
            return f"❌ Failed to place limit order: {response.status_code} - {response.text[:200]}"
            
    except httpx.TimeoutException:
        return "❌ Request timeout. Please try again."
    except Exception as e:
        logger.error(f"Place limit order error: {str(e)}")
        return f"❌ Error placing limit order: {str(e)}"


@mcp.tool()
def get_order_status(deal_reference: str = "") -> str:
    """Get the status of an order by deal reference."""
    deal_reference = deal_reference.strip()
    
    if not deal_reference:
        return "❌ Deal reference parameter is required"
    
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    try:
        _rate_limit()
        
        response = _client.get(
            f"{BASE_URL}/api/v1/confirms/{deal_reference}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            
            deal_status = data.get("dealStatus", "N/A")
            deal_id = data.get("dealId", "N/A")
            epic = data.get("epic", "N/A")
            status_reason = data.get("reason", "N/A")
            direction = data.get("direction", "N/A")
            size = data.get("size", "N/A")
            level = data.get("level", "N/A")
            profit_loss = data.get("profit", "N/A")
            
            status_emoji = "✅" if deal_status == "ACCEPTED" else "⏳" if deal_status == "PENDING" else "❌"
            
            return f"""{status_emoji} Order Status
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Deal Reference: {deal_reference}
Deal ID: {deal_id}
Status: {deal_status}
Reason: {status_reason}
Epic: {epic}
Direction: {direction}
Size: {size}
Level: {level}
P&L: {profit_loss}
"""
        elif response.status_code == 404:
            return f"❌ Deal reference not found: {deal_reference}"
        else:
            logger.error(f"Get order status failed: {response.status_code}")
            return f"❌ Failed to get order status: {response.status_code} - {response.text[:200]}"
            
    except httpx.TimeoutException:
        return "❌ Request timeout. Please try again."
    except Exception as e:
        logger.error(f"Get order status error: {str(e)}")
        return f"❌ Error getting order status: {str(e)}"


@mcp.tool()
def cancel_order(deal_id: str = "") -> str:
    """Cancel an open position or working order by deal ID."""
    deal_id = deal_id.strip()
    
    if not deal_id:
        return "❌ Deal ID parameter is required"
    
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    try:
        _rate_limit()
        
        env_warning = "🔴 LIVE" if _is_live_environment() else "🟢 DEMO"
        logger.info(f"{env_warning} Cancelling order/position: {deal_id}")
        
        response = _client.delete(
            f"{BASE_URL}/api/v1/positions/{deal_id}",
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            deal_reference = data.get("dealReference", "N/A")
            
            return f"""✅ Order Cancelled ({env_warning})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Deal ID: {deal_id}
Deal Reference: {deal_reference}

Use get_order_status with the deal reference to confirm cancellation.
"""
        elif response.status_code == 404:
            return f"❌ Deal ID not found: {deal_id}"
        else:
            logger.error(f"Cancel order failed: {response.status_code}")
            return f"❌ Failed to cancel order: {response.status_code} - {response.text[:200]}"
            
    except httpx.TimeoutException:
        return "❌ Request timeout. Please try again."
    except Exception as e:
        logger.error(f"Cancel order error: {str(e)}")
        return f"❌ Error cancelling order: {str(e)}"


@mcp.tool()
def poll_prices(epic_list: str = "", interval_seconds: str = "5", iterations: str = "10") -> str:
    """Poll prices for multiple instruments at regular intervals (non-streaming alternative)."""
    epic_list = epic_list.strip()
    interval_seconds = interval_seconds.strip()
    iterations = iterations.strip()
    
    if not epic_list:
        return "❌ Epic list parameter is required (comma-separated, e.g., 'EURUSD,US500,GOLD')"
    
    if not interval_seconds:
        interval_seconds = "5"
    
    if not iterations:
        iterations = "10"
    
    try:
        interval_int = int(interval_seconds)
        if interval_int < 1 or interval_int > 60:
            return "❌ Interval must be between 1 and 60 seconds"
    except ValueError:
        return f"❌ Invalid interval value: {interval_seconds}"
    
    try:
        iterations_int = int(iterations)
        if iterations_int < 1 or iterations_int > 100:
            return "❌ Iterations must be between 1 and 100"
    except ValueError:
        return f"❌ Invalid iterations value: {iterations}"
    
    # Parse epic list
    epics = [epic.strip() for epic in epic_list.split(",") if epic.strip()]
    
    if not epics:
        return "❌ No valid epics provided"
    
    if len(epics) > 10:
        return "❌ Maximum 10 instruments allowed for polling"
    
    # Ensure authenticated
    success, auth_msg = _authenticate()
    if not success:
        return auth_msg
    
    headers = _get_headers()
    if not headers:
        return "❌ Authentication headers missing"
    
    result = f"📊 Polling {len(epics)} instruments every {interval_int}s for {iterations_int} iterations\n"
    result += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    try:
        for i in range(iterations_int):
            result += f"[Iteration {i+1}/{iterations_int}]\n"
            
            for epic in epics:
                try:
                    _rate_limit()
                    
                    response = _client.get(
                        f"{BASE_URL}/api/v1/markets/{epic}",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        snapshot = data.get("snapshot", {})
                        
                        bid = snapshot.get("bid", "N/A")
                        offer = snapshot.get("offer", "N/A")
                        update_time = snapshot.get("updateTime", "N/A")
                        
                        result += f"  {epic}: Bid={bid} / Offer={offer} @ {update_time}\n"
                    else:
                        result += f"  {epic}: Error {response.status_code}\n"
                        
                except Exception as e:
                    result += f"  {epic}: Error - {str(e)}\n"
            
            result += "\n"
            
            # Sleep between iterations (except on last iteration)
            if i < iterations_int - 1:
                time.sleep(interval_int)
        
        result += "✅ Polling completed"
        return result
        
    except KeyboardInterrupt:
        result += "\n⚠️  Polling interrupted by user"
        return result
    except Exception as e:
        logger.error(f"Poll prices error: {str(e)}")
        return result + f"\n❌ Polling error: {str(e)}"


if __name__ == "__main__":
    # Log startup information
    logger.info(f"Starting Capital.com MCP Server in {CAP_ENVIRONMENT.upper()} mode")
    logger.info(f"Base URL: {BASE_URL}")
    
    if not _check_credentials():
        logger.warning("⚠️  Credentials not configured. Set CAP_API_KEY, CAP_IDENTIFIER, and CAP_PASSWORD environment variables.")
    
    if _is_live_environment():
        logger.warning("🔴 LIVE MODE ENABLED - REAL MONEY AT RISK!")
    else:
        logger.info("🟢 Demo mode - safe for testing")
    
    # Run the MCP server
    mcp.run()


