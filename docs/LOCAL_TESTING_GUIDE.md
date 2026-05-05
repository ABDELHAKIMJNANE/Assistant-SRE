# 🧪 LOCAL TESTING GUIDE — ASSISTANT-SRE

> **Purpose:** Complete step-by-step guide to run and test Assistant-SRE on your local machine.

---

## ⚙️ PREREQUISITES

Before starting, ensure the following are installed:

| Tool | Minimum Version | Install |
|------|----------------|---------|
| **Docker** | 24.0+ | https://docs.docker.com/get-docker/ |
| **Docker Compose** | v2.0+ | Bundled with Docker Desktop |
| **Python** | 3.11+ | https://www.python.org/downloads/ |
| **Git** | 2.30+ | https://git-scm.com/ |
| **curl** or **Postman** | any | For API testing |
| **VS Code** | any (optional) | https://code.visualstudio.com/ |

---

## 📋 SYSTEM REQUIREMENTS

| Resource | Minimum |
|----------|---------|
| **RAM** | 8 GB |
| **Disk** | 10 GB free |
| **CPU** | 2+ cores |
| **Network** | Internet access (Azure OpenAI API) |

---

## 🚀 STEP-BY-STEP LOCAL SETUP

### STEP 1: Clone Repository

```bash
git clone https://github.com/ABDELHAKIMJNANE/Assistant-SRE.git
cd Assistant-SRE
```

---

### STEP 2: Create Environment Files

**Backend `.env`:**

```bash
cd backend
cp .env.example .env
```

Open `.env` and set your values:

```dotenv
# Azure OpenAI (required for AI features)
AZURE_OPENAI_ENDPOINT=https://YOUR-RESOURCE.openai.azure.com/
AZURE_OPENAI_API_KEY=your_azure_openai_key_here
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# MongoDB (default works with docker-compose)
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB_NAME=aiops_db

# Loki (default works with docker-compose)
LOKI_URL=http://localhost:3100

# Prometheus (default works with docker-compose)
PROMETHEUS_URL=http://localhost:9090

# Email notifications (optional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_app_password
NOTIFICATION_EMAIL=sre-team@company.com

# Security
CORS_ORIGINS=["http://localhost:8501","http://localhost:8000"]
RATE_LIMIT_PER_MINUTE=60
```

**Frontend `.env`:**

```bash
cd ../frontend
cp .env.example .env
```

```dotenv
BACKEND_URL=http://localhost:8000
```

---

### STEP 3: Start Backend Services (Docker Compose)

```bash
cd backend

# Start all services: MongoDB, Loki, Prometheus, FastAPI
docker compose up -d

# Verify all services are running
docker compose ps
```

**Expected output:**

```
NAME                STATUS          PORTS
assistant-sre-api   Up (healthy)    0.0.0.0:8000->8000/tcp
assistant-sre-mongodb  Up           0.0.0.0:27017->27017/tcp
assistant-sre-loki  Up              0.0.0.0:3100->3100/tcp
assistant-sre-prometheus  Up        0.0.0.0:9090->9090/tcp
assistant-sre-mongo-express  Up     0.0.0.0:8081->8081/tcp
```

Follow API logs:

```bash
docker compose logs -f api
```

---

### STEP 4: Test Backend Health

```bash
# Liveness check
curl http://localhost:8000/healthz

# Expected: {"status": "ok"}

# Readiness check
curl http://localhost:8000/readyz

# Expected: {"status": "ready", "db": "connected"}
```

Open Swagger UI to explore all endpoints:

```
http://localhost:8000/docs
```

---

### STEP 5: Install Backend Python Dependencies

```bash
cd backend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install runtime + dev dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Verify pytest is available
python -m pytest --version
```

---

### STEP 6: Run Backend Tests

```bash
# Run all tests with verbose output
cd backend
python -m pytest tests/ -v

# Run with coverage report
python -m pytest tests/ --cov=app --cov-report=html --cov-report=term-missing

# Open HTML coverage report
open htmlcov/index.html        # macOS
xdg-open htmlcov/index.html    # Linux
start htmlcov/index.html       # Windows
```

