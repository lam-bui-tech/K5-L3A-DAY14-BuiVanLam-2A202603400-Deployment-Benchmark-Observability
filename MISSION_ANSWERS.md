# Day 14 Lab - Mission Answers

> **Student Name:** Bùi Văn Lâm
> **Student ID:** 2A202603400
> **Class:** K5-L3A

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`

1. **Hardcode secrets trong source code** (dòng 17–18): `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Khi push lên GitHub sẽ lộ ngay thông tin nhạy cảm.
2. **Không có config management / hardcode cấu hình** (dòng 21–22): `DEBUG = True`, `MAX_TOKENS = 500` được gán cứng trong code thay vì đọc từ biến môi trường, không thể thay đổi linh hoạt giữa dev/staging/production.
3. **Dùng `print()` thay cho structured logging và in cả secret ra log** (dòng 33–38): `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` vừa khó thu thập/tìm kiếm trên log aggregator (Loki, Datadog), vừa làm rò rỉ API key ra stdout/log.
4. **Thiếu health check endpoints** (`/health`, `/ready`): Nếu app bị treo hoặc chưa sẵn sàng, nền tảng (Railway/Render/Kubernetes) không biết để restart container hoặc ngừng route traffic.
5. **Bind `host="localhost"` và hardcode `port=8000`, bật `reload=True`** (dòng 49–54):
   - `host="localhost"` (`127.0.0.1`) chỉ nhận kết nối từ chính máy/container đó, bên ngoài container không truy cập được.
   - `port=8000` cố định, không đọc biến `PORT` do cloud platform inject.
   - `reload=True` tiêu tốn tài nguyên và không an toàn khi chạy production.
6. **Không xử lý graceful shutdown (`SIGTERM`)**: Khi tắt/redeploy, process bị ngắt đột ngột, có thể cắt ngang các request đang xử lý dở.

### Exercise 1.2: Test bản `develop`

```bash
curl -sS -i -X POST "http://localhost:8000/ask?question=Hello"
```

Kết quả:
```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 13:13:12 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

### Exercise 1.3: So sánh `develop/app.py` và `production/app.py`

| Feature | Develop (`develop/app.py`) | Production (`production/app.py`) | Tại sao quan trọng? |
| --- | --- | --- | --- |
| **Config & Secrets** | Hardcode `OPENAI_API_KEY`, `DATABASE_URL`, `DEBUG = True`, `MAX_TOKENS = 500` trong code (dòng 17–22) | Đọc toàn bộ qua `config.py` từ biến môi trường (`os.getenv`), fail-fast khi thiếu `AGENT_API_KEY` ở production | Tránh lộ secret trên Git; tách biệt cấu hình theo môi trường (12-Factor App) |
| **Logging** | Dùng `print(...)`, in cả `OPENAI_API_KEY` ra stdout (dòng 34) | Dùng `logging` chuẩn JSON (`{"time":..., "level":..., "msg":...}`), tuyệt đối không log secret | Dễ parse/truy vết tập trung trên log aggregator và đảm bảo bảo mật |
| **Health check** | Không có `/health` hay `/ready` | Có `/health` (liveness), `/ready` (readiness, trả 503 khi chưa sẵn sàng), `/metrics` | Platform biết khi nào container sống/chết để restart và khi nào sẵn sàng nhận traffic |
| **Network binding** | `host="localhost"`, `port=8000`, `reload=True` (dòng 51–53) | `host="0.0.0.0"`, `port=settings.port` (từ `PORT`), `reload=settings.debug` | `0.0.0.0` cho phép nhận traffic từ ngoài container; `PORT` động tương thích Railway/Render |
| **Shutdown** | Tắt đột ngột, không có lifecycle hook | Có `lifespan` + `signal.signal(signal.SIGTERM, handle_sigterm)` đặt `is_ready = False` và chờ request hoàn thành | Tránh drop request đang chạy (zero-downtime deploy) |
| **CORS & Input** | Không cấu hình CORS; nhận `question` qua query param | Cấu hình `CORSMiddleware` theo `ALLOWED_ORIGINS`; nhận JSON body và validate trả `422` nếu thiếu `question` | Kiểm soát nguồn truy cập từ browser và chuẩn hóa API contract |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)

1. **Base image:** `python:3.11` (bản đầy đủ của Python 3.11 trên Debian, dung lượng lớn vì chứa sẵn nhiều công cụ hệ thống/build).
2. **Working directory:** `/app` (`WORKDIR /app` — thư mục làm việc mặc định trong container).
3. **Tại sao `COPY requirements.txt` trước `COPY . .`?** Nhờ cơ chế **Docker layer cache**: nếu code trong `app.py` thay đổi nhưng `requirements.txt` không đổi, Docker sẽ dùng lại layer `pip install` đã cache, không phải tải và cài lại toàn bộ thư viện mỗi lần build.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào?** `CMD` là lệnh mặc định khi container chạy và **có thể bị ghi đè** dễ dàng bằng tham số truyền thêm vào `docker run ...`; còn `ENTRYPOINT` cố định chương trình chính sẽ chạy, các tham số truyền vào `docker run` sẽ được nối thêm làm argument cho `ENTRYPOINT`.

### Exercise 2.2: Build và test container `my-agent:develop`

```bash
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run -d --name p2dev -p 8000:8000 my-agent:develop
curl -sS -i -X POST "http://localhost:8000/ask?question=What+is+Docker?"
```

Kết quả:
```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 14:01:36 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Multi-stage build & so sánh kích thước (`02-docker/production/Dockerfile`)

