# Architecture Backend FastAPI AIOps — Développement Local

Ce document décrit l'architecture complète du backend FastAPI AIOps, ses composants internes, les flux de données, et la stratégie de test local.

---

## 1. Vue Globale — Tous les Composants et Communications

```mermaid
flowchart TD
    classDef entry fill:#e0f2fe,stroke:#0284c7,stroke-width:2px,color:#0f172a
    classDef route fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#0f172a
    classDef model fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#0f172a
    classDef service fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#0f172a
    classDef security fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#0f172a
    classDef ext fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#0f172a
    classDef storage fill:#f0fdf4,stroke:#16a34a,stroke-width:3px,color:#0f172a
    classDef notif fill:#fce7f3,stroke:#ec4899,stroke-width:2px,color:#0f172a

    %% ─── Points d'entrée ───
    STREAMLIT["💻 Streamlit UI"]:::entry
    GRAFANA["📊 Grafana Webhook"]:::entry

    %% ─── Backend FastAPI ───
    subgraph FASTAPI ["🐍 Backend FastAPI"]

        subgraph ROUTES ["📡 API Routes — Endpoints"]
            R_INCIDENTS["GET /api/v1/incidents\n(Liste historique)"]:::route
            R_DETAIL["GET /api/v1/incidents/{id}\n(Détail incident)"]:::route
            R_CHAT["POST /api/v1/chat\n(Discussion IA)"]:::route
            R_WEBHOOK["POST /api/v1/webhook\n(Reçoit Alertes Grafana)"]:::route
            R_RESOLVE["PUT /api/v1/incidents/{id}/resolve\n(Valider solution)"]:::route
            R_HEALTH["GET /healthz\n(Health check)"]:::route
        end

        subgraph MODELS ["📐 Pydantic Models — Validation"]
            M_ALERT["AlertPayload\n(alert_name, state,\nlabels, message)"]:::model
            M_INCIDENT["IncidentSchema\n(id, alert_name, diagnostic,\nstatus, created_at)"]:::model
            M_CHAT["ChatRequest\n(incident_id, question)"]:::model
        end

        subgraph SERVICES ["⚙️ Core Services — Logique Métier"]
            S_LOKI["LokiClient\nRécupère Logs\n(app, DB, erreurs)"]:::service
            S_PROM["PrometheusClient\nRécupère Métriques\n(CPU, RAM, MySQL)"]:::service
            S_SANITIZER["SanitizerService 🔐\nAnonymise Secrets,\nTokens et IPs"]:::security
            S_LLM["LLMEngine\nConstruit Mega-Prompt\net Appel OpenAI"]:::service
            S_COSMOS["CosmosDBClient\nCRUD Incidents\n(FIND/INSERT/UPDATE)"]:::service
            S_NOTIF["NotificationService\nEmail Outlook\n(Résumé alerte)"]:::notif
        end
    end

    %% ─── Services Externes ───
    EXT_PROM["📊 Prometheus"]:::ext
    EXT_LOKI["📝 Loki"]:::ext
    EXT_OPENAI["🤖 Azure OpenAI\n(via PE en AKS)"]:::ext
    EXT_COSMOS["🪐 Cosmos DB\n(via PE en AKS)"]:::ext
    EXT_OUTLOOK["📧 Outlook"]:::ext

    %% ─── Flux d'entrée ───
    GRAFANA -- "JSON Payload\n(alerte déclenchée)" --> R_WEBHOOK
    STREAMLIT -- "GET (lire)" --> R_INCIDENTS
    STREAMLIT -- "GET (détail)" --> R_DETAIL
    STREAMLIT -- "JSON Request" --> R_CHAT
    STREAMLIT -- "PUT (résoudre)" --> R_RESOLVE

    %% ─── Validation Pydantic ───
    R_WEBHOOK -- "Valide schema" --> M_ALERT
    R_INCIDENTS -- "Serialize" --> M_INCIDENT
    R_CHAT -- "Valide schema" --> M_CHAT

    %% ─── Routes → Services ───
    R_WEBHOOK --> S_LOKI
    R_WEBHOOK --> S_PROM
    R_WEBHOOK --> S_COSMOS
    R_WEBHOOK --> S_SANITIZER
    R_WEBHOOK --> S_LLM
    R_WEBHOOK --> S_NOTIF

    R_INCIDENTS --> S_COSMOS
    R_DETAIL --> S_COSMOS
    R_DETAIL --> S_LOKI
    R_DETAIL --> S_PROM
    R_CHAT --> S_COSMOS
    R_CHAT --> S_LLM
    R_RESOLVE --> S_COSMOS

    %% ─── Services → Externes ───
    S_LOKI -- "Scraping LogQL" --> EXT_LOKI
    S_PROM -- "Scraping PromQL" --> EXT_PROM
    S_LOKI -- "Logs bruts" --> S_SANITIZER
    S_PROM -- "Données brutes" --> S_SANITIZER
    S_SANITIZER -- "Contenu nettoyé" --> S_LLM
    S_LLM -- "Mega-Prompt\nDiagnostic IA" --> EXT_OPENAI
    S_COSMOS -- "FIND (Auto-Learning)" --> EXT_COSMOS
    S_COSMOS -- "INSERT Document" --> EXT_COSMOS
    S_COSMOS -- "UPDATE Status" --> EXT_COSMOS
    S_NOTIF -- "Email SMTP/API" --> EXT_OUTLOOK
```

