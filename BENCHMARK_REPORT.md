# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Bùi Văn Lâm (MSSV: 2A202603400)
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows 11 + WSL2 (Ubuntu 24.04, Python 3.12.3) + Docker Desktop

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | 95% người dùng nhận phản hồi dưới 0.5 giây (với latency cơ bản ~150–200ms), giữ trải nghiệm mượt mà |
| Error rate `/ask` | < 2.0 % | Cho phép error budget 2% để chịu được lỗi upstream ngẫu nhiên (~1% từ mock LLM) mà không gây báo động giả |
| Accuracy trên golden dataset | ≥ 80 % | Đảm bảo chất lượng trả lời tối thiểu trước khi cho phép merge/deploy lên production |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.11 | 190.6 | 222.3 | 1700.1 | 2.33% | FAIL (error rate > 2.0%) |
| 10 | 36.77 | 192.1 | 223.5 | 1707.8 | 1.33% | PASS |
| 50 | 106.26 | 200.7 | 300.0 | 1700.9 | 1.33% | PASS |
| 100 | 62.26 | 603.6 | 3975.4 | 4225.2 | 1.00% | FAIL (p95 > 500ms) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

Không. Từ concurrency 1 → 10 → 50, RPS tăng mạnh (4.11 → 36.77 → 106.26 req/s) nhờ tận dụng async I/O. Tuy nhiên đến concurrency 100, RPS giảm xuống còn 62.26 req/s và p95 vọt lên 3975.4 ms do quá tải event loop / kết nối đồng thời trên 1 worker (`uvicorn` đơn tiến trình), các request phải xếp hàng chờ xử lý.

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 195.9 | 236.2 | 260.7 |
| 0.03 (mặc định) | 226.2 | 267.3 | 1691.3 |
| 0.1 | 348.5 | 1689.9 | 1711.5 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

`p99` (và `p95` khi tỉ lệ chậm đạt 10%) nhạy nhất với tail latency: khi `MOCK_SLOW_RATE` tăng từ 0 lên 0.03, `avg` chỉ tăng nhẹ từ 195.9 ms lên 226.2 ms (trông vẫn bình thường), nhưng `p99` nhảy vọt từ 260.7 ms lên 1691.3 ms. Đặt SLO theo average sẽ che giấu trải nghiệm tệ của nhóm người dùng gặp request chậm, nên phải dùng `p95`/`p99`.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.1 | 108.7 | 113.7 |
| Tổng cost (USD) | $0.000404 | $0.000756 | $0.000791 |
| Cost / câu đúng (USD) | $0.00040395 | $0.00003599 | $0.00003440 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Thêm entry kiến thức về JWT vs API key vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Thêm entry kiến thức về Kubernetes HPA vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- Agent v2 tốn nhiều token hơn (~108.7–113.7 vs 57.1 tokens/câu) và chậm hơn một chút (~20ms bước retrieval, p95 218.3 ms vs 188.7 ms) nhưng accuracy tăng vọt từ 4.3% lên 100.0%.
- Nếu tính **cost / câu đúng**, v2 rẻ hơn ~11.7 lần so với v1 (`$0.00003440` vs `$0.00040395`), cho thấy đầu tư retrieval/RAG mang lại hiệu quả vượt trội.
- Trong CI/CD, dùng exit code của `python eval/run_eval.py --min-accuracy 1.0 --baseline reports/eval_v2.json` để chặn merge: nếu accuracy dưới ngưỡng hoặc có câu bị regression so với baseline, script trả về exit code `1` làm job CI fail.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): [grafana-dashboard.png](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): [jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`): [jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với ít nhất 2 alert đang **firing**: [prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (`for: 1m`) | ~1 phút 08 giây (14:23:42Z + `for: 1m`) | Error rate (18.69%) & Requests/s theo status code (`503`) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (`for: 2m`, trạng thái `pending` sau 1m08s) | ~2 phút 08 giây (khi đủ `for: 2m`) | Latency `/ask` — p50 / p95 / p99 (p95 vọt lên ~1.7s–1.89s) |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` (`> $2/giờ`, `for: 2m`) | ~2 phút (khi burn rate vượt $2/h) | Cost burn rate (USD/giờ) & LLM latency p95 theo model |
| D | `docker pause` 1 instance | `AgentInstanceDown` (`up{job="agent"} == 0`, `for: 30s`) | ~30–35 giây (activeAt 14:23:32Z) | Instances up (giảm từ 2 → 1) & Requests/s theo instance |
| E | `AGENT_VERSION=v1` | Không có alert nào firing | N/A | Retrieval hit ratio (tụt về 0%), Avg tokens giảm |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Alert hạ tầng/SLO (latency, error rate, instance up) không bắt được suy giảm chất lượng trả lời (v1 vẫn trả HTTP 200 bình thường, thậm chí nhanh và rẻ hơn v2). Để phát hiện trong production cần:
1. Chạy **eval tự động (`eval/run_eval.py`)** trong CI/CD trước khi deploy (quality gate chặn merge nếu accuracy giảm so với baseline).
2. Theo dõi các metric chất lượng/nghiệp vụ trên dashboard như **Retrieval hit ratio**, feedback người dùng (thumbs up/down) hoặc LLM-as-a-judge sampling trên traffic thật.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `e2493a79d01f87b667efcfc0aefaf2df`
- Tổng thời gian: `1676.5 ms`
- Span chiếm nhiều thời gian nhất: `llm_call` (`1652.6 ms`, `98.6%`)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T14:10:10.062315+00:00", "level": "INFO", "service": "observable-agent", "instance": "aff0c0233c41", "event": "llm_call", "trace_id": "e2493a79d01f87b667efcfc0aefaf2df", "span_id": "cd08c36f8425a34b", "request_id": "f8295beb3bd7", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1652.6}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 65.63 | 190 | 230 | 1700 | 77 / 7838 (0.98%) |
| 3 | 65.84 | 190 | 230 | 1700 | 75 / 7863 (0.95%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Ở tải 100 users với `wait_time` của Locust, RPS (~65.6 vs ~65.8 req/s) và p95 (230 ms) gần như không đổi khi scale từ 1 lên 3 instance vì 1 instance async FastAPI đã đủ xử lý 65 req/s (chưa bị bão hòa CPU/event loop). Nút thắt ở mức p99 (`1700 ms`) nằm ở **upstream LLM latency** (`MOCK_SLOW_RATE = 0.03` gây ~1500ms/request chậm) — tăng số instance không làm mỗi lời gọi LLM nhanh hơn, nhưng giúp tăng tổng thông lượng tối đa khi tải vượt ngưỡng bão hòa của 1 instance.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Latency trung bình (avg) che giấu tail latency; phải đặt SLO theo `p95`/`p99` và đo bằng load test thay vì eval nhỏ.
  2. Eval trên golden dataset với quality gate (`run_eval.py --baseline`) giúp phát hiện regression và đánh giá hiệu quả theo **cost / câu đúng** thay vì chỉ nhìn cost thô.
  3. 3 trụ cột Metrics (Prometheus/Grafana) + Traces (OpenTelemetry/Jaeger) + Structured JSON Logs liên kết qua `trace_id` giúp khoanh vùng đúng nút thắt (ví dụ `llm_call` chiếm 98.6% thời gian trace chậm).
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

  - Thêm metric theo dõi **Redis latency / connection errors** (`redis_operation_duration_seconds`), **rate limit & cost guard rejections** (`http_requests_total{status=~"429|402"}`), và alert **RedisDown** khi `/ready` trả `503` kéo dài > 30 giây.
