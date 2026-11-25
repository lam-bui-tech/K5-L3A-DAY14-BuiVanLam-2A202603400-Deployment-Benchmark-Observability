"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.

Khi chạy local, file .env (nếu có) được nạp; biến đã có sẵn trong môi trường
(Docker, Railway, Render, script chấm) luôn được ưu tiên hơn .env.
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    port: int
    environment: str
    agent_api_key: str
    redis_url: str
    rate_limit_per_minute: int
    daily_budget_usd: float
    monthly_budget_usd: float


def load_settings() -> Settings:
    return Settings(
        port=int(os.getenv("PORT", "8000")),
        environment=os.getenv("ENVIRONMENT", "development"),
        agent_api_key=os.getenv("AGENT_API_KEY", ""),
        redis_url=os.getenv("REDIS_URL", ""),
        rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")),
        daily_budget_usd=float(os.getenv("DAILY_BUDGET_USD", "1.0")),
        # 0 = không giới hạn theo tháng
        monthly_budget_usd=float(os.getenv("MONTHLY_BUDGET_USD", "0")),
    )


settings = load_settings()