---

## 2. Flux Détaillé du Webhook — Pipeline Complète

Ce diagramme séquence montre **exactement** ce qui se passe quand Grafana envoie une alerte :

```mermaid
sequenceDiagram
    autonumber
    participant G as 📊 Grafana
    participant F as 🐍 FastAPI
    participant L as 📝 Loki
    participant P as 📊 Prometheus
    participant SAN as 🔐 Sanitizer
    participant DB as 🪐 Cosmos DB
    participant AI as 🤖 Azure OpenAI
    participant OL as 📧 Outlook

    G->>F: POST /api/v1/webhook<br/>{alert_name:"OOMKilled",<br/>pod:"fastapi-demo-xxx",<br/>labels:{namespace:"app-demo"}}
    F-->>G: 202 Accepted<br/>"Traitement en cours"

    Note over F: ⚡ BackgroundTask démarre

    rect rgb(219, 234, 254)
        Note over F,P: ① Collecte des Preuves
        F->>L: GET /loki/api/v1/query_range<br/>LogQL: {pod="fastapi-demo-xxx"}<br/>last 30min, limit 100
        L-->>F: 100 lignes de logs<br/>(erreurs, warnings, infos)
        F->>P: GET /api/v1/query<br/>PromQL: container_memory_usage{pod="xxx"}<br/>+ cpu_usage + restart_count
        P-->>F: Métriques brutes<br/>(RAM: 268Mi, CPU: 42s, Restarts: 3)
    end

    rect rgb(254, 249, 195)
        Note over F,DB: ② Auto-Learning — FIND (0 token OpenAI)
        F->>DB: db.incidents.find_one(<br/>  alert_name="OOMKilled",<br/>  status="résolu",<br/>  sort: created_at DESC<br/>)
        alt Incident passé trouvé ✅
            DB-->>F: past_solution =<br/>"Augmenter RAM de 256Mi → 512Mi"
            Note over F: Le Mega-Prompt inclura<br/>cette solution passée
        else Aucun incident passé ❌
            DB-->>F: past_solution = None
            Note over F: Le Mega-Prompt sera<br/>généré sans historique
        end
    end

    rect rgb(254, 226, 226)
        Note over F,SAN: ③ Troncature + ④ Sanitizer Sécurité
        F->>SAN: Logs bruts (100) + Métriques brutes
        Note over SAN: Tronquer à 50 logs + 50 métriques<br/>password=*** | token=***<br/>192.168.1.100 → X.X.X.X<br/>Bearer eyJ... → ***
        SAN-->>F: Données nettoyées et tronquées
    end

    rect rgb(252, 231, 243)
        Note over F,AI: ⑤ Mega-Prompt Azure OpenAI
        F->>AI: POST /chat/completions<br/>system: "Tu es un SRE expert K8s"<br/>user: {<br/>  contexte_alerte: "OOMKilled...",<br/>  logs_nettoyés: [...50 lignes...],<br/>  métriques: [...50 points...],<br/>  solution_passée: "Augmenter RAM..."<br/>}
        AI-->>F: {<br/>  cause_racine: "Memory leak dans /api/data",<br/>  solution: "kubectl set resources...",<br/>  severite: "haute",<br/>  categorie: "resource_exhaustion"<br/>}
    end

    rect rgb(220, 252, 231)
        Note over F,DB: ⑥ Sauvegarde — INSERT
        F->>DB: db.incidents.insert_one({<br/>  alert_name: "OOMKilled",<br/>  diagnostic: {...},<br/>  past_solution_used: "...",<br/>  status: "ouvert",<br/>  created_at: now()<br/>})
        DB-->>F: inserted_id = "664..."
    end

    rect rgb(252, 231, 243)
        Note over F,OL: ⑦ Notification Email Outlook
        F->>OL: Envoyer Email via SMTP/API<br/>À: sre-team@company.com<br/>Sujet: "🔴 Alerte OOMKilled — app-demo"<br/>Corps:<br/>• Pod: fastapi-demo-xxx<br/>• Cause: Memory leak<br/>• Solution proposée: kubectl set...<br/>• Sévérité: haute
    end
```

