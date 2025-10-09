#!/usr/bin/env python3
"""
Contextual Multi-Armed Bandit for Strategy Selection
Implements LinUCB (Linear Upper Confidence Bound) algorithm
Learns which strategy/sizing/stop combination works best in different market contexts
"""

import json
import sys
import math
import os
from typing import Dict, Any, List, Tuple
import sqlite3
from datetime import datetime


# Enhanced action space with more strategies and market regime awareness
ACTIONS = [
    # ORB_VWAP variants (trend-following)
    {"id": 0, "strategy": "ORB_VWAP", "size_mult": 1.0, "stop_style": "base", "regime": "trending"},
    {"id": 1, "strategy": "ORB_VWAP", "size_mult": 0.5, "stop_style": "tight", "regime": "trending"},
    {"id": 2, "strategy": "ORB_VWAP", "size_mult": 1.5, "stop_style": "wide", "regime": "trending"},
    
    # SMA_RSI_ATR variants (mean-reversion)
    {"id": 3, "strategy": "SMA_RSI_ATR", "size_mult": 1.0, "stop_style": "base", "regime": "ranging"},
    {"id": 4, "strategy": "SMA_RSI_ATR", "size_mult": 0.5, "stop_style": "tight", "regime": "ranging"},
    {"id": 5, "strategy": "SMA_RSI_ATR", "size_mult": 1.5, "stop_style": "wide", "regime": "ranging"},
    
    # DONCHIAN_BREAKOUT variants (breakout)
    {"id": 6, "strategy": "DONCHIAN_BREAKOUT", "size_mult": 1.0, "stop_style": "base", "regime": "breakout"},
    {"id": 7, "strategy": "DONCHIAN_BREAKOUT", "size_mult": 0.5, "stop_style": "tight", "regime": "breakout"},
    {"id": 8, "strategy": "DONCHIAN_BREAKOUT", "size_mult": 1.5, "stop_style": "wide", "regime": "breakout"},
    
    # New strategies for diversity
    {"id": 9, "strategy": "BOLLINGER_SQUEEZE", "size_mult": 1.0, "stop_style": "base", "regime": "compression"},
    {"id": 10, "strategy": "MACD_CROSSOVER", "size_mult": 1.0, "stop_style": "base", "regime": "momentum"},
    {"id": 11, "strategy": "STOCH_OVERSOLD", "size_mult": 1.0, "stop_style": "base", "regime": "ranging"},
    {"id": 12, "strategy": "VOLUME_BREAKOUT", "size_mult": 1.0, "stop_style": "base", "regime": "breakout"},
    
    # SKIP action
    {"id": 13, "strategy": "SKIP", "size_mult": 0.0, "stop_style": "none", "regime": "none"}
]


