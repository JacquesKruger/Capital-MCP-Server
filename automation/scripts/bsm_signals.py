#!/usr/bin/env python3
"""
BSM Signals Generator
Converts Black-Scholes-Merton metrics into analysis-only context features
Generates proxy signals when real options data is unavailable
"""

import json
import sys
from typing import Dict, Any, List
from statistics import stdev, mean


def calculate_realized_volatility(closes: List[float], period: int = 20) -> float:
    """Calculate realized volatility from price history"""
    if len(closes) < period + 1:
        return 0.0
    
    returns = []
    for i in range(1, min(len(closes), period + 1)):
        ret = (closes[i] - closes[i-1]) / closes[i-1]
        returns.append(ret)
    
    if len(returns) < 2:
        return 0.0
    
    # Annualized volatility
    daily_vol = stdev(returns)
    annual_vol = daily_vol * (252 ** 0.5)
    
    return round(annual_vol, 4)


def calculate_iv_rank(current_iv: float, iv_history: List[float]) -> float:
    """Calculate IV rank (0-100 scale)"""
    if not iv_history or len(iv_history) < 2:
        return 50.0  # Neutral if no history
    
    iv_min = min(iv_history)
    iv_max = max(iv_history)
    
    if iv_max == iv_min:
        return 50.0
    
    rank = ((current_iv - iv_min) / (iv_max - iv_min)) * 100
    return round(rank, 2)


def generate_proxy_signal(
    symbol: str,
    candles: List[Dict],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate BSM proxy signal from realized volatility when options data unavailable"""
    
    if len(candles) < 20:
        return {
            "symbol": symbol,
            "mode": "proxy",
            "error": "Insufficient candle data for volatility calculation"
        }
    
    closes = [c['close'] for c in candles]
    
    # Calculate realized volatility
    realized_vol = calculate_realized_volatility(closes, period=20)
    
    # Apply bias from config (options usually trade at premium to realized)
    vol_bias = config.get('proxy_vol_bias', 1.10)
    proxy_iv = realized_vol * vol_bias
    
    # Calculate IV rank using recent volatility history
    vol_history = []
    for i in range(max(0, len(closes) - 252), len(closes), 20):
        if i + 20 <= len(closes):
            segment = closes[i:i+20]
            vol_history.append(calculate_realized_volatility(segment, 20))
    
    iv_rank = calculate_iv_rank(proxy_iv, vol_history) if vol_history else 50.0
    
    # Determine regime flags
    high_iv = iv_rank > 70
    low_iv = iv_rank < 30
    
    # Simple mispricing proxy (mean reversion assumption)
    # High IV rank suggests options overpriced (sell premium)
    # Low IV rank suggests options underpriced (buy premium)
    mispricing_score = (iv_rank - 50) / 50  # -1 to +1
    
    return {
        "symbol": symbol,
        "mode": "proxy",
        "bsm_ctx": {
            "proxy_iv": proxy_iv,
            "realized_vol": realized_vol,
            "iv_rank": iv_rank,
            "high_iv": high_iv,
            "low_iv": low_iv,
            "vol_regime": "high" if high_iv else ("low" if low_iv else "normal"),
            "mispricing_proxy": round(mispricing_score, 3)
        },
        "signal": "bsm_proxy",
        "score": abs(mispricing_score),
        "notes": f"Proxy IV rank {iv_rank:.1f}, realized vol {realized_vol:.2%}"
    }


def generate_bsm_context(
    symbol: str,
    options_data: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate BSM context from real options data"""
    
    iv = options_data.get('implied_volatility', 0)
    greeks = options_data.get('greeks', {})
    mispricing = options_data.get('mispricing', 0)
    vega = greeks.get('vega', 0)
    
    # Calculate IV rank if history provided
    iv_history = options_data.get('iv_history', [])
    iv_rank = calculate_iv_rank(iv, iv_history) if iv_history else 50.0
    
    # Determine regime
    high_iv = iv_rank > config.get('high_iv_threshold', 70)
    low_iv = iv_rank < config.get('low_iv_threshold', 30)
    
    # Mispricing score (normalized by vega)
    mispricing_vega_ratio = abs(mispricing) / vega if vega > config.get('min_vega', 0.02) else 0
    significant_mispricing = mispricing_vega_ratio > config.get('mispricing_threshold', 0.1)
    
    return {
        "symbol": symbol,
        "mode": "real",
        "bsm_ctx": {
            "iv": iv,
            "iv_rank": iv_rank,
            "high_iv": high_iv,
            "low_iv": low_iv,
            "vol_regime": "high" if high_iv else ("low" if low_iv else "normal"),
            "delta": greeks.get('delta', 0),
            "gamma": greeks.get('gamma', 0),
            "vega": vega,
            "theta": greeks.get('theta', 0),
            "rho": greeks.get('rho', 0),
            "mispricing": mispricing,
            "mispricing_vega_ratio": round(mispricing_vega_ratio, 3),
            "significant_mispricing": significant_mispricing
        },
        "signal": "bsm_analysis",
        "score": mispricing_vega_ratio,
        "notes": f"IV rank {iv_rank:.1f}, mispricing/vega {mispricing_vega_ratio:.2f}"
    }


def process_input(data: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single symbol's BSM signal"""
    
    symbol = data.get('symbol', 'UNKNOWN')
    mode = data.get('mode', 'proxy')
    
    if mode == 'proxy':
        # Generate proxy from candle data
        candles = data.get('candles', [])
        return generate_proxy_signal(symbol, candles, config)
    
    else:
        # Generate from real options data
        options_data = data.get('options_data', {})
        return generate_bsm_context(symbol, options_data, config)


def main():
    """Main entry point"""
    
    input_data = sys.stdin.read().strip()
    
    if not input_data:
        print(json.dumps({"error": "No input data provided"}))
        sys.exit(1)
    
    try:
        input_json = json.loads(input_data)
        
        # Extract config (can be passed in input or use defaults)
        config = input_json.get('config', {
            'proxy_vol_bias': 1.10,
            'high_iv_threshold': 70,
            'low_iv_threshold': 30,
            'min_vega': 0.02,
            'mispricing_threshold': 0.1
        })
        
        # Handle both single object and array
        data_items = input_json.get('data', input_json)
        
        if isinstance(data_items, dict):
            result = process_input(data_items, config)
            print(json.dumps(result))
        
        elif isinstance(data_items, list):
            results = [process_input(item, config) for item in data_items]
            print(json.dumps(results))
        
        else:
            print(json.dumps({"error": "Invalid input format"}))
            sys.exit(1)
    
    except (json.JSONDecodeError, ValueError) as e:
        print(json.dumps({"error": f"Input error: {str(e)}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Processing error: {str(e)}"}))
        sys.exit(1)


if __name__ == '__main__':
    main()
