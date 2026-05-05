# REALISTIC_SCENARIO_EXAMPLE.md — Guide Scénario de Charge Réaliste

> **Assistant-SRE AIOps** — Guide de test complet : de l'injection de logs/métriques jusqu'au diagnostic IA et à la validation de la solution.  
> Réutilisable par l'équipe dev, QA et ops en local ou CI.

---

## Table des Matières

1. [Prérequis & Architecture du Scénario](#1-prérequis--architecture-du-scénario)
2. [Démarrer la Stack Docker Compose](#2-démarrer-la-stack-docker-compose)
3. [Injecter 100 Logs Simulés dans Loki](#3-injecter-100-logs-simulés-dans-loki)
4. [Injecter 100 Métriques dans Prometheus](#4-injecter-100-métriques-dans-prometheus)
5. [Visualiser Logs et Métriques dans Grafana](#5-visualiser-logs-et-métriques-dans-grafana)
6. [Configurer une Alerte Grafana avec Webhook](#6-configurer-une-alerte-grafana-avec-webhook)
7. [Déclencher le Process via Webhook](#7-déclencher-le-process-via-webhook)
8. [Suivre la Pipeline de Diagnostic IA](#8-suivre-la-pipeline-de-diagnostic-ia)
9. [Valider la Solution (Approval SRE)](#9-valider-la-solution-approval-sre)
10. [Vérifier l'Auto-Learning](#10-vérifier-lauto-learning)
11. [Checklist de Validation Finale](#11-checklist-de-validation-finale)

---

## 1. Prérequis & Architecture du Scénario

### Services requis

```
┌─────────────────────────────────────────────────────────────┐
│                    STACK LOCALE                              │
│                                                              │
│  Grafana :3000   ──webhook──►  FastAPI :8000                │
│                                    │                         │
│  Loki    :3100   ◄──LogQL──        ├──► MongoDB :27017      │
│  Prometheus :9090 ◄──PromQL──      └──► Azure OpenAI (web)  │
│                                                              │
│  Mongo Express :8081  (GUI MongoDB)                          │
└─────────────────────────────────────────────────────────────┘
```

### Scénario simulé

**Incident type :** `OOMKilledAlert` — Pod `fastapi-demo-7b9c8d6f4-x2k9p` dans le namespace `app-demo` tué par le kernel Linux pour dépassement de mémoire (OOM Kill). Redémarrages en boucle.

**Timeline :** 10 minutes d'escalade (09:00 → 09:10 UTC)

```
09:00:00  INFO   — Application démarrée, health check OK
09:01:30  INFO   — 150 requêtes/s traitées normalement
09:02:45  WARN   — Mémoire à 75% de la limite (192 Mi / 256 Mi)
09:03:20  WARN   — Garbage collector appelé 12 fois en 30s
09:04:10  ERROR  — Mémoire à 92% (236 Mi / 256 Mi), GC inefficace
09:05:00  ERROR  — Memory leak détecté sur /api/data endpoint
09:05:45  CRIT   — Mémoire à 99% (253 Mi / 256 Mi)
09:06:00  CRIT   — OOM Kill — Container terminé par le kernel
09:06:05  INFO   — Pod redémarré par K8s (restart #1)
09:07:15  WARN   — Même pattern de fuite mémoire détecté
09:08:30  ERROR  — Mémoire à 89% après seulement 2 minutes
09:09:00  CRIT   — OOM Kill — Container terminé (restart #2)
09:09:05  INFO   — Pod redémarré (restart #3)
09:10:00  CRIT   — Alerte Grafana déclenchée → Webhook vers FastAPI
```

---

## 2. Démarrer la Stack Docker Compose

```bash
# ── Depuis le dossier backend/ ──
cd ~/app/Assistant-SRE/backend

# Vérifier que Docker tourne
sudo service docker start
docker ps

# Copier et éditer les variables d'environnement
cp .env.example .env
nano .env
# Remplir : OPENAI_ENDPOINT, OPENAI_API_KEY, OPENAI_DEPLOYMENT
# Laisser les autres valeurs par défaut pour le test local

# Démarrer tous les services
docker-compose up -d

# Vérifier que tout est UP (attendre ~30s pour Loki/Prometheus)
docker-compose ps
```

**Sortie attendue :**

```
NAME                    STATUS          PORTS
backend-api-1           Up              0.0.0.0:8000->8000/tcp
backend-mongodb-1       Up              0.0.0.0:27017->27017/tcp
backend-mongo-express-1 Up              0.0.0.0:8081->8081/tcp
backend-loki-1          Up              0.0.0.0:3100->3100/tcp
backend-prometheus-1    Up              0.0.0.0:9090->9090/tcp
backend-log-generator-1 Up
```

**Tester les endpoints de santé :**

```bash
# Liveness
curl -s http://localhost:8000/healthz | python3 -m json.tool
# {"status": "ok"}

# Readiness (vérifie MongoDB)
curl -s http://localhost:8000/api/v1/health/ready | python3 -m json.tool
# {"status": "ready", "checks": {"mongodb": "ok"}}

# Loki UP ?
curl -s http://localhost:3100/ready
# ready

# Prometheus UP ?
curl -s http://localhost:9090/-/ready
# Prometheus Server is Ready.
```

---

## 3. Injecter 100 Logs Simulés dans Loki

### 3.1 — Script d'injection Python

Sauvegarder le script suivant dans `/tmp/inject_logs.py` :

```python
#!/usr/bin/env python3
"""
inject_logs.py — Injecte 100 logs simulés d'un incident OOMKilled dans Loki.
Simule la timeline réaliste d'un pod en fuite mémoire (09:00 → 09:10 UTC).
"""

import json
import time
import requests
from datetime import datetime, timezone, timedelta

LOKI_URL = "http://localhost:3100/loki/api/v1/push"

POD = "fastapi-demo-7b9c8d6f4-x2k9p"
NAMESPACE = "app-demo"
CONTAINER = "fastapi"
NODE = "aks-nodepool1-12345678-vmss000000"

EXPECTED_LOG_COUNT = 100  # Mettre à jour si des logs sont ajoutés/supprimés

# Base timestamp : 09:00:00 UTC aujourd'hui (dynamique — les timestamps changent à chaque exécution).
# Pour une reproductibilité totale (ex: CI), remplacer par une date fixe :
#   BASE_TS = datetime(2024, 1, 15, 9, 0, 0, tzinfo=timezone.utc)
BASE_TS = datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0)


def ts_ns(dt: datetime) -> str:
    """Convertir datetime en timestamp nanoseconde (string) pour Loki."""
    return str(int(dt.timestamp() * 1_000_000_000))


def offset(minutes: float, seconds: float = 0) -> datetime:
    return BASE_TS + timedelta(minutes=minutes, seconds=seconds)


# ── 100 logs simulés avec timeline réaliste ──
LOGS = [
    # ── Démarrage normal (09:00 – 09:02) ──
    (offset(0, 0),  "INFO",  "Application startup complete — uvicorn listening on 0.0.0.0:8000"),
    (offset(0, 5),  "INFO",  "Health check /healthz → 200 OK in 2ms"),
    (offset(0, 10), "INFO",  "MongoDB connection established — ping OK"),
    (offset(0, 15), "INFO",  "Azure OpenAI client initialized — model=gpt-35-turbo"),
    (offset(0, 20), "INFO",  "GET /api/v1/incidents → 200 OK — 0 incidents, 8ms"),
    (offset(0, 30), "INFO",  "POST /api/v1/webhook received — alert_name=TestStartup, state=ok"),
    (offset(0, 45), "INFO",  "Worker threads: 4 — max_workers=8"),
    (offset(1, 0),  "INFO",  "Request: GET /api/data → 200 OK — 45ms — user=sre-team"),
    (offset(1, 5),  "INFO",  "Request: GET /api/data → 200 OK — 47ms — user=sre-team"),
    (offset(1, 10), "INFO",  "Request: GET /api/data → 200 OK — 52ms — user=monitoring"),
    (offset(1, 15), "INFO",  "Memory usage: 45.2 Mi / 256 Mi (17.6%) — normal"),
    (offset(1, 20), "INFO",  "CPU usage: 0.8% — load average: 0.12 0.10 0.08"),
    (offset(1, 30), "INFO",  "GC collection gen0: 0.8ms — objects: 124502"),
    (offset(1, 45), "INFO",  "Active connections: 12 — queue depth: 0"),
    (offset(2, 0),  "INFO",  "Throughput: 150 req/s — p50=45ms p95=120ms p99=250ms"),
    # ── Dégradation mémoire commence (09:02 – 09:04) ──
    (offset(2, 10), "WARN",  "Memory usage: 75.4% — 193.0 Mi / 256 Mi — threshold=70%"),
    (offset(2, 15), "WARN",  "GC collection gen1: 15ms — objects retained: 892341 — possible leak"),
    (offset(2, 20), "INFO",  "Request: POST /api/data/bulk → 200 OK — 380ms — payload=2.1MB"),
    (offset(2, 25), "WARN",  "Request: GET /api/data → 200 OK — 180ms — latency increasing"),
    (offset(2, 30), "WARN",  "Cache miss rate: 68% — cache size: 45.2 Mi — evictions: 1240/s"),
    (offset(2, 35), "WARN",  "Memory usage: 78.2% — 200.2 Mi / 256 Mi — trend: +3 Mi/min"),
    (offset(2, 40), "WARN",  "Slow query detected: SELECT * FROM sessions — 1.2s — full scan"),
    (offset(2, 45), "WARN",  "Thread pool saturation: 7/8 workers busy — queue: 42 pending"),
    (offset(2, 50), "WARN",  "Connection pool: 95/100 connections used — pool pressure HIGH"),
    (offset(3, 0),  "WARN",  "GC called 12 times in last 30s — memory not being freed"),
    (offset(3, 5),  "WARN",  "Memory usage: 82.0% — 209.9 Mi / 256 Mi — alert threshold approaching"),
    (offset(3, 10), "WARN",  "Large object allocation: 512 KB — endpoint /api/data/export"),
    (offset(3, 15), "WARN",  "In-memory cache growing: 52.1 Mi — unbounded growth detected"),
    (offset(3, 20), "WARN",  "Response time degraded: p95=450ms — SLA threshold=400ms BREACHED"),
    (offset(3, 30), "WARN",  "Memory usage: 86.3% — 220.9 Mi / 256 Mi — rate of increase: 5 Mi/min"),
    # ── Erreurs actives (09:04 – 09:05:45) ──
    (offset(4, 0),  "ERROR", "Memory usage: 92.1% — 235.8 Mi / 256 Mi — CRITICAL THRESHOLD"),
    (offset(4, 5),  "ERROR", "GC overhead limit exceeded: 98% time in GC — throughput: 2%"),
    (offset(4, 10), "ERROR", "Request timeout: GET /api/data → 504 Gateway Timeout after 30s"),
    (offset(4, 15), "ERROR", "Request timeout: POST /api/data/bulk → 504 Gateway Timeout after 30s"),
    (offset(4, 20), "ERROR", "Memory leak confirmed: heap dump analysis shows 45K retained Session objects"),
    (offset(4, 25), "ERROR", "Session cache not evicting expired entries — TTL enforcement disabled"),
    (offset(4, 30), "ERROR", "Memory usage: 94.5% — 241.9 Mi / 256 Mi — imminent OOM"),
    (offset(4, 35), "ERROR", "Thread dump: 7 threads blocked on synchronized(sessionCache) — deadlock risk"),
    (offset(4, 40), "ERROR", "New connection rejected: max pool size reached — clients getting ECONNREFUSED"),
    (offset(4, 45), "ERROR", "Request: GET /api/health → 500 Internal Server Error — heap exhausted"),
    (offset(4, 50), "ERROR", "Metrics endpoint /metrics → 500 — prometheus scrape FAILED"),
    (offset(5, 0),  "ERROR", "Memory leak at /api/data: 12,450 Session objects not GC'd in 5 min"),
    (offset(5, 10), "ERROR", "Memory usage: 97.2% — 248.8 Mi / 256 Mi — OOM imminent in <60s"),
    (offset(5, 20), "ERROR", "Dropping incoming requests — circuit breaker OPEN — threshold exceeded"),
    (offset(5, 30), "ERROR", "Unable to allocate 4096 bytes — malloc failed — heap exhausted"),
    (offset(5, 40), "ERROR", "Stack trace: java.lang.OutOfMemoryError: Java heap space at SessionCache.put"),
    (offset(5, 45), "CRIT",  "Memory usage: 99.1% — 253.7 Mi / 256 Mi — LAST WARNING"),
    # ── OOM Kill #1 (09:06:00) ──
    (offset(6, 0),  "CRIT",  "Killed process 1 (python3) total-vm:456MB, anon-rss:253MB — Out of memory"),
    (offset(6, 1),  "CRIT",  "Container fastapi in pod fastapi-demo-7b9c8d6f4-x2k9p OOMKilled"),
    (offset(6, 2),  "CRIT",  "oom-kill event: constraint=CONSTRAINT_MEMCG — cpuset=/ mem=256MiB"),
    (offset(6, 3),  "INFO",  "Container restarted by Kubernetes — restart count: 1"),
    (offset(6, 5),  "INFO",  "Application startup complete — restart #1"),
    (offset(6, 10), "INFO",  "Memory usage after restart: 42.1 Mi / 256 Mi (16.4%)"),
    (offset(6, 15), "INFO",  "Connections re-established — MongoDB OK — Loki OK"),
    # ── Rechute rapide (09:07 – 09:08:30) ──
    (offset(7, 0),  "INFO",  "Resuming normal operations — 85 req/s"),
    (offset(7, 15), "WARN",  "Memory usage: 65.3% — 167.2 Mi / 256 Mi — same leak pattern"),
    (offset(7, 30), "WARN",  "Session cache growing again — 8,200 objects in 1 min 20s"),
    (offset(7, 45), "WARN",  "Memory usage: 71.8% — 183.8 Mi / 256 Mi — rate: 6 Mi/min (FASTER)"),
    (offset(8, 0),  "ERROR", "Memory usage: 82.4% — 211.0 Mi / 256 Mi — reaching OOM faster"),
    (offset(8, 10), "ERROR", "GC overhead: 95% — throughput collapsing — 8 req/s (was 85)"),
    (offset(8, 20), "ERROR", "Memory usage: 89.1% — 228.2 Mi / 256 Mi"),
    (offset(8, 25), "ERROR", "Request timeout cascade: 48 timeouts in last 30s"),
    (offset(8, 30), "ERROR", "Memory usage: 93.7% — 239.9 Mi / 256 Mi — OOM in ~90s"),
    # ── OOM Kill #2 (09:09:00) ──
    (offset(9, 0),  "CRIT",  "Killed process 1 (python3) total-vm:456MB, anon-rss:251MB — Out of memory"),
    (offset(9, 1),  "CRIT",  "Container fastapi OOMKilled — restart count: 2"),
    (offset(9, 2),  "CRIT",  "Pod fastapi-demo-7b9c8d6f4-x2k9p — CrashLoopBackOff detected"),
    (offset(9, 3),  "INFO",  "Container restarted by Kubernetes — restart count: 3 — backoff: 20s"),
    (offset(9, 5),  "INFO",  "Application startup complete — restart #3"),
    (offset(9, 10), "WARN",  "Memory usage: 38.4 Mi / 256 Mi — leak will resume within 3 minutes"),
    (offset(9, 15), "WARN",  "K8s event: BackOff — Back-off restarting failed container"),
    (offset(9, 20), "WARN",  "PodDisruptionBudget violated — 0/1 pods available in app-demo"),
    (offset(9, 25), "ERROR", "Upstream service /api/data returning 503 — circuit breaker open"),
    (offset(9, 30), "ERROR", "Downstream consumers experiencing errors — retry queue: 1240 messages"),
    # ── Alerte Grafana déclenchée (09:10:00) ──
    (offset(10, 0), "CRIT",  "ALERT FIRED: OOMKilledAlert — pod=fastapi-demo-7b9c8d6f4-x2k9p namespace=app-demo"),
    (offset(10, 1), "CRIT",  "kube_pod_container_status_restarts_total > 2 — threshold exceeded"),
    (offset(10, 2), "INFO",  "Webhook sent to http://fastapi-sre:8000/api/v1/webhook — awaiting AI diagnosis"),
    (offset(10, 3), "INFO",  "SRE notification dispatched — severity=CRITICAL — team=platform-eng"),
    # ── Logs de la pipeline IA (traitement backend) ──
    (offset(10, 5), "INFO",  "[AIOps] Webhook received: OOMKilledAlert — background processing started"),
    (offset(10, 6), "INFO",  "[AIOps] Loki query: namespace=app-demo pod=fastapi-demo-7b9c8d6f4-x2k9p — 87 logs fetched"),
    (offset(10, 7), "INFO",  "[AIOps] Prometheus query: memory_usage_bytes=253Mi restart_count=3"),
    (offset(10, 8), "INFO",  "[AIOps] Auto-Learning: no previous resolved incident for OOMKilledAlert"),
    (offset(10, 9), "INFO",  "[AIOps] Sanitizer: 87 logs cleaned — 50 sent to OpenAI"),
    (offset(10, 10),"INFO",  "[AIOps] Mega-Prompt sent to Azure OpenAI — gpt-35-turbo — WITH logs+metrics"),
    (offset(10, 15),"INFO",  "[AIOps] Diagnostic received: severite=critique categorie=resource_exhaustion"),
    (offset(10, 16),"INFO",  "[AIOps] Incident saved: id=65f3a2b4c8d9e1f2a3b4c5d6"),
    (offset(10, 17),"INFO",  "[AIOps] Email notification sent to sre-team@company.com"),
]

assert len(LOGS) == EXPECTED_LOG_COUNT, f"Expected {EXPECTED_LOG_COUNT} logs, got {len(LOGS)}"


def build_loki_payload(logs: list) -> dict:
    """Construire le payload Loki push API v1."""
    values = []
    for dt, level, message in logs:
        log_line = json.dumps({
            "level": level,
            "msg": message,
            "pod": POD,
            "namespace": NAMESPACE,
            "container": CONTAINER,
        })
        values.append([ts_ns(dt), log_line])

    return {
        "streams": [
            {
                "stream": {
                    "pod": POD,
                    "namespace": NAMESPACE,
                    "container": CONTAINER,
                    "node": NODE,
                    "app": "fastapi-demo",
                    "severity": "mixed",
                },
                "values": values,
            }
        ]
    }


if __name__ == "__main__":
    print(f"📝 Injection de {len(LOGS)} logs dans Loki...")
    payload = build_loki_payload(LOGS)

    response = requests.post(
        LOKI_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
    )

    if response.status_code == 204:
        print(f"✅ {len(LOGS)} logs injectés avec succès dans Loki")
        print(f"   Pod: {POD}")
        print(f"   Namespace: {NAMESPACE}")
        print(f"   Timeline: 09:00 → 09:10 UTC")
    else:
        print(f"❌ Erreur Loki: {response.status_code} — {response.text}")
```

### 3.2 — Exécuter l'injection

```bash
# Injecter les 100 logs
python3 /tmp/inject_logs.py
# ✅ 100 logs injectés avec succès dans Loki

# Vérifier en interrogeant Loki directement
curl -s -G 'http://localhost:3100/loki/api/v1/query_range' \
  --data-urlencode 'query={namespace="app-demo",pod="fastapi-demo-7b9c8d6f4-x2k9p"}' \
  --data-urlencode 'limit=5' \
  | python3 -m json.tool | head -40

# Compter les logs par niveau
curl -s -G 'http://localhost:3100/loki/api/v1/query' \
  --data-urlencode 'query=count_over_time({namespace="app-demo"}[10m])' \
  | python3 -m json.tool
```

---

## 4. Injecter 100 Métriques dans Prometheus

### 4.1 — Serveur de métriques Prometheus

Sauvegarder dans `/tmp/metrics_server.py` :

```python
#!/usr/bin/env python3
"""
metrics_server.py — Expose 100 métriques Prometheus simulant un pod OOMKilled.
Lance un serveur HTTP sur :9091 que Prometheus va scraper.
Simule l'évolution des métriques sur la timeline du scénario.
"""

import time
import math
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timezone

POD = "fastapi-demo-7b9c8d6f4-x2k9p"
NAMESPACE = "app-demo"
CONTAINER = "fastapi"
NODE = "aks-nodepool1-12345678-vmss000000"

# Heure de début du scénario
START_TIME = time.time()
LIMIT_BYTES = 256 * 1024 * 1024  # 256 Mi

def elapsed_minutes() -> float:
    return (time.time() - START_TIME) / 60.0


def memory_usage_bytes() -> float:
    """Simule la montée de mémoire jusqu'à l'OOM Kill (cycle de 6 minutes)."""
    t = elapsed_minutes() % 6  # Cycle de 6 min (montée + restart)
    if t < 0.1:
        return 42 * 1024 * 1024  # Post-restart : 42 Mi
    # Montée exponentielle
    pct = min(0.99, 0.17 + (t / 6.0) ** 1.8)
    return LIMIT_BYTES * pct


def cpu_seconds() -> float:
    """Augmente avec le temps (cumulatif)."""
    return elapsed_minutes() * 3.2 + 15.4


def restart_count() -> int:
    """Nombre de restarts basé sur le cycle."""
    return int(elapsed_minutes() / 6)


def generate_metrics() -> str:
    """Génère les 100 métriques en format text Prometheus."""
    t = elapsed_minutes()
    mem = memory_usage_bytes()
    mem_mi = mem / (1024 * 1024)
    cpu = cpu_seconds()
    restarts = restart_count()
    req_rate = max(0, 150 - (mem_mi / 256 * 145))  # Req/s baisse quand mémoire monte
    error_rate = max(0, (mem_mi - 192) / 64 * 15)  # Erreurs apparaissent à 75%+
    latency_p99 = 250 + (mem_mi / 256) ** 3 * 30000  # Latence explose

    labels = f'{{pod="{POD}",namespace="{NAMESPACE}",container="{CONTAINER}",node="{NODE}"}}'
    labels_no_container = f'{{pod="{POD}",namespace="{NAMESPACE}",node="{NODE}"}}'
    labels_pod_only = f'{{pod="{POD}",namespace="{NAMESPACE}"}}'

    lines = [
        "# HELP container_memory_usage_bytes Current memory usage in bytes",
        "# TYPE container_memory_usage_bytes gauge",
        f"container_memory_usage_bytes{labels} {mem:.0f}",

        "# HELP container_memory_working_set_bytes Memory working set in bytes",
        "# TYPE container_memory_working_set_bytes gauge",
        f"container_memory_working_set_bytes{labels} {mem * 0.92:.0f}",

        "# HELP container_memory_rss RSS memory in bytes",
        "# TYPE container_memory_rss gauge",
        f"container_memory_rss{labels} {mem * 0.85:.0f}",

        "# HELP container_memory_cache Cache memory in bytes",
        "# TYPE container_memory_cache gauge",
        f"container_memory_cache{labels} {mem * 0.08:.0f}",

        "# HELP container_memory_swap Swap memory in bytes",
        "# TYPE container_memory_swap gauge",
        f"container_memory_swap{labels} 0",

        "# HELP container_memory_limit_bytes Memory limit in bytes",
        "# TYPE container_memory_limit_bytes gauge",
        f"container_memory_limit_bytes{labels} {LIMIT_BYTES}",

        "# HELP container_memory_usage_ratio Memory usage ratio (0-1)",
        "# TYPE container_memory_usage_ratio gauge",
        f"container_memory_usage_ratio{labels} {mem / LIMIT_BYTES:.4f}",

        "# HELP container_cpu_usage_seconds_total CPU usage in seconds",
        "# TYPE container_cpu_usage_seconds_total counter",
        f"container_cpu_usage_seconds_total{labels} {cpu:.2f}",

        "# HELP container_cpu_cfs_throttled_seconds_total CPU throttle seconds",
        "# TYPE container_cpu_cfs_throttled_seconds_total counter",
        f"container_cpu_cfs_throttled_seconds_total{labels} {max(0, (mem_mi - 200) * 0.15):.2f}",

        "# HELP container_cpu_cfs_periods_total CPU CFS periods",
        "# TYPE container_cpu_cfs_periods_total counter",
        f"container_cpu_cfs_periods_total{labels} {int(t * 1000)}",

        "# HELP kube_pod_container_status_restarts_total Container restart count",
        "# TYPE kube_pod_container_status_restarts_total counter",
        f"kube_pod_container_status_restarts_total{labels_pod_only} {restarts}",

        "# HELP kube_pod_container_status_running Container running status",
        "# TYPE kube_pod_container_status_running gauge",
        f"kube_pod_container_status_running{labels} 1",

        "# HELP kube_pod_container_status_ready Container ready status",
        "# TYPE kube_pod_container_status_ready gauge",
        f"kube_pod_container_status_ready{labels} {1 if mem_mi < 250 else 0}",

        "# HELP kube_pod_container_status_terminated Container terminated status",
        "# TYPE kube_pod_container_status_terminated gauge",
        f"kube_pod_container_status_terminated{labels} {1 if mem_mi >= 253 else 0}",

        "# HELP kube_pod_container_resource_limits_memory_bytes Memory limit in bytes",
        "# TYPE kube_pod_container_resource_limits_memory_bytes gauge",
        f"kube_pod_container_resource_limits_memory_bytes{labels} {LIMIT_BYTES}",

        "# HELP kube_pod_container_resource_requests_memory_bytes Memory request in bytes",
        "# TYPE kube_pod_container_resource_requests_memory_bytes gauge",
        f"kube_pod_container_resource_requests_memory_bytes{labels} {128 * 1024 * 1024}",

        "# HELP kube_pod_status_phase Pod phase",
        "# TYPE kube_pod_status_phase gauge",
        f'kube_pod_status_phase{{pod="{POD}",namespace="{NAMESPACE}",phase="Running"}} 1',

        "# HELP http_requests_total HTTP requests counter",
        "# TYPE http_requests_total counter",
        f'http_requests_total{{pod="{POD}",method="GET",endpoint="/api/data",status="200"}} {int(t * 60 * req_rate * 0.92):.0f}',
        f'http_requests_total{{pod="{POD}",method="GET",endpoint="/api/data",status="500"}} {int(t * 60 * error_rate):.0f}',
        f'http_requests_total{{pod="{POD}",method="GET",endpoint="/api/data",status="504"}} {int(max(0, t - 4) * 60 * 2):.0f}',
        f'http_requests_total{{pod="{POD}",method="POST",endpoint="/api/data/bulk",status="200"}} {int(t * 12):.0f}',
        f'http_requests_total{{pod="{POD}",method="GET",endpoint="/healthz",status="200"}} {int(t * 60 * 0.5):.0f}',

        "# HELP http_request_duration_seconds HTTP request duration histogram",
        "# TYPE http_request_duration_seconds histogram",
        f'http_request_duration_seconds_bucket{{pod="{POD}",le="0.1"}} {int(t * 30 * max(0, 1 - mem_mi/200))}',
        f'http_request_duration_seconds_bucket{{pod="{POD}",le="0.5"}} {int(t * 50 * max(0, 1 - mem_mi/256))}',
        f'http_request_duration_seconds_bucket{{pod="{POD}",le="1.0"}} {int(t * 55)}',
        f'http_request_duration_seconds_bucket{{pod="{POD}",le="+Inf"}} {int(t * 60)}',
        f'http_request_duration_seconds_sum{{pod="{POD}"}} {latency_p99 * t / 1000:.2f}',
        f'http_request_duration_seconds_count{{pod="{POD}"}} {int(t * 60)}',

        "# HELP http_request_duration_p99_seconds p99 latency in seconds",
        "# TYPE http_request_duration_p99_seconds gauge",
        f'http_request_duration_p99_seconds{{pod="{POD}"}} {latency_p99 / 1000:.3f}',

        "# HELP http_error_rate HTTP error rate (0-1)",
        "# TYPE http_error_rate gauge",
        f'http_error_rate{{pod="{POD}"}} {min(1.0, error_rate / 150):.4f}',

        "# HELP go_gc_duration_seconds GC pause duration",
        "# TYPE go_gc_duration_seconds summary",
        f'go_gc_duration_seconds{{pod="{POD}",quantile="0.5"}} {max(0.001, mem_mi / 256 * 0.15):.4f}',
        f'go_gc_duration_seconds{{pod="{POD}",quantile="0.9"}} {max(0.005, mem_mi / 256 * 0.45):.4f}',
        f'go_gc_duration_seconds{{pod="{POD}",quantile="0.99"}} {max(0.010, mem_mi / 256 * 0.98):.4f}',
        f'go_gc_duration_seconds_sum{{pod="{POD}"}} {t * 0.8:.2f}',
        f'go_gc_duration_seconds_count{{pod="{POD}"}} {int(t * 4 + restarts * 15)}',

        "# HELP go_gc_calls_total Total GC calls",
        "# TYPE go_gc_calls_total counter",
        f'go_gc_calls_total{{pod="{POD}"}} {int(t * 4 + restarts * 15)}',

        "# HELP go_heap_objects Heap objects in use",
        "# TYPE go_heap_objects gauge",
        f'go_heap_objects{{pod="{POD}"}} {int(124502 + t * 8000 + restarts * 5000)}',

        "# HELP go_heap_alloc_bytes Heap allocated bytes",
        "# TYPE go_heap_alloc_bytes gauge",
        f'go_heap_alloc_bytes{{pod="{POD}"}} {mem * 0.78:.0f}',

        "# HELP go_heap_inuse_bytes Heap in-use bytes",
        "# TYPE go_heap_inuse_bytes gauge",
        f'go_heap_inuse_bytes{{pod="{POD}"}} {mem * 0.82:.0f}',

        "# HELP go_goroutines Number of goroutines",
        "# TYPE go_goroutines gauge",
        f'go_goroutines{{pod="{POD}"}} {int(45 + mem_mi / 5)}',

        "# HELP process_open_fds Open file descriptors",
        "# TYPE process_open_fds gauge",
        f'process_open_fds{{pod="{POD}"}} {int(42 + t * 0.5)}',

        "# HELP process_max_fds Max file descriptors",
        "# TYPE process_max_fds gauge",
        f'process_max_fds{{pod="{POD}"}} 1048576',

        "# HELP mongodb_connections_active Active MongoDB connections",
        "# TYPE mongodb_connections_active gauge",
        f'mongodb_connections_active{{pod="{POD}"}} {min(100, int(12 + t * 2))}',

        "# HELP mongodb_connections_available Available MongoDB connections",
        "# TYPE mongodb_connections_available gauge",
        f'mongodb_connections_available{{pod="{POD}"}} {max(0, 100 - int(12 + t * 2))}',

        "# HELP mongodb_operations_total MongoDB operations counter",
        "# TYPE mongodb_operations_total counter",
        f'mongodb_operations_total{{pod="{POD}",op="find"}} {int(t * 45)}',
        f'mongodb_operations_total{{pod="{POD}",op="insert"}} {int(t * 8)}',
        f'mongodb_operations_total{{pod="{POD}",op="update"}} {int(t * 3)}',

        "# HELP session_cache_size Session objects in memory cache",
        "# TYPE session_cache_size gauge",
        f'session_cache_size{{pod="{POD}"}} {int(1200 + t * 7200)}',

        "# HELP session_cache_evictions_total Session cache evictions",
        "# TYPE session_cache_evictions_total counter",
        f'session_cache_evictions_total{{pod="{POD}"}} {int(max(0, t - 2) * 1240)}',

        "# HELP network_receive_bytes_total Bytes received",
        "# TYPE network_receive_bytes_total counter",
        f'network_receive_bytes_total{labels_no_container} {int(t * 60 * 15000)}',

        "# HELP network_transmit_bytes_total Bytes transmitted",
        "# TYPE network_transmit_bytes_total counter",
        f'network_transmit_bytes_total{labels_no_container} {int(t * 60 * 45000)}',

        "# HELP network_receive_packets_total Packets received",
        "# TYPE network_receive_packets_total counter",
        f'network_receive_packets_total{labels_no_container} {int(t * 60 * 120)}',

        "# HELP network_transmit_packets_dropped_total Packets dropped",
        "# TYPE network_transmit_packets_dropped_total counter",
        f'network_transmit_packets_dropped_total{labels_no_container} {int(max(0, t - 5) * 12)}',

        "# HELP container_fs_reads_total Filesystem reads",
        "# TYPE container_fs_reads_total counter",
        f'container_fs_reads_total{labels} {int(t * 220)}',

        "# HELP container_fs_writes_total Filesystem writes",
        "# TYPE container_fs_writes_total counter",
        f'container_fs_writes_total{labels} {int(t * 85)}',

        "# HELP container_fs_usage_bytes Filesystem usage bytes",
        "# TYPE container_fs_usage_bytes gauge",
        f'container_fs_usage_bytes{labels} {int(45 * 1024 * 1024 + t * 512 * 1024)}',

        "# HELP container_threads Number of threads",
        "# TYPE container_threads gauge",
        f'container_threads{labels} {int(8 + mem_mi / 30)}',

        "# HELP kube_node_status_allocatable_memory_bytes Node allocatable memory",
        "# TYPE kube_node_status_allocatable_memory_bytes gauge",
        f'kube_node_status_allocatable_memory_bytes{{node="{NODE}"}} {7516192768}',

        "# HELP kube_node_memory_pressure Node memory pressure",
        "# TYPE kube_node_memory_pressure gauge",
        f'kube_node_memory_pressure{{node="{NODE}"}} {1 if mem_mi > 240 else 0}',

        "# HELP up Scrape success indicator",
        "# TYPE up gauge",
        f'up{{job="fastapi-demo",pod="{POD}"}} {0 if mem_mi > 253 else 1}',
    ]

    return "\n".join(lines) + "\n"


class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/metrics":
            body = generate_metrics().encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Silencieux


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 9091), MetricsHandler)
    print("📊 Serveur métriques démarré sur http://localhost:9091/metrics")
    print(f"   Pod: {POD}")
    print(f"   Namespace: {NAMESPACE}")
    print(f"   Simule: montée mémoire OOMKill (cycle 6 min)")
    print("   Ctrl+C pour arrêter")
    server.serve_forever()
```

### 4.2 — Démarrer le serveur de métriques

```bash
# Terminal 1 — Lancer le serveur métriques (laisse tourner)
python3 /tmp/metrics_server.py &
METRICS_PID=$!
echo "Serveur métriques PID: $METRICS_PID"

# Vérifier les métriques exposées
curl -s http://localhost:9091/metrics | head -30

# Compter les métriques (doit être ~100 lignes de valeurs)
curl -s http://localhost:9091/metrics | grep -v "^#" | grep -v "^$" | wc -l
```

### 4.3 — Configurer Prometheus pour scraper ce serveur

Ajouter dans `backend/prometheus.yml` (puis redémarrer Prometheus) :

```yaml
scrape_configs:
  - job_name: 'fastapi-demo-sim'
    static_configs:
      - targets: ['host.docker.internal:9091']
    scrape_interval: 15s
    labels:
      pod: 'fastapi-demo-7b9c8d6f4-x2k9p'
      namespace: 'app-demo'
```

```bash
# Recharger Prometheus sans redémarrage
curl -X POST http://localhost:9090/-/reload

# Vérifier que le target est actif
curl -s http://localhost:9090/api/v1/targets | python3 -m json.tool | grep -A5 "fastapi-demo-sim"
```

---

## 5. Visualiser Logs et Métriques dans Grafana

### 5.1 — Accéder à Grafana

```
URL    : http://localhost:3000
User   : admin
Pass   : admin  (ou selon .env)
```

### 5.2 — Configurer les datasources

```bash
# Datasource Loki — via API Grafana
curl -s -X POST http://admin:admin@localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Loki",
    "type": "loki",
    "url": "http://loki:3100",
    "access": "proxy",
    "isDefault": false
  }' | python3 -m json.tool

# Datasource Prometheus
curl -s -X POST http://admin:admin@localhost:3000/api/datasources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Prometheus",
    "type": "prometheus",
    "url": "http://prometheus:9090",
    "access": "proxy",
    "isDefault": true
  }' | python3 -m json.tool
```

### 5.3 — Requêtes de visualisation

**Loki — Explorer les logs du pod :**

```logql
# Tous les logs du pod
{namespace="app-demo", pod="fastapi-demo-7b9c8d6f4-x2k9p"}

# Uniquement les erreurs et critiques
{namespace="app-demo"} | json | level=~"ERROR|CRIT"

# Logs contenant "OOM"
{namespace="app-demo"} |= "OOM"

# Timeline des niveaux de sévérité (count_over_time)
sum by (level) (
  count_over_time(
    {namespace="app-demo"} | json [1m]
  )
)
```

**Prometheus — Métriques clés :**

```promql
# Mémoire utilisée en Mi
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p"} / 1024 / 1024

# Ratio mémoire / limite
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p"}
  / container_memory_limit_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p"}

# Taux de restart par minute
rate(kube_pod_container_status_restarts_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"}[5m])

# Taux d'erreur HTTP
rate(http_requests_total{pod="fastapi-demo-7b9c8d6f4-x2k9p", status=~"5.."}[1m])
  / rate(http_requests_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"}[1m])

# Latence p99
http_request_duration_p99_seconds{pod="fastapi-demo-7b9c8d6f4-x2k9p"} * 1000

# Taille du cache session (fuite mémoire)
session_cache_size{pod="fastapi-demo-7b9c8d6f4-x2k9p"}
```

---

## 6. Configurer une Alerte Grafana avec Webhook

### 6.1 — Créer le Contact Point (Webhook)

```bash
# Créer le contact point webhook vers le backend FastAPI
curl -s -X POST http://admin:admin@localhost:3000/api/v1/provisioning/contact-points \
  -H "Content-Type: application/json" \
  -d '{
    "name": "AIOps SRE Backend",
    "type": "webhook",
    "settings": {
      "url": "http://api:8000/api/v1/webhook",
      "httpMethod": "POST",
      "contentType": "application/json",
      "title": "{{ .CommonLabels.alertname }}",
      "message": "{{ range .Alerts }}{{ .Annotations.summary }}{{ end }}"
    },
    "disableResolveMessage": false
  }' | python3 -m json.tool
```

### 6.2 — Créer la règle d'alerte OOMKilled

```bash
# Créer la règle d'alerte Grafana (Unified Alerting)
curl -s -X POST http://admin:admin@localhost:3000/api/v1/provisioning/alert-rules \
  -H "Content-Type: application/json" \
  -d '{
    "title": "OOMKilledAlert",
    "ruleGroup": "kubernetes-pod-alerts",
    "folderUID": "alerting",
    "condition": "C",
    "data": [
      {
        "refId": "A",
        "datasourceUid": "__expr__",
        "model": {
          "type": "math",
          "expression": "1"
        }
      },
      {
        "refId": "B",
        "queryType": "instant",
        "datasourceUid": "prometheus",
        "model": {
          "expr": "kube_pod_container_status_restarts_total{namespace=\"app-demo\"}",
          "legendFormat": "{{pod}}"
        }
      },
      {
        "refId": "C",
        "datasourceUid": "__expr__",
        "model": {
          "type": "threshold",
          "expression": "B",
          "conditions": [
            {
              "evaluator": {"params": [2], "type": "gt"},
              "operator": {"type": "and"},
              "reducer": {"type": "last"}
            }
          ]
        }
      }
    ],
    "noDataState": "NoData",
    "execErrState": "Error",
    "for": "1m",
    "annotations": {
      "summary": "Pod {{ $labels.pod }} OOMKilled — {{ $values.B }} restarts",
      "description": "Le pod {{ $labels.pod }} dans {{ $labels.namespace }} a redémarré plus de 2 fois en 5 minutes — suspicion de fuite mémoire"
    },
    "labels": {
      "severity": "critical",
      "team": "platform-eng",
      "alert_type": "OOMKilledAlert"
    }
  }' | python3 -m json.tool
```

### 6.3 — Format du payload webhook envoyé par Grafana

Grafana envoie ce payload JSON à `POST /api/v1/webhook` :

```json
{
  "alert_name": "OOMKilledAlert",
  "state": "alerting",
  "labels": {
    "pod": "fastapi-demo-7b9c8d6f4-x2k9p",
    "namespace": "app-demo",
    "container": "fastapi",
    "severity": "critical",
    "team": "platform-eng"
  },
  "message": "Pod fastapi-demo-7b9c8d6f4-x2k9p OOMKilled — 3 restarts",
  "dashboard_url": "http://localhost:3000/d/abc/kubernetes-pods"
}
```

---

## 7. Déclencher le Process via Webhook

### 7.1 — Déclencher manuellement (sans attendre Grafana)

```bash
# Envoyer le webhook directement au backend
curl -s -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "OOMKilledAlert",
    "state": "alerting",
    "labels": {
      "pod": "fastapi-demo-7b9c8d6f4-x2k9p",
      "namespace": "app-demo",
      "container": "fastapi",
      "severity": "critical"
    },
    "message": "Container fastapi in pod fastapi-demo-7b9c8d6f4-x2k9p OOMKilled — 3 restarts in 10 minutes"
  }' | python3 -m json.tool
```

**Réponse attendue (immédiate) :**

```json
{
  "message": "Alerte reçue, traitement en cours"
}
```

**HTTP 202 Accepted** — La pipeline s'exécute en arrière-plan.

### 7.2 — Simuler plusieurs alertes différentes (charge)

```bash
#!/bin/bash
# Envoyer 5 alertes différentes en séquence pour tester la charge

ALERTS=(
  '{"alert_name":"OOMKilledAlert","state":"alerting","labels":{"pod":"fastapi-demo-7b9c8d6f4-x2k9p","namespace":"app-demo"},"message":"OOMKilled - restart 3"}'
  '{"alert_name":"HighMemoryUsage","state":"alerting","labels":{"pod":"redis-cache-5d9f-abc12","namespace":"app-demo"},"message":"Memory at 94% - 471 Mi / 512 Mi"}'
  '{"alert_name":"CrashLoopBackOff","state":"alerting","labels":{"pod":"worker-7c6d-def45","namespace":"app-demo"},"message":"CrashLoopBackOff - exit code 1"}'
  '{"alert_name":"HighLatency","state":"alerting","labels":{"pod":"api-gateway-4e8f-ghi78","namespace":"app-demo"},"message":"p99 latency 8.4s - SLA breached"}'
  '{"alert_name":"DiskPressure","state":"alerting","labels":{"pod":"postgres-8a2b-jkl01","namespace":"data"},"message":"PVC usage 89% - /data/pgdata"}'
)

for payload in "${ALERTS[@]}"; do
  echo "📤 Envoi: $(echo $payload | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["alert_name"])')"
  curl -s -X POST http://localhost:8000/api/v1/webhook \
    -H "Content-Type: application/json" \
    -d "$payload" | python3 -m json.tool
  sleep 2
done

echo "✅ 5 alertes envoyées"
```

---

## 8. Suivre la Pipeline de Diagnostic IA

### 8.1 — Observer les logs du backend en temps réel

```bash
# Suivre les logs du container FastAPI
docker-compose logs -f api

# Filtrer uniquement les logs de traitement d'alerte
docker-compose logs -f api | grep -E "(OOMKilled|Traitement|Loki|Prometheus|OpenAI|Mega-Prompt|Diagnostic|Incident|Email)"
```

**Sortie attendue de la pipeline complète :**

```
api-1  | {"timestamp":"2024-01-15T09:10:05Z","level":"INFO","message":"📥 Webhook reçu : OOMKilledAlert — alerting"}
api-1  | {"timestamp":"2024-01-15T09:10:05Z","level":"INFO","message":"🔄 Traitement de l'alerte 'OOMKilledAlert' — pod=fastapi-demo-7b9c8d6f4-x2k9p"}
api-1  | {"timestamp":"2024-01-15T09:10:06Z","level":"INFO","message":"📝 87 logs récupérés depuis Loki pour pod=fastapi-demo-7b9c8d6f4-x2k9p"}
api-1  | {"timestamp":"2024-01-15T09:10:06Z","level":"INFO","message":"📊 Métriques récupérées pour pod=fastapi-demo-7b9c8d6f4-x2k9p : {'memory_usage_bytes': 265289728, 'cpu_usage_seconds': 48.2, 'restart_count': 3}"}
api-1  | {"timestamp":"2024-01-15T09:10:06Z","level":"INFO","message":"❌ Aucun incident passé résolu pour 'OOMKilledAlert'"}
api-1  | {"timestamp":"2024-01-15T09:10:06Z","level":"INFO","message":"🔐 Sanitizer : 87 logs → 50 nettoyés (tronqué à 50)"}
api-1  | {"timestamp":"2024-01-15T09:10:07Z","level":"INFO","message":"📤 Mega-Prompt envoyé à OpenAI SANS historique (50 logs, 3 métriques)"}
api-1  | {"timestamp":"2024-01-15T09:10:19Z","level":"INFO","message":"✅ Diagnostic IA reçu — sévérité: critique"}
api-1  | {"timestamp":"2024-01-15T09:10:20Z","level":"INFO","message":"💾 Incident sauvegardé : 65f3a2b4c8d9e1f2a3b4c5d6"}
api-1  | {"timestamp":"2024-01-15T09:10:20Z","level":"INFO","message":"📧 Email envoyé à sre-team@company.com pour alerte OOMKilledAlert"}
api-1  | {"timestamp":"2024-01-15T09:10:20Z","level":"INFO","message":"✅ Incident 'OOMKilledAlert' traité et sauvegardé (id=65f3a2b4c8d9e1f2a3b4c5d6)"}
```

### 8.2 — Récupérer le diagnostic via l'API

```bash
# Lister les incidents (attendre ~15s après le webhook)
curl -s http://localhost:8000/api/v1/incidents | python3 -m json.tool

# Récupérer l'ID du premier incident
INCIDENT_ID=$(curl -s http://localhost:8000/api/v1/incidents | python3 -c "
import json, sys
incidents = json.load(sys.stdin)
if incidents:
    print(incidents[0]['_id'])
else:
    print('AUCUN INCIDENT')
")

echo "Incident ID: $INCIDENT_ID"

# Détail complet de l'incident avec logs et métriques actuels
curl -s http://localhost:8000/api/v1/incidents/$INCIDENT_ID | python3 -m json.tool
```

**Exemple de réponse du diagnostic IA :**

```json
{
  "_id": "65f3a2b4c8d9e1f2a3b4c5d6",
  "alert_name": "OOMKilledAlert",
  "state": "alerting",
  "labels": {
    "pod": "fastapi-demo-7b9c8d6f4-x2k9p",
    "namespace": "app-demo",
    "container": "fastapi"
  },
  "message": "Container fastapi OOMKilled — 3 restarts in 10 minutes",
  "logs_collected": 87,
  "metrics_collected": 3,
  "past_solution_used": null,
  "diagnostic": {
    "cause_racine": "Fuite mémoire dans l'endpoint /api/data causée par un cache de sessions non borné. L'objet SessionCache accumule 12,450+ objets non garbage-collectés. La limite mémoire de 256 Mi est atteinte en ~6 minutes, déclenchant un OOM Kill par le kernel Linux.",
    "solution": "1. Augmenter la limite mémoire temporairement : kubectl set resources deployment/fastapi-demo -c fastapi --limits=memory=512Mi\n2. Corriger le cache : ajouter un TTL et une taille maximale (ex: max_size=1000, ttl=300s)\n3. Redémarrer le pod : kubectl rollout restart deployment/fastapi-demo -n app-demo\n4. Vérifier : kubectl top pods -n app-demo --watch",
    "severite": "critique",
    "categorie": "resource_exhaustion"
  },
  "status": "ouvert",
  "validated_solution": null,
  "created_at": "2024-01-15T09:10:20Z",
  "resolved_at": null,
  "current_logs": ["[09:10:05] INFO: Application startup complete", "..."],
  "current_metrics": {
    "memory_usage_bytes": 44040192,
    "cpu_usage_seconds": 51.4,
    "restart_count": 3
  }
}
```

### 8.3 — Poser des questions au chatbot SRE

```bash
# Question 1 : Impact sur les autres pods
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"incident_id\": \"$INCIDENT_ID\",
    \"question\": \"Est-ce que cette fuite mémoire peut impacter les autres pods dans le même namespace ?\"
  }" | python3 -m json.tool

# Question 2 : Commande de vérification
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"incident_id\": \"$INCIDENT_ID\",
    \"question\": \"Donne-moi la commande exacte pour surveiller la mémoire du pod en temps réel\"
  }" | python3 -m json.tool

# Question 3 : Cause racine plus détaillée
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"incident_id\": \"$INCIDENT_ID\",
    \"question\": \"Quel est le code Python qui cause la fuite mémoire selon les logs ?\"
  }" | python3 -m json.tool
```

**Exemples de réponses attendues :**

```json
{
  "answer": "Oui, si le pod fastapi-demo est dans le même namespace app-demo et que d'autres pods dépendent de son API, ils recevront des erreurs 503/504 pendant les phases de CrashLoopBackOff. Pour isoler l'impact : kubectl get pods -n app-demo | grep -v Running",
  "incident_id": "65f3a2b4c8d9e1f2a3b4c5d6"
}
```

---

## 9. Valider la Solution (Approval SRE)

### 9.1 — Valider la solution proposée par l'IA

```bash
# L'ingénieur SRE valide la solution (avec modification)
curl -s -X PUT http://localhost:8000/api/v1/incidents/$INCIDENT_ID/resolve \
  -H "Content-Type: application/json" \
  -d '{
    "validated_solution": "1. kubectl set resources deployment/fastapi-demo -c fastapi --limits=memory=512Mi -n app-demo\n2. kubectl rollout restart deployment/fastapi-demo -n app-demo\n3. Corriger SessionCache : ajouter maxsize=1000 et ttl=300 dans app/cache.py line 45\n4. Déployer le fix via CI/CD pipeline dans les 4h"
  }' | python3 -m json.tool
```

**Réponse attendue :**

```json
{
  "message": "Incident marqué comme résolu",
  "incident_id": "65f3a2b4c8d9e1f2a3b4c5d6",
  "validated_solution": "1. kubectl set resources deployment/fastapi-demo..."
}
```

### 9.2 — Vérifier l'état dans MongoDB

```bash
# Via Mongo Express (GUI)
open http://localhost:8081
# Naviguer : aiops_db → incidents → voir le document

# Via API REST
curl -s http://localhost:8000/api/v1/incidents/$INCIDENT_ID \
  | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'Status         : {d[\"status\"]}')
print(f'Résolu le      : {d.get(\"resolved_at\", \"N/A\")}')
print(f'Solution validée: {d.get(\"validated_solution\", \"N/A\")[:100]}...')
"

# Sortie attendue :
# Status          : résolu
# Résolu le       : 2024-01-15T09:15:30Z
# Solution validée: 1. kubectl set resources deployment/fastapi-demo...
```

---

## 10. Vérifier l'Auto-Learning

### 10.1 — Déclencher une deuxième alerte identique

```bash
# Simuler la même alerte OOMKilledAlert quelques minutes plus tard
curl -s -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "OOMKilledAlert",
    "state": "alerting",
    "labels": {
      "pod": "fastapi-demo-7b9c8d6f4-x2k9p",
      "namespace": "app-demo",
      "container": "fastapi"
    },
    "message": "OOMKilledAlert recurrence — restart count: 5"
  }' | python3 -m json.tool
```

### 10.2 — Vérifier que l'Auto-Learning s'active

```bash
# Observer les logs (l'Auto-Learning doit être loggé)
docker-compose logs api | grep -E "(Auto-Learning|passé|résolu|incident passé)"

# Sortie attendue (Auto-Learning actif) :
# {"message":"🔄 Incident passé trouvé pour 'OOMKilledAlert' — solution: 1. kubectl set resources..."}
# {"message":"📤 Mega-Prompt envoyé à OpenAI AVEC historique (50 logs, 3 métriques)"}
```

### 10.3 — Comparer les deux diagnostics

```bash
# Lister les 2 incidents OOMKilledAlert
curl -s http://localhost:8000/api/v1/incidents | python3 -c "
import json, sys
incidents = json.load(sys.stdin)
oom_incidents = [i for i in incidents if i['alert_name'] == 'OOMKilledAlert']
print(f'Nombre d incidents OOMKilledAlert: {len(oom_incidents)}')
for i, inc in enumerate(oom_incidents):
    print(f'\nIncident #{i+1} (id={inc[\"_id\"]}):')
    print(f'  past_solution_used: {inc.get(\"past_solution_used\", \"None\")[:80] if inc.get(\"past_solution_used\") else \"None\"}')
    print(f'  diagnostic.solution: {inc.get(\"diagnostic\", {}).get(\"solution\", \"N/A\")[:80]}...')
"

# Sortie attendue :
# Nombre d incidents OOMKilledAlert: 2
#
# Incident #1 (id=65f3a2b4c8d9e1f2a3b4c5d6):
#   past_solution_used: None
#   diagnostic.solution: 1. Augmenter la limite mémoire temporairement : kubectl set...
#
# Incident #2 (id=65f3a2b4c8d9e1f2a3b4c5d7):
#   past_solution_used: 1. kubectl set resources deployment/fastapi-demo...
#   diagnostic.solution: En tenant compte de la solution précédemment validée...
```

---

## 11. Checklist de Validation Finale

```
INFRASTRUCTURE
══════════════
✅ docker-compose ps → Tous les services "Up"
✅ curl /healthz → {"status":"ok"}
✅ curl /api/v1/health/ready → {"status":"ready","checks":{"mongodb":"ok"}}
✅ curl http://localhost:3100/ready → ready
✅ curl http://localhost:9090/-/ready → Prometheus is Ready

INJECTION DONNÉES
═════════════════
✅ python3 /tmp/inject_logs.py → "✅ 100 logs injectés"
✅ curl Loki query_range → retourne les 100 logs du pod
✅ curl http://localhost:9091/metrics → ~100 métriques exposées
✅ Prometheus target fastapi-demo-sim → State: UP
✅ PromQL container_memory_usage_bytes → valeur > 0

PIPELINE WEBHOOK → IA
══════════════════════
✅ curl POST /api/v1/webhook → HTTP 202 {"message":"...traitement en cours"}
✅ logs backend : "📝 87 logs récupérés depuis Loki"
✅ logs backend : "📊 Métriques récupérées"
✅ logs backend : "📤 Mega-Prompt envoyé à OpenAI"
✅ logs backend : "✅ Diagnostic IA reçu — sévérité: critique"
✅ logs backend : "💾 Incident sauvegardé"
✅ curl GET /api/v1/incidents → liste avec au moins 1 incident
✅ incident.diagnostic.cause_racine → non vide
✅ incident.diagnostic.solution → contient "kubectl"
✅ incident.diagnostic.severite → "critique" ou "haute"
✅ incident.diagnostic.categorie → "resource_exhaustion"

CHATBOT SRE
════════════
✅ curl POST /api/v1/chat → HTTP 200 {"answer":"...","incident_id":"..."}
✅ Réponse pertinente à la question posée

VALIDATION / APPROVE
═════════════════════
✅ curl PUT /api/v1/incidents/{id}/resolve → HTTP 200 {"message":"Incident marqué comme résolu"}
✅ curl GET /api/v1/incidents/{id} → status="résolu"
✅ incident.validated_solution → non vide
✅ incident.resolved_at → timestamp présent

AUTO-LEARNING
══════════════
✅ Deuxième webhook OOMKilledAlert → HTTP 202
✅ logs backend : "🔄 Incident passé trouvé pour 'OOMKilledAlert'"
✅ logs backend : "📤 Mega-Prompt envoyé à OpenAI AVEC historique"
✅ Deuxième incident.past_solution_used → non null

TESTS AUTOMATISÉS
══════════════════
✅ cd backend && python -m pytest tests/ -v → 64 passed
✅ Aucun test en échec (0 failed)
```

---

**Guide rédigé pour l'équipe Assistant-SRE AIOps.**  
Reproduisible en local, CI, ou environnement de staging.  
Timeline scénario : OOMKilled pod en 10 minutes → diagnostic IA < 20s → résolution SRE en 5 min.