class LinUCBBandit:
    """Linear Upper Confidence Bound bandit"""
    
    def __init__(self, n_features: int, alpha: float = 1.0):
        self.n_features = n_features
        self.alpha = alpha  # Exploration parameter
        self.n_actions = len(ACTIONS)
        
        # Initialize A (covariance) and b (rewards) for each action
        self.A = {}
        self.b = {}
        
        for action in ACTIONS:
            aid = action["id"]
            self.A[aid] = [[1.0 if i == j else 0.0 for j in range(n_features)] for i in range(n_features)]
            self.b[aid] = [0.0] * n_features
    
    def matrix_multiply(self, A: List[List[float]], x: List[float]) -> List[float]:
        """Multiply matrix by vector"""
        return [sum(A[i][j] * x[j] for j in range(len(x))) for i in range(len(A))]
    
    def matrix_inverse(self, A: List[List[float]]) -> List[List[float]]:
        """Compute matrix inverse using Gauss-Jordan elimination"""
        n = len(A)
        # Create augmented matrix [A | I]
        aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(A)]
        
        # Forward elimination
        for i in range(n):
            # Find pivot
            max_row = i
            for k in range(i + 1, n):
                if abs(aug[k][i]) > abs(aug[max_row][i]):
                    max_row = k
            aug[i], aug[max_row] = aug[max_row], aug[i]
            
            # Make diagonal 1
            pivot = aug[i][i]
            if abs(pivot) < 1e-10:
                pivot = 1e-10
            for j in range(2 * n):
                aug[i][j] /= pivot
            
            # Eliminate column
            for k in range(n):
                if k != i:
                    factor = aug[k][i]
                    for j in range(2 * n):
                        aug[k][j] -= factor * aug[i][j]
        
        # Extract inverse from right half
        return [row[n:] for row in aug]
    
    def dot_product(self, a: List[float], b: List[float]) -> float:
        """Compute dot product"""
        return sum(x * y for x, y in zip(a, b))
    
    def detect_market_regime(self, context: List[float]) -> str:
        """Detect current market regime based on context features"""
        if len(context) < 10:
            return "unknown"
        
        # Extract key features (assuming standard feature order)
        # Features: [rsi, sma_ratio, atr_pct, volume_ratio, volatility, ...]
        rsi = context[0] if len(context) > 0 else 50
        sma_ratio = context[1] if len(context) > 1 else 1.0
        atr_pct = context[2] if len(context) > 2 else 0.01
        volume_ratio = context[3] if len(context) > 3 else 1.0
        volatility = context[4] if len(context) > 4 else 0.01
        
        # Regime detection logic
        if atr_pct > 0.02 and volume_ratio > 1.5:
            return "breakout"  # High volatility + volume
        elif abs(sma_ratio - 1.0) > 0.02 and atr_pct > 0.015:
            return "trending"  # Strong trend + volatility
        elif atr_pct < 0.01 and volume_ratio < 0.8:
            return "compression"  # Low volatility + volume
        elif (rsi < 30 or rsi > 70) and abs(sma_ratio - 1.0) < 0.01:
            return "ranging"  # Extreme RSI but no trend
        else:
            return "momentum"  # Default for mixed signals
    
    def select_action(self, context: List[float], epsilon: float = 0.0) -> Tuple[int, Dict[str, Any]]:
        """Select action using LinUCB algorithm with regime awareness"""
        
        # Ensure context is the right size
        if len(context) != self.n_features:
            # Pad or truncate
            context = (context + [0.0] * self.n_features)[:self.n_features]
        
        # Detect market regime
        regime = self.detect_market_regime(context)
        
        # Filter actions by regime
        regime_actions = [a for a in ACTIONS if a["regime"] == regime or a["regime"] == "none"]
        if not regime_actions:
            regime_actions = ACTIONS  # Fallback to all actions
        
        # ε-greedy exploration
        if epsilon > 0 and (hash(str(context)) % 100) / 100.0 < epsilon:
            # Random exploration within regime
            import random
            action_id = random.choice([a["id"] for a in regime_actions])
            action = ACTIONS[action_id]
            return action_id, {
                "action": action,
                "ucb_score": 0.0,
                "expected_reward": 0.0,
                "exploration": True,
                "regime": regime
            }
        
        # LinUCB action selection (within regime)
        best_action = None
        best_ucb = -float('inf')
        action_scores = {}
        
        for action in regime_actions:
            aid = action["id"]
            
            try:
                # Compute A_inv * b (expected reward)
                A_inv = self.matrix_inverse(self.A[aid])
                theta = self.matrix_multiply(A_inv, self.b[aid])
                expected_reward = self.dot_product(theta, context)
                
                # Compute uncertainty bonus
                A_inv_x = self.matrix_multiply(A_inv, context)
                uncertainty = math.sqrt(max(0, self.dot_product(context, A_inv_x)))
                
                # UCB score
                ucb = expected_reward + self.alpha * uncertainty
                
                action_scores[aid] = {
                    "expected_reward": expected_reward,
                    "uncertainty": uncertainty,
                    "ucb": ucb
                }
                
                if ucb > best_ucb:
                    best_ucb = ucb
                    best_action = aid
            
            except Exception:
                # Fallback if matrix operations fail
                if best_action is None:
                    best_action = aid
        
        if best_action is None:
            best_action = 9  # SKIP
        
        return best_action, {
            "action": ACTIONS[best_action],
            "ucb_score": action_scores.get(best_action, {}).get("ucb", 0.0),
            "expected_reward": action_scores.get(best_action, {}).get("expected_reward", 0.0),
            "uncertainty": action_scores.get(best_action, {}).get("uncertainty", 0.0),
            "exploration": False,
            "regime": regime,
            "regime_actions_count": len(regime_actions),
            "all_scores": action_scores
        }
    
    def update(self, action_id: int, context: List[float], reward: float):
        """Update bandit with observed reward"""
        
        # Ensure context is the right size
        if len(context) != self.n_features:
            context = (context + [0.0] * self.n_features)[:self.n_features]
        
        # Update A = A + x*x^T
        for i in range(self.n_features):
            for j in range(self.n_features):
                self.A[action_id][i][j] += context[i] * context[j]
        
        # Update b = b + r*x
        for i in range(self.n_features):
            self.b[action_id][i] += reward * context[i]
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize bandit state"""
        return {
            "n_features": self.n_features,
            "alpha": self.alpha,
            "A": self.A,
            "b": self.b,
            "updated_at": datetime.utcnow().isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LinUCBBandit':
        """Deserialize bandit state"""
        bandit = cls(data["n_features"], data["alpha"])
        bandit.A = {int(k): v for k, v in data["A"].items()}
        bandit.b = {int(k): v for k, v in data["b"].items()}
        return bandit


def load_bandit_from_db(db_path: str = "/data/bandit_policy.db") -> LinUCBBandit:
    """Load bandit state from SQLite database"""
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT policy_json FROM bandit_policy 
            ORDER BY id DESC LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            policy_data = json.loads(row[0])
            return LinUCBBandit.from_dict(policy_data)
    
    except Exception:
        pass
    
    # Default: new bandit with 28 features (from context_builder)
    return LinUCBBandit(n_features=28, alpha=1.0)


def save_bandit_to_db(bandit: LinUCBBandit, db_path: str = "/data/bandit_policy.db"):
    """Save bandit state to SQLite database"""
    
    try:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table if not exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bandit_policy (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                updated_at TEXT,
                policy_json TEXT
            )
        """)
        
        policy_json = json.dumps(bandit.to_dict())
        cursor.execute("""
            INSERT INTO bandit_policy (updated_at, policy_json)
            VALUES (?, ?)
        """, (datetime.utcnow().isoformat(), policy_json))
        
        conn.commit()
        conn.close()
    
    except Exception as e:
        print(f"Warning: Failed to save bandit state: {e}", file=sys.stderr)


