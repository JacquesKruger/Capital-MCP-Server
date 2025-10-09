#!/usr/bin/env python3
"""
Black-Scholes-Merton Options Pricing Model
Calculates theoretical option prices and Greeks (Delta, Gamma, Vega, Theta, Rho)
Pure Python implementation - no external dependencies
"""

import json
import sys
import math
from typing import Dict, Any, Tuple


def norm_cdf(x: float) -> float:
    """Cumulative distribution function for standard normal distribution"""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def norm_pdf(x: float) -> float:
    """Probability density function for standard normal distribution"""
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black_scholes_price(
    S: float,  # Current stock price
    K: float,  # Strike price
    T: float,  # Time to expiration (years)
    r: float,  # Risk-free rate
    sigma: float,  # Volatility
    option_type: str = "call"  # "call" or "put"
) -> float:
    """Calculate Black-Scholes option price"""
    
    # Handle edge cases
    if T <= 0:
        if option_type.lower() == "call":
            return max(S - K, 0)
        else:
            return max(K - S, 0)
    
    if sigma <= 0:
        return 0.0
    
    # Clamp extreme values
    sigma = min(max(sigma, 0.01), 5.0)
    T = max(T, 0.001)
    
    # Calculate d1 and d2
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    if option_type.lower() == "call":
        price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:  # put
        price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    
    return max(price, 0.0)


def calculate_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: str = "call"
) -> Dict[str, float]:
    """Calculate option Greeks"""
    
    if T <= 0 or sigma <= 0:
        return {
            "delta": 0.0,
            "gamma": 0.0,
            "vega": 0.0,
            "theta": 0.0,
            "rho": 0.0
        }
    
    # Clamp values
    sigma = min(max(sigma, 0.01), 5.0)
    T = max(T, 0.001)
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    # Delta
    if option_type.lower() == "call":
        delta = norm_cdf(d1)
    else:
        delta = norm_cdf(d1) - 1
    
    # Gamma (same for call and put)
    gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
    
    # Vega (same for call and put) - per 1% change in volatility
    vega = S * norm_pdf(d1) * math.sqrt(T) / 100
    
    # Theta (per day)
    if option_type.lower() == "call":
        theta = (
            -S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * norm_cdf(d2)
        ) / 365
    else:
        theta = (
            -S * norm_pdf(d1) * sigma / (2 * math.sqrt(T))
            + r * K * math.exp(-r * T) * norm_cdf(-d2)
        ) / 365
    
    # Rho (per 1% change in interest rate)
    if option_type.lower() == "call":
        rho = K * T * math.exp(-r * T) * norm_cdf(d2) / 100
    else:
        rho = -K * T * math.exp(-r * T) * norm_cdf(-d2) / 100
    
    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "vega": round(vega, 4),
        "theta": round(theta, 4),
        "rho": round(rho, 4)
    }


def implied_volatility(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: str = "call",
    max_iter: int = 100,
    tol: float = 1e-6
) -> float:
    """Calculate implied volatility using Newton-Raphson method"""
    
    if T <= 0 or price <= 0:
        return 0.0
    
    # Initial guess (Brenner-Subrahmanyam approximation)
    sigma = math.sqrt(2 * math.pi / T) * price / S
    sigma = max(min(sigma, 5.0), 0.01)
    
    for _ in range(max_iter):
        try:
            # Calculate price and vega with current sigma
            calc_price = black_scholes_price(S, K, T, r, sigma, option_type)
            greeks = calculate_greeks(S, K, T, r, sigma, option_type)
            vega = greeks["vega"] * 100  # Convert back to full vega
            
            # Check convergence
            diff = calc_price - price
            if abs(diff) < tol:
                return round(sigma, 4)
            
            # Newton-Raphson step
            if vega > 1e-10:
                sigma = sigma - diff / vega
                sigma = max(min(sigma, 5.0), 0.01)  # Clamp
            else:
                break
                
        except (ValueError, ZeroDivisionError):
            break
    
    # If Newton-Raphson fails, try bisection
    sigma_low, sigma_high = 0.01, 5.0
    
    for _ in range(50):
        sigma_mid = (sigma_low + sigma_high) / 2
        price_mid = black_scholes_price(S, K, T, r, sigma_mid, option_type)
        
        if abs(price_mid - price) < tol:
            return round(sigma_mid, 4)
        
        if price_mid < price:
            sigma_low = sigma_mid
        else:
            sigma_high = sigma_mid
    
    return round((sigma_low + sigma_high) / 2, 4)


def process_option(data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single option calculation"""
    
    mode = data.get('mode', 'full')  # price, iv, or full
    S = float(data.get('S', 0))
    K = float(data.get('K', 0))
    T = float(data.get('T', 0))
    r = float(data.get('r', 0.04))
    option_type = data.get('type', 'call').lower()
    
    result = {
        "S": S,
        "K": K,
        "T": T,
        "r": r,
        "type": option_type
    }
    
    if mode == 'iv':
        # Calculate implied volatility
        price = float(data.get('price', 0))
        iv = implied_volatility(price, S, K, T, r, option_type)
        result['implied_volatility'] = iv
        result['market_price'] = price
    
    elif mode == 'price':
        # Calculate theoretical price
        sigma = float(data.get('sigma', 0))
        theo_price = black_scholes_price(S, K, T, r, sigma, option_type)
        result['theoretical_price'] = round(theo_price, 4)
        result['volatility'] = sigma
    
    else:  # mode == 'full'
        # Calculate everything
        sigma = float(data.get('sigma', 0))
        
        if sigma > 0:
            theo_price = black_scholes_price(S, K, T, r, sigma, option_type)
            greeks = calculate_greeks(S, K, T, r, sigma, option_type)
            
            result['theoretical_price'] = round(theo_price, 4)
            result['volatility'] = sigma
            result['greeks'] = greeks
            
            # If market price provided, calculate mispricing
            if 'price' in data:
                market_price = float(data['price'])
                mispricing = market_price - theo_price
                result['market_price'] = market_price
                result['mispricing'] = round(mispricing, 4)
                result['mispricing_pct'] = round((mispricing / theo_price * 100) if theo_price > 0 else 0, 2)
    
    return result


def main():
    """Main entry point - reads option data from stdin"""
    
    input_data = sys.stdin.read().strip()
    
    if not input_data:
        print(json.dumps({"error": "No input data provided"}))
        sys.exit(1)
    
    try:
        data = json.loads(input_data)
        
        # Handle both single object and array
        if isinstance(data, dict):
            result = process_option(data)
            print(json.dumps(result))
        
        elif isinstance(data, list):
            results = [process_option(item) for item in data]
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
