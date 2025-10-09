#!/usr/bin/env python3
"""
Position Sizing Calculator

Calculates position size in USD based on:
- Available capital
- Risk tolerance (max % of capital to risk)
- Stop-loss distance
- Reserve requirements

Philosophy:
- Always keep 60% of capital in reserve (minimum)
- Size positions so that stop-loss hit = acceptable loss
- Position size = (Risk Amount) / (Stop Distance %)
"""

import sys
import json
from typing import Dict, Any


def calculate_position_size(
    available_capital: float,
    current_price: float,
    stop_loss_pct: float,
    max_risk_pct: float = 0.02,  # 2% of capital per trade
    min_reserve_pct: float = 0.60,  # 60% reserve minimum
    instrument_type: str = 'forex',
    size_multiplier: float = 1.0  # Bandit size multiplier
) -> Dict[str, Any]:
    """
    Calculate position size ensuring reserve requirements
    
    Args:
        available_capital: Current available USD
        current_price: Entry price for instrument
        stop_loss_pct: Stop-loss distance as % (e.g., 0.02 = 2%)
        max_risk_pct: Max % of capital to risk (default 2%)
        min_reserve_pct: Minimum % to keep in reserve (default 60%)
        instrument_type: 'forex', 'crypto', 'stocks', 'indices', 'metals'
    
    Returns:
        Dict with position_size_usd, position_size_units, risk_amount, etc.
    """
    
    # Calculate maximum deployable capital (40% of available = 100% - 60% reserve)
    max_deployable = available_capital * (1 - min_reserve_pct)
    
    # Calculate risk amount (2% of total capital) with size multiplier
    risk_amount = available_capital * max_risk_pct * size_multiplier
    
    # Calculate position size based on stop-loss distance
    # Position Size = Risk Amount / (Stop Distance % × Price)
    # This ensures if stop is hit, we lose exactly risk_amount
    if stop_loss_pct <= 0:
        stop_loss_pct = 0.02  # Default 2% stop if not provided
    
    # For position sizing, we need to calculate how many units we can buy
    # with the risk amount, given the stop distance
    stop_loss_distance_usd = current_price * stop_loss_pct
    position_size_units = risk_amount / stop_loss_distance_usd
    position_size_usd = position_size_units * current_price
    
    # Cap position size at max deployable (respect 60% reserve)
    if position_size_usd > max_deployable:
        position_size_usd = max_deployable
        position_size_units = position_size_usd / current_price
        # Recalculate actual risk with capped position
        actual_risk = position_size_usd * stop_loss_pct
    else:
        actual_risk = risk_amount
    
    # Adjust for instrument-specific lot sizing
    min_size, size_increment = get_instrument_constraints(instrument_type)
    position_size_units = round_to_increment(position_size_units, size_increment)
    
    # Ensure minimum size
    if position_size_units < min_size:
        position_size_units = min_size
    
    # Recalculate USD position with rounded units
    final_position_usd = position_size_units * current_price
    final_risk_usd = final_position_usd * stop_loss_pct
    
    # Calculate metrics
    risk_reward_ratio = 2.0  # Default 2:1 target
    take_profit_pct = stop_loss_pct * risk_reward_ratio
    take_profit_usd = final_position_usd * take_profit_pct
    
    capital_after_position = available_capital - final_position_usd
    reserve_pct_after = capital_after_position / available_capital if available_capital > 0 else 0
    
    return {
        'position_size_usd': round(final_position_usd, 2),
        'position_size_units': round(position_size_units, 4),
        'risk_amount_usd': round(final_risk_usd, 2),
        'risk_pct_of_capital': round((final_risk_usd / available_capital) * 100, 2) if available_capital > 0 else 0,
        'stop_loss_pct': round(stop_loss_pct * 100, 2),
        'take_profit_pct': round(take_profit_pct * 100, 2),
        'take_profit_usd': round(take_profit_usd, 2),
        'reserve_after_entry': round(capital_after_position, 2),
        'reserve_pct_after_entry': round(reserve_pct_after * 100, 2),
        'max_deployable': round(max_deployable, 2),
        'meets_reserve_requirement': reserve_pct_after >= min_reserve_pct,
        'warnings': get_warnings(
            reserve_pct_after, 
            final_risk_usd, 
            available_capital, 
            position_size_units, 
            min_size
        )
    }


def get_instrument_constraints(instrument_type: str) -> tuple:
    """
    Get minimum size and increment for instrument type
    
    Returns (min_size, increment)
    """
    constraints = {
        'forex': (0.01, 0.01),      # Min 0.01 lots (1000 units)
        'crypto': (0.001, 0.001),   # Min 0.001 BTC
        'stocks': (1, 1),           # Min 1 share
        'indices': (0.1, 0.1),      # Min 0.1 contracts
        'metals': (0.01, 0.01)      # Min 0.01 oz
    }
    return constraints.get(instrument_type, (0.01, 0.01))


def round_to_increment(value: float, increment: float) -> float:
    """Round value to nearest increment"""
    if increment <= 0:
        return value
    return round(value / increment) * increment


def get_warnings(
    reserve_pct: float, 
    risk_usd: float, 
    capital: float,
    position_units: float,
    min_units: float
) -> list:
    """Generate warnings about the position"""
    warnings = []
    
    if reserve_pct < 0.60:
        warnings.append(f'Reserve too low: {reserve_pct*100:.1f}% (need 60% minimum)')
    
    if risk_usd > capital * 0.05:
        warnings.append(f'Risk too high: {risk_usd:.2f} USD ({risk_usd/capital*100:.1f}% of capital)')
    
    if position_units < min_units:
        warnings.append(f'Position below minimum size: {position_units} units (min: {min_units})')
    
    return warnings


def main():
    """
    Main entry point - reads JSON from stdin
    
    Expected input:
    {
        "available_capital": 10000,
        "current_price": 1.0850,
        "stop_loss_pct": 0.015,
        "instrument_type": "forex"
    }
    """
    try:
        data = json.load(sys.stdin)
        
        result = calculate_position_size(
            available_capital=float(data.get('available_capital', 0)),
            current_price=float(data.get('current_price', 0)),
            stop_loss_pct=float(data.get('stop_loss_pct', 0.02)),
            max_risk_pct=float(data.get('max_risk_pct', 0.02)),
            min_reserve_pct=float(data.get('min_reserve_pct', 0.60)),
            instrument_type=data.get('instrument_type', 'forex'),
            size_multiplier=float(data.get('size_multiplier', 1.0))
        )
        
        print(json.dumps(result, indent=2))
        return 0
        
    except Exception as e:
        error_result = {
            'error': str(e),
            'position_size_usd': 0,
            'position_size_units': 0,
            'warnings': [f'Calculation failed: {str(e)}']
        }
        print(json.dumps(error_result, indent=2))
        return 1


if __name__ == '__main__':
    sys.exit(main())

