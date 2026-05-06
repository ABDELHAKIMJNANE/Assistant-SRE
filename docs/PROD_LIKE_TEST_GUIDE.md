# Guide de Test Complet — Style Production
## Assistant-SRE : Flux de Bout en Bout avec Docker

> **Scénario** : Le pod `fastapi-demo-7b9c8d6f4-x2k9p` (namespace `app-demo`) est en **pression mémoire critique** — 486 Mi utilisés sur 512 Mi alloués (95%). Sans intervention, l'OOM Killer le terminera dans quelques minutes.
>
> Ce guide couvre l'intégralité du flux : injection des données → collecte → analyse IA → notification email → interface → approbation → stockage final.

---

## Table des Matières

1. [Prérequis et Configuration](#1-prérequis-et-configuration)
2. [Démarrage de la Stack Docker](#2-démarrage-de-la-stack-docker)
3. [Vérification des Services](#3-vérification-des-services)
4. [Injection de 100 Logs dans Loki](#4-injection-de-100-logs-dans-loki)
5. [Génération des 100 Métriques Prometheus](#5-génération-des-100-métriques-prometheus)
6. [Déclenchement du Webhook (Simulation Grafana)](#6-déclenchement-du-webhook-simulation-grafana)
7. [Traitement par FastAPI — Pipeline Étape par Étape](#7-traitement-par-fastapi--pipeline-étape-par-étape)
8. [Le Mega-Prompt envoyé au Modèle IA](#8-le-mega-prompt-envoyé-au-modèle-ia)
9. [Format de Réponse Attendu de l'IA](#9-format-de-réponse-attendu-de-lia)
10. [Notification Email — MailHog](#10-notification-email--mailhog)
11. [Interface Assistant-SRE — Streamlit](#11-interface-assistant-sre--streamlit)
12. [Approbation et Stockage Final](#12-approbation-et-stockage-final)
13. [Vérification en Base MongoDB](#13-vérification-en-base-mongodb)
14. [Checklist de Validation Finale](#14-checklist-de-validation-finale)

---

## 1. Prérequis et Configuration

### 1.1 Outils requis

```bash
# Vérifier que Docker et Docker Compose sont installés
docker --version
# Output attendu : Docker version 24.x.x ou supérieur

docker compose version
# Output attendu : Docker Compose version v2.x.x

python3 --version
# Output attendu : Python 3.11.x

curl --version
# Output attendu : curl 7.x ou supérieur (pour les commandes de test)
```

### 1.2 Configuration du fichier .env

```bash
# Depuis le répertoire backend/
cd /path/to/Assistant-SRE/backend

# Copier le fichier d'exemple
cp .env.example .env

# Ouvrir et remplir les valeurs
nano .env
```

Contenu du `.env` pour les tests locaux :

```ini
# MongoDB
MONGODB_URL=mongodb://mongodb:27017
MONGODB_DB_NAME=aiops_db

# Azure OpenAI (OBLIGATOIRE pour le test complet)
OPENAI_ENDPOINT=https://votre-instance.openai.azure.com/
OPENAI_API_KEY=votre-clé-api-ici
OPENAI_DEPLOYMENT=gpt-35-turbo
OPENAI_API_VERSION=2024-02-01

# Observabilité
LOKI_URL=http://loki:3100
PROMETHEUS_URL=http://prometheus:9090

# Email — MailHog (test local)
SMTP_HOST=mailhog
SMTP_PORT=1025
SMTP_USE_TLS=false
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM_NAME=Assistant SRE
SRE_EMAIL=sre-team@example.com

# Logging
LOG_LEVEL=INFO
```

> ⚠️ **Important** : Sans clé Azure OpenAI valide, le backend retournera une erreur sur le Mega-Prompt. Pour tester sans OpenAI, le diagnostic aura `"categorie": "api_error"` et l'email ne sera pas envoyé (comportement intentionnel).

---

## 2. Démarrage de la Stack Docker

### 2.1 Lancer tous les services

```bash
# Depuis le répertoire backend/
cd /path/to/Assistant-SRE/backend

# Construire et démarrer tous les conteneurs
docker compose up -d --build

# Output attendu :
# [+] Running 7/7
#  ✔ Container backend-mongodb-1       Started
#  ✔ Container backend-mailhog-1       Started
#  ✔ Container backend-loki-1          Started
#  ✔ Container backend-prometheus-1    Started
#  ✔ Container backend-api-1           Started
#  ✔ Container backend-mongo-express-1 Started
#  ✔ Container backend-log-generator-1 Started
```

### 2.2 Vérifier que les conteneurs tournent

```bash
docker compose ps

# Output attendu :
# NAME                          STATUS          PORTS
# backend-api-1                 Up              0.0.0.0:8000->8000/tcp
# backend-loki-1                Up              0.0.0.0:3100->3100/tcp
# backend-log-generator-1       Up
# backend-mailhog-1             Up              0.0.0.0:1025->1025/tcp, 0.0.0.0:8025->8025/tcp
# backend-mongo-express-1       Up              0.0.0.0:8081->8081/tcp
# backend-mongodb-1             Up              0.0.0.0:27017->27017/tcp
# backend-prometheus-1          Up              0.0.0.0:9090->9090/tcp
```

### 2.3 Attendre que les services soient prêts

```bash
# Attendre 15 secondes pour que tous les services démarrent complètement
sleep 15

# Vérifier les logs du backend pour confirmer le démarrage
docker compose logs api --tail=20

# Output attendu :
# backend-api-1  | INFO:     Started server process [1]
# backend-api-1  | INFO:     Waiting for application startup.
# backend-api-1  | INFO:     ✅ MongoDB connecté : mongodb://mongodb:27017...
# backend-api-1  | INFO:     Application startup complete.
# backend-api-1  | INFO:     Uvicorn running on http://0.0.0.0:8000
```

---

## 3. Vérification des Services

Exécuter chaque commande et vérifier que le statut HTTP est 200.

### 3.1 Backend FastAPI

```bash
curl -s http://localhost:8000/api/v1/health | python3 -m json.tool

# Output attendu :
# {
#     "status": "ok",
#     "version": "1.0.0",
#     "environment": "development"
# }
```

### 3.2 Loki

```bash
curl -s http://localhost:3100/ready

# Output attendu :
# ready
```

### 3.3 Prometheus

```bash
curl -s http://localhost:9090/-/healthy

# Output attendu :
# Prometheus Server is Healthy.
```

### 3.4 MailHog (Interface email de test)

```bash
curl -s http://localhost:8025/api/v2/messages | python3 -m json.tool | head -5

# Output attendu :
# {
#     "total": 0,
#     "count": 0,
#     "start": 0,
#     ...
# }
```

### 3.5 Mongo Express (Interface MongoDB)

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8081

# Output attendu :
# 200
```

✅ **Point de vérification 1** : Tous les services répondent. On peut commencer l'injection des données.

---

## 4. Injection de 100 Logs dans Loki

### 4.1 Le script d'injection

Créer le fichier `/tmp/inject_loki_100.py` :

```python
#!/usr/bin/env python3
"""
Injecte 100 logs réalistes dans Loki simulant un pod en pression mémoire.
Scénario : HighMemoryPressure — pod fastapi-demo-7b9c8d6f4-x2k9p
           mémoire : 486Mi/512Mi = 95% — approche de l'OOMKilled
"""
import json
import time
import urllib.request
from datetime import datetime, timedelta

LOKI_URL = "http://localhost:3100/loki/api/v1/push"
POD = "fastapi-demo-7b9c8d6f4-x2k9p"
NAMESPACE = "app-demo"
CONTAINER = "fastapi"

# Générer les timestamps : 100 logs sur les 30 dernières minutes
now = datetime.utcnow()
start = now - timedelta(minutes=29, seconds=30)

# 100 lignes de log simulant la dégradation mémoire au fil du temps
LOG_LINES = [
    # T=0min — état initial normal
    ("info",    "INFO: Application started — heap size: 180Mi, limit: 512Mi"),
    ("info",    "INFO: Incoming request GET /api/health — status 200 — 3ms"),
    ("info",    "INFO: Incoming request POST /api/data — payload size: 2MB"),
    ("info",    "INFO: Database connection pool: 10/50 connections active"),
    ("info",    "INFO: Request completed GET /api/users — 200 — 12ms"),
    # T=1min — début du traitement intensif
    ("info",    "INFO: Processing batch job #4521 — records: 50000"),
    ("info",    "INFO: Incoming request POST /api/batch — payload size: 15MB"),
    ("warning", "WARNING: Memory usage at 42% — 215Mi/512Mi allocated"),
    ("info",    "INFO: GC cycle completed — freed 12Mi — heap now: 203Mi"),
    ("info",    "INFO: Request completed POST /api/batch — 200 — 450ms"),
    # T=2min — charge croissante
    ("info",    "INFO: Processing batch job #4522 — records: 75000"),
    ("warning", "WARNING: Memory usage at 51% — 261Mi/512Mi allocated"),
    ("info",    "INFO: GC cycle triggered — heap pressure detected"),
    ("warning", "WARNING: Slow query detected — 1250ms execution time"),
    ("info",    "INFO: Connection pool: 18/50 connections active"),
    # T=3min — fuite mémoire visible
    ("warning", "WARNING: Memory usage at 58% — 297Mi/512Mi allocated"),
    ("warning", "WARNING: GC pressure detected — heap size growing unbounded"),
    ("info",    "INFO: GC pause duration: 250ms — objects not collected: 15000"),
    ("warning", "WARNING: Slow query detected — 2100ms execution time"),
    ("warning", "WARNING: Response time degrading — p99: 850ms"),
    # T=4min — dégradation des performances
    ("warning", "WARNING: Memory usage at 65% — 333Mi/512Mi allocated"),
    ("warning", "WARNING: Connection pool exhausted — waiting for available connection"),
    ("warning", "WARNING: GC pause duration: 450ms — blocking request processing"),
    ("info",    "INFO: Circuit breaker OPEN — database connection threshold exceeded"),
    ("warning", "WARNING: Request queue depth: 45 — approaching limit of 100"),
    # T=5min — seuil d'alerte franchi
    ("warning", "WARNING: Memory usage at 72% — 369Mi/512Mi allocated"),
    ("error",   "ERROR: Request timeout — client disconnected after 30s"),
    ("warning", "WARNING: GC overhead limit approaching — 85% of time in GC"),
    ("error",   "ERROR: Failed to allocate 64Mi for large payload processing"),
    ("warning", "WARNING: Heap dump triggered — size: 369Mi"),
    # T=6min — pression critique
    ("warning", "WARNING: Memory usage at 78% — 400Mi/512Mi allocated"),
    ("error",   "ERROR: Connection refused to database on port 3306 — pool exhausted"),
    ("error",   "ERROR: Failed to process request — out of memory for allocation"),
    ("warning", "WARNING: Container approaching memory limit — 78% used"),
    ("error",   "ERROR: Slow query timeout after 5000ms — query aborted"),
    # T=7min — impact utilisateurs
    ("error",   "ERROR: Request failed — 503 Service Unavailable"),
    ("error",   "ERROR: Request failed — 503 Service Unavailable"),
    ("error",   "ERROR: Request failed — 503 Service Unavailable"),
    ("warning", "WARNING: Memory usage at 83% — 425Mi/512Mi allocated"),
    ("error",   "ERROR: GC overhead limit exceeded — OutOfMemoryError thrown"),
    # T=8min — OOM imminent
    ("warning", "WARNING: Memory usage at 87% — 445Mi/512Mi allocated"),
    ("error",   "ERROR: Failed to allocate 128Mi for request processing"),
    ("error",   "ERROR: java.lang.OutOfMemoryError: Java heap space"),
    ("error",   "ERROR: CrashLoopBackOff — container restarted 1 times"),
    ("warning", "WARNING: Container restart detected — reinitializing connections"),
    # T=9min — redémarrage et reprise
    ("info",    "INFO: Container restarted — heap size: 180Mi (reset), limit: 512Mi"),
    ("info",    "INFO: Reconnecting to database — attempt 1/3"),
    ("info",    "INFO: Database connection re-established — pool: 0/50"),
    ("info",    "INFO: Service recovering — processing queued requests"),
    ("warning", "WARNING: Backlog: 230 requests queued during restart"),
    # T=10min — rechargement de la charge
    ("info",    "INFO: Processing queued requests — 230 pending"),
    ("warning", "WARNING: Memory usage at 47% — 241Mi/512Mi allocated"),
    ("warning", "WARNING: Rapid memory growth detected — +30Mi in last 60 seconds"),
    ("warning", "WARNING: Memory usage at 55% — 282Mi/512Mi allocated"),
    ("warning", "WARNING: GC pressure detected — heap size growing unbounded"),
    # T=11min — même pattern de fuite
    ("warning", "WARNING: Memory usage at 62% — 318Mi/512Mi allocated"),
    ("warning", "WARNING: Slow query detected — 1850ms execution time"),
    ("warning", "WARNING: GC pause duration: 380ms — blocking request processing"),
    ("warning", "WARNING: Memory usage at 69% — 354Mi/512Mi allocated"),
    ("error",   "ERROR: Failed to allocate 32Mi for buffer"),
    # T=12min — accélération de la dégradation
    ("warning", "WARNING: Memory usage at 75% — 384Mi/512Mi allocated"),
    ("error",   "ERROR: Heap dump written to /tmp/heapdump-1234.hprof"),
    ("warning", "WARNING: Connection pool exhausted — queue: 28 requests waiting"),
    ("error",   "ERROR: Request timeout — 30s limit exceeded"),
    ("warning", "WARNING: Memory usage at 81% — 415Mi/512Mi allocated"),
    # T=13min — dégradation sévère
    ("error",   "ERROR: OutOfMemoryError: Cannot allocate 256Mi — heap exhausted"),
    ("error",   "ERROR: Request failed — 500 Internal Server Error — OOM"),
    ("warning", "WARNING: Memory usage at 86% — 440Mi/512Mi allocated"),
    ("error",   "ERROR: GC cannot reclaim memory — live objects: 180000"),
    ("error",   "ERROR: Failed to allocate 64Mi for request processing"),
    # T=14min — niveau critique
    ("warning", "WARNING: Memory usage at 89% — 456Mi/512Mi allocated"),
    ("error",   "ERROR: Connection refused to database on port 3306"),
    ("error",   "ERROR: All retry attempts exhausted — 503 to clients"),
    ("error",   "ERROR: Heap fragmentation critical — GC ineffective"),
    ("warning", "WARNING: Memory usage at 91% — 466Mi/512Mi allocated"),
    # T=15min — limite imminente (logs plus récents, seront gardés par le Sanitizer)
    ("error",   "ERROR: Memory usage at 93% — 476Mi/512Mi — OOMKilled imminent"),
    ("error",   "ERROR: Failed to allocate 128Mi — limit exceeded"),
    ("error",   "ERROR: CrashLoopBackOff — container restarted 2 times"),
    ("warning", "WARNING: Memory usage at 94% — 481Mi/512Mi allocated"),
    ("error",   "ERROR: GC overhead — 98% of CPU time spent in garbage collection"),
    # T=16min — les 20 derniers logs : critiques (seront dans les 50 gardés)
    ("error",   "ERROR: Memory usage at 95% — 486Mi/512Mi — CRITICAL"),
    ("error",   "ERROR: Failed to process incoming request — out of memory"),
    ("error",   "ERROR: java.lang.OutOfMemoryError: GC overhead limit exceeded"),
    ("error",   "ERROR: Heap dump initiated — current size: 486Mi"),
    ("error",   "ERROR: All worker threads blocked — memory exhausted"),
    ("error",   "ERROR: Request processing halted — memory threshold exceeded"),
    ("error",   "ERROR: CrashLoopBackOff — container restarted 3 times"),
    ("error",   "ERROR: Container killed — OOM — memory usage exceeded limit of 512Mi"),
    ("error",   "ERROR: OOMKilled — pod fastapi-demo-7b9c8d6f4-x2k9p terminated"),
    ("error",   "ERROR: Container restart #3 detected — backoff: 160s"),
    # T=17min — dernière minute (logs les plus récents)
    ("error",   "ERROR: Memory usage at 95% — 486Mi/512Mi — risque OOMKilled"),
    ("error",   "ERROR: Allocation failure — Cannot allocate 32Mi"),
    ("warning", "WARNING: Memory usage at 95% — 486Mi/512Mi allocated"),
    ("error",   "ERROR: GC pause: 2.3s — application frozen"),
    ("error",   "ERROR: Failed to allocate 256Mi for request processing"),
    ("error",   "ERROR: OutOfMemoryError — heap space exhausted"),
    ("warning", "WARNING: Memory usage at 95% — 486Mi/512Mi — limite critique"),
    ("error",   "ERROR: Kubernetes OOM event detected — pod at risk"),
    ("error",   "ERROR: Memory pressure — eviction threshold crossed"),
    ("error",   "ERROR: CRITICAL — container memory 486Mi/512Mi — OOMKill en 2-3 minutes"),
]

assert len(LOG_LINES) == 100, f"Attendu 100 logs, obtenu {len(LOG_LINES)}"

# Distribuer les timestamps sur les 30 dernières minutes
interval_seconds = (29 * 60 + 30) / 99  # ~17.9 secondes entre chaque log
values = []
for i, (level, line) in enumerate(LOG_LINES):
    ts = start + timedelta(seconds=i * interval_seconds)
    ts_ns = str(int(ts.timestamp() * 1_000_000_000))
    # Préfixe de timestamp lisible dans le log
    ts_readable = ts.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    values.append([ts_ns, f"{ts_readable} [{level.upper()}] {line}"])

payload = {
    "streams": [
        {
            "stream": {
                "namespace": NAMESPACE,
                "pod": POD,
                "container": CONTAINER,
                "level": "mixed",
                "job": "app-demo/fastapi",
            },
            "values": values,
        }
    ]
}

print(f"📤 Injection de {len(values)} logs dans Loki...")
print(f"   Pod       : {POD}")
print(f"   Namespace : {NAMESPACE}")
print(f"   Période   : {start.strftime('%H:%M:%S')} → {now.strftime('%H:%M:%S')} UTC")

data = json.dumps(payload).encode("utf-8")
req = urllib.request.Request(
    LOKI_URL,
    data=data,
    headers={"Content-Type": "application/json"},
    method="POST",
)

try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        status = resp.getcode()
        if status == 204:
            print(f"✅ SUCCESS — {len(values)} logs injectés dans Loki (HTTP 204)")
        else:
            print(f"⚠️ Statut inattendu : {status}")
except Exception as e:
    print(f"❌ Erreur : {e}")
    raise
```

### 4.2 Exécution du script d'injection

```bash
python3 /tmp/inject_loki_100.py

# Output attendu :
# 📤 Injection de 100 logs dans Loki...
#    Pod       : fastapi-demo-7b9c8d6f4-x2k9p
#    Namespace : app-demo
#    Période   : 09:35:22 → 10:05:22 UTC
# ✅ SUCCESS — 100 logs injectés dans Loki (HTTP 204)
```

### 4.3 Vérifier les logs dans Loki

```bash
# Vérifier que Loki a bien reçu les 100 logs via la query API
curl -s -G 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={namespace="app-demo", pod="fastapi-demo-7b9c8d6f4-x2k9p"}' \
  --data-urlencode 'limit=150' \
  --data-urlencode 'since=30m' \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
total = sum(len(s.get('values', [])) for s in results)
print(f'✅ Loki contient {total} logs pour ce pod')
print(f'   Streams trouvés : {len(results)}')
if results:
    first_ts = results[0]['values'][-1][0]
    last_ts  = results[0]['values'][0][0]
    print(f'   Premier log : {results[0][\"values\"][-1][1][:80]}')
    print(f'   Dernier log : {results[0][\"values\"][0][1][:80]}')
"

# Output attendu :
# ✅ Loki contient 100 logs pour ce pod
#    Streams trouvés : 1
#    Premier log : 2026-05-06T09:35:22.000Z [INFO] INFO: Application started — heap size: 180Mi
#    Dernier log : 2026-05-06T10:04:51.000Z [ERROR] ERROR: CRITICAL — container memory 486Mi/512Mi
```

✅ **Point de vérification 2** : 100 logs présents dans Loki.

---

## 5. Génération des 100 Métriques Prometheus

### 5.1 Comment fonctionne l'exposition des métriques

Le conteneur `log-generator` (déjà démarré par docker-compose) expose un serveur HTTP sur le port 8080 avec des métriques au format Prometheus. Ces métriques sont scrappées automatiquement par Prometheus toutes les **15 secondes**.

```
log-generator:8080/metrics  ──scrape 15s──►  Prometheus:9090
```

Les 3 métriques exposées :
| Métrique | Type | Description |
|---|---|---|
| `container_memory_usage_bytes` | Gauge | Mémoire utilisée par le container |
| `container_cpu_usage_seconds_total` | Counter | CPU cumulé en secondes |
| `kube_pod_container_status_restarts_total` | Counter | Nombre de redémarrages |

### 5.2 Vérifier que le log-generator expose des métriques

```bash
# Vérifier les métriques exposées par le log-generator depuis l'intérieur du réseau Docker
docker compose exec api curl -s http://log-generator:8080/metrics

# Output attendu :
# # HELP container_memory_usage_bytes Current memory usage in bytes
# # TYPE container_memory_usage_bytes gauge
# container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo",container="fastapi"} 247000000
#
# # HELP container_cpu_usage_seconds_total Total CPU usage
# # TYPE container_cpu_usage_seconds_total counter
# container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo",container="fastapi"} 42.80
#
# # HELP kube_pod_container_status_restarts_total Total restarts
# # TYPE kube_pod_container_status_restarts_total counter
# kube_pod_container_status_restarts_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo",container="fastapi"} 3
```

### 5.3 Attendre l'accumulation de 100 données dans Prometheus

Prometheus scrape toutes les 15 secondes → **100 données = 25 minutes de fonctionnement**.

> 💡 **Pour accélérer le test** : modifier `scrape_interval: 5s` dans `prometheus.yml`, puis relancer avec `docker compose restart prometheus`. Dans ce cas, 100 données s'accumulent en ~8 minutes.

```bash
# Vérifier le nombre de points de données accumulés dans Prometheus
# (Remplacer 30m par la durée effective depuis le démarrage)
curl -s -G 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=count_over_time(container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p"}[30m])' \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
if results:
    count = int(float(results[0]['value'][1]))
    print(f'✅ Prometheus a {count} points de données pour container_memory_usage_bytes')
    print(f'   (100 points = scénario prêt pour le test)')
else:
    print('⚠️  Aucun résultat — Prometheus scrape pas encore commencé')
"

# Output attendu (après ~25 min) :
# ✅ Prometheus a 103 points de données pour container_memory_usage_bytes
#    (100 points = scénario prêt pour le test)
```

### 5.4 Vérifier les valeurs actuelles des métriques

```bash
# Valeur actuelle de la mémoire
curl -s 'http://localhost:9090/api/v1/query?query=container_memory_usage_bytes%7Bpod%3D%22fastapi-demo-7b9c8d6f4-x2k9p%22%7D' \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
if results:
    val = float(results[0]['value'][1])
    print(f'Mémoire : {val/1024/1024:.1f} Mi')
"

# Output attendu :
# Mémoire : 247.0 Mi

# Valeur actuelle du CPU
curl -s 'http://localhost:9090/api/v1/query?query=container_cpu_usage_seconds_total%7Bpod%3D%22fastapi-demo-7b9c8d6f4-x2k9p%22%7D' \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
if results:
    val = float(results[0]['value'][1])
    print(f'CPU cumulé : {val:.1f}s')
"

# Output attendu :
# CPU cumulé : 42.8s

# Nombre de redémarrages
curl -s 'http://localhost:9090/api/v1/query?query=kube_pod_container_status_restarts_total%7Bpod%3D%22fastapi-demo-7b9c8d6f4-x2k9p%22%7D' \
  | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('data', {}).get('result', [])
if results:
    val = int(float(results[0]['value'][1]))
    print(f'Redémarrages : {val}')
"

# Output attendu :
# Redémarrages : 3
```

✅ **Point de vérification 3** : 100+ points de données dans Prometheus, métriques cohérentes avec le scénario.

---

## 6. Déclenchement du Webhook (Simulation Grafana)

### 6.1 Structure du payload webhook

En production, Grafana envoie ce JSON automatiquement quand une alerte se déclenche. Ici on le simule avec `curl`.

```bash
# Déclencher le webhook — simulation d'une alerte Grafana HighMemoryPressure
curl -s -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "HighMemoryPressure",
    "state": "alerting",
    "message": "Container fastapi in namespace app-demo is using 95% of its memory limit (486Mi/512Mi). OOMKill risk in the next 2-3 minutes.",
    "labels": {
      "pod": "fastapi-demo-7b9c8d6f4-x2k9p",
      "namespace": "app-demo",
      "container": "fastapi",
      "node": "aks-nodepool1-12345678-vmss000001",
      "severity": "critical",
      "team": "backend"
    },
    "dashboard_url": "http://localhost:3000/d/k8s-pods/kubernetes-pods?orgId=1"
  }' | python3 -m json.tool

# Output attendu (réponse immédiate 202 Accepted) :
# {
#     "message": "Alerte reçue, traitement en cours"
# }
```

> 📌 **Note** : Le backend répond immédiatement `202 Accepted`. Le traitement complet (Loki + Prometheus + OpenAI + Email) s'exécute en **arrière-plan** (BackgroundTask FastAPI). Cela prend 10-30 secondes selon la latence OpenAI.

### 6.2 Surveiller le traitement en arrière-plan

```bash
# Observer les logs du backend pour suivre la pipeline
docker compose logs api -f --tail=50

# Output attendu (pendant le traitement) :
# INFO     📥 Webhook reçu : HighMemoryPressure — alerting
# INFO     🔄 Traitement de l'alerte 'HighMemoryPressure' — pod=fastapi-demo-7b9c8d6f4-x2k9p
# INFO     📝 100 logs récupérés depuis Loki pour pod=fastapi-demo-7b9c8d6f4-x2k9p
# INFO     📊 Métriques récupérées pour pod=fastapi-demo-7b9c8d6f4-x2k9p : {'memory_usage_bytes': 258998272.0, 'cpu_usage_seconds': 42.8, 'restart_count': 3.0}
# INFO     ❌ Aucun incident passé résolu pour 'HighMemoryPressure'
# INFO     🔐 Sanitizer : 100 logs → 50 nettoyés (tronqué à 50)
# INFO     📤 Mega-Prompt envoyé à OpenAI (SANS historique) — 50 logs, 31 erreurs, 3 métriques
# INFO     ✅ Diagnostic IA reçu — sévérité: critique, catégorie: memory_leak
# INFO     💾 Incident sauvegardé : 683a1b2c3d4e5f6789012345
# INFO     📧 Email envoyé à sre-team@example.com pour alerte 'HighMemoryPressure' (tentative 1/3)
# INFO     ✅ Incident 'HighMemoryPressure' traité et sauvegardé (id=683a1b2c3d4e5f6789012345)
```

> 🔴 Appuyer sur `Ctrl+C` pour arrêter le suivi des logs.

✅ **Point de vérification 4** : La pipeline complète s'est exécutée. Noter l'`incident_id` (ex: `683a1b2c3d4e5f6789012345`).

---

## 7. Traitement par FastAPI — Pipeline Étape par Étape

Cette section explique ce que fait FastAPI **en détail** à l'intérieur de la fonction `process_alert()`.

### Étape ① — Collecte des Logs depuis Loki

```
FastAPI → GET http://loki:3100/loki/api/v1/query_range
  params:
    query = {namespace="app-demo", pod="fastapi-demo-7b9c8d6f4-x2k9p"}
    limit = 100
    since = 30m
```

**Ce que Loki retourne** : jusqu'à **100 lignes de logs** triées du plus récent au plus ancien. C'est exactement nos 100 logs injectés à l'étape 4.

**Résultat** : `logs = [<100 lignes de log>]`

### Étape ② — Collecte des Métriques depuis Prometheus

```
FastAPI → GET http://prometheus:9090/api/v1/query (3 requêtes PromQL)
  query 1: container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p", namespace="app-demo"}
  query 2: container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p", namespace="app-demo"}
  query 3: kube_pod_container_status_restarts_total{pod="fastapi-demo-7b9c8d6f4-x2k9p", namespace="app-demo"}
```

**Résultat** :
```python
metrics = {
    "memory_usage_bytes": 258998272.0,   # 247 Mi
    "cpu_usage_seconds": 42.8,
    "restart_count": 3.0,
}
```

> Note : `len(metrics)` = 3 (3 métriques scalaires, chacune issue de 100+ points de données historiques dans Prometheus).

### Étape ③ — Auto-Learning (Recherche en Base)

```
FastAPI → MongoDB → find_one({alert_name: "HighMemoryPressure", status: "résolu"})
```

Premier test → pas d'incident résolu trouvé → `past_solution = None`.

**Résultat** : `past_solution = None` (log : `❌ Aucun incident passé résolu pour 'HighMemoryPressure'`)

### Étape ④ — Filtrage : 100 → 50 Logs (Sanitizer)

Le Sanitizer fait **deux choses** :

1. **Troncature** : garde les **50 dernières lignes** (`logs[-50:]`) — ce sont les logs les plus récents, donc les plus pertinents pour le diagnostic.

2. **Nettoyage** des données sensibles : masque les IPs, tokens, mots de passe, clés Azure via des regex.

```python
# Code réel dans sanitizer.py
def sanitize_logs(logs: list[str], max_lines: int = 50) -> list[str]:
    truncated = logs[-max_lines:]          # Garder les 50 DERNIERS logs
    cleaned = [sanitize_text(line) for line in truncated]  # Masquer données sensibles
    return cleaned
```

**Pourquoi les 50 derniers ?**
- Les logs les plus récents sont les plus pertinents pour comprendre ce qui se passe **maintenant**.
- Réduction du coût Azure OpenAI (moins de tokens consommés).

**Résultat** :
```
Input  : 100 logs (logs[0] = plus ancien, logs[99] = plus récent)
Output : 50 logs (logs[50] à logs[99]) — tous sans données sensibles
```

Pour vérifier :

```bash
# Vérifier que le Sanitizer conserve les 50 derniers logs
# Les 50 logs gardés commencent à T=14min dans notre scénario
# (les logs les plus critiques sont dans la fenêtre T=14min → T=17min)
echo "Les 50 logs les plus récents incluent les lignes critiques :"
echo "  ERROR: Memory usage at 95% — 486Mi/512Mi — CRITICAL"
echo "  ERROR: OOMKilled — pod fastapi-demo-7b9c8d6f4-x2k9p terminated"
echo "  ERROR: CRITICAL — container memory 486Mi/512Mi — OOMKill en 2-3 minutes"
```

---

## 8. Le Mega-Prompt envoyé au Modèle IA

### 8.1 Construction du Mega-Prompt

Voici le prompt **exact** que FastAPI construit et envoie à Azure OpenAI (fonction `llm_engine.analyze()`).

**System Prompt** (invariant — définit le comportement de l'IA) :

```
Tu es un expert SRE (Site Reliability Engineer) spécialisé en Kubernetes et observabilité.
Tu reçois des alertes de monitoring Grafana avec des logs applicatifs et des métriques système.

Ton rôle : analyser les preuves collectées et produire un diagnostic exploitable.

Réponds UNIQUEMENT avec un objet JSON valide ayant exactement ces champs :
{
  "cause_racine": "Explication technique précise de la cause du problème (2-4 phrases)",
  "solution": "Commandes exactes et étapes pour résoudre le problème (prêtes à copier-coller)",
  "severite": "critique | haute | moyenne | basse",
  "categorie": "resource_exhaustion | memory_leak | crash_loop | network_error | disk_full | high_latency | configuration_error | unknown",
  "actions_immediates": ["action 1", "action 2", "action 3"],
  "prevention": "Recommandation pour éviter la récurrence"
}

Règles importantes :
- Ne jamais inclure de texte en dehors du JSON
- La solution doit contenir des commandes kubectl/bash concrètes et exécutables
- Les actions immédiates doivent être ordonnées par priorité
- Tenir compte des logs ET des métriques pour le diagnostic
```

**User Prompt** (construit dynamiquement avec le contexte de l'incident) :

```
## Alerte Kubernetes reçue de Grafana
- Nom de l'alerte : HighMemoryPressure
- Message         : Container fastapi in namespace app-demo is using 95% of its memory limit (486Mi/512Mi). OOMKill risk in the next 2-3 minutes.
- Pod             : fastapi-demo-7b9c8d6f4-x2k9p
- Namespace       : app-demo
- Container       : fastapi
- Node            : aks-nodepool1-12345678-vmss000001

## Statistiques des logs (50 lignes collectées)
- Erreurs   : 31
- Warnings  : 14
- Info      : 5

### Erreurs récentes détectées dans les logs
  ❌ ERROR: Memory usage at 95% — 486Mi/512Mi — CRITICAL
  ❌ ERROR: Failed to process incoming request — out of memory
  ❌ ERROR: java.lang.OutOfMemoryError: GC overhead limit exceeded
  ❌ ERROR: All worker threads blocked — memory exhausted
  ❌ ERROR: CRITICAL — container memory 486Mi/512Mi — OOMKill en 2-3 minutes

### Warnings récents
  ⚠️ WARNING: Memory usage at 95% — 486Mi/512Mi — limite critique
  ⚠️ WARNING: Memory usage at 94% — 481Mi/512Mi allocated
  ⚠️ WARNING: Memory usage at 91% — 466Mi/512Mi allocated

## Logs complets (triés du plus ancien au plus récent)
```
[50 lignes de logs — les plus récentes du scénario, de T=14min à T=17min]
2026-05-06T09:49:18.000Z [WARNING] WARNING: Memory usage at 87% — 445Mi/512Mi allocated
2026-05-06T09:49:35.000Z [ERROR] ERROR: java.lang.OutOfMemoryError: Java heap space
2026-05-06T09:49:53.000Z [ERROR] ERROR: CrashLoopBackOff — container restarted 2 times
...
2026-05-06T10:04:34.000Z [ERROR] ERROR: OOMKilled — pod fastapi-demo-7b9c8d6f4-x2k9p terminated
2026-05-06T10:04:51.000Z [ERROR] ERROR: CRITICAL — container memory 486Mi/512Mi — OOMKill en 2-3 minutes
```

## Métriques système
- Mémoire utilisée    : 247.2 Mi / 512.0 Mi limit (48%)
- CPU cumulé          : 42.8s
- CPU throttled       : 0.0s
- Redémarrages        : 3 ⚠️ CRASH LOOP
- Réseau RX/TX        : 0.0 Mi / 0.0 Mi
🔴 ALERTE : 3 redémarrages — potentiel crash loop
```

### 8.2 Paramètres de l'appel Azure OpenAI

```python
model       = "gpt-35-turbo"     # défini dans .env OPENAI_DEPLOYMENT
temperature = 0.2                # Réponses précises et reproductibles
max_tokens  = 1200               # Limite la longueur de la réponse
```

---

## 9. Format de Réponse Attendu de l'IA

### 9.1 Réponse JSON attendue

Azure OpenAI retourne un JSON strict (imposé par le System Prompt) :

```json
{
  "cause_racine": "Le pod fastapi-demo-7b9c8d6f4-x2k9p présente une fuite mémoire progressive. La mémoire heap Java croît de façon non-bornée malgré les cycles GC, atteignant 486Mi sur 512Mi alloués (95%). Le GC consume 98% du CPU (GC overhead limit exceeded), bloquant tous les threads applicatifs. Avec 3 redémarrages déjà enregistrés, un nouveau CrashLoopBackOff est imminent dans les 2-3 prochaines minutes.",

  "solution": "# Résolution immédiate — Avant OOMKill\nkubectl -n app-demo delete pod fastapi-demo-7b9c8d6f4-x2k9p\n# Le pod redémarrera automatiquement via le Deployment\n\n# Vérifier le redémarrage propre\nkubectl -n app-demo get pod -l app=fastapi -w\n\n# Analyser la fuite mémoire — thread dump avant suppression\nkubectl -n app-demo exec fastapi-demo-7b9c8d6f4-x2k9p -- jstack -l 1 > /tmp/thread_dump.txt\n\n# Ajuster les limites mémoire et JVM\nkubectl -n app-demo set env deployment/fastapi-demo JAVA_OPTS='-Xmx384m -Xms256m -XX:+UseG1GC -XX:MaxGCPauseMillis=200'\n\n# Augmenter la limite mémoire du Deployment\nkubectl -n app-demo patch deployment fastapi-demo -p '{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"fastapi\",\"resources\":{\"limits\":{\"memory\":\"768Mi\"},\"requests\":{\"memory\":\"512Mi\"}}}]}}}}'\n\n# Vérifier les métriques après correction\nkubectl -n app-demo top pod -l app=fastapi",

  "severite": "critique",

  "categorie": "memory_leak",

  "actions_immediates": [
    "Supprimer immédiatement le pod pour éviter l'OOMKill brutal : kubectl -n app-demo delete pod fastapi-demo-7b9c8d6f4-x2k9p",
    "Vérifier les heap dumps dans /tmp/ pour identifier les objets qui fuient",
    "Augmenter la limite mémoire du Deployment à 768Mi pour gagner du temps",
    "Réduire la concurrence des batch jobs (batch_size=10000 au lieu de 75000)",
    "Activer les alertes JVM HeapMemoryUsage dans Grafana pour prévenir la récurrence"
  ],

  "prevention": "Configurer des HPA (Horizontal Pod Autoscaler) pour scaler horizontalement au lieu de laisser un pod épuiser sa mémoire. Mettre en place des heap dumps automatiques sur OOMKill (env JAVA_TOOL_OPTIONS='-XX:+HeapDumpOnOutOfMemoryError'). Ajouter une alerte Prometheus sur container_memory_usage_bytes > 80% de la limite pour intervenir avant le seuil critique."
}
```

### 9.2 Où ce diagnostic est utilisé

Ce JSON est stocké dans MongoDB sous le champ `diagnostic` du document incident, et affiché dans l'interface Streamlit sous les onglets dédiés.

---

## 10. Notification Email — MailHog

### 10.1 Vérifier la réception de l'email

```bash
# Lister les emails reçus par MailHog
curl -s http://localhost:8025/api/v2/messages | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'📧 Emails reçus : {data[\"total\"]}')
for msg in data.get('items', []):
    print(f'   Sujet : {msg[\"Content\"][\"Headers\"][\"Subject\"][0]}')
    print(f'   De    : {msg[\"Content\"][\"Headers\"][\"From\"][0]}')
    print(f'   À     : {msg[\"Content\"][\"Headers\"][\"To\"][0]}')
    print(f'   Date  : {msg[\"Created\"]}')
"

# Output attendu :
# 📧 Emails reçus : 1
#    Sujet : 🔴 Alerte HighMemoryPressure — app-demo/fastapi-demo-7b9c8d6f4-x2k9p
#    De    : Assistant SRE <assistant-sre@localhost>
#    À     : sre-team@example.com
#    Date  : 2026-05-06T10:05:45.123Z
```

### 10.2 Voir l'email dans l'interface web MailHog

Ouvrir dans le navigateur : **http://localhost:8025**

L'email contient :
- 🔴 **Titre** : `Alerte HighMemoryPressure — app-demo/fastapi-demo-7b9c8d6f4-x2k9p`
- 📍 **Pod** : `fastapi-demo-7b9c8d6f4-x2k9p`
- 📍 **Namespace** : `app-demo`
- ⚠️ **Sévérité** : **CRITIQUE** (en rouge)
- 🏷️ **Catégorie** : `memory_leak`
- 🔍 **Cause Racine** : description de la fuite mémoire Java
- 💡 **Solution Proposée** : commandes kubectl prêtes à copier-coller
- 🔗 **Lien** : `Connectez-vous au dashboard pour valider la solution proposée.`

> ℹ️ **Note sur le lien** : En production, l'email inclurait l'URL de l'interface Streamlit (`http://assistant-sre.internal/`) pour permettre à l'ingénieur SRE de valider directement depuis l'email. En local, naviguer manuellement vers `http://localhost:8501`.

✅ **Point de vérification 5** : Email reçu avec la description du problème.

---

## 11. Interface Assistant-SRE — Streamlit

### 11.1 Démarrer le frontend Streamlit

```bash
# Dans un nouveau terminal — depuis le répertoire frontend/
cd /path/to/Assistant-SRE/frontend

# Installer les dépendances si pas encore fait
pip install -r requirements.txt

# Démarrer l'interface
streamlit run app.py --server.port 8501

# Output attendu :
#   You can now view your Streamlit app in your browser.
#   Local URL: http://localhost:8501
#   Network URL: http://192.168.x.x:8501
```

### 11.2 Naviguer dans l'interface

Ouvrir dans le navigateur : **http://localhost:8501**

**Dashboard principal** — liste des incidents :
```
┌─────────────────────────────────────────────────────────┐
│  🤖 Assistant SRE                                       │
│  ─────────────────────────────────────────────────────  │
│  📋 Incidents récents                                   │
│                                                         │
│  🔴 HighMemoryPressure                                  │
│     Pod: fastapi-demo-7b9c8d6f4-x2k9p                  │
│     Namespace: app-demo                                 │
│     Status: ⏳ pending_approval                         │
│     Créé: 06/05/2026 10:05:45                           │
│                                        [Voir détails ▶] │
└─────────────────────────────────────────────────────────┘
```

### 11.3 Accéder au détail de l'incident

Cliquer sur **[Voir détails]** pour l'incident `HighMemoryPressure`.

L'interface affiche :

```
┌─────────────────────────────────────────────────────────┐
│  🔴 HighMemoryPressure                                  │
│  pod: fastapi-demo-7b9c8d6f4-x2k9p | ns: app-demo      │
│  Status: ⏳ En attente d'approbation                    │
│  ─────────────────────────────────────────────────────  │
│  📊 Diagnostic IA                                       │
│                                                         │
│  🏷️ Catégorie : memory_leak                             │
│  ⚠️ Sévérité  : CRITIQUE                               │
│                                                         │
│  🔍 Cause Racine                                        │
│  Le pod fastapi-demo présente une fuite mémoire...      │
│                                                         │
│  ⚡ Actions Immédiates                                  │
│  1. Supprimer le pod pour éviter l'OOMKill brutal...    │
│  2. Vérifier les heap dumps dans /tmp/...               │
│  3. Augmenter la limite mémoire à 768Mi...              │
│                                                         │
│  💡 Solution                                            │
│  kubectl -n app-demo delete pod fastapi-demo-xxx        │
│  kubectl -n app-demo get pod -l app=fastapi -w          │
│  ...                                                    │
│                                                         │
│  🛡️ Prévention                                         │
│  Configurer des HPA pour scaler horizontalement...      │
│                                                         │
│  ─────────────────────────────────────────────────────  │
│              [✅ Approuver la solution]                  │
└─────────────────────────────────────────────────────────┘
```

✅ **Point de vérification 6** : L'incident est visible dans l'interface avec le diagnostic IA structuré.

---

## 12. Approbation et Stockage Final

### 12.1 Via l'interface Streamlit

Cliquer sur le bouton **[✅ Approuver la solution]**.

**Ce qui se passe en arrière-plan** :

```
Frontend (Streamlit)
  └─► POST http://localhost:8000/api/v1/incidents/{id}/approve

FastAPI (resolve.py)
  ├── 1. Récupère le document incident depuis MongoDB
  ├── 2. Appelle Azure OpenAI avec le prompt de formatage (format_final_solution())
  ├── 3. Reçoit une solution markdown bien structurée
  ├── 4. Sauvegarde : status = "résolu", validated_solution = <solution_markdown>
  └── 5. Retourne la solution formatée au frontend
```

### 12.2 Via curl (pour tester sans le frontend)

```bash
# Remplacer INCIDENT_ID par l'ID noté à l'étape 6.2
INCIDENT_ID="683a1b2c3d4e5f6789012345"

curl -s -X POST "http://localhost:8000/api/v1/incidents/${INCIDENT_ID}/approve" \
  -H "Content-Type: application/json" \
  | python3 -m json.tool

# Output attendu :
# {
#     "message": "Incident approuvé et résolu",
#     "incident_id": "683a1b2c3d4e5f6789012345",
#     "already_resolved": false,
#     "formatted_solution": "### ✅ Résolution de l'incident : HighMemoryPressure\n\n**Cause identifiée :** Fuite mémoire Java progressive dans le container fastapi...\n\n**Commandes de résolution :**\n```bash\nkubectl -n app-demo delete pod fastapi-demo-7b9c8d6f4-x2k9p\nkubectl -n app-demo get pod -l app=fastapi -w\n```\n\n**Étapes de vérification :**\n1. Vérifier que le nouveau pod démarre sans erreur\n2. Surveiller la consommation mémoire pendant 10 minutes\n3. Confirmer l'absence de CrashLoopBackOff\n\n**Prévention future :**\nConfigurer un HPA et des alertes Prometheus à 80% de la limite mémoire."
# }
```

### 12.3 La solution finale formatée (markdown)

```markdown
### ✅ Résolution de l'incident : HighMemoryPressure

**Cause identifiée :** Fuite mémoire Java progressive dans le container fastapi (namespace app-demo). La heap JVM a atteint 486Mi sur 512Mi alloués (95%), déclenchant un GC overhead critique avec 3 redémarrages.

**Commandes de résolution :**
```bash
# Supprimer le pod (redémarrage propre via le Deployment)
kubectl -n app-demo delete pod fastapi-demo-7b9c8d6f4-x2k9p

# Surveiller le redémarrage
kubectl -n app-demo get pod -l app=fastapi -w

# Augmenter la limite mémoire
kubectl -n app-demo patch deployment fastapi-demo \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"fastapi","resources":{"limits":{"memory":"768Mi"}}}]}}}}'
```

**Étapes de vérification :**
1. Vérifier que le nouveau pod démarre sans erreur (`kubectl get pod`)
2. Surveiller la mémoire pendant 10 minutes (`kubectl top pod`)
3. Confirmer l'absence de `CrashLoopBackOff`

**Prévention future :**
Configurer un HPA et des alertes Prometheus sur `container_memory_usage_bytes > 80%` de la limite.
```

✅ **Point de vérification 7** : L'incident est approuvé. La solution formatée est retournée et sauvegardée.

---

## 13. Vérification en Base MongoDB

### 13.1 Via Mongo Express (interface graphique)

Ouvrir : **http://localhost:8081**

Navigation :
1. Cliquer sur `aiops_db`
2. Cliquer sur `incidents`
3. Trouver le document avec `alert_name: "HighMemoryPressure"`

Le document final doit ressembler à :

```json
{
  "_id": "683a1b2c3d4e5f6789012345",
  "alert_name": "HighMemoryPressure",
  "state": "alerting",
  "labels": {
    "pod": "fastapi-demo-7b9c8d6f4-x2k9p",
    "namespace": "app-demo",
    "container": "fastapi",
    "node": "aks-nodepool1-12345678-vmss000001",
    "severity": "critical",
    "team": "backend"
  },
  "message": "Container fastapi in namespace app-demo is using 95% of its memory limit...",
  "logs_collected": 100,
  "metrics_collected": 3,
  "past_solution_used": null,
  "diagnostic": {
    "cause_racine": "Le pod fastapi-demo-7b9c8d6f4-x2k9p présente une fuite mémoire progressive...",
    "solution": "kubectl -n app-demo delete pod fastapi-demo-7b9c8d6f4-x2k9p\n...",
    "severite": "critique",
    "categorie": "memory_leak",
    "actions_immediates": ["Supprimer immédiatement le pod...", "..."],
    "prevention": "Configurer des HPA..."
  },
  "status": "résolu",
  "validated_solution": "### ✅ Résolution de l'incident : HighMemoryPressure\n\n...",
  "created_at": "2026-05-06T10:05:45.000Z",
  "resolved_at": "2026-05-06T10:08:12.000Z"
}
```

### 13.2 Via curl (API MongoDB directe)

```bash
# Lister les incidents via l'API FastAPI
curl -s "http://localhost:8000/api/v1/incidents?limit=5" | python3 -c "
import json, sys
incidents = json.load(sys.stdin)
print(f'📦 {len(incidents)} incident(s) en base :')
for inc in incidents:
    print(f\"   ID     : {inc['_id']}\")
    print(f\"   Alerte : {inc['alert_name']}\")
    print(f\"   Status : {inc['status']}\")
    print(f\"   Logs   : {inc['logs_collected']} collectés\")
    print(f\"   Métriques : {inc['metrics_collected']} collectées\")
    print(f\"   Créé   : {inc['created_at']}\")
    print(f\"   Résolu : {inc.get('resolved_at', 'N/A')}\")
    print()
"

# Output attendu :
# 📦 1 incident(s) en base :
#    ID     : 683a1b2c3d4e5f6789012345
#    Alerte : HighMemoryPressure
#    Status : résolu
#    Logs   : 100 collectés
#    Métriques : 3 collectées
#    Créé   : 2026-05-06T10:05:45+00:00
#    Résolu : 2026-05-06T10:08:12+00:00
```

### 13.3 Vérifier la solution validée finale

```bash
INCIDENT_ID="683a1b2c3d4e5f6789012345"

curl -s "http://localhost:8000/api/v1/incidents/${INCIDENT_ID}" | python3 -c "
import json, sys
inc = json.load(sys.stdin)
print('=== INCIDENT RÉSOLU ===')
print(f'Status           : {inc[\"status\"]}')
print(f'Logs collectés   : {inc[\"logs_collected\"]}')
print(f'Métriques        : {inc[\"metrics_collected\"]}')
print(f'Sévérité IA      : {inc[\"diagnostic\"][\"severite\"]}')
print(f'Catégorie IA     : {inc[\"diagnostic\"][\"categorie\"]}')
print()
print('=== SOLUTION VALIDÉE ===')
print(inc.get('validated_solution', 'Non disponible')[:500])
"

# Output attendu :
# === INCIDENT RÉSOLU ===
# Status           : résolu
# Logs collectés   : 100
# Métriques        : 3
# Sévérité IA      : critique
# Catégorie IA     : memory_leak
#
# === SOLUTION VALIDÉE ===
# ### ✅ Résolution de l'incident : HighMemoryPressure
#
# **Cause identifiée :** Fuite mémoire Java progressive dans le container fastapi...
```

✅ **Point de vérification 8** : Le document en base contient `status: "résolu"`, `validated_solution` non vide, et `resolved_at` défini.

---

## 14. Checklist de Validation Finale

Voici la liste complète des points à valider pour considérer le test comme réussi.

### 14.1 Infrastructure

```
☐ docker compose ps → 7 services en status "Up"
☐ curl http://localhost:8000/api/v1/health → {"status":"ok"}
☐ curl http://localhost:3100/ready → "ready"
☐ curl http://localhost:9090/-/healthy → "Prometheus Server is Healthy."
☐ curl http://localhost:8025/api/v2/messages → HTTP 200
☐ curl http://localhost:8081 → HTTP 200
```

### 14.2 Injection des données

```
☐ 100 logs injectés dans Loki (HTTP 204)
☐ Loki query_range retourne 100 logs pour le pod fastapi-demo
☐ Prometheus expose les métriques container_memory_usage_bytes
☐ Prometheus a ≥ 100 points de données pour container_memory_usage_bytes[30m]
```

### 14.3 Pipeline FastAPI

```
☐ POST /api/v1/webhook → 202 {"message": "Alerte reçue, traitement en cours"}
☐ Logs backend : "100 logs récupérés depuis Loki"
☐ Logs backend : "Métriques récupérées pour pod=fastapi-demo"
☐ Logs backend : "Sanitizer : 100 logs → 50 nettoyés (tronqué à 50)"
☐ Logs backend : "Mega-Prompt envoyé à OpenAI"
☐ Logs backend : "Diagnostic IA reçu — sévérité: critique"
☐ Logs backend : "Incident sauvegardé : <id>"
☐ Logs backend : "Email envoyé à sre-team@example.com"
```

### 14.4 Email

```
☐ MailHog (http://localhost:8025) affiche 1 email
☐ Sujet contient "HighMemoryPressure"
☐ Email contient la cause racine
☐ Email contient la solution avec commandes kubectl
☐ Email indique la sévérité "CRITIQUE"
```

### 14.5 Interface Streamlit

```
☐ http://localhost:8501 accessible
☐ L'incident HighMemoryPressure apparaît dans la liste
☐ Status = "pending_approval" avant approbation
☐ La page détail affiche : cause_racine, solution, actions_immediates, prevention
☐ Le bouton "Approuver" est visible et cliquable
```

### 14.6 Approbation et Stockage

```
☐ POST /api/v1/incidents/{id}/approve → 200 avec formatted_solution
☐ La formatted_solution est en markdown structuré
☐ GET /api/v1/incidents/{id} → status = "résolu"
☐ GET /api/v1/incidents/{id} → validated_solution non vide
☐ GET /api/v1/incidents/{id} → resolved_at défini
☐ Mongo Express → document avec status "résolu" et tous les champs
```

---

## Annexe A — Résumé des Commandes Clés

| Étape | Commande | Résultat attendu |
|---|---|---|
| Démarrage | `docker compose up -d --build` | 7 services Up |
| Santé backend | `curl localhost:8000/api/v1/health` | `{"status":"ok"}` |
| Injection Loki | `python3 /tmp/inject_loki_100.py` | `✅ SUCCESS — 100 logs injectés` |
| Vérif Loki | `curl + LogQL query_range` | `100 logs pour ce pod` |
| Vérif Prometheus | `curl + count_over_time PromQL` | `≥ 100 points de données` |
| Déclenchement | `curl -X POST localhost:8000/api/v1/webhook` | `202 Accepted` |
| Suivi pipeline | `docker compose logs api -f` | Logs de chaque étape |
| Vérif email | `curl localhost:8025/api/v2/messages` | `1 email reçu` |
| Approbation API | `curl -X POST localhost:8000/api/v1/incidents/{id}/approve` | `200 + formatted_solution` |
| Vérif base | `curl localhost:8000/api/v1/incidents/{id}` | `status: résolu` |

## Annexe B — Résolution des Problèmes Courants

### Loki retourne 0 logs

```bash
# Vérifier que Loki est prêt
curl http://localhost:3100/ready

# Vérifier la plage de temps (les logs injectés doivent être dans since=30m)
# Si plus de 30 minutes se sont écoulées depuis l'injection, ré-injecter :
python3 /tmp/inject_loki_100.py
```

### Prometheus n'a pas assez de données

```bash
# Vérifier que le log-generator tourne
docker compose logs log-generator --tail=10

# Accélérer le scraping (pour les tests)
# Dans backend/prometheus.yml, changer scrape_interval: 15s → scrape_interval: 5s
# Puis redémarrer Prometheus
docker compose restart prometheus
# Attendre 8 minutes = 100 scrapes × 5s
```

### Email non reçu dans MailHog

```bash
# Vérifier la configuration SMTP dans .env
grep SMTP .env

# SMTP_HOST doit être "mailhog" (et non "localhost")
# SMTP_PORT doit être 1025
# SMTP_USE_TLS doit être false

# Vérifier les logs backend pour des erreurs d'envoi
docker compose logs api | grep -i email
```

### OpenAI API Error

```bash
# Si le diagnostic retourne "categorie": "api_error", vérifier la clé
grep OPENAI .env

# Tester la connexion directement
curl -s https://${OPENAI_ENDPOINT}/openai/deployments/${OPENAI_DEPLOYMENT}/chat/completions?api-version=2024-02-01 \
  -H "api-key: ${OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"test"}]}'
```

### Incident non trouvé après le webhook

```bash
# Vérifier que le traitement background s'est terminé (attendre 20-30 secondes)
sleep 30

# Lister les incidents
curl -s http://localhost:8000/api/v1/incidents | python3 -m json.tool
```
