#!/usr/bin/env python3
"""
Context Builder for Contextual Bandit
Merges TA features, BSM context, regime features, and risk context
into a single feature vector for strategy selection
"""

import json
import sys
from typing import Dict, Any, List
from datetime import datetime


def get_time_bucket(timestamp: str = None) -> str:
    """Determine market time bucket"""
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else datetime.utcnow()
    hour = dt.hour
    minute = dt.minute
    
    # Market hours (approximate - adjust for your timezone)
    if hour < 9 or (hour == 9 and minute < 30):
        return "pre_market"
    elif hour < 12:
        return "morning"
    elif hour < 14:
        return "lunch"
    elif hour < 16:
        return "afternoon"
    elif hour < 20:
        return "after_hours"
    else:
        return "closed"


def get_day_of_week(timestamp: str = None) -> str:
    """Get day of week"""
    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00')) if timestamp else datetime.utcnow()
    days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    return days[dt.weekday()]


def extract_ta_features(indicators: Dict[str, Any]) -> Dict[str, float]:
    """Extract technical analysis features"""
    
    ta_features = {}
    
    # Price vs SMAs
    current_price = indicators.get('current_price', 0)
    sma_20 = indicators.get('indicators', {}).get('sma_20', 0)
    sma_50 = indicators.get('indicators', {}).get('sma_50', 0)
    
    if current_price > 0 and sma_20 > 0:
        ta_features['price_sma20_gap'] = (current_price - sma_20) / sma_20
    else:
        ta_features['price_sma20_gap'] = 0.0
    
    if current_price > 0 and sma_50 > 0:
        ta_features['price_sma50_gap'] = (current_price - sma_50) / sma_50
        ta_features['sma20_sma50_gap'] = (sma_20 - sma_50) / sma_50 if sma_20 > 0 else 0.0
    else:
        ta_features['price_sma50_gap'] = 0.0
        ta_features['sma20_sma50_gap'] = 0.0
    
    # RSI (already 0-100, normalize to 0-1)
    rsi = indicators.get('indicators', {}).get('rsi', 50)
    ta_features['rsi_normalized'] = rsi / 100.0
    ta_features['rsi_oversold'] = 1.0 if rsi < 30 else 0.0
    ta_features['rsi_overbought'] = 1.0 if rsi > 70 else 0.0
    
    # ATR (normalized by price)
    atr = indicators.get('indicators', {}).get('atr', 0)
    ta_features['atr_pct'] = (atr / current_price) if current_price > 0 else 0.0
    
    # VWAP
    vwap = indicators.get('indicators', {}).get('vwap', 0)
    if current_price > 0 and vwap > 0:
        ta_features['price_vwap_gap'] = (current_price - vwap) / vwap
    else:
        ta_features['price_vwap_gap'] = 0.0
    
    # Donchian position
    donchian = indicators.get('indicators', {}).get('donchian', {})
    upper = donchian.get('upper', 0)
    lower = donchian.get('lower', 0)
    
    if upper > 0 and lower > 0 and upper != lower:
        ta_features['donchian_position'] = (current_price - lower) / (upper - lower)
    else:
        ta_features['donchian_position'] = 0.5
    
    return ta_features


def extract_bsm_features(bsm_ctx: Dict[str, Any]) -> Dict[str, float]:
    """Extract BSM context features"""
    
    bsm_features = {}
    
    # IV rank (already 0-100, normalize)
    iv_rank = bsm_ctx.get('iv_rank', 50)
    bsm_features['iv_rank_normalized'] = iv_rank / 100.0
    
    # Regime flags
    bsm_features['high_iv_regime'] = 1.0 if bsm_ctx.get('high_iv', False) else 0.0
    bsm_features['low_iv_regime'] = 1.0 if bsm_ctx.get('low_iv', False) else 0.0
    
    # Volatility level
    vol_regime = bsm_ctx.get('vol_regime', 'normal')
    bsm_features['vol_regime_high'] = 1.0 if vol_regime == 'high' else 0.0
    bsm_features['vol_regime_low'] = 1.0 if vol_regime == 'low' else 0.0
    
    # Greeks (if available)
    bsm_features['vega'] = bsm_ctx.get('vega', 0.0)
    bsm_features['delta'] = abs(bsm_ctx.get('delta', 0.0))
    
    # Mispricing
    bsm_features['mispricing_proxy'] = bsm_ctx.get('mispricing_proxy', 0.0)
    
    return bsm_features