- **Stage 1 (`builder`):** Dùng `python:3.11-slim`, cài `gcc`, `libpq-dev` và `pip install --user -r requirements.txt` vào `/root/.local`. Image trung gian này không dùng để deploy.
- **Stage 2 (`runtime`):** Bắt đầu sạch từ `python:3.11-slim`, chỉ copy `/root/.local` (các package đã cài) và source code từ stage `builder`, chạy dưới non-root user `appuser` và có `HEALTHCHECK`. Nhờ loại bỏ `gcc`, header files và cache build nên image nhỏ hơn nhiều và ít bề mặt tấn công hơn.

Kết quả đo bằng `docker images my-agent`:
- **Develop (`my-agent:develop`):** `1.67 GB` (~`1670 MB`)
- **Production (`my-agent:advanced`):** `240 MB`
- **Chênh lệch:** Giảm **`85.6%`** (`1430 MB`)

### Exercise 2.4: Docker Compose stack (`02-docker/production/docker-compose.yml`)

**Sơ đồ kiến trúc:**
```text
Client ──(HTTP :80)──▶ Nginx (reverse proxy / LB, network: internal)
                          │
                          ▼
                      Agent (:8000) ──▶ Redis (:6379, session & rate limit)
                          │
                          └───────────▶ Qdrant (:6333, vector DB)
```

Các service được start: `redis` (`redis:7-alpine`), `qdrant` (`qdrant/qdrant:v1.9.0`), `agent` (build từ `02-docker/production/Dockerfile`, đợi `redis` và `qdrant` healthy), `nginx` (`nginx:alpine`, expose port 80/443). Tất cả giao tiếp qua bridge network `internal`, chỉ `nginx` mở port ra ngoài.

Kết quả test qua Nginx:
```http
GET http://localhost/health → 200 OK
{"status":"ok","uptime_seconds":9.1,"version":"2.0.0","timestamp":"2026-11-25T14:02:14.057914"}

POST http://localhost/ask → 200 OK
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication (`04-api-gateway/develop/`)

1. **Không gửi `X-API-Key` (trả về `401`):**
```http
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 13:14:25 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

2. **Gửi đúng `X-API-Key: secret-key-123` (trả về `200`):**
```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 13:14:25 GMT
server: uvicorn
content-length: 114
content-type: application/json

{"question":"Hello","answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

### Exercise 4.2 & 4.3: JWT Authentication & Rate Limiting (`04-api-gateway/production/`)

Lấy JWT token từ `POST /auth/token` với tài khoản `student` / `demo123` (token đã được che: `eyJhbGciOiJI...`), sau đó gọi `POST /ask`:

1. **Request hợp lệ (trả về `200`, kèm thông tin `usage`):**
```http
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 13:14:29 GMT
server: uvicorn
content-length: 196
content-type: application/json
vary: Origin
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"what is docker?","answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

