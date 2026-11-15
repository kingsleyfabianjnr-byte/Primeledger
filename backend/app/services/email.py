"""Email service — sends invite and password-reset emails.

Uses SendGrid if SENDGRID_API_KEY is set, otherwise logs to console (dev mode).
"""
import logging
import secrets
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def _send_via_sendgrid(to: str, subject: str, html: str) -> bool:
    """Send via SendGrid. Returns True on success."""
    try:
        from app.core.config import settings
        import urllib.request, urllib.error, json

        payload = json.dumps({
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": settings.EMAIL_FROM, "name": "PrimeLedger"},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        }).encode()

        req = urllib.request.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={
                "Authorization": f"Bearer {settings.SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception as exc:
        logger.error("SendGrid send failed: %s", exc)
        return False


def send_invite_email(to_email: str, inviter_name: str, token: str, app_url: str) -> None:
    """Send a new-user invitation email with a one-time setup link."""
    from app.core.config import settings
    setup_url = f"{app_url}/setup-account?token={token}"

    subject = "You've been invited to PrimeLedger"
    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:480px;margin:40px auto;padding:0 20px;">
      <h2 style="font-size:20px;color:#1f2328;">You're invited to PrimeLedger</h2>
      <p style="color:#57606a;">{inviter_name} has invited you to join the PrimeLedger reconciliation workspace.</p>
      <a href="{setup_url}"
         style="display:inline-block;margin:20px 0;padding:12px 24px;background:#2563eb;color:#fff;
                text-decoration:none;border-radius:8px;font-size:14px;font-weight:500;">
        Set up your account →
      </a>
      <p style="color:#57606a;font-size:13px;">This link expires in 48 hours.</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
      <p style="color:#57606a;font-size:12px;">PrimeLedger · Agentic Bank Reconciliation</p>
    </div>
    """

    if settings.SENDGRID_API_KEY:
        ok = _send_via_sendgrid(to_email, subject, html)
        if ok:
            logger.info("Invite email sent to %s", to_email)
            return

    # Dev fallback — print to console
    logger.info(
        "\n=== INVITE EMAIL (dev mode — no SENDGRID_API_KEY set) ===\n"
        "To: %s\nSubject: %s\nSetup URL: %s\n"
        "=========================================================",
        to_email, subject, setup_url
    )


def send_password_reset_email(to_email: str, token: str, app_url: str) -> None:
    """Send a password-reset email."""
    from app.core.config import settings
    reset_url = f"{app_url}/reset-password?token={token}"

    subject = "Reset your PrimeLedger password"
    html = f"""
    <div style="font-family:system-ui,sans-serif;max-width:480px;margin:40px auto;padding:0 20px;">
      <h2 style="font-size:20px;color:#1f2328;">Reset your password</h2>
      <p style="color:#57606a;">We received a request to reset your PrimeLedger password.</p>
      <a href="{reset_url}"
         style="display:inline-block;margin:20px 0;padding:12px 24px;background:#2563eb;color:#fff;
                text-decoration:none;border-radius:8px;font-size:14px;font-weight:500;">
        Reset password →
      </a>
      <p style="color:#57606a;font-size:13px;">This link expires in 1 hour. If you didn't request this, ignore this email.</p>
      <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
      <p style="color:#57606a;font-size:12px;">PrimeLedger · Agentic Bank Reconciliation</p>
    </div>
    """

    if settings.SENDGRID_API_KEY:
        ok = _send_via_sendgrid(to_email, subject, html)
        if ok:
            logger.info("Password reset email sent to %s", to_email)
            return

    logger.info(
        "\n=== PASSWORD RESET EMAIL (dev mode) ===\n"
        "To: %s\nReset URL: %s\n"
        "=======================================",
        to_email, reset_url
    )


def generate_token() -> str:
    """Generate a cryptographically secure URL-safe token."""
    return secrets.token_urlsafe(32)


def token_expiry(hours: int = 48) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)