---

## 3. Flux Auto-Learning — Comment Cosmos DB Apprend

L'Auto-Learning est le mécanisme qui permet à FastAPI de **s'améliorer avec le temps** sans coûter de tokens OpenAI supplémentaires.

```mermaid
flowchart TD
    classDef alert fill:#fecaca,stroke:#dc2626,stroke-width:2px,color:#0f172a
    classDef db fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#0f172a
    classDef decision fill:#fef9c3,stroke:#ca8a04,stroke-width:2px,color:#0f172a
    classDef ai fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#0f172a
    classDef sre fill:#dbeafe,stroke:#2563eb,stroke-width:2px,color:#0f172a

    ALERTE["🔴 Nouvelle Alerte\nOOMKilled"]:::alert

    subgraph AUTOLEARN ["🧠 Phase Auto-Learning (0 Token OpenAI)"]
        FIND["FIND dans Cosmos DB\ndb.incidents.find_one(\n  alert_name='OOMKilled',\n  status='résolu',\n  sort: date DESC\n)"]:::db

        CHECK{"Incident\nrésolu\ntrouvé ?"}:::decision

        YES["✅ past_solution =\n'kubectl set resources...\n--limits=memory=512Mi'"]
        NO["❌ past_solution = None\n(Première occurrence)"]
    end

    ALERTE --> FIND --> CHECK
    CHECK -- "OUI" --> YES
    CHECK -- "NON" --> NO

    subgraph PROMPT ["⑤ Mega-Prompt OpenAI"]
        P_WITH["Prompt ENRICHI :\n• Contexte alerte\n• 50 Logs + 50 Métriques\n• 💡 Solution passée incluse\n→ IA plus précise"]:::ai
        P_WITHOUT["Prompt STANDARD :\n• Contexte alerte\n• 50 Logs + 50 Métriques\n• Pas d'historique\n→ IA analyse from scratch"]:::ai
    end

    YES --> P_WITH
    NO --> P_WITHOUT

    SAVE["💾 INSERT nouvel incident\ndans Cosmos DB\n(status: 'ouvert')"]:::db
    P_WITH --> SAVE
    P_WITHOUT --> SAVE

    subgraph VALIDATION ["👨‍🔧 Validation SRE (Plus tard)"]
        SRE["L'ingénieur SRE valide\nla solution via Streamlit\n→ PUT /incidents/{id}/resolve"]:::sre
        UPDATE["UPDATE Cosmos DB\nstatus: 'résolu'\nresolved_at: now()"]:::db
    end

    SAVE -.-> SRE --> UPDATE

    UPDATE -. "La prochaine fois que\nOOMKilled arrive, FIND\ntrouvera cette solution ✅" .-> FIND
```

