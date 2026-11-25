# Deployment Information

## Public URL
https://agent-production-63912e22.up.railway.app

## Platform
Railway (Project: `k5-day14-agent`, Services: `agent` + `Redis`)

## Test Commands

### 1. Health Check (`/health`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://agent-production-63912e22.up.railway.app/health"
# Expected & Observed: 200
# Body: {"status":"ok","environment":"production"}
```

### 2. Readiness Check (`/ready`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' "https://agent-production-63912e22.up.railway.app/ready"
# Expected & Observed: 200
# Body: {"status":"ready"}
```

### 3. API Test — Không có API Key (`401 Unauthorized`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://agent-production-63912e22.up.railway.app/ask" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Hello"}'
# Expected & Observed: 401
```

### 4. API Test — Có API Key (`200 OK`)
```bash
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "https://agent-production-63912e22.up.railway.app/ask" \
  -H 'Content-Type: application/json' \
  -H "X-API-Key: $AGENT_API_KEY" \
  -d '{"question":"Hello"}'
# Expected & Observed: 200
# Body: {"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

## Environment Variables Set (trên Railway Dashboard, không commit vào code)
- `ENVIRONMENT=production`
- `LOG_LEVEL=INFO`
- `RATE_LIMIT_PER_MINUTE=10`
- `MONTHLY_BUDGET_USD=10.0`
- `AGENT_API_KEY` (đặt trực tiếp trên Railway)
- `REDIS_URL=${{Redis.REDIS_URL}}`

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
