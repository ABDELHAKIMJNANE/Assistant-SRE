# 🧪 Local Testing Plan — Assistant-SRE FastAPI Backend

This guide describes how to run the FastAPI backend locally with Docker Compose, execute tests, and validate integrations.

---

## ✅ Prerequisites

- Docker + Docker Compose
- Python 3.12+
- `pip` or `pipx`
- Optional: `kubectl` for local K8s testing

---

## 1️⃣ Local Setup (Docker Compose)

### 1. Copy environment variables

```bash
cp /home/runner/work/Assistant-SRE/Assistant-SRE/backend/.env.example /home/runner/work/Assistant-SRE/Assistant-SRE/backend/.env
```

Fill in:
- `OPENAI_ENDPOINT`
- `OPENAI_API_KEY`
- `SMTP_USER` / `SMTP_PASSWORD`
- `SRE_EMAIL`

### 2. Start local stack

```bash
cd /home/runner/work/Assistant-SRE/Assistant-SRE/backend

docker compose up -d
```

Expected services:
- FastAPI → `http://localhost:8000`
- MongoDB → `mongodb://localhost:27017`
- Loki → `http://localhost:3100`
- Prometheus → `http://localhost:9090`
- Mongo Express → `http://localhost:8081`

### 3. Verify health

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/api/v1/health/ready
```

---

## 2️⃣ Running Tests

### Unit + API tests

```bash
cd /home/runner/work/Assistant-SRE/Assistant-SRE/backend
python -m pytest tests/ -v
```

### Coverage

```bash
python -m pytest tests/ --cov=app --cov-report=term-missing
```

---

## 3️⃣ Integration Tests (All Services)

To validate full integration:

1. Start Docker Compose (MongoDB, Loki, Prometheus).
2. Configure `.env` with real Azure OpenAI credentials.
3. Send a Grafana webhook payload:

```bash
curl -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{"alert_name":"OOMKilled","state":"alerting","labels":{"pod":"demo","namespace":"app-demo"},"message":"Container killed"}'
```

4. Verify incident insertion:

```bash
curl http://localhost:8000/api/v1/incidents
```

---

## 4️⃣ Mocking External Services

The test suite mocks:
- **MongoDB** (patched motor client)
- **OpenAI** (patched `llm_engine`)
- **Loki/Prometheus** (patched HTTP calls)
- **SMTP** (patched `notification`)

Use `unittest.mock.patch` in tests (see `/backend/tests/`).

---

## 5️⃣ Performance Testing (Local)

Recommended tools:
- `hey` or `wrk` for HTTP stress tests
- `locust` for scenario-based testing

Example with `hey`:

```bash
hey -n 500 -c 20 http://localhost:8000/api/v1/incidents
```

Key metrics:
- Response time percentiles
- CPU usage
- MongoDB latency

---

## 6️⃣ Debugging Guide

**Logs** (JSON structured):
```bash
docker logs -f backend-fastapi
```

**Common debug actions:**
- Verify `.env` variables
- Check MongoDB connectivity (`mongodb://localhost:27017`)
- Check Loki/Prometheus URLs
- Inspect OpenAI errors (API key, deployment)

---

## 7️⃣ Common Issues & Fixes

| Issue | Cause | Solution |
|------|-------|----------|
| `ModuleNotFoundError: fastapi` | Dependencies not installed | `pip install -r backend/requirements.txt` |
| MongoDB connection refused | Docker Compose not started | `docker compose up -d` |
| OpenAI error 401 | Missing/invalid API key | Update `.env` with valid key |
| Loki/Prometheus errors | Services not running | Check containers and URLs |
| Rate limit exceeded | Too many requests | Wait or increase `RATE_LIMIT_*` |

---

✅ **Local testing complete when:**
- All tests pass
- `/healthz` and `/health/ready` return OK
- Webhook creates an incident
- Logs + metrics queries succeed