### Les 3 Scénarios de Cosmos DB

```text
SCÉNARIO 1 — Alerte Nouvelle (Jamais vue)
  FastAPI → Cosmos DB : FIND(alert_name='OOMKilled', status='résolu') → Rien ❌
  FastAPI → OpenAI    : Prompt SANS historique
  FastAPI → Cosmos DB : INSERT(incident + diagnostic, status='ouvert')
  FastAPI → Outlook   : Email à l'équipe SRE

SCÉNARIO 2 — Alerte Récurrente (Déjà résolue avant)
  FastAPI → Cosmos DB : FIND(alert_name='OOMKilled', status='résolu') → Solution trouvée ✅
  FastAPI → OpenAI    : Prompt AVEC "La dernière fois on a fait: kubectl set resources..."
  FastAPI → Cosmos DB : INSERT(nouvel incident + nouveau diagnostic + past_solution_used)
  FastAPI → Outlook   : Email enrichi avec historique

SCÉNARIO 3 — Validation Humaine (Interface Streamlit)
  Streamlit → FastAPI : PUT /api/v1/incidents/{id}/resolve
  FastAPI → Cosmos DB : UPDATE(status='résolu', resolved_at=now())
  = L'Auto-Learning est prêt pour la prochaine alerte identique
```

---

## 4. Service de Notification — Email Outlook

FastAPI envoie un email automatique à l'ingénieur SRE via **Outlook SMTP** ou **Microsoft Graph API** quand un incident est détecté.

```mermaid
flowchart LR
    classDef api fill:#eff6ff,stroke:#2563eb,stroke-width:2px,color:#0f172a
    classDef notif fill:#fce7f3,stroke:#ec4899,stroke-width:2px,color:#0f172a
    classDef email fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#0f172a

    FASTAPI["🐍 FastAPI\nNotificationService"]:::api

    subgraph EMAIL_CONTENT ["📧 Contenu de l'Email"]
        SUJET["Sujet:\n🔴 Alerte OOMKilled — Pod fastapi-demo"]:::notif
        CORPS["Corps:\n━━━━━━━━━━━━━━━━━━━━━━\n📍 Pod: fastapi-demo-7b9c8d6f4-x2k9p\n📍 Namespace: app-demo\n📍 Sévérité: HAUTE\n━━━━━━━━━━━━━━━━━━━━━━\n🔍 Cause racine:\nMemory leak dans /api/data\n━━━━━━━━━━━━━━━━━━━━━━\n💡 Solution proposée:\nkubectl set resources...\n━━━━━━━━━━━━━━━━━━━━━━\n🔗 Voir détails: Dashboard URL"]:::notif
    end

    OUTLOOK["📧 Outlook\n(SMTP / Graph API)"]:::email
    SRE["👨‍🔧 Ingénieur SRE\n(reçoit l'email)"]:::email

    FASTAPI --> EMAIL_CONTENT --> OUTLOOK --> SRE
```

### Options d'implémentation (choix à faire)

| Méthode | Avantage | Inconvénient |
|---|---|---|
| **SMTP direct** (`smtplib`) | Simple, pas de dépendance | Nécessite mot de passe SMTP Outlook |
| **Microsoft Graph API** | Plus sécurisé, OAuth2 | Configuration Azure AD plus complexe |

> **Recommandation :** Utiliser **SMTP** (`smtp.office365.com:587`) pour le PFE. C'est plus simple et suffisant pour une démo.

---

## 5. Architecture de la Stack Docker Compose (Local)

