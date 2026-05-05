# CODE_VERIFICATION_PLAN.md — Analyse Critique du Backend Assistant-SRE

> Analyse point par point de chaque grande fonctionnalité du plan produit validé.  
> Base de code : `backend/` — FastAPI + Motor + Azure OpenAI + Loki + Prometheus  
> Tests : 64 tests, tous verts. Commande : `cd backend && python -m pytest tests/ -v`

---

## Table des Matières

1. [Pipeline Webhook / Réception Alertes Grafana](#1-pipeline-webhook--réception-alertes-grafana)
2. [Collecte Logs — LokiClient](#2-collecte-logs--lokiclient)
3. [Collecte Métriques — PrometheusClient](#3-collecte-métriques--prometheusclient)
4. [Auto-Learning — Recherche Incident Passé](#4-auto-learning--recherche-incident-passé)
5. [Sanitizer — Nettoyage Données Sensibles](#5-sanitizer--nettoyage-données-sensibles)
6. [LLM Engine — Mega-Prompt Azure OpenAI](#6-llm-engine--mega-prompt-azure-openai)
7. [Persistence — MongoDB / Cosmos DB](#7-persistence--mongodb--cosmos-db)
8. [Notification Email Outlook SMTP](#8-notification-email-outlook-smtp)
9. [Endpoint GET /incidents — Liste Paginée](#9-endpoint-get-incidents--liste-paginée)
10. [Endpoint GET /incidents/{id} — Détail Incident](#10-endpoint-get-incidentsid--détail-incident)
11. [Endpoint PUT /incidents/{id}/resolve — Validation SRE](#11-endpoint-put-incidentsidresolve--validation-sre)
12. [Endpoint POST /chat — Chatbot SRE Contextuel](#12-endpoint-post-chat--chatbot-sre-contextuel)
13. [Health Checks — Probes K8s](#13-health-checks--probes-k8s)
14. [Rate Limiting](#14-rate-limiting)
15. [Gestion Centralisée des Erreurs](#15-gestion-centralisée-des-erreurs)
16. [Logging Structuré JSON](#16-logging-structuré-json)
17. [Modèles Pydantic — Validation des Entrées](#17-modèles-pydantic--validation-des-entrées)
18. [Couverture de Tests — Bilan Global](#18-couverture-de-tests--bilan-global)

---

## 1. Pipeline Webhook / Réception Alertes Grafana

**Statut : ✅ Présent et fonctionnel**  
**Fichier :** `backend/app/api/v1/webhook.py`

### Ce qui est implémenté

Le endpoint `POST /api/v1/webhook` reçoit le JSON de Grafana, répond `202 Accepted` immédiatement, et délègue la totalité du traitement à une `BackgroundTask` (`process_alert`). Ce pattern est correct et critique : Grafana a un timeout court (~5 s) et l'analyse IA prend 10–20 s.

La pipeline `process_alert` enchaîne dans l'ordre :
1. Collecte logs Loki
2. Collecte métriques Prometheus
3. Recherche Auto-Learning dans MongoDB
4. Sanitize + troncature des logs
5. Appel Azure OpenAI (Mega-Prompt)
6. Insert incident dans MongoDB
7. Envoi email Outlook

### Points à optimiser ou compléter

**① `datetime.utcnow()` déprécié** (ligne 69 de `webhook.py`)  
Python 3.12 émet un `DeprecationWarning` qui pollue les logs et cassera en Python 3.14+.

```python
# ACTUEL — À supprimer
"created_at": datetime.utcnow(),

# CORRECT
from datetime import datetime, timezone
"created_at": datetime.now(timezone.utc),
```

Même problème dans `database.py` ligne 118 et dans `models/incident.py` (`Field(default_factory=datetime.utcnow)`).

**② Absence de gestion d'erreur dans `process_alert`**  
Si Loki est DOWN ou si OpenAI échoue, la `BackgroundTask` lève une exception non catchée. Rien n'est sauvegardé en base, rien n'est notifié. Le SRE ne voit aucune trace de l'alerte reçue.

```python
# CORRECTIF RECOMMANDÉ — Wrapper try/except global dans process_alert
async def process_alert(payload: AlertPayload) -> None:
    try:
        # ... pipeline complète ...
    except Exception as exc:
        logger.error(f"❌ Pipeline échouée pour {payload.alert_name}: {exc}", exc_info=True)
        # Sauvegarder l'incident en état d'erreur pour ne pas perdre la trace
        await database.insert_incident({
            "alert_name": payload.alert_name,
            "state": payload.state,
            "labels": payload.labels,
            "message": payload.message,
            "diagnostic": {"cause_racine": f"Erreur pipeline: {exc}", "solution": "Analyse manuelle requise", "severite": "haute", "categorie": "pipeline_error"},
            "status": "erreur",
            "created_at": datetime.now(timezone.utc),
        })
```

**③ `metrics_collected` toujours à 0 dans le doc inséré**  
`len(metrics)` retourne le nombre de **clés** du dict (toujours 3), pas le nombre de métriques réellement récupérées. Ce champ n'est pas significatif. Documenter ou le remplacer par un booléen `metrics_available`.

**④ Tests de la pipeline en background non couverts**  
Les tests valident la réponse 202 mais ne vérifient pas que `process_alert` est bien appelé avec le bon payload. Ajouter :

```python
def test_webhook_triggers_background_task(client, sample_webhook_payload):
    with patch("app.api.v1.webhook.process_alert") as mock_process:
        mock_process.return_value = None
        response = client.post("/api/v1/webhook", json=sample_webhook_payload)
        assert response.status_code == 202
        # BackgroundTasks ne s'exécute pas en TestClient sync, mais on peut vérifier l'enqueue
```

---

## 2. Collecte Logs — LokiClient

**Statut : ✅ Présent — Robustesse partielle**  
**Fichier :** `backend/app/services/loki_client.py`

### Ce qui est implémenté

Requête `GET /loki/api/v1/query_range` via `httpx.AsyncClient` avec timeout 10 s. Parse la réponse JSON Loki et extrait les lignes de logs. En cas d'erreur HTTP, retourne une liste vide (fail-safe).

### Points à optimiser ou compléter

**① Pas de retry**  
Une seule tentative. Si Loki répond avec un 503 transitoire (redémarrage du pod Loki), les logs sont perdus. Ajouter un retry avec backoff exponentiel :

```python
import tenacity

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=4),
    retry=tenacity.retry_if_exception_type(httpx.HTTPError),
)
async def _query_loki(url: str, params: dict) -> dict: ...
```

**② `since` non compatible avec l'API Loki query_range**  
Le paramètre `since` n'est pas un paramètre natif de `/loki/api/v1/query_range`. L'API Loki attend `start` (timestamp nanoseconde ou RFC3339) et `end`. Le paramètre `since` est silencieusement ignoré, ce qui peut retourner des logs hors de la fenêtre attendue.

```python
# CORRECTIF
from datetime import datetime, timezone, timedelta

now = datetime.now(timezone.utc)
start = (now - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

params = {
    "query": query,
    "limit": limit,
    "start": start,
    "end": end,
}
```

**③ Logs extraits sans timestamp**  
Chaque log Loki a un timestamp (`_timestamp`) et une ligne. Actuellement seule la ligne est conservée. Inclure le timestamp dans la ligne aide l'IA à comprendre la timeline des événements.

```python
for _timestamp, line in stream.get("values", []):
    # Convertir timestamp nanoseconds → datetime lisible
    ts = datetime.fromtimestamp(int(_timestamp) / 1e9, tz=timezone.utc)
    logs.append(f"[{ts.strftime('%H:%M:%S')}] {line}")
```

**④ Tests Loki insuffisants**  
`tests/test_services/test_loki_client.py` ne teste pas le parsing des données Loki (structure `data.result[].values[]`). Ajouter un test avec un payload Loki réaliste mocké.

---

## 3. Collecte Métriques — PrometheusClient

**Statut : ✅ Présent — Robustesse partielle**  
**Fichier :** `backend/app/services/prometheus_client.py`

### Ce qui est implémenté

3 requêtes PromQL séquentielles vers `GET /api/v1/query` pour `memory_usage_bytes`, `cpu_usage_seconds`, `restart_count`. Timeout 10 s. En cas d'erreur, retourne `{memory: 0, cpu: 0, restarts: 0}`.

### Points à optimiser ou compléter

**① Requêtes séquentielles au lieu de parallèles**  
3 requêtes HTTP séquentielles = 3 × latence réseau. Avec un timeout de 10 s par requête, ça peut bloquer la pipeline jusqu'à 30 s. Utiliser `asyncio.gather` :

```python
import asyncio

async def get_metrics(pod: str, namespace: str = "app-demo") -> dict[str, float]:
    base_url = f"{settings.prometheus_url}/api/v1/query"
    queries = {
        "memory_usage_bytes": f'container_memory_usage_bytes{{pod="{pod}",namespace="{namespace}"}}',
        "cpu_usage_seconds": f'container_cpu_usage_seconds_total{{pod="{pod}",namespace="{namespace}"}}',
        "restart_count": f'kube_pod_container_status_restarts_total{{pod="{pod}",namespace="{namespace}"}}',
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        tasks = [client.get(base_url, params={"query": q}) for q in queries.values()]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    metrics = {}
    for metric_name, response in zip(queries.keys(), responses):
        if isinstance(response, Exception):
            metrics[metric_name] = 0.0
            continue
        results = response.json().get("data", {}).get("result", [])
        metrics[metric_name] = float(results[0]["value"][1]) if results else 0.0
    return metrics
```

**② `format_metrics_for_prompt` jamais appelé**  
La fonction existe mais `webhook.py` reconstruit manuellement le texte des métriques dans `llm_engine.py`. Cette duplication est un bug potentiel si le format change. Centraliser :

```python
# Dans webhook.py, remplacer la logique dans llm_engine.analyze
# par un appel à prometheus_client.format_metrics_for_prompt(metrics)
```

**③ Aucun test pour `PrometheusClient`**  
Il n'existe aucun fichier `test_services/test_prometheus_client.py`. À créer, similaire à `test_loki_client.py`.

---

## 4. Auto-Learning — Recherche Incident Passé

**Statut : ✅ Présent et fonctionnel**  
**Fichier :** `backend/app/services/database.py` → `find_past_incident()`  
**Utilisé dans :** `backend/app/api/v1/webhook.py`

### Ce qui est implémenté

Recherche dans MongoDB le dernier incident RÉSOLU (`status: "résolu"`) pour la même `alert_name`, trié par `created_at DESC`. La `validated_solution` est extraite et injectée dans le Mega-Prompt d'OpenAI. Coût : 0 token supplémentaire si solution trouvée, le LLM recycle la solution validée.

### Points à optimiser ou compléter

**① Pas d'index MongoDB sur `(alert_name, status)`**  
La requête `find_one({alert_name, status: "résolu"})` fait un full collection scan si aucun index n'existe. En production avec des milliers d'incidents, cela devient lent.

```javascript
// À ajouter dans un script de migration ou au démarrage :
db.incidents.createIndex({ alert_name: 1, status: 1, created_at: -1 })
```

Ou dans `database.py` au `connect_db()` :

```python
async def connect_db() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.mongodb_url)
    await _client.admin.command("ping")
    db = get_db()
    await db["incidents"].create_index(
        [("alert_name", 1), ("status", 1), ("created_at", -1)]
    )
    logger.info("✅ Index MongoDB créé")
```

**② Match strict sur `alert_name` uniquement**  
Deux alertes `OOMKilled` sur des pods différents (`fastapi-demo` vs `redis-cache`) partagent la même `alert_name`. L'auto-learning pourrait proposer une solution inapplicable. Considérer un match également sur le namespace ou le container.

**③ Pas de test d'intégration pour ce mécanisme end-to-end**  
Le test `test_find_past_incident_not_found` vérifie seulement le cas vide. Ajouter un test qui vérifie que la solution passée est bien injectée dans le Mega-Prompt :

```python
async def test_past_solution_injected_in_prompt(mock_llm_call):
    # Mock find_past_incident → retourne un incident résolu avec validated_solution
    # Vérifier que user_prompt contient "## Historique Auto-Learning"
```

---

## 5. Sanitizer — Nettoyage Données Sensibles

**Statut : ✅ Présent, bien testé**  
**Fichier :** `backend/app/services/sanitizer.py`  
**Tests :** `tests/test_sanitizer.py` + `tests/test_services/test_sanitizer.py` (duplication)

### Ce qui est implémenté

5 patterns regex pour masquer : mots de passe, Bearer JWT, adresses IP, connection strings, clés Azure (base64 longues). Troncature aux N dernières lignes.

### Points à optimiser ou compléter

**① Double couverture de tests — duplication à nettoyer**  
`tests/test_sanitizer.py` et `tests/test_services/test_sanitizer.py` testent les mêmes cas. 8 tests dupliqués. Supprimer `tests/test_sanitizer.py` (racine) et conserver `tests/test_services/test_sanitizer.py`.

**② Pattern base64 trop agressif**  
Le pattern `[A-Za-z0-9+/]{40,}={0,2}` masque n'importe quelle chaîne alphanumérique de 40+ caractères. Il va masquer des UUIDs, des noms de pods longs, des noms de fichiers, des hash Git — ce qui peut rendre les logs illisibles pour l'IA.

```python
# PROBLÈME — trop large :
(re.compile(r'[A-Za-z0-9+/]{40,}={0,2}'), '***REDACTED_KEY***'),

# MIEUX — cibler les patterns Azure Key Vault / Storage Account connus :
(re.compile(r'(?:AccountKey|SharedAccessSignature|sv=)[A-Za-z0-9+/%]{40,}'), '***REDACTED_AZURE_KEY***'),
```

**③ Pas de test pour le pattern base64**  
Ajouter un test qui vérifie que le masquage base64 ne touche pas les noms de pods normaux :

```python
def test_base64_does_not_mask_pod_names():
    raw = "pod=fastapi-demo-7b9c8d6f4-x2k9p namespace=app-demo"
    cleaned = sanitize_text(raw)
    assert "fastapi-demo" in cleaned  # Ne doit pas être masqué
```

**④ Logs masqués avant l'IA mais pas avant MongoDB**  
Les logs bruts (non sanitisés) sont stockés dans `logs_collected` (juste le count), mais si on enregistrait les logs eux-mêmes, ils iraient en clair en base. C'est correct pour l'instant mais à documenter explicitement.

---

## 6. LLM Engine — Mega-Prompt Azure OpenAI

**Statut : ✅ Présent et fonctionnel**  
**Fichier :** `backend/app/services/llm_engine.py`

### Ce qui est implémenté

- Client `AsyncAzureOpenAI` avec initialisation lazy (singleton)
- `SYSTEM_PROMPT` qui force une réponse JSON structurée (cause_racine, solution, severite, categorie)
- Mega-Prompt construit avec alert_name, message, labels, logs, métriques, et optionnellement la solution auto-learning
- Gestion du cas où l'IA répond avec un bloc ```json ... ```
- Fallback JSON en cas d'erreur de parsing ou d'erreur API
- Fonction séparée `chat_about_incident()` pour le chatbot contextuel

### Points à optimiser ou compléter

**① Reconstruction des métriques dans `llm_engine.analyze` — couplage fort**  
`llm_engine.py` reconstruit lui-même la ligne texte des métriques (mem_mi, cpu, restarts). C'est une logique qui appartient à `prometheus_client.format_metrics_for_prompt()`. Si on ajoute une nouvelle métrique, il faut modifier deux fichiers.

```python
# ACTUEL dans llm_engine.py — à supprimer
mem_mi = metrics.get("memory_usage_bytes", 0) / (1024 * 1024)
metrics_text = (
    f"- Mémoire : {mem_mi:.1f} Mi\n"
    ...
)

# REMPLACER PAR
from app.services.prometheus_client import format_metrics_for_prompt
metrics_text = format_metrics_for_prompt(metrics)
```

**② `max_tokens=800` peut être insuffisant**  
Un diagnostic complet avec cause racine détaillée + solution multi-étapes peut dépasser 800 tokens. Si la réponse est tronquée, le JSON est invalide → `JSONDecodeError` → fallback générique. Passer à `max_tokens=1200` ou détecter la troncature via `finish_reason`.

```python
response = await client.chat.completions.create(...)
if response.choices[0].finish_reason == "length":
    logger.warning("⚠️ Réponse OpenAI tronquée (max_tokens atteint)")
```

**③ Pas de validation du JSON retourné**  
L'IA peut retourner un JSON valide mais avec des champs manquants ou des valeurs hors nomenclature (ex: `severite: "critical"` au lieu de `"critique"`). Ajouter une validation Pydantic :

```python
from app.models.incident import Diagnostic

try:
    diagnostic_raw = json.loads(raw_content)
    diagnostic = Diagnostic(**diagnostic_raw).model_dump()
except (json.JSONDecodeError, ValidationError) as e:
    logger.error(f"❌ Diagnostic invalide : {e}")
    diagnostic = {"cause_racine": raw_content[:500], ...}
```

**④ Client OpenAI jamais réinitialisé**  
Si les credentials Azure OpenAI sont rotés (renouvellement de clé), le singleton `_openai_client` garde l'ancienne clé. Pas de mécanisme de refresh. En production, cela provoque des erreurs 401 sans redémarrage du pod.

**⑤ Tests couvrent les cas d'erreur mais pas le contenu du prompt**  
Les tests vérifient que `analyze()` retourne un dict, mais pas que le prompt contient bien les logs, métriques et la solution auto-learning. Ajouter :

```python
async def test_past_solution_in_prompt(mock_openai_client):
    # Capturer le prompt envoyé à OpenAI
    # Vérifier "## Historique Auto-Learning" dans le user_prompt
```

---

## 7. Persistence — MongoDB / Cosmos DB

**Statut : ✅ Présent et fonctionnel**  
**Fichier :** `backend/app/services/database.py`

### Ce qui est implémenté

- Connexion async via `motor` (`AsyncIOMotorClient`)
- Ping au démarrage (lifespan)
- CRUD complet : `find_past_incident`, `insert_incident`, `get_incident`, `list_incidents`, `update_incident_status`
- Conversion `ObjectId → str` pour la sérialisation JSON
- Tri par `created_at DESC` pour la liste

### Points à optimiser ou compléter

**① `get_incident` peut lever une `bson.errors.InvalidId` non catchée**  
Si `incident_id` n'est pas un ObjectId valide (ex: `"abc"` ou une chaîne vide), `ObjectId(incident_id)` lève une `bson.errors.InvalidId`. Cette exception n'est pas catchée et remonte comme erreur 500 au lieu de 400/422.

```python
from bson.errors import InvalidId

async def get_incident(incident_id: str) -> Optional[dict[str, Any]]:
    try:
        oid = ObjectId(incident_id)
    except InvalidId:
        logger.warning(f"ID invalide : {incident_id}")
        return None  # Le endpoint retournera 404
    db = get_db()
    doc = await db["incidents"].find_one({"_id": oid})
    if doc:
        doc["_id"] = str(doc["_id"])
    return doc
```

**② `update_incident_status` non protégé contre la concurrence**  
Deux appels simultanés à `/resolve` sur le même incident peuvent passer le check `status != "résolu"` en même temps. Utiliser une mise à jour conditionnelle :

```python
result = await db["incidents"].update_one(
    {"_id": ObjectId(incident_id), "status": {"$ne": "résolu"}},  # Condition atomique
    {"$set": update_fields},
)
if result.matched_count == 0:
    raise DatabaseException("Incident déjà résolu ou inexistant")
```

**③ `datetime.utcnow()` dans `database.py` et `models/incident.py`**  
Même problème de dépréciation que dans `webhook.py`. Utiliser `datetime.now(timezone.utc)`.

**④ Pas d'index sur `created_at`**  
Le tri `sort("created_at", -1)` dans `list_incidents()` sera lent sans index. Créer l'index au démarrage (voir point §4).

**⑤ Tests `test_database.py` incomplets**  
Manquent : `test_get_incident`, `test_update_incident_status`, `test_find_past_incident_found`. Seuls 3 cas sont testés sur 5 fonctions.

---

## 8. Notification Email Outlook SMTP

**Statut : ✅ Présent — Non critique au bon fonctionnement**  
**Fichier :** `backend/app/services/notification.py`

### Ce qui est implémenté

Email HTML via `aiosmtplib` + STARTTLS sur `smtp.office365.com:587`. Corps HTML riche avec tableau (pod, namespace, sévérité, catégorie, cause racine, solution). Guard clause si SMTP non configuré (log warning et skip silencieux).

### Points à optimiser ou compléter

**① Pas de retry SMTP**  
Un seul essai. Si le serveur SMTP refuse la connexion (rate limit, timeout), l'email est perdu sans trace.

**② Email envoyé même si le diagnostic est une erreur de pipeline**  
Si `diagnostic = {"categorie": "api_error"}`, l'email est envoyé avec `"Analyse manuelle requise"` comme solution. Ce n'est pas utile. Conditionner l'envoi à `diagnostic.get("categorie") not in {"api_error", "parse_error"}`.

**③ Zéro test pour le service de notification**  
`notification.py` n'est testé nulle part. Le mock dans `conftest.py` existe (`mock_notification`) mais aucun test ne l'utilise pour valider le contenu de l'email. Ajouter au minimum un test de smoke :

```python
async def test_send_alert_email_skipped_when_not_configured():
    with patch("app.services.notification.settings") as mock_settings:
        mock_settings.smtp_user = ""
        mock_settings.smtp_password = ""
        # Doit retourner sans erreur et sans appel SMTP
        await notification.send_alert_email("OOMKilled", "pod", "ns", {})
```

---

## 9. Endpoint GET /incidents — Liste Paginée

**Statut : ✅ Présent et fonctionnel**  
**Fichier :** `backend/app/api/v1/incidents.py`

### Ce qui est implémenté

`GET /api/v1/incidents?skip=0&limit=20`. Paramètres validés (`ge=0`, `ge=1 le=100`). Tri `created_at DESC`. Retourne une liste de dicts bruts.

### Points à optimiser ou compléter

**① Pas de `response_model` Pydantic**  
Le endpoint retourne `list[dict[str, Any]]` sans validation de sortie. Un champ inattendu en base (ou un `datetime` non sérialisable) peut provoquer une erreur 500 silencieuse.

```python
from app.models.incident import IncidentResponse

@router.get("/incidents", response_model=list[IncidentResponse], tags=["Incidents"])
async def list_incidents(...) -> list[IncidentResponse]:
```

**② `created_at` datetime non sérialisable**  
MongoDB stocke `created_at` comme `datetime`. FastAPI ne sait pas le sérialiser automatiquement si le `response_model` n'est pas Pydantic. Avec `response_model=list[IncidentResponse]`, Pydantic gère la conversion.

**③ Pas de filtre par statut**  
Le SRE devrait pouvoir filtrer `?status=ouvert` ou `?status=résolu`. Ajouter le Query param optionnel.

---

## 10. Endpoint GET /incidents/{id} — Détail Incident

**Statut : ✅ Présent et fonctionnel**  
**Fichier :** `backend/app/api/v1/incidents.py`

### Ce qui est implémenté

Récupère l'incident par ID, puis re-fetch en parallèle les logs Loki et métriques Prometheus du pod concerné. Retourne tout dans un seul dict enrichi.

### Points à optimiser ou compléter

**① `ObjectId` invalide → 500 au lieu de 422**  
Même problème que `database.get_incident()` : un ID malformé lève `bson.errors.InvalidId`. Le endpoint ne repackage pas cette exception en 422.

**② Logs et métriques récupérés séquentiellement**  
`loki_client.get_logs()` puis `prometheus_client.get_metrics()` sont appelés séquentiellement. Utiliser `asyncio.gather` pour les paralléliser :

```python
import asyncio
logs, metrics = await asyncio.gather(
    loki_client.get_logs(pod=pod, namespace=namespace, limit=50),
    prometheus_client.get_metrics(pod=pod, namespace=namespace),
)
```

**③ Pas de `response_model`** (même remarque qu'au §9)

---

## 11. Endpoint PUT /incidents/{id}/resolve — Validation SRE

**Statut : ✅ Présent et fonctionnel**  
**Fichier :** `backend/app/api/v1/resolve.py`

### Ce qui est implémenté

Récupère l'incident, vérifie qu'il n'est pas déjà résolu, appelle `database.update_incident_status()` avec la solution validée. Retourne un dict de confirmation.

### Points à optimiser ou compléter

**① Race condition (déjà mentionné en §7)**  
Deux SRE qui cliquent en même temps → double résolution possible.

**② `validated_solution` tronquée dans le log**  
`body.validated_solution[:80]` peut crasher si la solution est vide (même si `ValidateRequest` l'empêche via `Field(...)`). À sécuriser.

**③ Pas de test pour `resolve` dans `test_api/`**  
`test_api/` n'a pas de `test_resolve.py`. Le endpoint PUT n'est pas testé. À créer :

```python
class TestResolveEndpoint:
    def test_resolve_existing_incident(self, client, sample_incident):
        sample_incident["status"] = "ouvert"
        with patch("app.api.v1.resolve.database") as mock_db:
            mock_db.get_incident = AsyncMock(return_value=sample_incident)
            mock_db.update_incident_status = AsyncMock()
            response = client.put(
                f"/api/v1/incidents/{sample_incident['_id']}/resolve",
                json={"validated_solution": "kubectl rollout restart deployment/fastapi-demo"}
            )
        assert response.status_code == 200
        assert "résolu" in response.json()["message"]

    def test_resolve_already_resolved(self, client, sample_incident):
        sample_incident["status"] = "résolu"
        with patch("app.api.v1.resolve.database") as mock_db:
            mock_db.get_incident = AsyncMock(return_value=sample_incident)
            response = client.put(
                f"/api/v1/incidents/{sample_incident['_id']}/resolve",
                json={"validated_solution": "irrelevant"}
            )
        assert response.status_code == 400

    def test_resolve_nonexistent(self, client):
        with patch("app.api.v1.resolve.database") as mock_db:
            mock_db.get_incident = AsyncMock(return_value=None)
            response = client.put(
                "/api/v1/incidents/507f1f77bcf86cd799439011/resolve",
                json={"validated_solution": "fix"}
            )
        assert response.status_code == 404
```

---

## 12. Endpoint POST /chat — Chatbot SRE Contextuel

**Statut : ✅ Présent et fonctionnel**  
**Fichier :** `backend/app/api/v1/chat.py`

### Ce qui est implémenté

Récupère le contexte complet de l'incident (alert_name, message, diagnostic, status), construit un prompt contextuel, appelle Azure OpenAI avec `temperature=0.4`, retourne la réponse en texte libre.

### Points à optimiser ou compléter

**① Pas de limite sur `question`**  
Un utilisateur peut envoyer une question de 10 000 caractères. Le `ChatRequest` ne limite pas la longueur. Ajouter `Field(..., max_length=2000)` dans le modèle.

**② Historique des échanges non conservé**  
Chaque question repart de zéro (pas d'historique de conversation). Pour un vrai chatbot contextuel, les échanges précédents devraient être passés dans les `messages`. C'est une limitation majeure de l'expérience utilisateur.

**③ Erreur OpenAI retourne une string d'erreur, pas un HTTP 503**  
Si Azure OpenAI est indisponible, `chat_about_incident()` retourne `"Erreur lors de la communication avec l'IA : ..."` avec un HTTP 200. Le client Streamlit ne peut pas détecter l'erreur. Lever une exception à la place :

```python
except Exception as e:
    logger.error(f"❌ Erreur chat OpenAI : {e}")
    raise LLMException(f"Service IA indisponible : {str(e)}")
```

---

## 13. Health Checks — Probes K8s

**Statut : ✅ Présent et complet**  
**Fichiers :** `backend/app/main.py` (GET /healthz) + `backend/app/api/v1/health.py`

### Ce qui est implémenté

| Endpoint | Probe K8s | Vérifie |
|---|---|---|
| `GET /healthz` | Liveness | App en vie (toujours 200) |
| `GET /api/v1/health/live` | Liveness | App en vie + nom du service |
| `GET /api/v1/health/ready` | Readiness | MongoDB ping |
| `GET /api/v1/health/startup` | Startup | Version de l'app |

La readiness probe retourne 503 si MongoDB n'est pas joignable. Exempt du rate limiting.

### Points à optimiser ou compléter

**① `/healthz` et `/api/v1/health/live` font la même chose**  
Deux liveness probes distinctes. Aucun impact fonctionnel mais confusion potentielle. Documenter que `/healthz` est l'alias K8s standard et `/api/v1/health/live` est pour la cohérence de l'API.

**② `/health/ready` ne vérifie pas Loki/Prometheus**  
En AKS, si Loki ou Prometheus sont down, le pod est quand même marqué "ready" et reçoit du trafic. Les alertes Grafana déclencheront `process_alert`, qui collectera 0 logs / 0 métriques, et le diagnostic IA sera de moins bonne qualité. Ajouter des checks optionnels (soft checks) pour les services observabilité.

**③ Test de `/health/ready` absent dans `test_health.py`**  
`test_api/test_health.py` ne teste pas `/api/v1/health/ready` (le cas MongoDB OK ou KO). Ajouter :

```python
def test_readiness_mongodb_ok(self, client):
    response = client.get("/api/v1/health/ready")
    # Le mock du client fixture a déjà mocké MongoDB → doit retourner 200
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
```

---

## 14. Rate Limiting

**Statut : ✅ Présent**  
**Fichier :** `backend/app/dependencies/rate_limit.py`

### Ce qui est implémenté

Sliding window in-memory par IP client. 100 requêtes / 60 secondes par défaut (configurable via `.env`). Exempt pour les endpoints de santé. Retourne HTTP 429 avec `Retry-After` header.

### Points à optimiser ou compléter

**① In-memory = ne scale pas**  
Si le backend est déployé avec plusieurs replicas (AKS HPA), chaque pod a son propre compteur. Un client peut envoyer 100 req/min × N pods sans être bloqué. En production, utiliser Redis comme store partagé.

**② Pas de test du rate limiter**  
Aucun test ne vérifie que la 101ème requête reçoit un 429. Ajouter :

```python
def test_rate_limit_exceeded(client):
    settings.rate_limit_requests = 3
    for _ in range(3):
        client.get("/api/v1/health/live")
    response = client.get("/api/v1/health/live")
    # Note: health/live est exempt → tester sur /webhook
```

---

## 15. Gestion Centralisée des Erreurs

**Statut : ✅ Présent**  
**Fichier :** `backend/app/core/exceptions.py` + `backend/app/main.py`

### Ce qui est implémenté

Hiérarchie d'exceptions custom (`AIOpsException`, `DatabaseException`, `LLMException`, `NotFoundException`, `ValidationException`, `RateLimitException`). Deux `exception_handler` dans `main.py` pour `AIOpsException` et `RateLimitException`. Réponse structurée via `ErrorResponse` Pydantic.

### Points à optimiser ou compléter

**① Les exceptions custom ne sont pas utilisées dans les services**  
`database.py`, `loki_client.py`, `prometheus_client.py` et `llm_engine.py` catchent les erreurs et retournent des valeurs fallback sans lever d'exception. Les handlers dans `main.py` ne servent donc jamais. Utiliser les exceptions dans les services pour que les handlers s'activent réellement.

**② Handler pour `RequestValidationError` manquant**  
FastAPI gère automatiquement les erreurs Pydantic (422) avec son propre format. Le format de l'`ErrorResponse` custom n'est pas appliqué aux erreurs de validation. Ajouter :

```python
from fastapi.exceptions import RequestValidationError

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error="Validation error",
            details=[ErrorDetail(field=str(e["loc"]), message=e["msg"]) for e in exc.errors()],
            status_code=422,
        ).model_dump(),
    )
```

---

## 16. Logging Structuré JSON

**Statut : ✅ Présent**  
**Fichier :** `backend/app/core/logging.py`

### Ce qui est implémenté

`python-json-logger` avec format `asctime + name + levelname + message`. Configuré au démarrage via `lifespan`. Niveau de log configurable via `LOG_LEVEL` dans `.env`.

### Points à optimiser ou compléter

**① Pas de `correlation_id` dans les logs**  
En production, tracer une requête de bout en bout (webhook → pipeline → OpenAI → MongoDB) nécessite un ID de corrélation commun. Sans lui, les logs de la `BackgroundTask` ne peuvent pas être liés à la requête d'origine.

```python
import uuid
# Dans rate_limit_middleware ou un middleware dédié :
correlation_id = str(uuid.uuid4())
request.state.correlation_id = correlation_id
```

**② `extra={"environment": settings.environment}` dans un seul log**  
Le champ `environment` n'est pas présent dans tous les logs structurés. Pour que Loki puisse filtrer sur `{environment="production"}`, il faut l'inclure dans tous les messages ou dans le formatter.

---

## 17. Modèles Pydantic — Validation des Entrées

**Statut : ✅ Présent et bien structuré**  
**Fichiers :** `backend/app/models/`

### Ce qui est implémenté

- `AlertPayload` : `alert_name` (required), `state`, `labels`, `message`, `dashboard_url`
- `IncidentCreate`, `IncidentResponse`, `Diagnostic`
- `ValidateRequest` : `validated_solution` (required, exemples inclus)
- `ChatRequest`, `ChatResponse`
- `ErrorResponse`, `ErrorDetail`, `HTTPErrorResponse`

### Points à optimiser ou compléter

**① `IncidentResponse` a `id: str = Field(alias="_id")` mais les endpoints ne l'utilisent pas**  
Les endpoints `incidents.py` retournent des `dict` bruts, pas des `IncidentResponse`. Le modèle de réponse est défini mais pas appliqué. Ajouter `response_model=IncidentResponse` ou `response_model=list[IncidentResponse]` sur les endpoints GET.

**② `ValidateRequest.validated_solution` accepte une chaîne vide**  
Malgré `Field(...)` (required), une string vide `""` passe la validation Pydantic. Ajouter un validator :

```python
from pydantic import field_validator

@field_validator("validated_solution")
@classmethod
def solution_not_empty(cls, v: str) -> str:
    if not v.strip():
        raise ValueError("La solution validée ne peut pas être vide")
    return v
```

Les tests `TestCustomValidators::test_empty_string_fails` passent mais testent un autre validator dans `test_models/test_validators.py`.

---

## 18. Couverture de Tests — Bilan Global

**Tests actuels : 64 tests, 100% verts**  
**Commande :** `cd backend && python -m pytest tests/ -v`

### Matrice de couverture

| Composant | Tests existants | Couverture estimée | Manquant |
|---|---|---|---|
| `webhook.py` endpoint | ✅ 8 tests | ~85% | Pipeline background non validée |
| `incidents.py` endpoints | ✅ 6 tests | ~80% | Filtre statut, ObjectId invalide |
| `chat.py` endpoint | ✅ 3 tests | ~80% | Erreur OpenAI → 503 |
| `resolve.py` endpoint | ❌ 0 tests | 0% | Tout manque |
| `health.py` endpoints | ✅ 3 tests | ~70% | /health/ready non testé |
| `sanitizer.py` | ✅ 12 tests (dupliqués) | ~95% | Pattern base64 agressif non testé |
| `database.py` | ✅ 3 tests | ~40% | get_incident, update, find_found |
| `llm_engine.py` | ✅ 4 tests | ~70% | Validation JSON sortie, troncature |
| `loki_client.py` | ✅ 3 tests | ~60% | Parsing timestamps, retry |
| `prometheus_client.py` | ❌ 0 tests | 0% | Tout manque |
| `notification.py` | ❌ 0 tests | 0% | Tout manque |
| `rate_limit.py` | ❌ 0 tests | 0% | Tout manque |
| Modèles Pydantic | ✅ 11 tests | ~80% | validated_solution vide |

### Priorités de correction (ordre d'impact)

1. **Critique** — Ajouter try/except global dans `process_alert` (perte silencieuse d'alertes)
2. **Critique** — Corriger le paramètre `since` dans `loki_client.py` (logs potentiellement vides)
3. **Haute** — Créer `test_api/test_resolve.py` (endpoint PUT non testé)
4. **Haute** — Créer `tests/test_services/test_prometheus_client.py` (0 test)
5. **Haute** — Protéger `database.get_incident` contre `bson.errors.InvalidId`
6. **Haute** — Paralléliser les requêtes Prometheus avec `asyncio.gather`
7. **Moyenne** — Remplacer `datetime.utcnow()` → `datetime.now(timezone.utc)` partout
8. **Moyenne** — Ajouter `response_model` Pydantic sur les endpoints GET incidents
9. **Moyenne** — Restreindre le pattern regex base64 dans le sanitizer
10. **Basse** — Créer les index MongoDB au démarrage
11. **Basse** — Supprimer la duplication de tests sanitizer (`tests/test_sanitizer.py`)
12. **Basse** — Ajouter `correlation_id` dans les logs structurés