**Expected output:**

```
tests/test_api/test_webhook.py::test_webhook_accepted PASSED
tests/test_api/test_webhook.py::test_webhook_invalid_payload PASSED
tests/test_api/test_incidents.py::test_list_incidents_empty PASSED
tests/test_api/test_incidents.py::test_get_incident_not_found PASSED
tests/test_api/test_health.py::test_healthz PASSED
tests/test_services/test_sanitizer.py::test_sanitize_ip PASSED
tests/test_services/test_sanitizer.py::test_sanitize_password PASSED

---------- coverage: 92% ----------
✅ All tests PASSED
```

---

### STEP 7: Test API Endpoints Manually

#### Webhook — Simulate a Grafana alert

```bash
curl -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "OOMKilled",
    "labels": {
      "pod_name": "fastapi-demo-abc123",
      "namespace": "app-demo",
      "severity": "critical"
    }
  }'

# Expected response (202 Accepted):
# {
#   "message": "Alert accepted for processing",
#   "incident_id": "64f3ab..."
# }
```

#### List Incidents

```bash
curl "http://localhost:8000/api/v1/incidents?skip=0&limit=20"

# Returns paginated list of incidents
```

#### Get Incident Details

```bash
# Replace {id} with an actual incident_id from the list
curl http://localhost:8000/api/v1/incidents/{id}
```

#### Chat with AI about an Incident

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": "{id}",
    "message": "Why did this OOMKilled happen and what should I check first?"
  }'
```

#### Approve an Incident Resolution

```bash
curl -X PUT http://localhost:8000/api/v1/incidents/{id}/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "status": "resolved",
    "approved_by": "engineer@company.com"
  }'
```

---

### STEP 8: Inspect Data in MongoDB

**Via Mongo Express UI (browser):**

```
http://localhost:8081
```

Database: `aiops_db` → Collection: `incidents`

**Via mongosh CLI:**

```bash
docker compose exec mongodb mongosh

# Inside mongosh:
use aiops_db
db.incidents.find().pretty()     # View all incidents
db.incidents.countDocuments()    # Count incidents
db.incidents.findOne()           # View one document
```

---

### STEP 9: Check Logs in Loki

```bash
# Query via HTTP (replace timestamps)
START=$(date -u -d '1 hour ago' +%s%N 2>/dev/null || date -u -v-1H +%s%N)
END=$(date -u +%s%N)

curl -G "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode 'query={job="api"}' \
  --data-urlencode "start=$START" \
  --data-urlencode "end=$END" \
  --data-urlencode 'limit=50'
```

Or navigate to:

```
http://localhost:3100/ready     # Loki health
```

---

### STEP 10: Check Metrics in Prometheus

Open Prometheus UI:

```
http://localhost:9090
```

Useful example queries:

```promql
# Total HTTP requests to FastAPI
fastapi_requests_total

# Request duration histogram
fastapi_request_duration_seconds_bucket

# MongoDB connection pool size
mongodb_connection_pool_size
```

Check targets are UP:

```
http://localhost:9090/targets
```

---

### STEP 11: Install Frontend Dependencies

```bash
cd ../frontend

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify Streamlit
streamlit --version
```

---

### STEP 12: Start the Streamlit Dashboard

```bash
streamlit run streamlit_app.py
```

**Expected output:**

```
  You can now view your Streamlit app in your browser.
  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

Open in browser:

```
http://localhost:8501
```

You should see: **🏢 SRE Assistant AIOps Dashboard**

---

### STEP 13: End-to-End Test

Run the full incident-to-resolution flow in one go:

**Terminal 1 — Watch backend logs:**

```bash
cd backend
docker compose logs -f api
```

**Terminal 2 — Send a simulated alert:**

```bash
curl -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "OOMKilled",
    "labels": {
      "pod_name": "test-pod-xyz",
      "namespace": "default",
      "severity": "critical"
    }
  }'
```

**Browser — Observe the result:**

