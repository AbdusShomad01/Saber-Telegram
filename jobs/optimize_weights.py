"""
Saber Trader — Weight Optimization Job
Performs historical performance-based optimization (Random Search + Hill Climbing)
to tune the category weights of the ScoringEngine to maximize the Win Rate and Profit Factor.
Saves the optimized weights to weights_config.json.
"""

import os
import json
import sqlite3
import random
import logging
from typing import Dict, List, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("WeightOptimizer")

DEFAULT_WEIGHTS: Dict[str, float] = {
    "trend_momentum": 21.0,
    "volume_liquidity": 20.0,
    "pattern": 10.0,
    "gap_analysis": 5.0,
    "sector_correlation": 4.0,
    "support_resistance": 15.0,
    "bandarmology": 15.0,
    "foreign_flow": 10.0,
}

# Bounds for each category to ensure no category is completely zeroed out
CATEGORY_BOUNDS = {
    "trend_momentum": (10, 35),
    "volume_liquidity": (10, 30),
    "pattern": (5, 20),
    "gap_analysis": (2, 10),
    "sector_correlation": (2, 10),
    "support_resistance": (5, 25),
    "bandarmology": (5, 25),
    "foreign_flow": (5, 20),
}

def load_resolved_signals(db_path: str) -> List[Dict]:
    """Load historical resolved signals from the database."""
    if not os.path.exists(db_path):
        logger.warning(f"Database file not found at {db_path}")
        return []

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Sertakan EXPIRED sebagai loss ringan (-0.5%)
        # EXPIRED = sinyal tidak hit TP dalam waktu hold = opportunity cost
        cursor.execute("""
            SELECT id, ticker, signal, raw_score, category_raw_json, 
                   outcome_status, outcome_pnl_pct, created_at
            FROM signals
            WHERE outcome_status IS NOT NULL 
              AND outcome_status != 'PENDING'
              AND category_raw_json IS NOT NULL
        """)
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()

        # Assign pnl untuk EXPIRED yang belum punya nilai
        for row in rows:
            if row["outcome_status"] == "EXPIRED" and (row["outcome_pnl_pct"] is None or row["outcome_pnl_pct"] == 0):
                row["outcome_pnl_pct"] = -0.5  # Penalty kecil: opportunity cost

        return rows
    except Exception as e:
        logger.error(f"Error loading resolved signals: {e}")
        return []

def evaluate_weights(weights: Dict[str, float], signals: List[Dict], buy_threshold: float = 75.0) -> Tuple[float, Dict]:
    """
    Evaluate a candidate set of weights against historical signals.
    EXPIRED dihitung sebagai loss ringan (-0.5%) untuk mencerminkan opportunity cost.
    Returns a score metric and performance statistics.
    """
    total_triggered = 0
    wins = 0
    losses = 0
    total_pnl = 0.0
    gains_sum = 0.0
    losses_sum = 0.0

    for s in signals:
        try:
            raw_scores = json.loads(s["category_raw_json"])
        except Exception:
            continue

        simulated_score = 0.0
        for cat, w_val in weights.items():
            raw_val = raw_scores.get(cat, 0.0)
            simulated_score += min(float(raw_val), w_val)

        if simulated_score >= buy_threshold:
            total_triggered += 1
            # EXPIRED mendapat pnl -0.5 (opportunity cost), bukan 0
            pnl = s["outcome_pnl_pct"] if s["outcome_pnl_pct"] is not None else 0.0
            if s["outcome_status"] == "EXPIRED" and pnl == 0:
                pnl = -0.5
            total_pnl += pnl
            if pnl > 0:
                wins += 1
                gains_sum += pnl
            else:
                losses += 1
                losses_sum += abs(pnl)

    if total_triggered == 0:
        return -999.0, {"trades": 0, "winrate": 0, "profit_factor": 0, "pnl": 0}

    winrate = (wins / total_triggered) * 100
    profit_factor = gains_sum / losses_sum if losses_sum > 0 else (gains_sum if gains_sum > 0 else 1.0)
    if losses_sum == 0 and gains_sum > 0:
        profit_factor = 5.0

    norm_winrate = winrate / 100.0
    norm_pf = min(profit_factor, 5.0) / 5.0
    trades_penalty = min(total_triggered, 10) / 10.0
    fitness = (norm_winrate * 0.5 + norm_pf * 0.3 + (total_pnl / 100.0) * 0.2) * trades_penalty

    stats = {
        "trades": total_triggered,
        "winrate": round(winrate, 1),
        "profit_factor": round(profit_factor, 2),
        "pnl": round(total_pnl, 2)
    }
    return fitness, stats