2. **Vòng lặp test Rate Limiting (10 requests/phút cho `student`):**
- Request 1 → `200` (`requests_remaining: 9`)
- Request 2..10 → `HTTP 200`
- Request 11 → `HTTP 429`

Response `429 Too Many Requests`:
```http
HTTP/1.1 429 Too Many Requests
date: Wed, 25 Nov 2026 13:14:30 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795612530
retry-after: 59
content-length: 98
content-type: application/json
vary: Origin
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cost Guard Implementation (`cost_guard.py`)

- **Cơ chế hoạt động:**
  - **Trước khi gọi LLM (`check_budget`):** Kiểm tra chi phí tích lũy trong ngày của toàn hệ thống (`global_daily_budget_usd = $10.0`, vượt ngưỡng trả `503`) và của từng user (`daily_budget_usd = $1.0`, vượt ngưỡng trả `402 Payment Required`). Nếu đạt `80%` (`warn_at_pct = 0.8`) thì ghi log cảnh báo.
  - **Sau khi gọi LLM (`record_usage`):** Cộng dồn `input_tokens` và `output_tokens`, tính chi phí USD theo đơn giá từng loại token (`$0.00015 / 1K input`, `$0.0006 / 1K output`).
- **Vì sao cần cả Rate Limit và Cost Guard?**
  - **Rate limit** bảo vệ **tốc độ/tài nguyên hệ thống** (chống spam/DDoS theo số request/phút).
  - **Cost guard** bảo vệ **ngân sách tài chính** (vì một vài request hợp lệ nhưng prompt/response rất dài vẫn có thể đốt hết tiền LLM API nếu chỉ giới hạn số request).
  - Trong bản `production` thực tế (như Part 6), state của cả Rate Limit và Cost Guard được lưu trong **Redis** thay vì RAM để dùng chung giữa nhiều instance.

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Public URL & Deployment
- **URL public:** `https://agent-production-63912e22.up.railway.app`
- **Platform:** Railway (`k5-day14-agent`, gồm service `agent` deploy từ `06-lab-complete/` và service `Redis`)
- **Kết quả tự kiểm CP6:**
  - `GET /health` → `200` (`{"status":"ok","environment":"production"}`)
  - `GET /ready` → `200` (`{"status":"ready"}`)
  - `POST /ask` (không có `X-API-Key`) → `401`
  - `POST /ask` (có `X-API-Key: $AGENT_API_KEY`) → `200` (`{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}`)
- **Chi tiết test & biến môi trường:** Xem [DEPLOYMENT.md](DEPLOYMENT.md) và ảnh trong `screenshots/` (`dashboard.png`, `running.png`, `test.png`).

### So sánh `railway.toml` và `render.yaml`
- **`railway.toml` (TOML, cấu hình từng service):** Định nghĩa cách build (`builder = "DOCKERFILE"`, `dockerfilePath = "Dockerfile"`) và chính sách chạy (`healthcheckPath = "/health"`, `healthcheckTimeout`, `restartPolicyType = "ON_FAILURE"`, `restartPolicyMaxRetries = 3`). Biến môi trường và dịch vụ đi kèm (như Redis) được tạo và gắn trực tiếp trên dashboard/CLI của Railway chứ không khai báo chung trong `railway.toml`.
- **`render.yaml` (YAML Blueprint, Infrastructure as Code cho cả stack):** Cho phép khai báo nhiều service cùng lúc (web service dùng `runtime: docker`, `healthCheckPath: /health`, cùng database/Redis nếu cần) và khai báo danh sách `envVars` ngay trong file (secret dùng `generateValue: true` hoặc `sync: false` để không hardcode).

