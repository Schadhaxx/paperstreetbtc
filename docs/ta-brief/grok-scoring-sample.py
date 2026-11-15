# Grok's sample scoring logic (sent by Sunil Nov 13 3:45 PM). Review/improve at Stage 3.
def score_level(level, current_price, now):
    score = 0
    score += (level.touches - 1) * 2
    days_ago = (now - level.last_touch).days
    if days_ago <= 7: score += 4
    elif days_ago <= 21: score += 2
    elif days_ago <= 45: score += 1
    if level.price_spread_pct < 0.8: score += 3
    elif level.price_spread_pct < 1.5: score += 1
    if not is_broken(level, current_price): score += 5
    else: score -= 10
    return score

def is_broken(level, current_price):
    if level.type == "support": return current_price < level.price
    else: return current_price > level.price
# Comparative layer: run variants (lookback / clustering sensitivity), pick highest-scoring set.
