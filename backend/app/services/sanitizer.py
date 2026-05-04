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


def sanitize_text(text: str) -> str:
    """
    Nettoyer une chaîne de caractères en masquant les données sensibles.
    Utilisé avant d'envoyer les logs à Azure OpenAI.
    """
    result = text
    for pattern, replacement in PATTERNS:
        result = pattern.sub(replacement, result)
    return result


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