```mermaid
flowchart TD
    classDef api fill:#eff6ff,stroke:#2563eb,stroke-width:2px,color:#0f172a
    classDef db fill:#f0fdf4,stroke:#16a34a,stroke-width:2px,color:#0f172a
    classDef obs fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#0f172a
    classDef gen fill:#fce7f3,stroke:#ec4899,stroke-width:2px,color:#0f172a
    classDef ext fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#0f172a

    DEV((("👨‍💻 Développeur")))

    subgraph DOCKER ["🐳 Docker Compose — Stack Locale"]
        subgraph API_LAYER ["Couche API"]
            FASTAPI["🐍 FastAPI\nport 8000\n(hot-reload)"]:::api
        end

        subgraph DATA_LAYER ["Couche Données"]
            MONGO["🍃 MongoDB 7.0\nport 27017\n(simule Cosmos DB)"]:::db
            MONGO_EXPRESS["🖥️ Mongo Express\nport 8081\n(GUI MongoDB)"]:::db
        end

        subgraph OBS_LAYER ["Couche Observabilité"]
            LOKI["📝 Loki\nport 3100"]:::obs
            PROM["📊 Prometheus\nport 9090"]:::obs
            LOG_GEN["🔥 Log Generator\n(simule pods K8s)"]:::gen
        end
    end

    subgraph CLOUD ["☁️ Azure (via Internet en local)"]
        OPENAI["🤖 Azure OpenAI"]:::ext
        OUTLOOK["📧 Outlook SMTP"]:::ext
    end

    DEV -- "curl / Swagger UI\nhttp://localhost:8000/docs" --> FASTAPI
    DEV -- "Voir données\nhttp://localhost:8081" --> MONGO_EXPRESS

    FASTAPI -- "motor async\nFIND / INSERT / UPDATE" --> MONGO
    FASTAPI -- "httpx GET\nLogQL" --> LOKI
    FASTAPI -- "httpx GET\nPromQL" --> PROM
    FASTAPI -- "openai SDK\nMega-Prompt" --> OPENAI
    FASTAPI -- "smtplib\nEmail alerte" --> OUTLOOK

    LOG_GEN -- "POST logs simulés" --> LOKI
    LOG_GEN -- "Expose /metrics" --> PROM
    PROM -- "Scrape /metrics" --> LOG_GEN
    MONGO_EXPRESS --> MONGO
```

---

## 6. Structure du Code FastAPI

```text
PFE/
└── backend/
    ├── app/
    │   ├── __init__.py
    │   ├── main.py                    # Point d'entrée FastAPI + Lifespan
    │   ├── config.py                  # Settings Pydantic (lecture .env)
    │   │
    │   ├── api/
    │   │   ├── __init__.py
    │   │   └── v1/
    │   │       ├── __init__.py
    │   │       ├── router.py          # Agrégation des routes v1
    │   │       ├── webhook.py         # POST /api/v1/webhook  (Grafana → Pipeline)
    │   │       ├── incidents.py       # GET  /api/v1/incidents (Liste historique)
    │   │       ├── incident_detail.py # GET  /api/v1/incidents/{id} (Détail)
    │   │       ├── chat.py            # POST /api/v1/chat     (Discussion IA)
    │   │       └── resolve.py         # PUT  /api/v1/incidents/{id}/resolve
    │   │
    │   ├── services/
    │   │   ├── __init__.py
    │   │   ├── database.py            # CosmosDBClient : Motor async (FIND/INSERT/UPDATE)
    │   │   ├── loki_client.py         # LokiClient : httpx async → LogQL
    │   │   ├── prometheus_client.py   # PrometheusClient : httpx async → PromQL
    │   │   ├── sanitizer.py           # SanitizerService : Regex nettoyage
    │   │   ├── llm_engine.py          # LLMEngine : Mega-Prompt + Azure OpenAI
    │   │   └── notification.py        # NotificationService : Email via Outlook SMTP
    │   │
    │   ├── models/
    │   │   ├── __init__.py
    │   │   ├── webhook.py             # AlertPayload (Pydantic)
    │   │   ├── incident.py            # IncidentSchema (Pydantic)
    │   │   └── chat.py                # ChatRequest (Pydantic)
    │   │
    │   └── core/
    │       ├── __init__.py
    │       └── logging.py             # Logging structuré
    │
    ├── tests/
    │   ├── conftest.py
    │   ├── test_webhook.py
    │   ├── test_incidents.py
    │   ├── test_sanitizer.py
    │   └── test_chat.py
    │
    ├── scripts/
    │   └── seed_logs.py               # Injecter des logs test dans Loki
    │
    ├── .env.example
    ├── .env                           # (dans .gitignore)
    ├── .gitignore
    ├── Dockerfile
    ├── docker-compose.yml
    ├── prometheus.yml
    ├── loki-config.yml
    └── requirements.txt
```

