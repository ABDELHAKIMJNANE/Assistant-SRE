"""NotificationService — Envoi d'emails via Outlook SMTP (async)."""

import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any

import aiosmtplib

from app.config import settings

logger = logging.getLogger(__name__)


async def send_alert_email(
    alert_name: str,
    pod: str,
    namespace: str,
    diagnostic: dict[str, Any],
) -> None:
    """
    Envoyer un email d'alerte à l'ingénieur SRE via Outlook SMTP.

    Args:
        alert_name: Nom de l'alerte
        pod: Pod concerné
        namespace: Namespace K8s
        diagnostic: Résultat de l'analyse IA
    """
    if not settings.smtp_user or not settings.smtp_password:
        logger.warning("⚠️ Email non configuré (SMTP_USER/SMTP_PASSWORD vides) — notification ignorée")
        return

    cause = diagnostic.get("cause_racine", "Analyse en cours...")
    solution = diagnostic.get("solution", "Aucune solution automatique")
    severite = diagnostic.get("severite", "moyenne")
    categorie = diagnostic.get("categorie", "unknown")

    # ── Construire l'email ──
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🔴 Alerte {alert_name} — {namespace}/{pod}"
    msg["From"] = settings.smtp_user
    msg["To"] = settings.sre_email

    # Corps HTML de l'email
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #dc2626;">🔴 Alerte : {alert_name}</h2>
        <hr/>
        <table style="border-collapse: collapse; width: 100%;">
            <tr>
                <td style="padding: 8px; font-weight: bold;">📍 Pod</td>
                <td style="padding: 8px;">{pod}</td>
            </tr>
            <tr style="background-color: #f9fafb;">
                <td style="padding: 8px; font-weight: bold;">📍 Namespace</td>
                <td style="padding: 8px;">{namespace}</td>
            </tr>
            <tr>
                <td style="padding: 8px; font-weight: bold;">⚠️ Sévérité</td>
                <td style="padding: 8px; color: {'#dc2626' if severite in ['haute','critique'] else '#d97706'};">
                    <strong>{severite.upper()}</strong>
                </td>
            </tr>
            <tr style="background-color: #f9fafb;">
                <td style="padding: 8px; font-weight: bold;">🏷️ Catégorie</td>
                <td style="padding: 8px;">{categorie}</td>
            </tr>
        </table>
        <hr/>
        <h3>🔍 Cause Racine</h3>
        <p style="background-color: #fef2f2; padding: 12px; border-radius: 6px;">
            {cause}
        </p>
        <h3>💡 Solution Proposée</h3>
        <p style="background-color: #f0fdf4; padding: 12px; border-radius: 6px; font-family: monospace;">
            {solution}
        </p>
        <hr/>
        <p style="color: #6b7280; font-size: 12px;">
            Email généré automatiquement par AIOps SRE Backend.
            Consultez le dashboard pour plus de détails et valider la solution.
        </p>
    </body>
    </html>
    """

    msg.attach(MIMEText(html_body, "html"))

    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user,
            password=settings.smtp_password,
            use_tls=False,
            start_tls=True,
        )
        logger.info(f"📧 Email envoyé à {settings.sre_email} pour alerte {alert_name}")
    except Exception as e:
        logger.error(f"❌ Erreur envoi email : {e}")
