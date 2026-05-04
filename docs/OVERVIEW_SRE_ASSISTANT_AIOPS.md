# 🛰️ Overview: SRE Assistant AIOps Platform

This document provides a 360° technical view of the AIOps platform. It details the infrastructure, the FastAPI backend architecture, the intelligent workflows, and the secure communication protocols.

---

## 1. Project Identity & Value Proposition
The **SRE Assistant AIOps** is a cognitive layer built on top of Azure infrastructure. It transforms raw monitoring data into actionable intelligence while strictly adhering to **Zero-Trust** and **FinOps** principles.

- **Automated Diagnosis**: Replaces manual log diving with AI-driven root cause analysis.
- **Auto-Learning Loop**: A persistent memory system that learns from human corrections.
- **Privacy-First**: No sensitive data (IPs, passwords) leaves the internal network.

---

## 2. Global Infrastructure View (Zero-Trust Network)

The infrastructure is orchestrated by **Terraform** and isolated in a multi-tier VNet.

```mermaid
graph TD
    subgraph PUBLIC_INTERNET ["🌎 External Access"]
        ADMIN(("👨‍🔧 SRE Engineer"))
        GRAFANA["📊 Grafana Alerting"]
    end

    subgraph AZURE_VNET ["🔒 Azure VNet (10.0.0.0/16)"]
        subgraph SNET_GW ["Subnet 1: Gateway"]
            WAF["🛡️ App Gateway / WAF"]
        end

        subgraph SNET_AKS ["Subnet 2: AKS Cluster"]
            direction TB
            BACKEND["🐍 FastAPI AIOps Engine"]
            FRONTEND["💻 Streamlit Dashboard"]
            OBS["📈 Loki & Prometheus"]
        end

        subgraph SNET_PE ["Subnet 3: Private Endpoints"]
            PE_DB{{"🪐 PE: Cosmos DB"}}
            PE_AI{{"🤖 PE: Azure OpenAI"}}
            PE_KV{{"🔑 PE: Key Vault"}}
        end
    end

    GRAFANA -- "Webhook" --> WAF --> BACKEND
    ADMIN -- "HTTPS" --> WAF --> FRONTEND
    BACKEND -- "Private Link" --> PE_DB
    BACKEND -- "Private Link" --> PE_AI
    BACKEND -- "CSI Driver" --> PE_KV
```

---

## 3. The Brain: FastAPI Backend Architecture

The `assistant-sre` backend is a modular FastAPI application designed for high-concurrency and asynchronous processing.

### Internal Layers:
- **API (Transport)**: Handles HTTP requests, versioning (`/v1`), and background tasks.
- **Models (Validation)**: Pydantic schemas that enforce strict data typing and security.
- **Services (Logic)**:
    - `Loki/Prom Clients`: Async evidence gatherers.
    - `Sanitizer`: Regex-based data anonymization engine.
    - `LLM Engine`: Mega-Prompt generator and OpenAI orchestrator.
    - `Database`: Async Mongo driver (Motor) for incident persistence and memory.
    - `Notification`: SMTP handler for Outlook alerting.

---

## 4. Operational Workflow: The AIOps Cycle

The power of the platform lies in its 8-step operational cycle:

```mermaid
sequenceDiagram
    autonumber
    participant Mon as 📊 Monitoring
    participant Engine as 🐍 AIOps Engine (FastAPI)
    participant Obs as 📈 Loki / Prom
    participant Mem as 🪐 Cosmos DB (Memory)
    participant AI as 🤖 Azure OpenAI
    participant SRE as 👨‍🔧 SRE Dashboard

    Note over Mon, Engine: [Trigger]
    Mon->>Engine: Webhook: Alerte OOMKilled
    
    Note over Engine, Obs: [Evidence]
    Engine->>Obs: GET Logs & Metrics
    Obs-->>Engine: Raw Data
    
    Note over Engine, Mem: [Memory]
    Engine->>Mem: FIND Past Solution (résolu)
    Mem-->>Engine: Reference solution (if exists)
    
    Note over Engine, AI: [Inference]
    Engine->>AI: Mega-Prompt (Evidence + Memory + Sanitization)
    AI-->>Engine: JSON Diagnostic (Cause + Solution)
    
    Note over Engine, Mem: [Persistence]
    Engine->>Mem: INSERT Incident (status='ouvert')
    
    Note over Engine, SRE: [Action]
    Engine->>SRE: Send Email & Update UI
    SRE->>Engine: PUT /resolve (Validation Humaine)
    
    Note over Engine, Mem: [Learning]
    Engine->>Mem: UPDATE (status='résolu', validated_solution=X)
```

---

## 5. Technical Communication Matrix

Every communication is secured and uses specific protocols/ports:

| Connection | Protocol | Security Layer | Purpose |
|---|---|---|---|
| **Grafana → Backend** | HTTP / JSON | WAF + Internal DNS | Alert Trigger |
| **Backend → Loki/Prom** | HTTP / LogQL | Network Isolation | Evidence Collection |
| **Backend → Cosmos DB** | MongoDB Wire (10255) | **Private Endpoint** | Incident Memory |
| **Backend → OpenAI** | HTTPS (443) | **Private Endpoint** | AI Diagnosis |
| **Backend → Key Vault** | HTTPS (443) | **Managed Identity** | Secret Management |
| **Backend → Outlook** | SMTP (587) | TLS Encryption | SRE Notification |
| **Frontend → Backend** | REST API | CORS + WAF | User Interface |

---

## 6. Key Features Detail

### A. Auto-Learning (The "Memory")
The platform doesn't just use AI; it learns from humans. When an SRE clicks the **"Valider"** button, the final solution is stored. The next time the same alert triggers, the backend retrieves this solution and feeds it to the IA, ensuring consistent and expert-validated diagnostics.

### B. Sanitization (The "Privacy")
Logs are never sent "raw" to the cloud. The Sanitizer service masks sensitive data:
- `192.168.1.10` → `X.X.X.X`
- `password=admin123` → `password=***`
- `Bearer eyJ...` → `Bearer ***`

### C. Background Processing
The Backend uses **FastAPI BackgroundTasks** to ensure high availability. The webhook returns a `202 Accepted` to Grafana in milliseconds, while the heavy IA analysis runs in the background.
