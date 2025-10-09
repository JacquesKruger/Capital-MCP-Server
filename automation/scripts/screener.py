#!/usr/bin/env python3
"""
Dynamic Daily Watchlist Screener

Generates a ranked watchlist of symbols based on:
- ATR% (volatility)
- Overnight gaps
- Range compression (Bollinger Band squeeze proxy)
- Liquidity metrics
- News sentiment

No internet dependencies - works entirely from database data.
"""

import sys
import json
import psycopg2
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import math


def load_config(config_path: str = '/app/config/watchlist_rules.yaml') -> dict:
    """Load watchlist rules from YAML config"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}", file=sys.stderr)
        sys.exit(1)


def get_db_connection() -> psycopg2.extensions.connection:
    """Get PostgreSQL connection"""
    import os
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'trading-db'),
        port=int(os.getenv('POSTGRES_PORT', '5432')),
        database=os.getenv('POSTGRES_DB', 'trading'),
        user=os.getenv('POSTGRES_USER', 'trader'),
        password=os.getenv('POSTGRES_PASSWORD', '')
    )


def classify_instrument(symbol: str, epic: str, exchange: str) -> str:
    """Classify instrument into asset class"""
    symbol_upper = symbol.upper()
    epic_upper = (epic or '').upper()
    exchange_upper = (exchange or '').upper()
    
    # Crypto
    if 'BTC' in symbol_upper or 'ETH' in symbol_upper or exchange_upper == 'CRYPTO':
        return 'crypto'
    
    # Forex
    if len(symbol) == 6 and any(c in symbol_upper for c in ['USD', 'EUR', 'GBP', 'JPY', 'AUD', 'NZD', 'CAD', 'CHF']):
        return 'forex'
    
    # Metals
    if 'XAU' in symbol_upper or 'XAG' in symbol_upper or 'GOLD' in symbol_upper or 'SILVER' in symbol_upper:
        return 'metals'
    
    # Indices
    if any(idx in symbol_upper for idx in ['SPX', 'NDX', 'DJI', 'DAX', 'FTSE', 'CAC', 'NIKKEI']):
        return 'indices'
    
    # Default to stocks
    return 'stocks'


def calculate_atr_pct(candles: List[tuple], period: int = 14) -> float:
    """Calculate ATR as percentage of price"""
    if len(candles) < period + 1:
        return 0.0
    
    trs = []
    for i in range(1, len(candles)):
        high = candles[i][3]  # high
        low = candles[i][4]   # low
        prev_close = candles[i-1][5]  # prev close
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        trs.append(tr)
    
    if not trs or len(trs) < period:
        return 0.0
    
    atr = sum(trs[-period:]) / period
    current_price = candles[-1][5]  # latest close
    
    if current_price == 0:
        return 0.0
    
    return (atr / current_price) * 100


def calculate_gap_pct(candles: List[tuple]) -> float:
    """Calculate overnight gap percentage"""
    if len(candles) < 2:
        return 0.0
    
    prev_close = candles[-2][5]  # previous close
    current_open = candles[-1][2]  # current open
    
    if prev_close == 0:
        return 0.0
    
    gap_pct = ((current_open - prev_close) / prev_close) * 100
    return gap_pct


def calculate_compression(candles: List[tuple], lookback: int = 20) -> float:
    """
    Calculate price compression (0-1 scale)
    Higher = more compressed (tight range, potential breakout)
    Uses ratio of recent range to historical ATR
    """
    if len(candles) < lookback + 1:
        return 0.0
    
    recent_candles = candles[-lookback:]
    highs = [c[3] for c in recent_candles]
    lows = [c[4] for c in recent_candles]
    
    recent_range = max(highs) - min(lows)
    avg_price = sum([c[5] for c in recent_candles]) / len(recent_candles)
    
    if avg_price == 0:
        return 0.0
    
    range_pct = (recent_range / avg_price) * 100
    
    # Calculate historical ATR for comparison
    atr_pct = calculate_atr_pct(candles, period=14)
    
    if atr_pct == 0:
        return 0.0
    
    # Compression score: lower range relative to ATR = higher compression
    compression = 1.0 - min(range_pct / (atr_pct * 2), 1.0)
    return max(0.0, min(1.0, compression))


def calculate_liquidity_score(candles: List[tuple], lookback: int = 10) -> float:
    """
    Calculate liquidity score (0-1 scale)
    Based on volume consistency and average volume
    """
    if len(candles) < lookback:
        return 0.5  # Default mid-range
    
    recent_candles = candles[-lookback:]
    volumes = [c[6] for c in recent_candles if c[6] > 0]
    
    if not volumes:
        return 0.5
    
    avg_vol = sum(volumes) / len(volumes)
    
    # Volume consistency (lower std dev = higher score)
    if len(volumes) > 1:
        vol_std = math.sqrt(sum((v - avg_vol) ** 2 for v in volumes) / len(volumes))
        consistency = 1.0 - min(vol_std / avg_vol if avg_vol > 0 else 1.0, 1.0)
    else:
        consistency = 0.5
    
    # Normalize to 0-1 range
    return max(0.0, min(1.0, consistency))


def get_sentiment_score(conn, symbol: str, decay_hours: int = 12) -> float:
    """
    Get aggregated sentiment score for symbol (-1 to 1)
    Applies time decay to older sentiment data
    """
    cursor = conn.cursor()
    
    cutoff_time = datetime.now() - timedelta(hours=decay_hours * 2)
    
    # Get news sentiment
    cursor.execute("""
        SELECT sentiment, published_at 
        FROM news 
        WHERE symbol = %s 
          AND published_at > %s 
          AND sentiment IS NOT NULL
        ORDER BY published_at DESC
        LIMIT 50
    """, (symbol, cutoff_time))
    
    news_items = cursor.fetchall()
    
    if not news_items:
        return 0.0
    
    weighted_sentiment = 0.0
    total_weight = 0.0
    now = datetime.now()
    
    for sentiment, published_at in news_items:
        # Calculate time decay
        age_hours = (now - published_at).total_seconds() / 3600
        decay_factor = math.exp(-age_hours / decay_hours)
        
        weighted_sentiment += sentiment * decay_factor
        total_weight += decay_factor
    
    if total_weight == 0:
        return 0.0
    
    return weighted_sentiment / total_weight


def normalize_scores(scores: List[float], method: str = 'minmax_clip') -> List[float]:
    """Normalize scores to 0-1 range"""
    if not scores:
        return []
    
    if method == 'minmax_clip':
        min_val = min(scores)
        max_val = max(scores)
        
        if max_val == min_val:
            return [0.5] * len(scores)
        
        return [(s - min_val) / (max_val - min_val) for s in scores]
    
    elif method == 'zscore_clip':
        mean = sum(scores) / len(scores)
        std = math.sqrt(sum((s - mean) ** 2 for s in scores) / len(scores))
        
        if std == 0:
            return [0.5] * len(scores)
        
        # Z-score, then clip to -3 to 3 and normalize to 0-1
        z_scores = [(s - mean) / std for s in scores]
        clipped = [max(-3, min(3, z)) for z in z_scores]
        return [(z + 3) / 6 for z in clipped]
    
    return scores


def calculate_composite_score(metrics: dict, weights: dict, class_config: dict) -> Tuple[float, List[str]]:
    """
    Calculate weighted composite score and generate reasons
    Returns (score, reasons_list)
    """
    score = 0.0
    reasons = []
    
    # ATR (volatility)
    if 'atr_pct' in weights and metrics.get('atr_pct', 0) > 0:
        atr_score = metrics.get('atr_pct_norm', 0)
        score += weights['atr_pct'] * atr_score
        if atr_score > 0.7:
            reasons.append('high_volatility')
    
    # Gap
    if 'gap' in weights:
        gap_score = metrics.get('gap_norm', 0)
        score += weights['gap'] * gap_score
        if abs(metrics.get('gap_pct', 0)) > class_config.get('gap_abs_min_pct', 0.5):
            direction = 'up' if metrics.get('gap_pct', 0) > 0 else 'down'
            reasons.append(f'gap_{direction}')
    
    # Compression
    if 'compression' in weights:
        comp_score = metrics.get('compression', 0)
        score += weights['compression'] * comp_score
        if comp_score > 0.7:
            reasons.append('compressed_range')
    
    # Liquidity
    if 'liquidity' in weights:
        liq_score = metrics.get('liquidity', 0)
        score += weights['liquidity'] * liq_score
        if liq_score > 0.8:
            reasons.append('high_liquidity')
    
    # Sentiment
    if 'sentiment' in weights:
        sent_score = (metrics.get('sentiment', 0) + 1) / 2  # Convert -1..1 to 0..1
        score += weights['sentiment'] * sent_score
        if metrics.get('sentiment', 0) > 0.3:
            reasons.append('positive_sentiment')
        elif metrics.get('sentiment', 0) < -0.3:
            reasons.append('negative_sentiment')
    
    return score, reasons


def screen_symbols(config: dict) -> dict:
    """
    Main screening function
    Returns dict with watchlist data per asset class
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get today's date string
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Get all enabled instruments
    cursor.execute("""
        SELECT symbol, epic, name, exchange
        FROM instruments
        WHERE enabled = true
        ORDER BY priority DESC, symbol
    """)
    
    instruments = cursor.fetchall()
    
    # Group by asset class
    by_class = {}
    
    for symbol, epic, name, exchange in instruments:
        asset_class = classify_instrument(symbol, epic, exchange)
        
        if asset_class not in by_class:
            by_class[asset_class] = []
        
        # Get candle data (last 100 daily candles)
        cursor.execute("""
            SELECT symbol, tf, ts, open, high, low, close, volume
            FROM candles
            WHERE symbol = %s AND tf = '1d'
            ORDER BY ts DESC
            LIMIT 100
        """, (symbol,))
        
        candles = cursor.fetchall()
        
        if len(candles) < config['filters'].get('require_min_candles', 50):
            continue
        
        # Reverse to chronological order
        candles = list(reversed(candles))
        
        # Calculate metrics
        atr_pct = calculate_atr_pct(candles)
        gap_pct = calculate_gap_pct(candles)
        compression = calculate_compression(candles, config['scoring']['compression_lookback'])
        liquidity = calculate_liquidity_score(candles, config['scoring']['liquidity_lookback_days'])
        sentiment = get_sentiment_score(conn, symbol, config['sentiment']['decay_hours']) if config['sentiment']['enabled'] else 0.0
        
        # Store metrics
        metrics = {
            'symbol': symbol,
            'name': name,
            'atr_pct': atr_pct,
            'gap_pct': gap_pct,
            'compression': compression,
            'liquidity': liquidity,
            'sentiment': sentiment,
            'last_close': candles[-1][5] if candles else 0.0
        }
        
        by_class[asset_class].append(metrics)
    
    # Process each asset class
    results = {}
    
    for asset_class, candidates in by_class.items():
        if asset_class not in config['classes']:
            continue
        
        class_config = config['classes'][asset_class]
        
        # Filter by thresholds
        filtered = []
        for m in candidates:
            if m['atr_pct'] < class_config['atr_pct_min']:
                continue
            if m['liquidity'] < class_config['min_liquidity_score']:
                continue
            filtered.append(m)
        
        if not filtered:
            results[asset_class] = []
            continue
        
        # Normalize metrics
        atr_scores = [m['atr_pct'] for m in filtered]
        gap_scores = [abs(m['gap_pct']) for m in filtered]
        
        atr_norm = normalize_scores(atr_scores, config['scoring']['normalize_method'])
        gap_norm = normalize_scores(gap_scores, config['scoring']['normalize_method'])
        
        for i, m in enumerate(filtered):
            m['atr_pct_norm'] = atr_norm[i]
            m['gap_norm'] = gap_norm[i]
        
        # Calculate composite scores
        for m in filtered:
            score, reasons = calculate_composite_score(m, class_config['weights'], class_config)
            m['score'] = score
            m['reasons'] = reasons
        
        # Sort by score and take top N
        filtered.sort(key=lambda x: x['score'], reverse=True)
        top_n = class_config['top_n']
        results[asset_class] = filtered[:top_n]
    
    conn.close()
    return {
        'generated_at': datetime.now().isoformat(),
        'day': today,
        'watchlist': results
    }


