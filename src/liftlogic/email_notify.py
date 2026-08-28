"""Email notifications via SMTP (Gmail app password supported)."""

from __future__ import annotations

import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage


@dataclass(frozen=True)
class SmtpConfig:
    host: str
    port: int
    username: str
    password: str
    from_addr: str
    to_addr: str
    use_tls: bool = True


def load_smtp_config_from_env() -> SmtpConfig:
    """Load SMTP settings from environment variables."""
    username = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "").strip()
    to_addr = os.environ.get("EMAIL_TO", "").strip() or username
    from_addr = os.environ.get("EMAIL_FROM", "").strip() or username
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
    port = int(os.environ.get("SMTP_PORT", "587"))

    missing = [
        name
        for name, value in [
            ("SMTP_USER", username),
            ("SMTP_PASSWORD", password),
            ("EMAIL_TO", to_addr),
        ]
        if not value
    ]
    if missing:
        raise ValueError(
            "Missing email settings: "
            + ", ".join(missing)
            + ". Set SMTP_USER, SMTP_PASSWORD, and EMAIL_TO (Gmail app password)."
        )

    return SmtpConfig(
        host=host,
        port=port,
        username=username,
        password=password,
        from_addr=from_addr,
        to_addr=to_addr,
        use_tls=True,
    )


def send_email(
    subject: str,
    body: str,
    config: SmtpConfig | None = None,
) -> None:
    """Send a plain-text email via SMTP."""
    cfg = config or load_smtp_config_from_env()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = cfg.from_addr
    message["To"] = cfg.to_addr
    message.set_content(body)

    with smtplib.SMTP(cfg.host, cfg.port, timeout=60) as smtp:
        smtp.ehlo()
        if cfg.use_tls:
            smtp.starttls()
            smtp.ehlo()
        smtp.login(cfg.username, cfg.password)
        smtp.send_message(message)
