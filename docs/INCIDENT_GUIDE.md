# Guide d'incident réel — CPU > 80% + Memory Leak avant OOMKilled

> **Guide complet** : cas réel, processus de traitement, et procédure de test local A–Z.

---

## Table des matières

1. [Cas réel : incident avant OOMKilled](#1-cas-réel--incident-avant-oomkilled)
2. [Logs (100 lignes réalistes)](#2-logs-100-lignes-réalistes)
3. [Métriques Prometheus (100 points)](#3-métriques-prometheus-100-points)
4. [Processus complet de traitement](#4-processus-complet-de-traitement)
5. [Guide A–Z : tester localement en Docker](#5-guide-az--tester-localement-en-docker)

---

## 1. Cas réel : incident avant OOMKilled

### Contexte

- **Application** : `fastapi-demo` (API Python/FastAPI)
- **Namespace** : `app-demo`
- **Pod** : `fastapi-demo-7b9c8d6f4-x2k9p`
- **Limite mémoire** : 256 Mi (définie dans les ressources K8s)
- **Limite CPU** : 500m

### Timeline de l'incident (T-15 min → OOMKilled)

```
T-15:00  CPU: 12%, RAM: 110 Mi  → Normal
T-14:00  CPU: 18%, RAM: 128 Mi  → Normal
T-13:00  CPU: 25%, RAM: 148 Mi  → Normal — pic de trafic
T-12:00  CPU: 38%, RAM: 172 Mi  → Surveillance
T-11:00  CPU: 52%, RAM: 196 Mi  → ⚠️ WARN — fuite mémoire détectée
T-10:00  CPU: 65%, RAM: 215 Mi  → ⚠️ WARN
T-09:00  CPU: 74%, RAM: 233 Mi  → 🔴 ALERT — CPU > 70%
T-08:00  CPU: 81%, RAM: 244 Mi  → 🔴 ALERT — CPU > 80% — Grafana déclenche l'alerte
T-07:00  CPU: 83%, RAM: 250 Mi  → 🔴 CRITICAL
T-06:00  CPU: 85%, RAM: 254 Mi  → 🔴 CRITICAL — RAM à 99% de la limite
T-05:00  CPU: 88%, RAM: 256 Mi  → 🔥 OOM imminent
T-04:00  CPU: 90%, RAM: 256 Mi  → 🔥 Kernel OOM killer activé
T-03:00  Kernel envoie SIGKILL (exit code 137)
T-00:00  Container redémarré — OOMKilled confirmé
```

### Cause racine

La route `/api/data` charge l'intégralité d'un dataset en mémoire à chaque requête sans pagination ni garbage collection. Avec une charge concurrente de 50 req/s, la mémoire grossit linéairement jusqu'à dépasser la limite de 256 Mi.

---

## 2. Logs (100 lignes réalistes)

Logs formatés comme Loki les retourne depuis un pod Kubernetes.

```
2024-05-04T14:00:01Z [INFO]  fastapi-demo  Pod démarré — PID 1 — version 2.3.1
2024-05-04T14:00:02Z [INFO]  fastapi-demo  Connexion MongoDB OK — pool=5
2024-05-04T14:00:03Z [INFO]  fastapi-demo  Serveur Uvicorn prêt sur 0.0.0.0:8080
2024-05-04T14:00:10Z [INFO]  fastapi-demo  GET /health 200 — 3ms
2024-05-04T14:00:15Z [INFO]  fastapi-demo  GET /api/data 200 — 45ms — records=1500
2024-05-04T14:00:20Z [INFO]  fastapi-demo  GET /api/data 200 — 48ms — records=1500
2024-05-04T14:00:30Z [INFO]  fastapi-demo  GET /api/data 200 — 52ms — records=1500
2024-05-04T14:00:45Z [INFO]  fastapi-demo  POST /api/process 200 — 120ms
2024-05-04T14:01:00Z [INFO]  fastapi-demo  GET /api/data 200 — 55ms — records=1500
2024-05-04T14:01:15Z [INFO]  fastapi-demo  GET /api/data 200 — 58ms — records=1500
2024-05-04T14:01:30Z [INFO]  fastapi-demo  GET /api/data 200 — 61ms — records=1500
2024-05-04T14:01:45Z [INFO]  fastapi-demo  POST /api/process 200 — 135ms
2024-05-04T14:02:00Z [INFO]  fastapi-demo  GET /api/data 200 — 65ms — records=1500
2024-05-04T14:02:00Z [INFO]  fastapi-demo  Worker 1 — mémoire utilisée: 148 Mi
2024-05-04T14:02:15Z [INFO]  fastapi-demo  GET /api/data 200 — 68ms — records=1500
2024-05-04T14:02:30Z [INFO]  fastapi-demo  GET /api/data 200 — 72ms — records=1500
2024-05-04T14:02:45Z [INFO]  fastapi-demo  POST /api/process 200 — 142ms
2024-05-04T14:03:00Z [INFO]  fastapi-demo  GET /api/data 200 — 78ms — records=1500
2024-05-04T14:03:15Z [INFO]  fastapi-demo  GET /api/data 200 — 83ms — records=1500
2024-05-04T14:03:30Z [INFO]  fastapi-demo  Background job démarré — batch_id=abc123
2024-05-04T14:03:45Z [INFO]  fastapi-demo  GET /api/data 200 — 89ms — records=1500
2024-05-04T14:04:00Z [INFO]  fastapi-demo  Worker 2 — mémoire utilisée: 172 Mi
2024-05-04T14:04:00Z [WARN]  fastapi-demo  Latence en hausse — p95=210ms — seuil=200ms
2024-05-04T14:04:15Z [INFO]  fastapi-demo  GET /api/data 200 — 95ms — records=1500
2024-05-04T14:04:30Z [INFO]  fastapi-demo  POST /api/process 200 — 165ms
2024-05-04T14:04:45Z [INFO]  fastapi-demo  GET /api/data 200 — 101ms — records=1500
2024-05-04T14:05:00Z [WARN]  fastapi-demo  Mémoire heap en hausse — 190 Mi / 256 Mi (74%)
2024-05-04T14:05:00Z [WARN]  fastapi-demo  GC pause détectée — 45ms
2024-05-04T14:05:15Z [INFO]  fastapi-demo  GET /api/data 200 — 112ms — records=1500
2024-05-04T14:05:30Z [WARN]  fastapi-demo  Thread pool saturé — workers_busy=8/8
2024-05-04T14:05:45Z [INFO]  fastapi-demo  GET /api/data 200 — 125ms — records=1500
2024-05-04T14:06:00Z [WARN]  fastapi-demo  CPU throttling détecté — quota_exceeded=true
2024-05-04T14:06:00Z [INFO]  fastapi-demo  Worker 1 — mémoire utilisée: 210 Mi
2024-05-04T14:06:15Z [WARN]  fastapi-demo  Connexions DB en attente — queue=12
2024-05-04T14:06:30Z [INFO]  fastapi-demo  GET /api/data 200 — 145ms — records=1500
2024-05-04T14:06:45Z [WARN]  fastapi-demo  Request queue growing — pending=25
2024-05-04T14:07:00Z [WARN]  fastapi-demo  Mémoire heap — 225 Mi / 256 Mi (88%)
2024-05-04T14:07:00Z [WARN]  fastapi-demo  Cache L2 inefficace — hit_rate=12%
2024-05-04T14:07:15Z [WARN]  fastapi-demo  GET /api/data 200 — 178ms — records=1500 (SLOW)
2024-05-04T14:07:30Z [WARN]  fastapi-demo  Allocation mémoire lente — alloc_time=23ms
2024-05-04T14:07:45Z [ERROR] fastapi-demo  Connexion DB timeout — retry 1/3
2024-05-04T14:08:00Z [INFO]  fastapi-demo  Connexion DB rétablie
2024-05-04T14:08:00Z [WARN]  fastapi-demo  Mémoire heap — 237 Mi / 256 Mi (93%)
2024-05-04T14:08:15Z [WARN]  fastapi-demo  CPU throttled — cpu_cfs_throttled_periods=342
2024-05-04T14:08:30Z [ERROR] fastapi-demo  Memory allocation failure pour batch job — MemoryError
2024-05-04T14:08:30Z [ERROR] fastapi-demo  Traceback (most recent call last):
2024-05-04T14:08:30Z [ERROR] fastapi-demo    File "/app/jobs/batch.py", line 87, in run_batch
2024-05-04T14:08:30Z [ERROR] fastapi-demo      data = load_full_dataset()  # charge 1.5 Go de données
2024-05-04T14:08:30Z [ERROR] fastapi-demo  MemoryError: unable to allocate 512 MiB
2024-05-04T14:08:45Z [WARN]  fastapi-demo  GET /api/data 503 — timeout après 5000ms
2024-05-04T14:09:00Z [ERROR] fastapi-demo  Mémoire critique — 249 Mi / 256 Mi (97%)
2024-05-04T14:09:00Z [ERROR] fastapi-demo  OOM warning from kernel cgroup
2024-05-04T14:09:05Z [ERROR] fastapi-demo  Impossible d'allouer mémoire pour nouvelle requête
2024-05-04T14:09:10Z [ERROR] fastapi-demo  GET /api/data 500 — MemoryError
2024-05-04T14:09:15Z [ERROR] fastapi-demo  GET /api/data 500 — MemoryError
2024-05-04T14:09:20Z [ERROR] fastapi-demo  POST /api/process 500 — MemoryError
2024-05-04T14:09:25Z [ERROR] fastapi-demo  Worker 1 killed — signal=SIGKILL (OOM)
2024-05-04T14:09:25Z [ERROR] fastapi-demo  Worker 2 killed — signal=SIGKILL (OOM)
2024-05-04T14:09:25Z [FATAL] fastapi-demo  Kernel OOM killer — victim: fastapi-demo (PID 1)
2024-05-04T14:09:25Z [FATAL] fastapi-demo  Container killed — exit code 137 (OOMKilled)
2024-05-04T14:09:30Z [INFO]  fastapi-demo  --- REDÉMARRAGE DU POD ---
2024-05-04T14:09:31Z [INFO]  fastapi-demo  Pod démarré — PID 1 — version 2.3.1 — restart_count=1
2024-05-04T14:09:32Z [INFO]  fastapi-demo  Connexion MongoDB OK
2024-05-04T14:09:33Z [INFO]  fastapi-demo  Serveur Uvicorn prêt sur 0.0.0.0:8080
2024-05-04T14:09:40Z [INFO]  fastapi-demo  GET /health 200 — 2ms
2024-05-04T14:09:45Z [INFO]  fastapi-demo  GET /api/data 200 — 43ms — records=1500
2024-05-04T14:09:50Z [INFO]  fastapi-demo  GET /api/data 200 — 46ms — records=1500
2024-05-04T14:10:00Z [INFO]  fastapi-demo  GET /api/data 200 — 49ms — records=1500
2024-05-04T14:10:00Z [INFO]  fastapi-demo  Worker 1 — mémoire utilisée: 115 Mi (post-restart)
2024-05-04T14:10:15Z [INFO]  fastapi-demo  GET /api/data 200 — 51ms — records=1500
2024-05-04T14:10:30Z [WARN]  fastapi-demo  Même pattern de fuite mémoire — 128 Mi
2024-05-04T14:10:45Z [INFO]  fastapi-demo  GET /api/data 200 — 55ms — records=1500
2024-05-04T14:11:00Z [WARN]  fastapi-demo  Mémoire — 145 Mi / 256 Mi (57%) — en hausse
2024-05-04T14:11:15Z [INFO]  fastapi-demo  GET /api/data 200 — 58ms — records=1500
2024-05-04T14:11:30Z [WARN]  fastapi-demo  Pattern identique au cycle précédent — probable fuite
2024-05-04T14:11:45Z [INFO]  fastapi-demo  GET /api/data 200 — 62ms — records=1500
2024-05-04T14:12:00Z [WARN]  fastapi-demo  Mémoire — 168 Mi / 256 Mi (66%) — en hausse continue
2024-05-04T14:12:15Z [INFO]  fastapi-demo  GET /api/data 200 — 68ms — records=1500
2024-05-04T14:12:30Z [INFO]  fastapi-demo  GET /api/data 200 — 73ms — records=1500
2024-05-04T14:12:45Z [WARN]  fastapi-demo  Background job démarré — risque de répétition OOM
2024-05-04T14:13:00Z [WARN]  fastapi-demo  Mémoire — 189 Mi / 256 Mi (74%) — toujours en hausse
2024-05-04T14:13:15Z [WARN]  fastapi-demo  GC pause — 38ms
2024-05-04T14:13:30Z [WARN]  fastapi-demo  Latence p95 = 190ms (seuil: 200ms)
2024-05-04T14:13:45Z [WARN]  fastapi-demo  Mémoire — 205 Mi / 256 Mi (80%)
2024-05-04T14:14:00Z [ERROR] fastapi-demo  Mémoire critique — 230 Mi / 256 Mi (90%)
2024-05-04T14:14:00Z [ERROR] fastapi-demo  Répétition cycle OOM — intervention requise
2024-05-04T14:14:10Z [ERROR] fastapi-demo  GET /api/data 500 — MemoryError
2024-05-04T14:14:15Z [ERROR] fastapi-demo  POST /api/process 500 — MemoryError
2024-05-04T14:14:20Z [FATAL] fastapi-demo  OOMKilled — restart_count=2
2024-05-04T14:14:25Z [INFO]  fastapi-demo  --- REDÉMARRAGE DU POD (2ème) ---
2024-05-04T14:14:26Z [INFO]  fastapi-demo  Pod démarré — PID 1 — version 2.3.1 — restart_count=2
2024-05-04T14:14:27Z [WARN]  fastapi-demo  CrashLoopBackoff imminent si aucune action
2024-05-04T14:14:28Z [INFO]  fastapi-demo  Connexion MongoDB OK
2024-05-04T14:14:29Z [INFO]  fastapi-demo  Serveur Uvicorn prêt
2024-05-04T14:14:30Z [INFO]  fastapi-demo  GET /health 200 — 2ms
```

---

## 3. Métriques Prometheus (100 points)

Métriques au format `{nom} {valeur} {timestamp_unix}` (simulées comme `node_exporter` / `kube-state-metrics` les exposent).

```
# Timestamp de départ : 2024-05-04 14:00:00 UTC = 1714824000

container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 115343360 1714824000
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 119537664 1714824060
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 123731968 1714824120
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 130023424 1714824180
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 137363456 1714824240
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 147849216 1714824300
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 158334976 1714824360
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 168820736 1714824420
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 180355072 1714824480
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 190840832 1714824540
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 202375168 1714824600
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 213909504 1714824660
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 225443840 1714824720
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 236978176 1714824780
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 248512512 1714824840
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 257949696 1714824900
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 114688000 1714824960
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 120586240 1714825020
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 130023424 1714825080
container_memory_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 142606336 1714825140

container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 12.4 1714824000
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 18.1 1714824060
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 25.6 1714824120
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 33.2 1714824180
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 41.8 1714824240
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 52.3 1714824300
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 64.9 1714824360
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 74.1 1714824420
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 81.5 1714824480
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 83.2 1714824540
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 85.0 1714824600
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 87.8 1714824660
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 89.1 1714824720
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 90.4 1714824780
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 90.9 1714824840
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 14.2 1714824960
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 20.5 1714825020
container_cpu_usage_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 31.1 1714825080

container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 0.0   1714824000
container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 0.0   1714824060
container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 0.2   1714824300
container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 1.8   1714824360
container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 5.4   1714824420
container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 12.3  1714824480
container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 18.7  1714824540
container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 25.1  1714824600
container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 34.6  1714824660
container_cpu_cfs_throttled_seconds_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 42.3  1714824720

kube_pod_container_status_restarts_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 0 1714824000
kube_pod_container_status_restarts_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 0 1714824300
kube_pod_container_status_restarts_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 0 1714824600
kube_pod_container_status_restarts_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 1 1714824960
kube_pod_container_status_restarts_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",namespace="app-demo"} 2 1714825140

kube_pod_container_status_reason{pod="fastapi-demo-7b9c8d6f4-x2k9p",reason="OOMKilled"} 1 1714824900
kube_pod_container_status_reason{pod="fastapi-demo-7b9c8d6f4-x2k9p",reason="OOMKilled"} 1 1714825140

container_memory_max_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 115343360 1714824000
container_memory_max_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 148897792 1714824300
container_memory_max_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 200278016 1714824480
container_memory_max_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 248512512 1714824840
container_memory_max_usage_bytes{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 257949696 1714824900

container_memory_cache{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 10485760 1714824000
container_memory_cache{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 15728640 1714824300
container_memory_cache{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 26214400 1714824600
container_memory_cache{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 41943040 1714824840

http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.05"} 1250 1714824000
http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.1"}  1420 1714824000
http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.2"}  1497 1714824000
http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.5"}  1500 1714824000

http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.05"} 890  1714824480
http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.1"}  1020 1714824480
http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.2"}  1280 1714824480
http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.5"}  1490 1714824480

http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.05"} 120  1714824840
http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.1"}  230  1714824840
http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.2"}  390  1714824840
http_request_duration_seconds_bucket{pod="fastapi-demo-7b9c8d6f4-x2k9p",le="0.5"}  580  1714824840

http_requests_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",status="200"} 14850 1714824000
http_requests_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",status="200"} 16230 1714824300
http_requests_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",status="200"} 17100 1714824600
http_requests_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",status="500"} 0     1714824600
http_requests_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",status="500"} 45    1714824840
http_requests_total{pod="fastapi-demo-7b9c8d6f4-x2k9p",status="503"} 12    1714824840

container_network_receive_bytes_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"}  52428800  1714824000
container_network_receive_bytes_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"}  78643200  1714824300
container_network_receive_bytes_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"}  104857600 1714824600
container_network_transmit_bytes_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 31457280  1714824000
container_network_transmit_bytes_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 46137344  1714824300
container_network_transmit_bytes_total{pod="fastapi-demo-7b9c8d6f4-x2k9p"} 61865984  1714824600

kube_pod_container_resource_limits{pod="fastapi-demo-7b9c8d6f4-x2k9p",resource="memory"} 268435456 1714824000
kube_pod_container_resource_limits{pod="fastapi-demo-7b9c8d6f4-x2k9p",resource="cpu"}    0.5       1714824000
kube_pod_container_resource_requests{pod="fastapi-demo-7b9c8d6f4-x2k9p",resource="memory"} 134217728 1714824000
kube_pod_container_resource_requests{pod="fastapi-demo-7b9c8d6f4-x2k9p",resource="cpu"}    0.25      1714824000
```

---

## 4. Processus complet de traitement

```
┌──────────────────────────────────────────────────────────────────────┐
│  INCIDENT : CPU > 80% + Memory Leak → OOMKilled                     │
└──────────────────────────────────────────────────────────────────────┘

① COLLECTE (automatique, ~5s)
   Grafana détecte CPU > 80% via règle d'alerte Prometheus
   → Envoie webhook POST /api/v1/webhook au backend FastAPI
   → Backend répond 202 Accepted immédiatement (Grafana a un timeout court)
   → Background task démarre

② ENRICHISSEMENT (en arrière-plan, ~10s)
   ├─ Loki : collecte les 50 derniers logs du pod
   ├─ Prometheus : collecte mémoire, CPU, restarts, throttling
   └─ MongoDB : recherche un incident similaire passé (Auto-Learning)

③ ANALYSE IA (~5-15s selon Azure OpenAI)
   ├─ Prompt enrichi : logs + métriques + contexte Auto-Learning
   ├─ Modèle : GPT-35-turbo / GPT-4
   └─ Réponse : JSON structuré (cause, solution, sévérité, actions, prévention)

④ STOCKAGE INITIAL
   ├─ Incident sauvegardé en MongoDB avec status="pending_approval"
   ├─ Diagnostic IA initial stocké
   └─ validated_solution = null (pas encore approuvé)

⑤ NOTIFICATION EMAIL
   ├─ Email envoyé via MailHog (local) ou Outlook (prod)
   ├─ Contient : pod, namespace, cause, solution proposée
   └─ N'est pas envoyé si diagnostic = api_error ou parse_error

⑥ TABLEAU DE BORD SRE (Streamlit)
   ├─ SRE voit l'incident sur le dashboard
   ├─ Clique pour voir les détails
   ├─ Consulte les logs, métriques, solution IA
   └─ Peut poser des questions via le chatbot

⑦ APPROBATION (action SRE)
   ├─ SRE clique "Approuver" (tab Approuver)
   ├─ Backend appelle l'IA pour FORMATER la solution finale (markdown structuré)
   ├─ Solution finale sauvegardée dans validated_solution
   ├─ Statut → "résolu"
   └─ Solution affichée immédiatement dans le frontend

⑧ AUTO-LEARNING (pour les futures alertes)
   └─ Prochaine fois que la même alerte arrive :
      → find_past_incident() trouve cet incident résolu
      → La validated_solution est injectée dans le Mega-Prompt
      → L'IA tient compte de la solution éprouvée
```

---

## 5. Guide A–Z : tester localement en Docker

### Prérequis

```bash
# Vérifier les outils installés
docker --version         # >= 24.0
docker compose version   # >= 2.20
python --version         # >= 3.11
curl --version

# Ports qui doivent être libres :
# 8000 (FastAPI), 8080 (frontend), 8025 (MailHog), 8081 (Mongo Express)
# 3000 (Grafana), 3100 (Loki), 9090 (Prometheus), 27017 (MongoDB), 1025 (SMTP)
```

---

### Étape 1 — Cloner et configurer

```bash
git clone https://github.com/ABDELHAKIMJNANE/Assistant-SRE.git
cd Assistant-SRE/backend

# Créer le fichier .env depuis l'exemple
cp .env.example .env

# Éditer .env — remplir OBLIGATOIREMENT :
nano .env
# OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
# OPENAI_API_KEY=sk-...
# OPENAI_DEPLOYMENT=gpt-35-turbo
# SRE_EMAIL=votre@email.com   ← email destinataire (simulé par MailHog)
# Les autres valeurs par défaut fonctionnent pour le dev local
```

---

### Étape 2 — Lancer tous les services Docker

```bash
# Depuis backend/
docker compose up -d

# Vérifier que tous les services sont UP
docker compose ps

# Sortie attendue :
# NAME              STATUS          PORTS
# api               running         0.0.0.0:8000->8000/tcp
# mongodb           running         0.0.0.0:27017->27017/tcp
# mongo-express     running         0.0.0.0:8081->8081/tcp
# loki              running         0.0.0.0:3100->3100/tcp
# prometheus        running         0.0.0.0:9090->9090/tcp
# log-generator     running
# mailhog           running         0.0.0.0:1025->1025/tcp, 0.0.0.0:8025->8025/tcp
```

---

### Étape 3 — Vérifier que le backend répond

```bash
# Health check
curl -s http://localhost:8000/health | python3 -m json.tool
# Attendu : {"status": "ok", ...}

# Documentation interactive
open http://localhost:8000/docs
```

---

### Étape 4 — Injecter des logs réalistes dans Loki

```bash
# Injecter les 20 premières lignes de logs de l'incident CPU/RAM
LOKI_URL="http://localhost:3100"
POD="fastapi-demo-7b9c8d6f4-x2k9p"
NS="app-demo"

# Fonction d'injection d'un log
push_log() {
  local ts=$1 level=$2 msg=$3
  curl -s -X POST "${LOKI_URL}/loki/api/v1/push" \
    -H "Content-Type: application/json" \
    -d "{
      \"streams\": [{
        \"stream\": {\"pod\": \"${POD}\", \"namespace\": \"${NS}\", \"level\": \"${level}\"},
        \"values\": [[\"${ts}\", \"${msg}\"]]
      }]
    }"
}

# Injecter des logs simulant la progression de l'incident
BASE=$(date -u +%s%N)
push_log "$BASE"                  "info"  "Pod démarré — mémoire: 115 Mi"
push_log "$((BASE+60000000000))"  "info"  "GET /api/data 200 — 45ms"
push_log "$((BASE+300000000000))" "warn"  "Mémoire: 190 Mi / 256 Mi (74%)"
push_log "$((BASE+480000000000))" "warn"  "CPU throttling détecté"
push_log "$((BASE+510000000000))" "error" "Memory allocation failure — MemoryError"
push_log "$((BASE+540000000000))" "error" "GET /api/data 500 — MemoryError"
push_log "$((BASE+565000000000))" "fatal" "Container killed — exit code 137 (OOMKilled)"

echo "✅ Logs injectés dans Loki"

# Vérifier que Loki a reçu les logs
curl -s "${LOKI_URL}/loki/api/v1/query?query={pod=\"${POD}\"}&limit=5" | python3 -m json.tool
```

---

### Étape 5 — Envoyer un webhook Grafana simulé

```bash
# Simuler une alerte Grafana "HighCPUAndMemory" comme si Grafana l'envoyait
curl -s -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "HighCPUAndMemoryUsage",
    "state": "firing",
    "message": "CPU > 80% et mémoire à 97% de la limite — risque OOMKilled imminent",
    "labels": {
      "pod": "fastapi-demo-7b9c8d6f4-x2k9p",
      "namespace": "app-demo",
      "container": "fastapi-demo",
      "node": "aks-nodepool1-12345678-vmss000001",
      "severity": "critical"
    },
    "annotations": {
      "summary": "Pod en cours de saturation mémoire"
    }
  }' | python3 -m json.tool

# Réponse attendue :
# {"message": "Alerte reçue, traitement en cours"}

# Attendre 15-20 secondes que le traitement IA se termine
sleep 20
echo "⏳ Attente traitement IA terminé..."
```

---

### Étape 6 — Vérifier l'incident créé

```bash
# Lister les incidents
curl -s http://localhost:8000/api/v1/incidents | python3 -m json.tool

# Récupérer l'ID du premier incident
INCIDENT_ID=$(curl -s http://localhost:8000/api/v1/incidents | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data[0]['_id']) if data else print('AUCUN INCIDENT')
")
echo "Incident ID: $INCIDENT_ID"

# Voir le détail de l'incident
curl -s http://localhost:8000/api/v1/incidents/$INCIDENT_ID | python3 -m json.tool
```

---

### Étape 7 — Vérifier l'email dans MailHog

```bash
# Ouvrir l'interface web MailHog
open http://localhost:8025
# → Vous devriez voir l'email "🔴 Alerte HighCPUAndMemoryUsage"

# Ou via l'API MailHog
curl -s http://localhost:8025/api/v2/messages | python3 -m json.tool
```

---

### Étape 8 — Tester le chatbot SRE

```bash
# Poser une question sur l'incident
curl -s -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d "{
    \"incident_id\": \"$INCIDENT_ID\",
    \"question\": \"Quelles commandes kubectl puis-je utiliser pour augmenter la limite mémoire sans redémarrer ?\"
  }" | python3 -m json.tool
```

---

### Étape 9 — Approuver la solution (flux complet)

```bash
# Approuver l'incident → l'IA formate la solution finale
curl -s -X POST http://localhost:8000/api/v1/incidents/$INCIDENT_ID/approve \
  -H "Content-Type: application/json" | python3 -m json.tool

# Réponse attendue :
# {
#   "message": "Incident approuvé et résolu",
#   "incident_id": "...",
#   "formatted_solution": "### ✅ Résolution ...\n...",
#   "already_resolved": false
# }

# Vérifier que l'incident est maintenant résolu
curl -s http://localhost:8000/api/v1/incidents/$INCIDENT_ID | python3 -c "
import sys, json
data = json.load(sys.stdin)
print('Status:', data.get('status'))
print('Solution validée:', str(data.get('validated_solution', ''))[:200])
"
```

---

### Étape 10 — Tester le frontend Streamlit

```bash
# Dans un autre terminal, depuis le dossier frontend/
cd ../frontend
pip install -r requirements.txt
streamlit run app.py
# → Ouvre http://localhost:8501

# OU avec Docker (si Dockerfile frontend existe) :
# docker build -t sre-frontend .
# docker run -p 8501:8501 --env-file .env sre-frontend
```

**Dans l'interface Streamlit :**
1. Dashboard → Vérifiez que l'incident apparaît
2. Cliquez sur l'incident dans la sidebar
3. Onglet **Vue d'ensemble** → Vérifiez les logs/métriques collectés
4. Onglet **Solution IA** → Vérifiez le diagnostic (cause, solution, actions)
5. Onglet **Chat** → Posez une question
6. Onglet **Approuver** → Cliquez "Approuver la solution"

---

### Étape 11 — Vérifier les données dans MongoDB

```bash
# Interface web Mongo Express
open http://localhost:8081
# → Base: aiops_db → Collection: incidents

# Ou via CLI
docker exec -it $(docker compose ps -q mongodb) mongosh aiops_db --eval "
  db.incidents.find({}, {
    alert_name: 1, status: 1, 
    'diagnostic.severite': 1,
    validated_solution: 1
  }).toArray()
"
```

---

### Étape 12 — Tester l'Auto-Learning

```bash
# Envoyer une DEUXIÈME alerte du même type (après avoir résolu la première)
curl -s -X POST http://localhost:8000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "alert_name": "HighCPUAndMemoryUsage",
    "state": "firing",
    "message": "CPU > 80% et mémoire à 95% — récurrence",
    "labels": {
      "pod": "fastapi-demo-7b9c8d6f4-abc99",
      "namespace": "app-demo",
      "container": "fastapi-demo"
    }
  }' | python3 -m json.tool

sleep 20

# Le nouvel incident devrait avoir "past_solution_used" non-null
NEW_ID=$(curl -s http://localhost:8000/api/v1/incidents | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data[0]['_id']) if data else print('')
")
curl -s http://localhost:8000/api/v1/incidents/$NEW_ID | python3 -c "
import sys, json
data = json.load(sys.stdin)
past = data.get('past_solution_used')
print('✅ Auto-Learning actif:', bool(past))
print('Solution passée utilisée:', str(past)[:150] if past else 'Non')
"
```

---

### Résumé des URLs locales

| Service | URL | Description |
|---------|-----|-------------|
| Backend FastAPI | http://localhost:8000 | API principale |
| FastAPI Docs | http://localhost:8000/docs | Swagger UI interactif |
| Streamlit Frontend | http://localhost:8501 | Interface SRE |
| MailHog | http://localhost:8025 | Emails reçus |
| Mongo Express | http://localhost:8081 | Base de données |
| Grafana | http://localhost:3000 | Dashboard (admin/admin) |
| Prometheus | http://localhost:9090 | Métriques brutes |
| Loki | http://localhost:3100 | Logs bruts |

---

### Configuration Grafana pour déclencher une vraie alerte webhook

```
1. Aller sur http://localhost:3000 (admin / admin)

2. Ajouter datasource Prometheus :
   Configuration → Data Sources → Add → Prometheus
   URL: http://prometheus:9090
   Save & Test

3. Ajouter datasource Loki :
   Configuration → Data Sources → Add → Loki
   URL: http://loki:3100
   Save & Test

4. Créer une Alert Rule :
   Alerting → Alert Rules → New Alert Rule
   Query: container_memory_usage_bytes{namespace="app-demo"} > 200000000
   Condition: IS ABOVE 200000000
   Evaluation: Every 1m, For 0m
   
5. Créer un Contact Point :
   Alerting → Contact Points → New Contact Point
   Type: Webhook
   URL: http://api:8000/api/v1/webhook
   HTTP Method: POST
   Test → vérifier que le backend reçoit l'alerte

6. Créer une Notification Policy :
   Alerting → Notification Policies → Edit default
   Contact Point: votre webhook
   Save
```

---

### Dépannage rapide

```bash
# Voir les logs du backend en temps réel
docker compose logs -f api

# Redémarrer un service
docker compose restart api

# Tout arrêter et nettoyer
docker compose down -v

# Vérifier qu'un port est libre
lsof -i :8000

# Tester la connexion Loki manuellement
curl -s http://localhost:3100/loki/api/v1/labels | python3 -m json.tool

# Tester Prometheus
curl -s "http://localhost:9090/api/v1/query?query=up" | python3 -m json.tool
```