1. Open `http://localhost:8501` (Streamlit)
2. Navigate to **Dashboard**
3. The new incident should appear within 5 seconds
4. Click on it to view: logs, metrics, and AI solution
5. Try the **Chat** interface for follow-up questions
6. Click **APPROVE** to resolve the incident

---

## 🔬 PERFORMANCE BENCHMARKING

### Load Test with curl

```bash
# Send 10 concurrent webhook requests
for i in $(seq 1 10); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST http://localhost:8000/api/v1/webhook \
    -H "Content-Type: application/json" \
    -d "{\"alert_name\": \"LoadTest-$i\", \"labels\": {\"pod\": \"pod-$i\"}}" &
done
wait
```

### Load Test with wrk (if installed)

```bash
wrk -t4 -c20 -d30s http://localhost:8000/healthz
```

### Measure Webhook Response Time

```bash
time curl -s -o /dev/null -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{"alert_name":"PerfTest","labels":{"pod":"x","namespace":"y"}}'

# Expected: real < 0.200s (non-blocking 202 Accepted)
```

---

## 🧪 INTEGRATION TESTING

### Run Integration Tests Only

```bash
cd backend
python -m pytest tests/test_api/ -v -k "integration"
```

### Test with a Real MongoDB Instance

```bash
# Override MongoDB URL to use a real instance
MONGODB_URL=mongodb://localhost:27017 python -m pytest tests/ -v
```

### Test Sanitizer Service

```bash
python -c "
import asyncio
from app.services.sanitizer import sanitize_data

raw = 'Host: 192.168.1.100 password=secret Bearer eyJtoken'
result = asyncio.run(sanitize_data(raw))
print(result)
# Expected: 'Host: X.X.X.X password=*** Bearer ****'
"
```

---

## 🐛 TROUBLESHOOTING

### Problem: Backend won't start

```bash
# Check port conflicts
lsof -i :8000    # macOS/Linux
netstat -an | grep 8000   # Windows

# Free a port
kill -9 $(lsof -t -i:8000)

# Or change the port in docker-compose.yml:
# ports:
#   - "8001:8000"
```

### Problem: MongoDB connection fails

```bash
# Check MongoDB container logs
docker compose logs mongodb

# Restart MongoDB
docker compose restart mongodb

# Test connection directly
docker compose exec mongodb mongosh --eval "db.runCommand({ping:1})"
```

### Problem: Azure OpenAI API errors

```bash
# Verify env var is set
echo $AZURE_OPENAI_API_KEY

# Test connectivity
curl -H "api-key: $AZURE_OPENAI_API_KEY" \
  "https://YOUR-RESOURCE.openai.azure.com/openai/deployments?api-version=2024-02-01"

# Quick Python validation
python3 -c "
from openai import AzureOpenAI
import os
client = AzureOpenAI(
    azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'],
    api_key=os.environ['AZURE_OPENAI_API_KEY'],
    api_version='2024-02-01'
)
print('Azure OpenAI client initialized successfully')
"
```

### Problem: Frontend can't connect to backend

```bash
# Verify backend is running
curl http://localhost:8000/healthz

# Check BACKEND_URL in frontend/.env
cat frontend/.env

# Verify CORS settings include http://localhost:8501
grep CORS backend/.env

# Inspect Docker network (if running backend in Docker)
docker network inspect bridge | grep -A5 "assistant"
```

### Problem: Loki returns no results

```bash
# Check Loki health
curl http://localhost:3100/ready

# Check Docker logs for Loki
docker compose logs loki

# Verify Promtail/log pusher is configured correctly
cat backend/loki-config.yml
```

### Problem: Tests fail with ImportError

```bash
# Ensure virtual environment is active
which python  # should point to venv/bin/python

# Reinstall dependencies
pip install --force-reinstall -r requirements.txt -r requirements-dev.txt

# Check Python version
python --version  # must be 3.11+
```

### Problem: `docker compose` command not found

```bash
# Try the old syntax
docker-compose up -d

# Or update Docker Desktop to get Compose v2
# https://docs.docker.com/compose/migrate/
```

---

## 🧹 CLEANUP

