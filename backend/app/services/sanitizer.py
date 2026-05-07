"""SanitizerService — Nettoyage des données sensibles avant envoi à OpenAI."""

import re
import logging

logger = logging.getLogger(__name__)

# ── Patterns de données sensibles ──
PATTERNS = [
    # Mots de passe dans les URLs ou configs
    (re.compile(r'(password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*\S+', re.IGNORECASE), r'\1=***'),
    # Connection strings MongoDB/SQL
    (re.compile(r'://[^:]+:[^@]+@'), '://***:***@'),
    # Bearer tokens JWT
    (re.compile(r'Bearer\s+eyJ[A-Za-z0-9_-]+\.?[A-Za-z0-9_-]*\.?[A-Za-z0-9_-]*'), 'Bearer ***'),
    # Adresses IP v4
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), 'X.X.X.X'),
    # Clés Azure (base64-like longues)
    (re.compile(r'[A-Za-z0-9+/]{40,}={0,2}'), '***REDACTED_KEY***'),
]

_IP_PATTERN = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER_TOKEN_PATTERN = re.compile(r"(?i)\bBearer\s+([A-Za-z0-9._-]{10,})")
_LINE_SCORE_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"(?i)\b(fatal|critical|panic|oomkilled)\b"), 4),
    (re.compile(r"(?i)\b(error|exception|traceback)\b"), 3),
    (re.compile(r"(?i)\b(timeout|refused|unavailable)\b"), 2),
    (re.compile(r"(?i)\bwarn(ing)?\b"), 1),
)


def sanitize_text(text: str) -> str:
    """
    Nettoyer une chaîne de caractères en masquant les données sensibles.
    Utilisé avant d'envoyer les logs à Azure OpenAI.
    """
    result = text
    for pattern, replacement in PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _assign_placeholder(prefix: str, value: str, mapping: dict[str, str]) -> str:
    for placeholder, original in mapping.items():
        if placeholder.startswith(prefix) and original == value:
            return placeholder
    placeholder = f"{prefix}_{sum(1 for key in mapping if key.startswith(prefix)) + 1}"
    mapping[placeholder] = value
    return placeholder


def redact_with_placeholders(text: str, mapping: dict[str, str] | None = None) -> tuple[str, dict[str, str]]:
    """
    Replace sensitive values with stable placeholders (IP_1, SECRET_1, ...).
    Returns redacted text and the updated placeholder->original map.
    """
    active_mapping = mapping or {}
    redacted = text

    def replace_ip(match: re.Match[str]) -> str:
        return _assign_placeholder("IP", match.group(0), active_mapping)

    def replace_secret_assignment(match: re.Match[str]) -> str:
        key = match.group(1)
        value = match.group(2)
        placeholder = _assign_placeholder("SECRET", value, active_mapping)
        separator = "=" if "=" in match.group(0) else ":"
        return f"{key}{separator}{placeholder}"

    def replace_bearer(match: re.Match[str]) -> str:
        token = match.group(1)
        placeholder = _assign_placeholder("SECRET", token, active_mapping)
        return f"Bearer {placeholder}"

    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(replace_secret_assignment, redacted)
    redacted = _BEARER_TOKEN_PATTERN.sub(replace_bearer, redacted)
    redacted = _IP_PATTERN.sub(replace_ip, redacted)
    return redacted, active_mapping


def _line_score(line: str) -> int:
    base_score = 0
    for pattern, score in _LINE_SCORE_PATTERNS:
        if pattern.search(line):
            base_score = max(base_score, score)
    return base_score


def filter_and_redact_evidence(
    logs: list[str],
    metrics: dict[str, float],
    max_items: int = 50,
) -> tuple[list[str], dict[str, str], list[str], dict[str, float]]:
    """
    Keep top evidence entries and redact sensitive data with placeholders.
    Returns (evidence, redaction_map, redacted_logs, redacted_metrics).
    """
    scored_logs = [
        (_line_score(line), index, line)
        for index, line in enumerate(logs)
    ]
    scored_logs.sort(key=lambda item: (item[0], item[1]), reverse=True)
    top_logs = [line for _, _, line in scored_logs[:max_items]]

    redaction_map: dict[str, str] = {}
    redacted_logs: list[str] = []
    for line in top_logs:
        redacted_line, redaction_map = redact_with_placeholders(line, redaction_map)
        redacted_logs.append(redacted_line)

    redacted_metrics: dict[str, float] = {}
    metric_lines: list[str] = []
    for name, value in metrics.items():
        safe_metric_name, redaction_map = redact_with_placeholders(name, redaction_map)
        redacted_metrics[safe_metric_name] = value
        metric_lines.append(f"METRIC {safe_metric_name}={value}")

    evidence = (redacted_logs + metric_lines)[:max_items]
    return evidence, redaction_map, redacted_logs, redacted_metrics


def sanitize_logs(logs: list[str], max_lines: int = 50) -> list[str]:
    """
    Tronquer et nettoyer une liste de logs.

    Args:
        logs: Liste brute de lignes de logs
        max_lines: Nombre maximum de lignes à garder (FinOps)

    Returns:
        Liste tronquée et nettoyée
    """
    # Tronquer aux N dernières lignes
    truncated = logs[-max_lines:]

    # Nettoyer chaque ligne
    cleaned = [sanitize_text(line) for line in truncated]

    logger.info(
        f"🔐 Sanitizer : {len(logs)} logs → {len(cleaned)} nettoyés "
        f"(tronqué à {max_lines})"
    )
    return cleaned
