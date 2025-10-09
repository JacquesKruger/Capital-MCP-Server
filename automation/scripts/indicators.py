#!/usr/bin/env python3
"""
Technical Indicators Calculator
Computes SMA, RSI, ATR, VWAP, Donchian channels from candle data
Uses pure Python (no external TA libraries to avoid dependency issues)
"""

import json
import sys
from typing import List, Dict, Any
from statistics import mean


def calculate_sma(values: List[float], period: int) -> float:
    """Simple Moving Average"""
    if len(values) < period:
        return 0.0
    return mean(values[-period:])


def calculate_rsi(closes: List[float], period: int = 14) -> float:
    """Relative Strength Index"""
    if len(closes) < period + 1:
        return 50.0  # Neutral
    
    gains = []
    losses = []
    
    for i in range(1, len(closes)):
        change = closes[i] - closes[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    if len(gains) < period:
        return 50.0
    
    avg_gain = mean(gains[-period:])
    avg_loss = mean(losses[-period:])
    
    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 2)


def calculate_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> float:
    """Average True Range"""
    if len(highs) < period + 1:
        return 0.0
    
    true_ranges = []
    
    for i in range(1, len(highs)):
        high = highs[i]
        low = lows[i]
        prev_close = closes[i-1]
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        true_ranges.append(tr)
    
    if len(true_ranges) < period:
        return 0.0
    
    return round(mean(true_ranges[-period:]), 5)


def calculate_vwap(highs: List[float], lows: List[float], closes: List[float], volumes: List[float]) -> float:
    """Volume Weighted Average Price"""
    if not volumes or len(volumes) == 0:
        return 0.0
    
    typical_prices = [(h + l + c) / 3 for h, l, c in zip(highs, lows, closes)]
    
    pv_sum = sum(tp * v for tp, v in zip(typical_prices, volumes))
    v_sum = sum(volumes)
    
    if v_sum == 0:
        return 0.0
    
    return round(pv_sum / v_sum, 5)


def calculate_donchian(highs: List[float], lows: List[float], period: int = 20) -> Dict[str, float]:
    """Donchian Channels"""
    if len(highs) < period:
        return {"upper": 0.0, "lower": 0.0, "middle": 0.0}
    
    upper = max(highs[-period:])
    lower = min(lows[-period:])
    middle = (upper + lower) / 2
    
    return {
        "upper": round(upper, 5),
        "lower": round(lower, 5),
        "middle": round(middle, 5)
    }


def generate_signals(candles: List[Dict], symbol: str) -> Dict[str, Any]:
    """Generate trading signals from candles"""
    
    if len(candles) < 20:
        return {
            "symbol": symbol,
            "error": "Insufficient candle data (need at least 20)",
            "candles_count": len(candles)
        }
    
    # Extract OHLCV arrays
    opens = [c['open'] for c in candles]
    highs = [c['high'] for c in candles]
    lows = [c['low'] for c in candles]
    closes = [c['close'] for c in candles]
    volumes = [c['volume'] for c in candles]
    
    # Calculate indicators
    sma_20 = calculate_sma(closes, 20)
    sma_50 = calculate_sma(closes, 50) if len(closes) >= 50 else 0.0
    rsi = calculate_rsi(closes, 14)
    atr = calculate_atr(highs, lows, closes, 14)
    vwap = calculate_vwap(highs, lows, closes, volumes)
    donchian = calculate_donchian(highs, lows, 20)
    
    current_price = closes[-1]
    
    # Strategy 1: ORB + VWAP
    orb_vwap_signal = "NEUTRAL"
    orb_vwap_strength = 0.0
    
    if current_price > vwap and current_price > sma_20:
        orb_vwap_signal = "BUY"
        orb_vwap_strength = min(((current_price - vwap) / vwap) * 100, 1.0)
    elif current_price < vwap and current_price < sma_20:
        orb_vwap_signal = "SELL"
        orb_vwap_strength = min(((vwap - current_price) / vwap) * 100, 1.0)
    
    # Strategy 2: SMA + RSI + ATR
    sma_rsi_atr_signal = "NEUTRAL"
    sma_rsi_atr_strength = 0.0
    
    if sma_20 > 0 and sma_50 > 0:
        if current_price > sma_20 and sma_20 > sma_50 and rsi < 70:
            sma_rsi_atr_signal = "BUY"
            sma_rsi_atr_strength = (70 - rsi) / 70
        elif current_price < sma_20 and sma_20 < sma_50 and rsi > 30:
            sma_rsi_atr_signal = "SELL"
            sma_rsi_atr_strength = rsi / 100
    
    # Strategy 3: Donchian Breakout
    donchian_signal = "NEUTRAL"
    donchian_strength = 0.0
    
    if current_price >= donchian['upper']:
        donchian_signal = "BUY"
        donchian_strength = 0.8
    elif current_price <= donchian['lower']:
        donchian_signal = "SELL"
        donchian_strength = 0.8
    
    return {
        "symbol": symbol,
        "current_price": round(current_price, 5),
        "indicators": {
            "sma_20": round(sma_20, 5),
            "sma_50": round(sma_50, 5),
            "rsi": rsi,
            "atr": atr,
            "vwap": vwap,
            "donchian": donchian
        },
        "signals": {
            "ORB_VWAP": {
                "signal": orb_vwap_signal,
                "strength": round(orb_vwap_strength, 3),
                "confidence": 0.6 if orb_vwap_signal != "NEUTRAL" else 0.0
            },
            "SMA_RSI_ATR": {
                "signal": sma_rsi_atr_signal,
                "strength": round(sma_rsi_atr_strength, 3),
                "confidence": 0.7 if sma_rsi_atr_signal != "NEUTRAL" else 0.0
            },
            "DONCHIAN_BREAKOUT": {
                "signal": donchian_signal,
                "strength": round(donchian_strength, 3),
                "confidence": 0.75 if donchian_signal != "NEUTRAL" else 0.0
            }
        }
    }


def main():
    """Main entry point - reads candle data from stdin"""
    
    # Read input (JSON array of candle objects)
    input_data = sys.stdin.read().strip()
    
    if not input_data:
        print(json.dumps({"error": "No input data provided"}))
        sys.exit(1)
    
    try:
        data = json.loads(input_data)
        
        # Handle both single object and array
        if isinstance(data, dict):
            # Single symbol
            symbol = data.get('symbol', 'UNKNOWN')
            candles = data.get('candles', [])
            result = generate_signals(candles, symbol)
            print(json.dumps(result))
        
        elif isinstance(data, list):
            # Multiple symbols
            results = []
            for item in data:
                symbol = item.get('symbol', 'UNKNOWN')
                candles = item.get('candles', [])
                result = generate_signals(candles, symbol)
                results.append(result)
            print(json.dumps(results))
        
        else:
            print(json.dumps({"error": "Invalid input format"}))
            sys.exit(1)
    
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {str(e)}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Processing error: {str(e)}"}))
        sys.exit(1)


if __name__ == '__main__':
    main()