def save_to_database(data: dict):
    """Save watchlist to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    day = data['day']
    
    # Clear existing watchlist for today
    cursor.execute("DELETE FROM watchlist_daily WHERE day = %s", (day,))
    
    # Insert new watchlist
    for asset_class, symbols in data['watchlist'].items():
        for rank, symbol_data in enumerate(symbols, 1):
            metrics_json = json.dumps({
                'atr_pct': symbol_data['atr_pct'],
                'gap_pct': symbol_data['gap_pct'],
                'compression': symbol_data['compression'],
                'liquidity': symbol_data['liquidity'],
                'sentiment': symbol_data['sentiment'],
                'last_close': symbol_data['last_close']
            })
            
            reasons = ','.join(symbol_data['reasons'])
            
            cursor.execute("""
                INSERT INTO watchlist_daily 
                (day, asset_class, symbol, rank, score, reasons, metrics_json, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            """, (day, asset_class, symbol_data['symbol'], rank, symbol_data['score'], 
                  reasons, metrics_json))
    
    conn.commit()
    conn.close()


def format_output(data: dict, config: dict) -> str:
    """Format watchlist for output"""
    if config['output']['format'] == 'json':
        return json.dumps(data, indent=2)
    
    # Text format
    output = []
    output.append(f"📊 Daily Watchlist - {data['day']}")
    output.append("=" * 60)
    
    for asset_class, symbols in data['watchlist'].items():
        if not symbols:
            continue
        
        output.append(f"\n{asset_class.upper()}")
        output.append("-" * 40)
        
        for rank, s in enumerate(symbols, 1):
            reasons_str = ', '.join(s['reasons']) if s['reasons'] else 'no specific reasons'
            output.append(f"{rank}. {s['symbol']:<10} Score: {s['score']:.3f}")
            output.append(f"   {reasons_str}")
            
            if config['output']['include_metrics']:
                output.append(f"   ATR: {s['atr_pct']:.2f}% | Gap: {s['gap_pct']:+.2f}% | "
                             f"Comp: {s['compression']:.2f} | Liq: {s['liquidity']:.2f}")
    
    return '\n'.join(output)


def main():
    """Main entry point"""
    # Load configuration
    config = load_config()
    
    # Screen symbols
    watchlist_data = screen_symbols(config)
    
    # Save to database
    save_to_database(watchlist_data)
    
    # Output results
    output = format_output(watchlist_data, config)
    print(output)
    
    # Also output JSON for n8n workflow
    if config['output']['format'] != 'json':
        print("\n" + "=" * 60)
        print(json.dumps(watchlist_data))


if __name__ == '__main__':
    main()