### Exercise 3.3: Cloud Run CI/CD Pipeline (`03-cloud-deployment/production-cloud-run/`)
Dựa trên `cloudbuild.yaml` và `service.yaml`, pipeline CI/CD trên GCP gồm 4 bước tuần tự khi push lên `main`:
1. **`test`**: Chạy `pytest tests/ -v --tb=short` trong container `python:3.11-slim` để đảm bảo unit test pass trước khi build.
2. **`build`**: Dùng `gcr.io/cloud-builders/docker` build image gắn tag `$COMMIT_SHA` và `latest` (tận dụng `--cache-from` để tăng tốc).
3. **`push`**: Đẩy image vừa build lên Container Registry (`gcr.io/$PROJECT_ID/ai-agent`).
4. **`deploy`**: Dùng `gcloud run deploy` triển khai lên Cloud Run (`asia-southeast1`), cấu hình `min-instances=1`, `max-instances=10`, `512Mi` RAM, `1` CPU, `containerConcurrency=80`, health probe (`/health`, `/ready`) và lấy secret (`OPENAI_API_KEY`, `AGENT_API_KEY`) từ Google Secret Manager.

---

## Part 5: Scaling & Reliability

### Exercise 5.1–5.3: Liveness (`/health`), Readiness (`/ready`) & Graceful Shutdown
- **`/health` (Liveness probe):** Kiểm tra process còn sống hay không (uptime, memory). Nếu fail → platform restart container.
- **`/ready` (Readiness probe):** Kiểm tra agent đã sẵn sàng nhận traffic chưa (ví dụ đã load xong và kết nối Redis ổn định). Nếu fail (trả `503`) → load balancer ngừng route request mới tới instance đó nhưng **không** restart container.
- **Graceful shutdown:** Khi nhận tín hiệu `SIGTERM`, app đặt `_is_ready = False` để ngừng nhận request mới từ load balancer, đợi các request đang xử lý (`_in_flight_requests`) hoàn thành rồi mới thoát.

Kết quả test `05-scaling-reliability/develop/app.py`:
- `GET /health` → `{"status":"ok","uptime_seconds":1.4,"version":"1.0.0","environment":"development",...}`
- `GET /ready` → `{"ready":true,"in_flight_requests":1}`

### Exercise 5.4–5.5: Stateless Scaling với 3 instances + Redis + Nginx
Chạy stack trong `05-scaling-reliability/production/` với 3 replica:
```bash
docker compose -p k5-day14-scaling up -d --build --scale agent=3
python test_stateless.py
```

Kết quả `test_stateless.py`:
```text
Session ID: f283b9ae-612e-425f-aaba-563e548763a3

Request 1: [instance-c2447f]
Request 2: [instance-a48343]
Request 3: [instance-de36d8]
Request 4: [instance-c2447f]
Request 5: [instance-a48343]

Total requests: 5
Instances used: {'instance-de36d8', 'instance-c2447f', 'instance-a48343'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

**Giải thích:**
- Nếu lưu conversation history trong RAM (biến Python `dict`), khi Nginx phân phối round-robin 5 request sang 3 container khác nhau (`instance-c2447f`, `instance-a48343`, `instance-de36d8`), mỗi instance chỉ thấy phần tin nhắn gửi tới riêng nó và lịch sử hội thoại bị đứt quãng.
- Khi chuyển state sang **Redis** dùng chung, cả 3 instance đều đọc/ghi cùng một `session_id`, đảm bảo đủ 10 message (5 cặp user/assistant) và sẵn sàng scale ngang hoặc thay thế container không mất dữ liệu.

---

## Part 6: Final Project (`06-lab-complete/`)

Kết quả chạy `python check_production_ready.py` (chế độ đầy đủ có Docker & Redis trong WSL2):

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

---

## AI Log

- **Mục đích sử dụng AI:** Hỗ trợ giải thích yêu cầu từng Part, chạy kiểm thử tự động các kịch bản Part 1, 2, 4, 5, 6, 7 trong WSL2 và Docker, phân tích nguyên nhân lỗi thiếu `PYTHONUSERBASE` trong `06-lab-complete/benchmark-observability/production/Dockerfile`, và rà soát cấu trúc file nộp theo `SUBMISSION.md`.
- **Tự kiểm tra:** Toàn bộ kết quả đo đạc (kích thước Docker image `1.67 GB` vs `240 MB`, output `curl` 401/200/429, kết quả `test_stateless.py`, output `check_production_ready.py` `PASS 12/12`, file JSON/CSV trong `reports/` và `benchmark-results/`, 4 ảnh chụp màn hình trong `screenshots/`) đều được tạo ra từ quá trình chạy thực tế trên máy và đối chiếu khớp với `BENCHMARK_REPORT.md`.
