"""Global constants for the AIOps backend."""

# ── API ──
API_V1_PREFIX = "/api/v1"
API_TITLE = "AIOps SRE Backend"
API_VERSION = "1.0.0"
API_DESCRIPTION = "Backend intelligent pour l'assistant SRE — Analyse d'alertes, diagnostic IA, Auto-Learning"

# ── Incidents ──
INCIDENT_STATUS_OPEN = "ouvert"
INCIDENT_STATUS_RESOLVED = "résolu"
COLLECTION_INCIDENTS = "incidents"

# ── Pagination ──
DEFAULT_PAGE_SKIP = 0
DEFAULT_PAGE_LIMIT = 20
MAX_PAGE_LIMIT = 100

# ── Sanitizer ──
DEFAULT_LOG_MAX_LINES = 50
LOKI_DEFAULT_LIMIT = 100
LOKI_DEFAULT_SINCE = "30m"

# ── LLM ──
LLM_TEMPERATURE_ANALYZE = 0.3
LLM_TEMPERATURE_CHAT = 0.4
LLM_MAX_TOKENS_ANALYZE = 800
LLM_MAX_TOKENS_CHAT = 600

# ── Rate Limiting ──
RATE_LIMIT_REQUESTS = 100
RATE_LIMIT_PERIOD_SECONDS = 60
