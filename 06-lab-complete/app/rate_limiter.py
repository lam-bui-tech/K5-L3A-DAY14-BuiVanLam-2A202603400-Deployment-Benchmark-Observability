"""
Rate limiting (tiêu chí 7).

  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, kèm header Retry-After
  • State lưu trong Redis (sorted set) để mọi worker / instance dùng chung
    và vẫn còn sau khi restart agent
"""
import hashlib
import time
import uuid

import redis
from fastapi import HTTPException

from app.config import settings
from app.redis_client import require_redis

WINDOW_SECONDS = 60


def _bucket(api_key: str) -> str:
    # Không lưu API key thật trong Redis, chỉ lưu hash của nó.
    digest = hashlib.sha256(api_key.encode()).hexdigest()[:32]
    return f"ratelimit:{digest}"


def check_rate_limit(key: str) -> None:
    r = require_redis()
    limit = settings.rate_limit_per_minute
    bucket = _bucket(key)
    now = time.time()
    try:
        r.zremrangebyscore(bucket, 0, now - WINDOW_SECONDS)
        if r.zcard(bucket) >= limit:
            oldest = r.zrange(bucket, 0, 0, withscores=True)
            retry_after = max(1, int(oldest[0][1] + WINDOW_SECONDS - now) + 1) if oldest else WINDOW_SECONDS
            raise HTTPException(
                status_code=429,
                detail=f"Vượt giới hạn {limit} request/phút",
                headers={"Retry-After": str(retry_after)},
            )
        r.zadd(bucket, {f"{now}:{uuid.uuid4().hex}": now})
        r.expire(bucket, WINDOW_SECONDS)
    except redis.RedisError:
        raise HTTPException(status_code=503, detail="Redis không khả dụng")