---

## 7. Endpoints API REST

| Méthode | Route | Entrée | Service utilisé | Sortie |
|---|---|---|---|---|
| `POST` | `/api/v1/webhook` | `AlertPayload` (Grafana) | LokiClient, PrometheusClient, SanitizerService, CosmosDBClient (FIND + INSERT), LLMEngine, NotificationService | `202 {message}` |
| `GET` | `/api/v1/incidents` | Query: `?skip=0&limit=20` | CosmosDBClient (FIND) | `200 [{incident}, ...]` |
| `GET` | `/api/v1/incidents/{id}` | Path: `id` | CosmosDBClient (FIND), LokiClient, PrometheusClient | `200 {incident + logs + metrics}` |
| `POST` | `/api/v1/chat` | `ChatRequest` | CosmosDBClient (FIND), LLMEngine | `200 {answer}` |
| `PUT` | `/api/v1/incidents/{id}/resolve` | Path: `id` | CosmosDBClient (UPDATE) | `200 {message}` |
| `GET` | `/healthz` | _(vide)_ | _(ping DB)_ | `200 {status: "ok"}` |

---

## 8. Variables d'Environnement

| Variable | Local (`.env`) | AKS (K8s Secret) |
|---|---|---|
| `MONGODB_URL` | `mongodb://mongodb:27017/aiops_db` | `mongodb://cosmos-sre-xxx:CLE@...` |
| `MONGODB_DB_NAME` | `aiops_db` | `aiops_db` |
| `OPENAI_ENDPOINT` | `https://openai-sre-xxx.openai.azure.com/` | Idem (via PE) |
| `OPENAI_API_KEY` | Clé directe | Key Vault → CSI |
| `OPENAI_DEPLOYMENT` | `gpt-35-turbo` | `gpt-35-turbo` |
| `LOKI_URL` | `http://loki:3100` | `http://loki.monitoring.svc:3100` |
| `PROMETHEUS_URL` | `http://prometheus:9090` | `http://prometheus.monitoring.svc:9090` |
| `SMTP_HOST` | `smtp.office365.com` | `smtp.office365.com` |
| `SMTP_PORT` | `587` | `587` |
| `SMTP_USER` | Email Outlook | Email Outlook |
| `SMTP_PASSWORD` | Mot de passe | Key Vault → CSI |
| `SRE_EMAIL` | Email destinataire | Email destinataire |

---

## 9. Migration Local → AKS (Zéro Changement de Code Python)

| Élément | Local | AKS | Code modifié ? |
|---|---|---|---|
| Base de données | MongoDB conteneur | Cosmos DB via Private Endpoint | **NON** — même driver `motor` |
| OpenAI | Internet direct | Private Endpoint `10.0.2.x` | **NON** — même SDK |
| Loki | `http://loki:3100` | DNS K8s interne | **NON** — variable d'env |
| Prometheus | `http://prometheus:9090` | DNS K8s interne | **NON** — variable d'env |
| Outlook | Internet direct | Internet direct | **NON** — même SMTP |
| Secrets | Fichier `.env` | Key Vault → CSI → K8s Secret | **NON** — `os.getenv()` |
| **Total changements Python** | — | — | **ZÉRO** |