```bash
# Stop all containers (keep data volumes)
cd backend && docker compose down

# Stop and delete all data volumes
docker compose down -v

# Remove Python virtual environments
rm -rf backend/venv frontend/venv

# Remove coverage reports
rm -rf backend/htmlcov backend/.coverage
```

---

## ✅ VERIFICATION CHECKLIST

Use this checklist to confirm your local setup is complete:

- [ ] `docker compose ps` shows all services with status **Up**
- [ ] `curl http://localhost:8000/healthz` returns `{"status": "ok"}`
- [ ] `curl http://localhost:8000/readyz` returns `{"status": "ready"}`
- [ ] `python -m pytest tests/ -v` shows all tests **PASSED**
- [ ] Coverage report shows **≥ 90%**
- [ ] `http://localhost:8081` (Mongo Express) is accessible
- [ ] `http://localhost:9090` (Prometheus) shows targets **UP**
- [ ] `http://localhost:3100/ready` (Loki) returns **ready**
- [ ] `streamlit run streamlit_app.py` starts without errors
- [ ] `http://localhost:8501` (Streamlit) loads the dashboard
- [ ] Webhook `POST /api/v1/webhook` returns **202 Accepted**
- [ ] New incident appears in Streamlit dashboard
- [ ] Chat interface responds to questions
- [ ] APPROVE button resolves the incident

---

## 📊 EXPECTED RESULTS SUMMARY

After completing all steps:

| Component | URL | Expected Status |
|-----------|-----|----------------|
| FastAPI API | http://localhost:8000 | ✅ Healthy |
| Swagger Docs | http://localhost:8000/docs | ✅ Interactive UI |
| MongoDB | localhost:27017 | ✅ Connected |
| Mongo Express | http://localhost:8081 | ✅ Dashboard |
| Loki | http://localhost:3100 | ✅ Ready |
| Prometheus | http://localhost:9090 | ✅ Targets UP |
| Streamlit | http://localhost:8501 | ✅ Dashboard |

---

## 🚀 NEXT STEPS

### 1. Explore the Codebase

```bash
# Backend structure
find backend/app -type f -name "*.py" | sort

# Frontend structure
find frontend -type f -name "*.py" | sort
```

### 2. Read Additional Documentation

- [`docs/ARCHITECTURE_STRUCTURE.md`](./ARCHITECTURE_STRUCTURE.md) — Full system architecture
- [`docs/FASTAPI_ARCHITECTURE_DETAILED.md`](./FASTAPI_ARCHITECTURE_DETAILED.md) — Backend deep-dive
- [`docs/TESTING_PLAN_AKS.md`](./TESTING_PLAN_AKS.md) — Kubernetes deployment guide

### 3. Integrate with Your Grafana

```bash
# In Grafana:
# 1. Create a Contact Point → Webhook
# 2. URL: http://YOUR_BACKEND_IP:8000/api/v1/webhook
# 3. Method: POST
# 4. Assign to an Alert Rule
# 5. Trigger the alert → watch incident appear in Streamlit
```

### 4. Deploy to AKS

Follow the complete guide: [`docs/TESTING_PLAN_AKS.md`](./TESTING_PLAN_AKS.md)

---

## 📞 DEBUGGING TIPS

```bash
# Enable debug logging in FastAPI
LOG_LEVEL=debug docker compose up api

# Enable debug logging in Streamlit
streamlit run frontend/streamlit_app.py --logger.level=debug

# Inspect all Docker container logs
docker compose logs --tail=100

# Watch real-time API metrics in Prometheus
# http://localhost:9090/graph?g0.expr=fastapi_requests_total

# Use Postman collection (import from docs/postman/)
```

---

## 🔗 Useful Links

| Resource | URL |
|----------|-----|
| Swagger UI | http://localhost:8000/docs |
| Redoc | http://localhost:8000/redoc |
| Mongo Express | http://localhost:8081 |
| Prometheus | http://localhost:9090 |
| Loki | http://localhost:3100 |
| Streamlit Dashboard | http://localhost:8501 |
| FastAPI Health | http://localhost:8000/healthz |
| FastAPI Readiness | http://localhost:8000/readyz |