def extract_regime_features(timestamp: str = None) -> Dict[str, float]:
    """Extract time-based regime features"""
    
    time_bucket = get_time_bucket(timestamp)
    day = get_day_of_week(timestamp)
    
    regime_features = {
        # Time buckets (one-hot encoded)
        'time_pre_market': 1.0 if time_bucket == 'pre_market' else 0.0,
        'time_morning': 1.0 if time_bucket == 'morning' else 0.0,
        'time_lunch': 1.0 if time_bucket == 'lunch' else 0.0,
        'time_afternoon': 1.0 if time_bucket == 'afternoon' else 0.0,
        'time_after_hours': 1.0 if time_bucket == 'after_hours' else 0.0,
        
        # Day of week
        'day_monday': 1.0 if day == 'monday' else 0.0,
        'day_friday': 1.0 if day == 'friday' else 0.0,
        'day_midweek': 1.0 if day in ['tuesday', 'wednesday', 'thursday'] else 0.0,
    }
    
    return regime_features


def extract_risk_features(risk_context: Dict[str, Any]) -> Dict[str, float]:
    """Extract risk management features"""
    
    risk_features = {
        'recent_drawdown': risk_context.get('drawdown_pct', 0.0),
        'exposure_pct': risk_context.get('exposure_pct', 0.0),
        'open_positions': risk_context.get('open_positions', 0) / 10.0,  # Normalize
        'daily_loss_pct': risk_context.get('daily_loss_pct', 0.0),
        'trades_today': risk_context.get('trades_today', 0) / 20.0,  # Normalize
    }
    
    return risk_features


def build_context(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build complete context feature vector"""
    
    symbol = data.get('symbol', 'UNKNOWN')
    
    # Extract all feature groups
    ta_features = extract_ta_features(data.get('indicators', {}))
    bsm_features = extract_bsm_features(data.get('bsm_ctx', {}))
    regime_features = extract_regime_features(data.get('timestamp'))
    risk_features = extract_risk_features(data.get('risk_context', {}))
    
    # Merge all features
    context_features = {
        **ta_features,
        **bsm_features,
        **regime_features,
        **risk_features
    }
    
    # Create feature vector (ordered list for ML)
    feature_vector = [
        # TA features (8)
        context_features.get('price_sma20_gap', 0.0),
        context_features.get('price_sma50_gap', 0.0),
        context_features.get('sma20_sma50_gap', 0.0),
        context_features.get('rsi_normalized', 0.5),
        context_features.get('atr_pct', 0.0),
        context_features.get('price_vwap_gap', 0.0),
        context_features.get('donchian_position', 0.5),
        context_features.get('rsi_oversold', 0.0) + context_features.get('rsi_overbought', 0.0),
        
        # BSM features (7)
        context_features.get('iv_rank_normalized', 0.5),
        context_features.get('high_iv_regime', 0.0),
        context_features.get('low_iv_regime', 0.0),
        context_features.get('vega', 0.0),
        context_features.get('delta', 0.0),
        context_features.get('mispricing_proxy', 0.0),
        context_features.get('vol_regime_high', 0.0) + context_features.get('vol_regime_low', 0.0),
        
        # Regime features (8)
        context_features.get('time_morning', 0.0),
        context_features.get('time_lunch', 0.0),
        context_features.get('time_afternoon', 0.0),
        context_features.get('time_pre_market', 0.0) + context_features.get('time_after_hours', 0.0),
        context_features.get('day_monday', 0.0),
        context_features.get('day_friday', 0.0),
        context_features.get('day_midweek', 0.0),
        0.0,  # Reserved
        
        # Risk features (5)
        context_features.get('recent_drawdown', 0.0),
        context_features.get('exposure_pct', 0.0),
        context_features.get('open_positions', 0.0),
        context_features.get('daily_loss_pct', 0.0),
        context_features.get('trades_today', 0.0),
    ]
    
    return {
        "symbol": symbol,
        "context_features": context_features,
        "feature_vector": feature_vector,
        "feature_count": len(feature_vector),
        "timestamp": data.get('timestamp', datetime.utcnow().isoformat())
    }


def main():
    """Main entry point"""
    
    input_data = sys.stdin.read().strip()
    
    if not input_data:
        print(json.dumps({"error": "No input data provided"}))
        sys.exit(1)
    
    try:
        data = json.loads(input_data)
        
        # Handle both single object and array
        if isinstance(data, dict):
            result = build_context(data)
            print(json.dumps(result))
        
        elif isinstance(data, list):
            results = [build_context(item) for item in data]
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
