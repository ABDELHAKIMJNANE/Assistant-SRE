"""
Log Generator — Simule des pods Kubernetes qui émettent des logs et des métriques.
Ce script tourne dans Docker Compose et alimente Loki + Prometheus
pour permettre de tester le backend FastAPI en local.
"""

import time
import json
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

import urllib.request

LOKI_URL = "http://loki:3100/loki/api/v1/push"

# ── Pods simulés ──
PODS = [
    {"pod": "fastapi-demo-7b9c8d6f4-x2k9p", "namespace": "app-demo", "container": "fastapi"},
    {"pod": "nginx-frontend-5d8f9a-abc12", "namespace": "app-demo", "container": "nginx"},
    {"pod": "mysql-primary-0", "namespace": "app-demo", "container": "mysql"},
]

# ── Logs réalistes ──
LOG_TEMPLATES = [
    ("error", "ERROR: Container killed - OOM - memory usage exceeded limit of {mem}Mi"),
    ("error", "ERROR: Failed to allocate {mem}Mi for request processing"),
    ("error", "ERROR: Connection refused to database on port 3306"),
    ("error", "ERROR: CrashLoopBackOff - container restarted {count} times"),
    ("warning", "WARNING: Memory usage at {pct}% - {mem}Mi/{limit}Mi allocated"),
    ("warning", "WARNING: GC pressure detected - heap size growing unbounded"),
    ("warning", "WARNING: Slow query detected - {ms}ms execution time"),
    ("warning", "WARNING: Connection pool exhausted - waiting for available connection"),
    ("info", "INFO: Incoming request POST /api/data - payload size: {size}MB"),
    ("info", "INFO: Health check passed - status: healthy"),
    ("info", "INFO: Request completed in {ms}ms - status 200"),
    ("info", "INFO: Database connection established successfully"),
]

# ── Métriques simulées (format Prometheus) ──
metrics_state = {
    "memory": 180_000_000,
    "cpu": 10.0,
    "restarts": 0,
}


def generate_log_line():
    """Générer une ligne de log aléatoire réaliste."""
    level, template = random.choice(LOG_TEMPLATES)
    line = template.format(
        mem=random.randint(128, 512),
        limit=random.choice([256, 512]),
        pct=random.randint(70, 99),
        count=random.randint(1, 10),
        ms=random.randint(50, 5000),
        size=random.randint(1, 50),
    )
    return level, line


def push_logs_to_loki():
    """Envoyer des logs simulés à Loki toutes les 5 secondes."""
    print("📝 Log Generator démarré — envoi vers Loki", flush=True)

    while True:
        for pod_info in PODS:
            level, line = generate_log_line()
            timestamp = str(int(time.time() * 1e9))

            payload = {
                "streams": [{
                    "stream": {
                        "namespace": pod_info["namespace"],
                        "pod": pod_info["pod"],
                        "container": pod_info["container"],
                        "level": level,
                    },
                    "values": [[timestamp, line]],
                }]
            }

            try:
                data = json.dumps(payload).encode("utf-8")
                req = urllib.request.Request(
                    LOKI_URL,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass  # Loki pas encore prêt, on réessaie

        # Simuler l'évolution des métriques
        metrics_state["memory"] += random.randint(-5_000_000, 15_000_000)
        metrics_state["memory"] = max(50_000_000, min(metrics_state["memory"], 500_000_000))
        metrics_state["cpu"] += random.uniform(0.1, 2.0)

        if random.random() < 0.05:  # 5% de chance de restart
            metrics_state["restarts"] += 1

        time.sleep(5)


class MetricsHandler(BaseHTTPRequestHandler):
    """Serveur HTTP qui expose des métriques au format Prometheus."""

    def do_GET(self):
        if self.path == "/metrics":
            pod = PODS[0]
            body = f"""# HELP container_memory_usage_bytes Current memory usage in bytes
# TYPE container_memory_usage_bytes gauge
container_memory_usage_bytes{{pod="{pod['pod']}",namespace="{pod['namespace']}",container="{pod['container']}"}} {metrics_state['memory']}

# HELP container_cpu_usage_seconds_total Total CPU usage
# TYPE container_cpu_usage_seconds_total counter
container_cpu_usage_seconds_total{{pod="{pod['pod']}",namespace="{pod['namespace']}",container="{pod['container']}"}} {metrics_state['cpu']:.2f}

# HELP kube_pod_container_status_restarts_total Total restarts
# TYPE kube_pod_container_status_restarts_total counter
kube_pod_container_status_restarts_total{{pod="{pod['pod']}",namespace="{pod['namespace']}",container="{pod['container']}"}} {metrics_state['restarts']}
"""
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(body.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # Silence les logs HTTP


def start_metrics_server():
    """Démarrer le serveur de métriques sur le port 8080."""
    server = HTTPServer(("0.0.0.0", 8080), MetricsHandler)
    print("📊 Metrics server démarré sur :8080/metrics", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    # Attendre que Loki soit prêt
    print("⏳ Attente de Loki...", flush=True)
    time.sleep(10)

    # Démarrer le serveur de métriques dans un thread séparé
    metrics_thread = threading.Thread(target=start_metrics_server, daemon=True)
    metrics_thread.start()

    # Démarrer l'envoi de logs (boucle infinie)
    push_logs_to_loki()
