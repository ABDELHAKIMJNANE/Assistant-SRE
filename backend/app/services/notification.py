"""NotificationService — Envoi d'emails via SMTP (MailHog en dev, Outlook en prod)."""

import asyncio
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)

# Catégories de diagnostic qui ne méritent pas d'email (erreurs de pipeline)
_SKIP_CATEGORIES = {"api_error", "parse_error"}
_MAX_RETRIES = 3
_RETRY_DELAY = 2  # secondes entre chaque tentative


async def send_alert_email(
    alert_name: str,
    pod: str,
    namespace: str,
    diagnostic: dict[str, Any],
) -> None:
    """
    Envoyer un email d'alerte à l'ingénieur SRE.

    En développement local : utilise MailHog (smtp_host=mailhog, port=1025, sans TLS).
    En production : utilise Outlook SMTP (smtp_host=smtp.office365.com, port=587, STARTTLS).

    Retry automatique jusqu'à 3 fois en cas d'échec SMTP.
    N'envoie pas d'email si le diagnostic est une erreur de pipeline (api_error, parse_error).

    Args:
        alert_name: Nom de l'alerte
        pod: Pod concerné
        namespace: Namespace K8s
        diagnostic: Résultat de l'analyse IA
    """
    if not settings.sre_email:
        logger.warning("⚠️ SRE_EMAIL non configuré — notification ignorée")
        return

    # Ne pas envoyer d'email si le diagnostic est une erreur interne de pipeline
    categorie = diagnostic.get("categorie", "unknown")
    if categorie in _SKIP_CATEGORIES:
        logger.warning(
            f"⚠️ Email ignoré pour diagnostic '{categorie}' "
            f"(erreur de pipeline, pas une vraie alerte)"
        )
        return

    cause = diagnostic.get("cause_racine", "Analyse en cours...")
    solution = diagnostic.get("solution", "Aucune solution automatique")
    severite = diagnostic.get("severite", "moyenne")
    severity_color = "#dc2626" if severite in ("haute", "critique") else "#d97706"

    # ── Construire l'email ──
    from_addr = settings.smtp_user or f"assistant-sre@{settings.smtp_host}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔴 Alerte {alert_name} — {namespace}/{pod}"
    msg["From"] = f"{settings.smtp_from_name} <{from_addr}>"
    msg["To"] = settings.sre_email

    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333; max-width: 700px;">
        <h2 style="color: #dc2626;">🔴 Alerte : {alert_name}</h2>
        <hr/>
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 8px; font-weight: bold; width: 160px;">📍 Pod</td>
                <td style="padding: 8px;">{pod}</td>
            </tr>
            <tr style="background-color: #f9fafb;">
                <td style="padding: 8px; font-weight: bold;">📍 Namespace</td>
                <td style="padding: 8px;">{namespace}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">⚠️ Sévérité</td>
                <td style="padding: 8px; color: {severity_color};"><strong>{severite.upper()}</strong></td>
            </tr>
            <tr style="background-color: #f9fafb;">
                <td style="padding: 8px; font-weight: bold;">🏷️ Catégorie</td>
                <td style="padding: 8px;">{categorie}</td>
            </tr>
        </table>
        <hr/>
        <h3>🔍 Cause Racine</h3>
        <p style="background-color: #fef2f2; padding: 12px; border-radius: 6px;">{cause}</p>
        <h3>💡 Solution Proposée</h3>
        <pre style="background-color: #f0fdf4; padding: 12px; border-radius: 6px;
                    font-family: monospace; white-space: pre-wrap;">{solution}</pre>
        <hr/>
        <p style="color: #6b7280; font-size: 12px;">
            Email généré automatiquement par Assistant SRE.<br/>
            Connectez-vous au dashboard pour valider la solution proposée.
        </p>
    </body>
    </html>
    """
    msg.attach(MIMEText(html_body, "html"))

    # ── Envoi avec retry ──
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            send_kwargs: dict[str, Any] = {
                "hostname": settings.smtp_host,
                "port": settings.smtp_port,
            }
            if settings.smtp_user and settings.smtp_password:
                send_kwargs["username"] = settings.smtp_user
                send_kwargs["password"] = settings.smtp_password

            if settings.smtp_use_tls:
                send_kwargs["use_tls"] = False
                send_kwargs["start_tls"] = True
            else:
                # MailHog en local : pas de TLS
                send_kwargs["use_tls"] = False
                send_kwargs["start_tls"] = False

            await aiosmtplib.send(msg, **send_kwargs)
            logger.info(
                f"📧 Email envoyé à {settings.sre_email} "
                f"pour alerte '{alert_name}' (tentative {attempt}/{_MAX_RETRIES})"
            )
            return

        except Exception as exc:
            logger.warning(
                f"⚠️ Tentative {attempt}/{_MAX_RETRIES} échouée pour envoi email "
                f"({alert_name}) : {exc}"
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_DELAY)

    logger.error(
        f"❌ Email non envoyé après {_MAX_RETRIES} tentatives pour alerte '{alert_name}'"
    )