def generate_random_weights() -> Dict[str, float]:
    """Generate a random set of weights that sum to 100 within bounds."""
    weights = {}
    remaining = 100.0
    cats = list(DEFAULT_WEIGHTS.keys())
    
    # 1. Assign random values within bounds first
    for cat in cats[:-1]:
        min_w, max_w = CATEGORY_BOUNDS[cat]
        # Make sure remaining amount allows other bounds to be met
        # Sum of min bounds of remaining categories
        remaining_cats = len(cats) - len(weights) - 1
        min_req = sum(CATEGORY_BOUNDS[c][0] for c in cats if c not in weights and c != cat)
        
        # Max limit is constrained by remaining and min_req
        val_max = min(max_w, remaining - min_req)
        val_min = max(min_w, remaining - sum(CATEGORY_BOUNDS[c][1] for c in cats if c not in weights and c != cat))
        
        if val_min >= val_max:
            val = val_min
        else:
            val = round(random.uniform(val_min, val_max), 1)
        
        weights[cat] = val
        remaining -= val

    # Last category takes the remainder
    last_cat = cats[-1]
    weights[last_cat] = round(remaining, 1)
    
    # Double check bounds on last category
    min_w, max_w = CATEGORY_BOUNDS[last_cat]
    if weights[last_cat] < min_w:
        weights[last_cat] = min_w
    elif weights[last_cat] > max_w:
        weights[last_cat] = max_w
        
    # Re-normalize to exactly 100.0
    total = sum(weights.values())
    for k in weights:
        weights[k] = round((weights[k] / total) * 100, 1)
    
    # Fix rounding errors
    diff = round(100.0 - sum(weights.values()), 1)
    weights[cats[0]] = round(weights[cats[0]] + diff, 1)
    
    return weights

def optimize(db_path: str, iterations: int = 5000) -> Tuple[Dict[str, float], Dict]:
    """Run weight optimization using random search + local refinement."""
    signals = load_resolved_signals(db_path)
    
    if len(signals) < 5:
        logger.info(f"Insufficient resolved signals ({len(signals)}/5). Using default weights.")
        return DEFAULT_WEIGHTS.copy(), {"trades": 0, "winrate": 0, "profit_factor": 0, "pnl": 0}

    logger.info(f"Running optimization on {len(signals)} resolved signals...")

    best_weights = DEFAULT_WEIGHTS.copy()
    best_fitness, best_stats = evaluate_weights(best_weights, signals)
    logger.info(f"Initial (Default) weights fitness: {best_fitness:.4f} | Stats: {best_stats}")

    # Random search phase
    for i in range(iterations):
        cand_weights = generate_random_weights()
        fitness, stats = evaluate_weights(cand_weights, signals)
        if fitness > best_fitness:
            best_fitness = fitness
            best_weights = cand_weights
            best_stats = stats

    logger.info(f"After Random Search: Best fitness: {best_fitness:.4f} | Stats: {best_stats}")

    # Local hill climbing refinement phase
    cats = list(DEFAULT_WEIGHTS.keys())
    step = 1.0
    for _ in range(500):
        # Pick two categories to tweak (add to one, subtract from other to maintain 100 sum)
        c1, c2 = random.sample(cats, 2)
        cand_weights = best_weights.copy()
        
        # Apply tweak
        cand_weights[c1] = round(cand_weights[c1] + step, 1)
        cand_weights[c2] = round(cand_weights[c2] - step, 1)
        
        # Check bounds
        if (CATEGORY_BOUNDS[c1][0] <= cand_weights[c1] <= CATEGORY_BOUNDS[c1][1] and
            CATEGORY_BOUNDS[c2][0] <= cand_weights[c2] <= CATEGORY_BOUNDS[c2][1]):
            fitness, stats = evaluate_weights(cand_weights, signals)
            if fitness > best_fitness:
                best_fitness = fitness
                best_weights = cand_weights
                best_stats = stats

    # Round all values to 1 decimal place
    for k in best_weights:
        best_weights[k] = round(best_weights[k], 1)
        
    logger.info(f"Optimization complete! Best weights: {best_weights} | Stats: {best_stats}")
    return best_weights, best_stats

def save_weights(weights: Dict[str, float]):
    """Save the weights dictionary to weights_config.json."""
    config_path = "./weights_config.json"
    try:
        with open(config_path, "w") as f:
            json.dump(weights, f, indent=4)
        logger.info(f"Weights successfully saved to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save weights: {e}")

def run_optimization_job(db_path: str = "./idx_signal_bot.db"):
    """Entry point for the optimization job."""
    logger.info("Starting Saber Trader Weight Optimization Job...")
    best_weights, stats = optimize(db_path)
    save_weights(best_weights)
    logger.info("Weight Optimization Job complete.")

if __name__ == "__main__":
    from app.config import get_settings
    settings = get_settings()
    db_url = settings.DATABASE_URL_SYNC
    path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "./idx_signal_bot.db"
    run_optimization_job(db_path=path)
