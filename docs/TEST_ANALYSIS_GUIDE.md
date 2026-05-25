# 🧪 Guide d'Analyse Complète des Tests — SRE Assistant AIOps

> **Fichier:** `docs/TEST_ANALYSIS_GUIDE.md`  
> **Projet:** Assistant-SRE — Plateforme AIOps de diagnostic d'incidents Kubernetes  
> **Framework de test:** pytest + FastAPI TestClient  
> **Dernière mise à jour:** 2025

---

## Table des Matières

1. [Vue d'ensemble de l'architecture de test](#1-vue-densemble-de-larchitecture-de-test)
2. [Structure des fichiers de test](#2-structure-des-fichiers-de-test)
3. [conftest.py — Fixtures Partagées](#3-conftestpy--fixtures-partagées)
4. [test_webhook.py — Tests du Endpoint Webhook](#4-test_webhookpy--tests-du-endpoint-webhook)
5. [test_sanitizer.py — Tests du Service de Sanitisation](#5-test_sanitizerpy--tests-du-service-de-sanitisation)
6. [Flow Complet d'un Test d'Intégration](#6-flow-complet-dun-test-dintégration)
7. [Couverture de Tests](#7-couverture-de-tests)
8. [Commandes pour Lancer les Tests](#8-commandes-pour-lancer-les-tests)
9. [Stratégie de Mocking](#9-stratégie-de-mocking)
10. [Exemple de Test d'Intégration Complet](#10-exemple-de-test-dintégration-complet)
11. [Guide de Test Local sur WSL Ubuntu](#11-guide-de-test-local-sur-wsl-ubuntu)

---

## 1. Vue d'ensemble de l'Architecture de Test

L'architecture de test d'Assistant-SRE repose sur une isolation complète des dépendances externes (MongoDB, Azure OpenAI, Loki, Prometheus) grâce au **mocking**. Cela permet de tester la logique métier sans avoir besoin d'une infrastructure en cours d'exécution.

```mermaid
graph TB
    subgraph "Suite de Tests"
        A[pytest] --> B[conftest.py<br/>Fixtures & Mocks]
        A --> C[test_webhook.py<br/>Tests d'API]
        A --> D[test_sanitizer.py<br/>Tests unitaires]
        A --> E[test_services/]
    end

    subgraph "Services Mockés"
        B --> F[(MongoDB Mock)]
        B --> G[OpenAI LLM Mock]
        B --> H[Loki Mock]
        B --> I[Prometheus Mock]
        B --> J[Email Mock]
    end

    subgraph "Application Réelle"
        C --> K[FastAPI App]
        D --> L[sanitizer.py]
        K --> M[POST /api/v1/webhook]
        K --> N[GET /healthz]
    end

    style A fill:#4f46e5,color:#fff
    style B fill:#7c3aed,color:#fff
    style F fill:#dc2626,color:#fff
    style G fill:#dc2626,color:#fff
    style H fill:#dc2626,color:#fff
    style I fill:#dc2626,color:#fff
    style J fill:#dc2626,color:#fff
```

### Principe Fondamental

```mermaid
flowchart LR
    A[Test] -->|"1. Configure mocks"| B[conftest.py]
    B -->|"2. Crée client"| C[TestClient FastAPI]
    C -->|"3. Envoie requête"| D[Route FastAPI]
    D -->|"4. Appelle services"| E[Services Mockés]
    E -->|"5. Retourne données"| D
    D -->|"6. Réponse HTTP"| C
    C -->|"7. Vérifie assertions"| A
```

---

## 2. Structure des Fichiers de Test

```
backend/tests/
├── __init__.py                     # Package Python
├── conftest.py                     # Fixtures partagées entre tous les tests
├── test_webhook.py                 # Tests du endpoint POST /api/v1/webhook
├── test_sanitizer.py               # Tests unitaires du sanitizer
├── test_api/                       # Tests d'API spécifiques
├── test_models/                    # Tests des modèles Pydantic
└── test_services/                  # Tests des services individuels
    ├── __init__.py
    ├── test_database.py            # Tests des opérations MongoDB
    ├── test_llm_engine.py          # Tests du moteur LLM Azure OpenAI
    ├── test_loki_client.py         # Tests du client Loki
    └── test_sanitizer.py           # Tests du sanitizer (version services/)
```

```mermaid
graph TD
    subgraph "Tests Root Level"
        A[test_webhook.py<br/>🌐 API Tests]
        B[test_sanitizer.py<br/>🔒 Security Tests]
    end

    subgraph "test_services/"
        C[test_database.py<br/>🗄️ DB Tests]
        D[test_llm_engine.py<br/>🤖 AI Tests]
        E[test_loki_client.py<br/>📝 Logs Tests]
        F[test_sanitizer.py<br/>🧹 Clean Tests]
    end

    G[conftest.py<br/>⚙️ Fixtures] --> A
    G --> B
    G --> C
    G --> D
    G --> E
    G --> F

    style G fill:#059669,color:#fff
    style A fill:#2563eb,color:#fff
    style B fill:#7c3aed,color:#fff
```

---

## 3. conftest.py — Fixtures Partagées

Le fichier `conftest.py` est le **cœur** de l'infrastructure de test. Il définit des **fixtures** qui sont automatiquement disponibles pour tous les tests sans avoir à les importer.

### Vue d'ensemble des Fixtures

```mermaid
mindmap
  root((conftest.py))
    event_loop
      Scope session
      Gère asyncio
      Évite conflits
    client
      FastAPI TestClient
      MongoDB mocké
      Services patchés
    mock_db
      find_past_incident → None
      insert_incident → mock_id
    mock_openai
      analyze → diagnostic JSON
      Simule Azure OpenAI
    mock_loki
      get_logs → liste de logs
      Simule Grafana Loki
    mock_prometheus
      get_metrics → dict métriques
      Simule Prometheus
    mock_notification
      send_alert_email → None
      Simule email SMTP
    sample_webhook_payload
      OOMKilled alert
      Données Grafana réelles
    sample_incident
      Incident complet
      Toutes les données
```

### Détail de Chaque Fixture

#### `event_loop` — Gestion Async

```python
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

**Pourquoi :** FastAPI utilise `asyncio` pour les handlers async. pytest nécessite un event loop partagé pour toute la session de test afin d'éviter des erreurs du type `RuntimeError: Event loop is closed`.

**Scope `session`** : Créé une seule fois pour tous les tests — performant et stable.

---

#### `client` — FastAPI TestClient

```mermaid
sequenceDiagram
    participant T as Test
    participant CF as conftest.py
    participant P as patch()
    participant FA as FastAPI App
    participant TC as TestClient

    T->>CF: Demande fixture "client"
    CF->>P: patch("app.services.database.connect_db")
    CF->>P: patch("app.services.database.get_db")
    P->>FA: Injection des mocks MongoDB
    CF->>TC: TestClient(app)
    TC-->>T: Client HTTP prêt
    T->>TC: POST /api/v1/webhook
    TC->>FA: Route handler
    FA-->>TC: Response HTTP
    TC-->>T: Response object
```

**Ce que fait `client` :**
- Crée un `MagicMock` pour la collection MongoDB avec `find_one`, `insert_one`, `update_one`, et `find` mockés
- Patche `connect_db`, `close_db`, `_client`, et `get_db` du module database
- Instancie `TestClient(app)` — un client HTTP synchrone qui imite les requêtes HTTP réelles
- Yield le client, puis nettoie après le test

**Inputs :** Aucun (fixture autonome)  
**Outputs :** Instance `TestClient` prête à envoyer des requêtes HTTP

---

#### `mock_db` — Base de Données Mockée

```python
@pytest.fixture()
def mock_db():
    with patch("app.api.v1.webhook.database") as mock:
        mock.find_past_incident = AsyncMock(return_value=None)
        mock.insert_incident = AsyncMock(return_value="mock_incident_id")
        yield mock
```

**Pourquoi :** Les routes webhook appellent `database.find_past_incident()` et `database.insert_incident()`. Sans mock, les tests nécessiteraient une vraie instance MongoDB Atlas ou Cosmos DB.

| Méthode mockée | Valeur retournée | Raison |
|---|---|---|
| `find_past_incident()` | `None` | Simule: aucun incident similaire dans le passé |
| `insert_incident()` | `"mock_incident_id"` | Simule: insertion réussie avec un ID |

---

#### `mock_openai` — Service LLM Azure OpenAI

```python
@pytest.fixture()
def mock_openai():
    with patch("app.api.v1.webhook.llm_engine") as mock:
        mock.analyze = AsyncMock(return_value={
            "cause_racine": "Memory leak dans /api/data",
            "solution": "kubectl set resources deployment/fastapi-demo --limits=memory=512Mi",
            "severite": "haute",
            "categorie": "resource_exhaustion",
        })
        yield mock
```

**Pourquoi :** Azure OpenAI GPT-4 coûte de l'argent et nécessite une clé API. Les tests ne doivent pas appeler de vraies APIs LLM.

**Diagnostic retourné :**
```json
{
  "cause_racine": "Memory leak dans /api/data",
  "solution": "kubectl set resources deployment/fastapi-demo --limits=memory=512Mi",
  "severite": "haute",
  "categorie": "resource_exhaustion"
}
```

---

#### `mock_loki` — Collecteur de Logs

```python
@pytest.fixture()
def mock_loki():
    with patch("app.api.v1.webhook.loki_client") as mock:
        mock.get_logs = AsyncMock(return_value=[
            "ERROR: Container killed - OOM",
            "WARNING: Memory usage at 98%",
        ])
        yield mock
```

**Pourquoi :** Loki est un système de logs externe. Sans mock, les tests nécessiteraient un serveur Loki en cours d'exécution.

**Logs retournés simulés :**
- `"ERROR: Container killed - OOM"` — Log d'erreur critique
- `"WARNING: Memory usage at 98%"` — Avertissement précédant l'OOM

---

#### `mock_prometheus` — Métriques d'Infrastructure

```python
@pytest.fixture()
def mock_prometheus():
    with patch("app.api.v1.webhook.prometheus_client") as mock:
        mock.get_metrics = AsyncMock(return_value={
            "memory_usage_bytes": 268435456,   # 256 MB
            "cpu_usage_seconds": 42.5,
            "restart_count": 3,
        })
        yield mock
```

**Pourquoi :** Prometheus scrape les métriques Kubernetes en temps réel. Les tests nécessitent des valeurs prédictibles.

| Métrique | Valeur | Unité |
|---|---|---|
| `memory_usage_bytes` | 268 435 456 | bytes (256 MB) |
| `cpu_usage_seconds` | 42.5 | secondes |
| `restart_count` | 3 | redémarrages |

---

#### `mock_notification` — Notifications Email

```python
@pytest.fixture()
def mock_notification():
    with patch("app.api.v1.webhook.notification") as mock:
        mock.send_alert_email = AsyncMock()
        yield mock
```

**Pourquoi :** Les vrais emails SMTP nécessitent un serveur mail configuré. Les tests vérifient que la méthode est appelée, pas qu'un email est réellement envoyé.

---

#### `sample_webhook_payload` — Données de Test Grafana

```python
@pytest.fixture()
def sample_webhook_payload():
    return {
        "alert_name": "OOMKilled",
        "state": "alerting",
        "labels": {
            "pod": "fastapi-demo-7b9c8d6f4-x2k9p",
            "namespace": "app-demo",
            "container": "fastapi",
        },
        "message": "Container killed due to OOM",
    }
```

**Pourquoi :** Représente un webhook Grafana réel pour une alerte OOMKilled (Out Of Memory). Ce payload valide le modèle Pydantic de validation.

---

#### `sample_incident` — Incident Complet de Test

Représente un incident complet tel qu'il serait stocké en base de données, avec tous les champs remplis incluant le diagnostic AI, le statut, et les timestamps.

---

## 4. test_webhook.py — Tests du Endpoint Webhook

### Classe `TestWebhookEndpoint`

```mermaid
flowchart TD
    subgraph "TestWebhookEndpoint"
        A[test_webhook_returns_202] --> D{POST /api/v1/webhook<br/>payload complet}
        B[test_webhook_invalid_payload] --> E{POST /api/v1/webhook<br/>payload vide}
        C[test_webhook_minimal_payload] --> F{POST /api/v1/webhook<br/>alert_name seulement}

        D -->|"✅ assert 202 Accepted"| G[PASS]
        D -->|"✅ assert 'traitement en cours'"| G
        E -->|"✅ assert 422 Unprocessable"| H[PASS]
        F -->|"✅ assert 202 Accepted"| I[PASS]
    end

    style A fill:#2563eb,color:#fff
    style B fill:#dc2626,color:#fff
    style C fill:#059669,color:#fff
    style G fill:#059669,color:#fff
    style H fill:#059669,color:#fff
    style I fill:#059669,color:#fff
```

---

#### `test_webhook_returns_202`

**Objectif :** Vérifier que le webhook répond `202 Accepted` avec un message de confirmation en français.

**Pourquoi 202 et non 200 ?**  
Le webhook lance un traitement **asynchrone** en arrière-plan (background task). Il ne peut pas attendre la fin de l'analyse AI pour répondre car cela prendrait plusieurs secondes. La réponse 202 signifie "reçu, en cours de traitement".

```
Input:  POST /api/v1/webhook
        Body: {"alert_name": "OOMKilled", "state": "alerting", "labels": {...}, "message": "..."}

Output: HTTP 202 Accepted
        Body: {"message": "Webhook reçu — traitement en cours"}

Assertions:
  ✅ response.status_code == 202
  ✅ "traitement en cours" in response.json()["message"].lower()
```

**Fixtures utilisées :** `client`, `sample_webhook_payload`

---

#### `test_webhook_invalid_payload`

**Objectif :** Vérifier que FastAPI/Pydantic retourne `422 Unprocessable Entity` pour un payload vide.

**Pourquoi :** Le modèle Pydantic `WebhookPayload` requiert au minimum le champ `alert_name`. Un body vide `{}` doit échouer la validation.

```
Input:  POST /api/v1/webhook
        Body: {}

Output: HTTP 422 Unprocessable Entity
        Body: {"detail": [{"loc": ["body", "alert_name"], "msg": "field required", ...}]}

Assertions:
  ✅ response.status_code == 422
```

**Fixtures utilisées :** `client`

---

#### `test_webhook_minimal_payload`

**Objectif :** Vérifier que `alert_name` seul suffit pour déclencher le webhook.

**Pourquoi :** Tous les champs sauf `alert_name` sont optionnels dans le modèle Pydantic. Ce test valide que la conception flexible fonctionne correctement.

```
Input:  POST /api/v1/webhook
        Body: {"alert_name": "TestAlert"}

Output: HTTP 202 Accepted

Assertions:
  ✅ response.status_code == 202
```

**Fixtures utilisées :** `client`

---

### Classe `TestHealthCheck`

```mermaid
sequenceDiagram
    participant T as Test
    participant TC as TestClient
    participant FA as FastAPI /healthz
    participant DB as MongoDB Mock

    T->>TC: GET /healthz
    TC->>FA: Route handler
    FA->>DB: ping() [mocké]
    DB-->>FA: {"ok": 1}
    FA-->>TC: {"status": "ok"}
    TC-->>T: Response 200
    T->>T: assert status_code == 200
    T->>T: assert json["status"] == "ok"
```

#### `test_health_check`

**Objectif :** Vérifier que l'endpoint de santé `/healthz` répond correctement.

**Pourquoi :** Les health checks sont critiques en Kubernetes. Si `/healthz` ne répond pas, Kubernetes redémarre le pod.

```
Input:  GET /healthz

Output: HTTP 200 OK
        Body: {"status": "ok"}

Assertions:
  ✅ response.status_code == 200
  ✅ response.json()["status"] == "ok"
```

**Fixtures utilisées :** `client`

---

## 5. test_sanitizer.py — Tests du Service de Sanitisation

Le sanitizer est un service de sécurité **critique** : il masque les données sensibles avant qu'elles ne soient envoyées à Azure OpenAI ou stockées en base de données.

### Classe `TestSanitizeText`

```mermaid
flowchart LR
    subgraph "Données Sensibles Détectées"
        A[password=MySecret123] -->|regex| B[password=***]
        C[Bearer eyJhbGci...] -->|regex| D[Bearer ***]
        E[192.168.1.100] -->|regex| F[X.X.X.X]
        G[mongodb://admin:Secret@host] -->|regex| H[mongodb://admin:***@host]
        I[api_key=sk-1234...] -->|regex| J[api_key=***]
        K[INFO: Request 200ms] -->|pass-through| L[INFO: Request 200ms]
    end

    style B fill:#dc2626,color:#fff
    style D fill:#dc2626,color:#fff
    style F fill:#dc2626,color:#fff
    style H fill:#dc2626,color:#fff
    style J fill:#dc2626,color:#fff
    style L fill:#059669,color:#fff
```

---

#### `test_password_masking`

**Objectif :** Masquer les mots de passe dans les chaînes de texte.

```
Input:  "Connection: password=MySecret123 established"
Output: "Connection: password=*** established"

Assertions:
  ✅ "MySecret123" not in cleaned   # Le secret est masqué
  ✅ "password=***" in cleaned      # Remplacé par ***
```

**Regex pattern :** `password=\S+` → `password=***`

**Pourquoi crucial :** Les logs Kubernetes peuvent contenir des mots de passe passés en variables d'environnement ou arguments de ligne de commande.

---

#### `test_token_masking`

**Objectif :** Masquer les tokens JWT Bearer.

```
Input:  "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"
Output: "Authorization: Bearer ***"

Assertions:
  ✅ "eyJ" not in cleaned      # Début du JWT masqué
  ✅ "Bearer ***" in cleaned   # Format conservé
```

**Pourquoi crucial :** Les tokens JWT permettent l'accès aux API. Les envoyer à un LLM serait une fuite de sécurité majeure.

---

#### `test_ip_masking`

**Objectif :** Anonymiser les adresses IP des logs.

```
Input:  "Client IP: 192.168.1.100 connected to server 10.0.1.50"
Output: "Client IP: X.X.X.X connected to server X.X.X.X"

Assertions:
  ✅ "192.168.1.100" not in cleaned   # IP privée masquée
  ✅ "10.0.1.50" not in cleaned       # IP serveur masquée
  ✅ "X.X.X.X" in cleaned             # Format anonymisé présent
```

**Pourquoi crucial :** Les adresses IP révèlent la topologie réseau interne — information confidentielle de l'infrastructure.

---

#### `test_connection_string_masking`

**Objectif :** Masquer les mots de passe dans les connection strings de base de données.

```
Input:  "mongodb://admin:SuperSecret@host.cosmos.azure.com:10255"
Output: "mongodb://admin:***@host.cosmos.azure.com:10255"

Assertions:
  ✅ "SuperSecret" not in cleaned   # Password masqué
  ✅ "***" in cleaned               # Remplacé
```

**Pourquoi crucial :** Les connection strings MongoDB/Cosmos DB contiennent les credentials d'accès à la base de données de production.

---

#### `test_api_key_masking`

**Objectif :** Masquer les clés API (OpenAI, Azure, etc.).

```
Input:  "api_key=sk-1234567890abcdef1234567890abcdef"
Output: "api_key=***"

Assertions:
  ✅ "sk-1234567890" not in cleaned   # Clé API masquée
```

---

#### `test_normal_text_unchanged`

**Objectif :** Vérifier que le texte normal non-sensible n'est **pas modifié**.

```
Input:  "INFO: Request completed in 150ms - status 200"
Output: "INFO: Request completed in 150ms - status 200"

Assertions:
  ✅ "Request completed" in cleaned   # Texte préservé
  ✅ "150ms" in cleaned               # Timing préservé
```

**Pourquoi important :** Le sanitizer ne doit pas altérer les informations utiles de diagnostic.

---

### Classe `TestSanitizeLogs`

```mermaid
flowchart TD
    A[Liste de logs bruts] --> B{Nombre de lignes}
    B -->|"> max_lines=50"| C[Tronquer: garder les 50 dernières]
    B -->|"<= max_lines=50"| D[Conserver toutes les lignes]
    B -->|"= 0"| E[Retourner liste vide]
    C --> F[Appliquer sanitize_text sur chaque ligne]
    D --> F
    F --> G[Logs sanitisés et tronqués]

    style C fill:#ea580c,color:#fff
    style E fill:#6b7280,color:#fff
    style G fill:#059669,color:#fff
```

---

#### `test_truncation`

```
Input:  [f"Log line {i}" for i in range(100)]   # 100 lignes
        max_lines=50

Output: 50 lignes (les 50 dernières)

Assertions:
  ✅ len(result) == 50
  ✅ "Log line 99" in result[-1]   # La dernière ligne est conservée
```

**Pourquoi tronquer par la fin :** Les logs les plus récents sont les plus pertinents pour diagnostiquer un incident.

---

#### `test_empty_logs`

```
Input:  []   # Liste vide
        max_lines=50

Output: []

Assertions:
  ✅ result == []
```

**Pourquoi :** Cas limite important — les pods peuvent ne pas avoir encore généré de logs.

---

#### `test_less_than_max`

```
Input:  ["Line 1", "Line 2", "Line 3"]   # 3 lignes < 50
        max_lines=50

Output: ["Line 1", "Line 2", "Line 3"]   # 3 lignes

Assertions:
  ✅ len(result) == 3
```

---

#### `test_sanitization_applied`

```
Input:  ["password=secret123", "Normal log line"]
        max_lines=50

Output: ["password=***", "Normal log line"]

Assertions:
  ✅ "secret123" not in result[0]   # Password masqué dans les logs
```

**Ce test valide la combinaison :** troncature + sanitisation appliquées ensemble.

---

## 6. Flow Complet d'un Test d'Intégration

```mermaid
sequenceDiagram
    participant Client as 🌐 Client HTTP<br/>(Grafana/Test)
    participant FA as ⚡ FastAPI Router
    participant PY as 📋 Pydantic Model<br/>Validation
    participant BG as 🔄 Background Task
    participant DB as 🗄️ MongoDB
    participant AI as 🤖 Azure OpenAI
    participant LK as 📝 Loki
    participant PM as 📊 Prometheus
    participant EM as 📧 Email

    Client->>FA: POST /api/v1/webhook<br/>{"alert_name": "OOMKilled", ...}
    FA->>PY: Valider WebhookPayload
    PY-->>FA: ✅ Payload valide
    FA-->>Client: 202 Accepted (immédiat)
    FA->>BG: Lancer process_alert() en arrière-plan

    Note over BG: Traitement asynchrone

    BG->>DB: find_past_incident(alert_name)
    DB-->>BG: None (pas d'historique)
    BG->>LK: get_logs(pod, namespace)
    LK-->>BG: ["ERROR: OOM", "WARNING: 98%"]
    BG->>PM: get_metrics(pod)
    PM-->>BG: {memory: 256MB, cpu: 42.5s}
    BG->>AI: analyze(logs, metrics, alert)
    AI-->>BG: {cause: "Memory leak", solution: "kubectl..."}
    BG->>DB: insert_incident(incident_data)
    DB-->>BG: "incident_id_123"
    BG->>EM: send_alert_email(incident)
    EM-->>BG: Email envoyé
```

---

## 7. Couverture de Tests

### Chemins Testés ✅

```mermaid
pie title Couverture des Chemins de Code
    "API Webhook (202)" : 25
    "Validation Pydantic (422)" : 15
    "Health Check" : 10
    "Sanitisation Passwords" : 10
    "Sanitisation Tokens JWT" : 10
    "Sanitisation IPs" : 10
    "Sanitisation Connection Strings" : 5
    "Sanitisation API Keys" : 5
    "Troncature Logs" : 5
    "Texte Normal Inchangé" : 5
```

### Tableau de Couverture

| Module | Tests Existants | Couverture Estimée | Commentaire |
|---|---|---|---|
| `api/v1/webhook.py` | ✅ 3 tests | ~70% | Background task non testé |
| `services/sanitizer.py` | ✅ 10 tests | ~95% | Très bien couvert |
| `services/database.py` | ✅ tests dans test_services/ | ~60% | Cas d'erreur partiels |
| `services/llm_engine.py` | ✅ tests dans test_services/ | ~65% | Retry logic non testée |
| `services/loki_client.py` | ✅ tests dans test_services/ | ~60% | Timeout non testé |
| `main.py` | ✅ health check | ~80% | Startup/shutdown partiels |
| `models/` | Partiellement | ~50% | Validation champs optionnels |

### Gaps — Ce Qui N'est PAS Testé ⚠️

```mermaid
flowchart LR
    subgraph "Manquant"
        A[❌ Background Task<br/>process_alert complet]
        B[❌ Retry Logic<br/>LLM Engine]
        C[❌ Timeout Loki<br/>Prometheus]
        D[❌ Erreur MongoDB<br/>Connection failure]
        E[❌ Rate limiting<br/>API endpoints]
        F[❌ Tests de charge<br/>Concurrence]
    end

    style A fill:#dc2626,color:#fff
    style B fill:#ea580c,color:#fff
    style C fill:#ea580c,color:#fff
    style D fill:#dc2626,color:#fff
    style E fill:#6b7280,color:#fff
    style F fill:#6b7280,color:#fff
```

### Recommandations

1. **Tester la background task complète** avec `mock_db + mock_openai + mock_loki + mock_prometheus`
2. **Tests de cas d'erreur** : Que se passe-t-il si Loki timeout ? Si OpenAI retourne une erreur ?
3. **Tests des modèles Pydantic** : Valider tous les champs optionnels
4. **Tests de performance** : Vérifier que le webhook répond en < 100ms même avec 1000 requêtes simultanées

---

## 8. Commandes pour Lancer les Tests

### Lancer tous les tests

```bash
cd backend
python -m pytest tests/ -v
```

**Sortie attendue :**
```
tests/test_webhook.py::TestWebhookEndpoint::test_webhook_returns_202 PASSED
tests/test_webhook.py::TestWebhookEndpoint::test_webhook_invalid_payload PASSED
tests/test_webhook.py::TestWebhookEndpoint::test_webhook_minimal_payload PASSED
tests/test_webhook.py::TestHealthCheck::test_health_check PASSED
tests/test_sanitizer.py::TestSanitizeText::test_password_masking PASSED
...
```

### Lancer un seul fichier

```bash
python -m pytest tests/test_webhook.py -v
python -m pytest tests/test_sanitizer.py -v
```

### Lancer une seule classe

```bash
python -m pytest tests/test_webhook.py::TestWebhookEndpoint -v
```

### Lancer un seul test

```bash
python -m pytest tests/test_webhook.py::TestWebhookEndpoint::test_webhook_returns_202 -v
```

### Voir la couverture de code

```bash
# Couverture basique dans le terminal
python -m pytest --cov=app tests/

# Couverture avec rapport détaillé (fichier par fichier)
python -m pytest --cov=app --cov-report=term-missing tests/

# Générer rapport HTML interactif
python -m pytest --cov=app --cov-report=html tests/
# Ouvrir: htmlcov/index.html
```

### Tests rapides (sans sortie verbose)

```bash
python -m pytest tests/ -q
```

### Tests avec affichage des prints

```bash
python -m pytest tests/ -v -s
```

### Stopper au premier échec

```bash
python -m pytest tests/ -x
```

---

## 9. Stratégie de Mocking

### Pourquoi Mocker les Services Externes ?

```mermaid
graph TD
    A[Tests sans mocks] -->|Nécessite| B[MongoDB en cours]
    A -->|Nécessite| C[Azure OpenAI API Key]
    A -->|Nécessite| D[Loki Server]
    A -->|Nécessite| E[Prometheus Server]
    A -->|Problèmes| F[Tests lents<br/>Coût $$$<br/>Flakiness réseau<br/>État partagé]

    G[Tests avec mocks] -->|Remplace| H[MagicMock MongoDB]
    G -->|Remplace| I[AsyncMock OpenAI]
    G -->|Remplace| J[AsyncMock Loki]
    G -->|Remplace| K[AsyncMock Prometheus]
    G -->|Avantages| L[Tests rapides<br/>Gratuit<br/>Déterministe<br/>Isolation parfaite]

    style F fill:#dc2626,color:#fff
    style L fill:#059669,color:#fff
```

### Comment les Mocks Retournent des Données

Le module `unittest.mock` de Python fournit deux types principaux :

| Type | Usage | Exemple |
|---|---|---|
| `MagicMock` | Fonctions synchrones | `mock.find = MagicMock(return_value=[...])` |
| `AsyncMock` | Fonctions `async def` | `mock.get_logs = AsyncMock(return_value=[...])` |

Les mocks sont injectés via `patch()` qui remplace temporairement l'objet réel par le mock pendant la durée du test. Après le test, `patch()` restaure l'objet original.

### Comment Ajouter un Nouveau Mock

**Exemple : Ajouter un mock pour un service Redis**

```python
# Dans conftest.py
@pytest.fixture()
def mock_redis():
    """Mock du service cache Redis."""
    with patch("app.api.v1.webhook.redis_client") as mock:
        mock.get = AsyncMock(return_value=None)           # Cache miss
        mock.set = AsyncMock(return_value=True)           # Set réussi
        mock.delete = AsyncMock(return_value=1)           # Delete réussi
        yield mock
```

**Utilisation dans un test :**
```python
def test_cached_response(self, client, mock_redis, sample_webhook_payload):
    response = client.post("/api/v1/webhook", json=sample_webhook_payload)
    assert response.status_code == 202
    mock_redis.get.assert_called_once()  # Vérifie que le cache a été vérifié
```

---

## 10. Exemple de Test d'Intégration Complet

Voici un test qui orchestre tous les mocks pour vérifier le flow complet d'un webhook :

```python
"""Exemple de test d'intégration complet."""
import pytest
from unittest.mock import AsyncMock, patch


class TestWebhookIntegration:
    """Test d'intégration complet: webhook → services → réponse."""

    def test_full_webhook_flow(
        self,
        client,
        mock_db,
        mock_openai,
        mock_loki,
        mock_prometheus,
        mock_notification,
        sample_webhook_payload,
    ):
        """
        Scénario: Un webhook OOMKilled arrive.
        
        Flow:
        1. Client envoie POST /api/v1/webhook
        2. FastAPI valide le payload avec Pydantic
        3. Répond 202 immédiatement
        4. Background task appelle tous les services (mockés)
        5. Test vérifie la réponse finale
        """
        # ─── ÉTAPE 1: Envoyer le webhook ───────────────────────────
        response = client.post(
            "/api/v1/webhook",
            json=sample_webhook_payload
        )

        # ─── ÉTAPE 2: Vérifier la réponse immédiate ────────────────
        assert response.status_code == 202, \
            f"Attendu 202, reçu {response.status_code}"
        
        response_body = response.json()
        assert "message" in response_body, \
            "La réponse doit contenir un champ 'message'"
        assert "traitement en cours" in response_body["message"].lower(), \
            f"Message inattendu: {response_body['message']}"

        # ─── ÉTAPE 3: Vérifier que la DB a été consultée ───────────
        # (Optionnel — nécessite que la background task soit terminée)
        # mock_db.find_past_incident.assert_called_once_with("OOMKilled")
        # mock_db.insert_incident.assert_called_once()

        # ─── ÉTAPE 4: Vérifier le format de la réponse ─────────────
        assert isinstance(response_body, dict), \
            "La réponse doit être un objet JSON"
```

### Diagramme du Test d'Intégration

```mermaid
flowchart TD
    A[▶️ Test démarre] --> B[Fixtures initialisées:<br/>client + 5 mocks actifs]
    B --> C[POST /api/v1/webhook<br/>{"alert_name": "OOMKilled", ...}]
    C --> D{Pydantic Validation}
    D -->|❌ Invalide| E[422 → Test échoue]
    D -->|✅ Valide| F[202 Accepted → réponse]
    F --> G{assert status == 202}
    G -->|❌ Échec| H[Test FAILED ❌]
    G -->|✅ OK| I{assert message contient<br/>"traitement en cours"}
    I -->|❌ Échec| H
    I -->|✅ OK| J[Test PASSED ✅]

    style A fill:#4f46e5,color:#fff
    style J fill:#059669,color:#fff
    style H fill:#dc2626,color:#fff
    style E fill:#dc2626,color:#fff
```

---

## 11. Guide de Test Local sur WSL Ubuntu

Ce guide détaille chaque commande pour tester l'application sur Windows Subsystem for Linux (WSL) avec Ubuntu.

### Prérequis Système

```mermaid
flowchart LR
    A[Windows 10/11] --> B[WSL 2<br/>Ubuntu 22.04]
    B --> C[Python 3.11+]
    B --> D[pip / venv]
    B --> E[Docker Desktop<br/>optionnel]
    C --> F[FastAPI + pytest]
```

### Étape 1 — Vérifier WSL

Ouvrez un terminal PowerShell et entrez :

```powershell
# Vérifier la version WSL
wsl --version

# Lister les distributions installées
wsl --list --verbose

# Si Ubuntu n'est pas installé
wsl --install -d Ubuntu-22.04
```

### Étape 2 — Ouvrir Ubuntu dans WSL

```powershell
# Démarrer Ubuntu
wsl -d Ubuntu-22.04
```

Vous êtes maintenant dans le shell Ubuntu. Toutes les commandes suivantes s'exécutent dans WSL Ubuntu.

### Étape 3 — Vérifier Python

```bash
# Vérifier la version Python (besoin de 3.10+)
python3 --version
# Attendu: Python 3.10.x ou 3.11.x

# Si Python n'est pas installé
sudo apt update && sudo apt install -y python3 python3-pip python3-venv
```

### Étape 4 — Cloner le Projet

```bash
# Aller dans le dossier home WSL
cd ~

# Cloner le repository (remplacer par votre URL)
git clone https://github.com/ABDELHAKIMJNANE/Assistant-SRE.git

# Entrer dans le dossier
cd Assistant-SRE
```

### Étape 5 — Configurer l'Environnement Backend

```bash
# Aller dans le dossier backend
cd backend

# Créer un environnement virtuel Python
python3 -m venv .venv

# Activer l'environnement virtuel
source .venv/bin/activate

# Vérifier que le venv est activé (vous devez voir (.venv) dans le prompt)
which python
# Attendu: /home/<votre_user>/Assistant-SRE/backend/.venv/bin/python
```

### Étape 6 — Installer les Dépendances

```bash
# Installer les dépendances de production
pip install -r requirements.txt

# Installer les dépendances de développement/test
pip install -r requirements-dev.txt

# Vérifier les installations clés
pip list | grep -E "fastapi|pytest|httpx"
# Attendu: fastapi, pytest, httpx dans la liste
```

### Étape 7 — Configurer les Variables d'Environnement

```bash
# Copier le fichier d'exemple
cp .env.example .env

# Éditer le fichier .env
nano .env
```

**Contenu minimal du `.env` pour les tests :**

```ini
# MongoDB (pas nécessaire pour les tests, mais requis pour démarrer l'app)
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=sre_assistant

# Azure OpenAI (remplacer par vos vraies valeurs pour tester l'app réelle)
AZURE_OPENAI_KEY=fake-key-for-tests
AZURE_OPENAI_ENDPOINT=https://fake.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=gpt-4

# Loki (optionnel pour les tests unitaires)
LOKI_URL=http://localhost:3100
```

> **Note :** Pour les tests unitaires pytest, les vraies valeurs ne sont pas nécessaires car tous les services sont mockés.

### Étape 8 — Lancer les Tests Unitaires

```bash
# S'assurer que le venv est activé
source .venv/bin/activate

# Lancer tous les tests
python -m pytest tests/ -v

# Lancer les tests webhook uniquement
python -m pytest tests/test_webhook.py -v

# Lancer les tests sanitizer uniquement
python -m pytest tests/test_sanitizer.py -v
```

**Sortie attendue :**

```
============================================================ test session starts
platform linux -- Python 3.11.x, pytest-7.x.x, pluggy-1.x.x
collected 16 items

tests/test_webhook.py::TestWebhookEndpoint::test_webhook_returns_202 PASSED  [ 25%]
tests/test_webhook.py::TestWebhookEndpoint::test_webhook_invalid_payload PASSED  [ 37%]
tests/test_webhook.py::TestWebhookEndpoint::test_webhook_minimal_payload PASSED  [ 50%]
tests/test_webhook.py::TestHealthCheck::test_health_check PASSED  [ 62%]
tests/test_sanitizer.py::TestSanitizeText::test_password_masking PASSED  [ 68%]
tests/test_sanitizer.py::TestSanitizeText::test_token_masking PASSED  [ 75%]
tests/test_sanitizer.py::TestSanitizeText::test_ip_masking PASSED  [ 81%]
tests/test_sanitizer.py::TestSanitizeText::test_connection_string_masking PASSED  [ 87%]
tests/test_sanitizer.py::TestSanitizeText::test_api_key_masking PASSED  [ 93%]
tests/test_sanitizer.py::TestSanitizeText::test_normal_text_unchanged PASSED  [ 100%]
...
============================================================ X passed in X.XXs
```

### Étape 9 — Voir la Couverture de Code

```bash
# Installer pytest-cov si pas encore installé
pip install pytest-cov

# Couverture dans le terminal
python -m pytest --cov=app tests/ -v

# Rapport détaillé avec lignes manquantes
python -m pytest --cov=app --cov-report=term-missing tests/

# Rapport HTML (ouvrable dans navigateur Windows)
python -m pytest --cov=app --cov-report=html tests/

# Ouvrir le rapport HTML (depuis Windows)
# Trouver le chemin du fichier:
echo "$(wslpath -w $(pwd))/htmlcov/index.html"
# Copier ce chemin et l'ouvrir dans Chrome/Edge sur Windows
```

### Étape 10 — Démarrer l'Application (Tests Manuels)

Pour tester l'application réelle (avec vraies connexions) :

```bash
# Démarrer FastAPI avec Uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Dans un autre terminal WSL, tester le health check
curl http://localhost:8000/healthz
# Attendu: {"status": "ok"}

# Tester le webhook
curl -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{"alert_name": "OOMKilled", "state": "alerting"}'
# Attendu: {"message": "Webhook reçu — traitement en cours"}
```

### Étape 11 — Démarrer avec Docker Compose (Recommandé)

```bash
# Revenir à la racine du projet
cd ~/Assistant-SRE

# S'assurer que Docker Desktop est lancé sur Windows avec WSL integration

# Démarrer tous les services
docker compose up -d

# Vérifier que les services démarrent
docker compose ps

# Voir les logs du backend
docker compose logs -f backend

# Arrêter les services
docker compose down
```

### Tableau de Résolution des Problèmes WSL

| Erreur | Cause | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | Répertoire de travail incorrect | `cd backend` puis relancer |
| `pytest: command not found` | venv non activé | `source .venv/bin/activate` |
| `ConnectionRefusedError` lors des tests | Mocks non configurés | Vérifier que `conftest.py` est présent |
| `asyncio.SelectorEventLoop` error | Conflit event loop | Vérifier `event_loop` fixture dans conftest.py |
| `ImportError: cannot import name 'app'` | Dépendances manquantes | `pip install -r requirements.txt` |
| Port 8000 déjà utilisé | Autre processus | `kill $(lsof -t -i:8000)` |

### Récapitulatif des Commandes Essentielles

```bash
# ─── SETUP (une seule fois) ──────────────────────────────────
cd ~/Assistant-SRE/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
cp .env.example .env

# ─── TESTS ───────────────────────────────────────────────────
python -m pytest tests/ -v                          # Tous les tests
python -m pytest tests/test_webhook.py -v           # Tests webhook
python -m pytest tests/test_sanitizer.py -v         # Tests sanitizer
python -m pytest --cov=app --cov-report=html tests/ # Coverage HTML

# ─── DÉMARRER L'APP ──────────────────────────────────────────
uvicorn app.main:app --reload --port 8000           # Dev mode
docker compose up -d                                 # Production-like

# ─── TESTER MANUELLEMENT ─────────────────────────────────────
curl http://localhost:8000/healthz
curl -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{"alert_name": "CPUThrottling"}'
```

---

*Guide créé pour l'équipe SRE — Assistant-SRE AIOps Platform*  
*Framework: FastAPI + pytest + Mermaid Diagrams*