def main():
    """Main entry point"""
    
    input_data = sys.stdin.read().strip()
    
    if not input_data:
        print(json.dumps({"error": "No input data provided"}))
        sys.exit(1)
    
    try:
        data = json.loads(input_data)
        
        mode = data.get('mode', 'select')  # select or update
        
        if mode == 'select':
            # Select action based on context
            context = data.get('context', data.get('feature_vector', []))
            epsilon = data.get('epsilon', 0.0)
            
            bandit = load_bandit_from_db()
            action_id, info = bandit.select_action(context, epsilon)
            
            result = {
                "mode": "select",
                "action_id": action_id,
                "action": info["action"],
                "ucb_score": info["ucb_score"],
                "expected_reward": info["expected_reward"],
                "exploration": info["exploration"],
                "regime": info.get("regime", "unknown"),
                "regime_actions_count": info.get("regime_actions_count", len(ACTIONS))
            }
            
            print(json.dumps(result))
        
        elif mode == 'update':
            # Update bandit with observed reward
            action_id = data.get('action_id')
            context = data.get('context', data.get('feature_vector', []))
            reward = data.get('reward', 0.0)
            
            bandit = load_bandit_from_db()
            bandit.update(action_id, context, reward)
            save_bandit_to_db(bandit)
            
            result = {
                "mode": "update",
                "action_id": action_id,
                "reward": reward,
                "updated": True
            }
            
            print(json.dumps(result))
        
        else:
            print(json.dumps({"error": f"Unknown mode: {mode}"}))
            sys.exit(1)
    
    except (json.JSONDecodeError, ValueError) as e:
        print(json.dumps({"error": f"Input error: {str(e)}"}))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"error": f"Processing error: {str(e)}"}))
        sys.exit(1)


if __name__ == '__main__':
    main()
