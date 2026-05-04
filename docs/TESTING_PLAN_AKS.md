# ☸️ AKS Testing Plan — Assistant-SRE FastAPI Backend

This guide describes how to deploy and validate the backend in Azure Kubernetes Service (AKS).

---

## 1️⃣ Deployment Manifests (K8s YAML)

### ✅ Deployment (example)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aiops-backend
  labels:
    app: aiops-backend
spec:
  replicas: 2
  selector:
    matchLabels:
      app: aiops-backend
  template:
    metadata:
      labels:
        app: aiops-backend
    spec:
      containers:
        - name: backend
          image: myacr.azurecr.io/aiops-backend:1.0.0
          ports:
            - containerPort: 8000
          envFrom:
            - secretRef:
                name: aiops-backend-secrets
          resources:
            requests:
              cpu: "200m"
              memory: "512Mi"
            limits:
              cpu: "1000m"
              memory: "1Gi"
          readinessProbe:
            httpGet:
              path: /api/v1/health/ready
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 20
          startupProbe:
            httpGet:
              path: /api/v1/health/startup
              port: 8000
            failureThreshold: 30
            periodSeconds: 5
```

### ✅ Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: aiops-backend
spec:
  selector:
    app: aiops-backend
  ports:
    - name: http
      port: 80
      targetPort: 8000
  type: ClusterIP
```

### ✅ HPA

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: aiops-backend-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: aiops-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

---

## 2️⃣ Health Check Configuration

- **Liveness**: `/healthz`
- **Readiness**: `/api/v1/health/ready`
- **Startup**: `/api/v1/health/startup`

These probes are already implemented in `app/api/v1/health.py`.

---

## 3️⃣ AKS Testing Procedure

### 1. Deploy
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/hpa.yaml
```

### 2. Smoke Test
```bash
kubectl port-forward svc/aiops-backend 8080:80
curl http://localhost:8080/healthz
```

### 3. Webhook End-to-End
```bash
curl -X POST http://localhost:8080/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d '{"alert_name":"OOMKilled","state":"alerting","labels":{"pod":"demo","namespace":"app-demo"},"message":"Container killed"}'
```

---

## 4️⃣ Monitoring & Troubleshooting

### Logs
```bash
kubectl logs deploy/aiops-backend -f
```

### Metrics
- Prometheus scrape config should include the backend service
- Loki integration should capture logs from the `aiops-backend` namespace

### Common Issues
| Issue | Cause | Solution |
|------|-------|----------|
| Pods stuck in `CrashLoopBackOff` | Missing env vars | Validate secrets + Key Vault integration |
| `Readiness probe failed` | MongoDB not reachable | Verify Private Endpoint DNS |
| `429 Too Many Requests` | Rate limiter triggered | Tune `RATE_LIMIT_*` |

---

## 5️⃣ Load Testing in AKS

Recommended tools:
- `k6` or `hey`

Example with k6:
```bash
k6 run load-test.js
```

Monitor:
- CPU / Memory
- Response latency
- MongoDB latency

---

## 6️⃣ Integration with Prometheus & Loki

### Prometheus
- Ensure `prometheus_url` resolves to the in-cluster Prometheus service
- Validate metrics queries via `services/prometheus_client.py`

### Loki
- Ensure `loki_url` points to the Loki service in AKS
- Validate log retrieval via `/api/v1/incidents/{id}`

---

## 7️⃣ Private Endpoint Testing

1. Validate DNS resolution:
```bash
nslookup cosmos-sre-xxx.mongo.cosmos.azure.com
```

2. Test connectivity from a pod:
```bash
kubectl exec -it deploy/aiops-backend -- curl -s http://loki.monitoring.svc:3100/ready
```

3. Ensure all PaaS services are reachable without public access.

---

## 8️⃣ Cost Optimization Tips

- Enable **Auto-Learning** to reduce OpenAI calls
- Enforce **rate limiting**
- Use **HPA** to scale down during low traffic
- Reduce log/metric retention for dev clusters
- Use **Cosmos DB Serverless** for low throughput

---

✅ AKS testing complete when:
- Probes pass
- Webhook workflow stores an incident
- Logs/metrics retrieval succeed
- No errors in pod logs
