"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

  • Client được tạo lười (lazy): import module không ping Redis, nên app vẫn khởi động
    được khi Redis chưa sẵn sàng.
  • redis_healthy() dùng cho GET /ready: không kết nối được → False.
"""
import redis
from fastapi import HTTPException

from app.config import settings

_client = (
    redis.Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    if settings.redis_url
    else None
)


def require_redis() -> redis.Redis:
    """Trả về client Redis; chưa cấu hình REDIS_URL → 503."""
    if _client is None:
        raise HTTPException(status_code=503, detail="Redis chưa được cấu hình (REDIS_URL)")
    return _client


def redis_healthy() -> bool:
    if _client is None:
        return False
    try:
        return bool(_client.ping())
    except redis.RedisError:
        return False


def close_redis() -> None:
    if _client is not None:
        _client.close()
