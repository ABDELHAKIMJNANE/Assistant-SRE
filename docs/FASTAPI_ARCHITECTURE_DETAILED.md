# 🏗️ FastAPI Architecture — Detailed Design (Assistant-SRE)

This document details the layered architecture, data flows, dependency injection, error handling, async best practices, and service integrations for the Assistant-SRE backend.

---

## 1️⃣ Layered Architecture Overview

**Layers:**
1. **API Layer** — FastAPI routers (`app/api/v1/*`)
2. **Dependencies Layer** — DI helpers (`app/dependencies/*`)
3. **Services Layer** — Business logic & integrations (`app/services/*`)
4. **Models Layer** — Pydantic schemas (`app/models/*`)
5. **Core Layer** — shared utilities (`app/core/*`)
6. **Infrastructure** — external services (MongoDB, Loki, Prometheus, Azure OpenAI, SMTP)

### Mermaid — Layer Interactions

```mermaid
flowchart TB
  subgraph API[API Layer]
    R1[webhook.py]
    R2[incidents.py]
    R3[chat.py]
    R4[health.py]
  end

  subgraph DI[Dependencies Layer]
    D1[get_db_client]
    D2[rate_limit_check]
  end

  subgraph SVC[Services Layer]
    S1[database]
    S2[loki_client]
    S3[prometheus_client]
    S4[llm_engine]
    S5[notification]
    S6[sanitizer]
  end

  subgraph Models[Models Layer]
    M1[AlertPayload]
    M2[IncidentSchema]
    M3[ChatRequest/Response]
    M4[ErrorResponse]
  end

  subgraph Core[Core Layer]
    C1[exceptions]
    C2[logging]
    C3[constants]
  end

  API --> DI
  API --> SVC
  API --> Models
  SVC --> Core
  DI --> Core
```

---

## 2️⃣ Request / Response Flow

### Example: `/api/v1/webhook`
1. **Request** arrives with Grafana JSON payload
2. **Pydantic validation** ensures schema correctness
3. **Rate limiting middleware** applies global protection
4. **Background task** triggers async pipeline
5. **Services** collect logs, metrics, sanitize data
6. **LLM** generates diagnostic solution
7. **Database** persists incident
8. **Notification** sends email

### Mermaid — Request Lifecycle

```mermaid
sequenceDiagram
  autonumber
  participant G as Grafana
  participant API as FastAPI
  participant BG as Background Task
  participant S as Services
  participant DB as MongoDB
  participant LLM as Azure OpenAI

  G->>API: POST /api/v1/webhook
  API->>API: Validate AlertPayload
  API->>API: Rate limit check
  API-->>G: 202 Accepted
  API->>BG: process_alert()
  BG->>S: get_logs() / get_metrics()
  BG->>S: sanitize_logs()
  BG->>LLM: analyze()
  BG->>DB: insert_incident()
  BG->>S: send_alert_email()
```

---

## 3️⃣ Dependency Injection Patterns

- **Database** injected via `get_db_client()`
- **Rate limiting** enforced via middleware and DI helper
- Shared settings via `app.config.settings`

**Why DI?**
- Simplifies testing (mock dependencies)
- Improves modularity
- Avoids global state coupling

---

## 4️⃣ Error Handling (Centralized)

All domain errors extend `AIOpsException` and are handled in `main.py`.

### Mermaid — Error Handling Flow

```mermaid
flowchart LR
  A[Route] --> B[Service]
  B --> C{Exception?}
  C -- No --> D[Response]
  C -- Yes --> E[AIOpsException]
  E --> F[FastAPI Exception Handler]
  F --> G[Structured ErrorResponse]
```

---

## 5️⃣ Async/Await Best Practices

✅ All I/O operations are async:
- MongoDB via **Motor**
- HTTP requests via **httpx.AsyncClient**
- SMTP via **aiosmtplib**
- OpenAI via **AsyncAzureOpenAI**

✅ Background tasks for long-running workloads (`/webhook`).

✅ No blocking calls in request handlers.

---

## 6️⃣ Service Integration Points

| Service | File | Purpose |
|--------|------|---------|
| MongoDB / Cosmos DB | `services/database.py` | Persist incidents + Auto-learning |
| Loki | `services/loki_client.py` | Query logs with LogQL |
| Prometheus | `services/prometheus_client.py` | Query metrics with PromQL |
| Azure OpenAI | `services/llm_engine.py` | Generate diagnostics |
| SMTP Outlook | `services/notification.py` | Notify SREs |

### Mermaid — Service Communication

```mermaid
graph TD
  API[FastAPI] --> Loki
  API --> Prometheus
  API --> OpenAI
  API --> MongoDB
  API --> SMTP
```

---

## 7️⃣ Database Flow

### Mermaid — DB Interaction

```mermaid
sequenceDiagram
  participant API as FastAPI
  participant DB as MongoDB

  API->>DB: insert_incident()
  DB-->>API: incident_id
  API->>DB: find_past_incident()
  DB-->>API: last_valid_solution
  API->>DB: update_incident_status()
  DB-->>API: ok
```

---

## 8️⃣ Performance Optimizations

- **Async I/O everywhere** (no blocking)
- **MongoDB connection pooling** via Motor
- **Rate limiting** to prevent API abuse
- **Log truncation** to reduce token usage
- **Lazy OpenAI client initialization**

---

## 9️⃣ Security & Observability

- Structured JSON logging (`python-json-logger`)
- Sanitization of sensitive data before LLM
- Health endpoints for K8s probes
- Clear error responses with HTTP codes

---

✅ This architecture is production-ready and optimized for AKS deployment with private endpoints.
