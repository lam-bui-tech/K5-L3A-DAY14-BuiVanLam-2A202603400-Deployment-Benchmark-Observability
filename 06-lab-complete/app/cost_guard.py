"""
Cost guard (tiêu chí 8).

  • Cộng dồn chi phí LLM (tính theo token) vào Redis, theo ngày và theo tháng
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD > 0) → HTTP 402
"""
from datetime import datetime, timezone

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import require_redis

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _periods(now: datetime | None = None) -> list[tuple[str, str, float, int]]:
    """(tên, key Redis, ngân sách USD, TTL giây) cho kỳ ngày và kỳ tháng."""
    now = now or datetime.now(timezone.utc)
    return [
        ("ngày", f"cost:daily:{now:%Y-%m-%d}", settings.daily_budget_usd, 2 * 86400),
        ("tháng", f"cost:monthly:{now:%Y-%m}", settings.monthly_budget_usd, 40 * 86400),
    ]


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → HTTP 402."""
    r = require_redis()
    try:
        for name, key, budget, _ in _periods():
            if budget <= 0:
                continue
            if float(r.get(key) or 0) >= budget:
                raise HTTPException(status_code=402, detail=f"Hết ngân sách theo {name}")
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Redis không khả dụng")


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = input_tokens / 1000 * PRICE_INPUT_PER_1K + output_tokens / 1000 * PRICE_OUTPUT_PER_1K
    r = require_redis()
    try:
        pipe = r.pipeline()
        for _, key, _, ttl in _periods():
            pipe.incrbyfloat(key, cost)
            pipe.expire(key, ttl)
        pipe.execute()
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Redis không khả dụng")
    return cost
