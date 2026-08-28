"""Tests for SMTP email helpers."""

from __future__ import annotations

import pytest

from liftlogic.email_notify import SmtpConfig, load_smtp_config_from_env, send_email


def test_load_smtp_config_from_env(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "vectorvoyager111@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-pass")
    monkeypatch.setenv("EMAIL_TO", "vectorvoyager111@gmail.com")
    cfg = load_smtp_config_from_env()
    assert cfg.host == "smtp.gmail.com"
    assert cfg.port == 587
    assert cfg.username == "vectorvoyager111@gmail.com"
    assert cfg.to_addr == "vectorvoyager111@gmail.com"


def test_load_smtp_config_requires_password(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "user@gmail.com")
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    monkeypatch.setenv("EMAIL_TO", "user@gmail.com")
    with pytest.raises(ValueError, match="SMTP_PASSWORD"):
        load_smtp_config_from_env()


def test_send_email_uses_smtp(monkeypatch):
    calls: list[str] = []

    class FakeSMTP:
        def __init__(self, host, port, timeout=60):
            calls.append(f"connect:{host}:{port}")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ehlo(self):
            calls.append("ehlo")

        def starttls(self):
            calls.append("starttls")

        def login(self, user, password):
            calls.append(f"login:{user}")

        def send_message(self, message):
            calls.append(f"send:{message['To']}")

    monkeypatch.setattr("liftlogic.email_notify.smtplib.SMTP", FakeSMTP)
    cfg = SmtpConfig(
        host="smtp.gmail.com",
        port=587,
        username="vectorvoyager111@gmail.com",
        password="secret",
        from_addr="vectorvoyager111@gmail.com",
        to_addr="vectorvoyager111@gmail.com",
    )
    send_email("Subject", "Body text", config=cfg)
    assert "connect:smtp.gmail.com:587" in calls
    assert "starttls" in calls
    assert "login:vectorvoyager111@gmail.com" in calls
    assert "send:vectorvoyager111@gmail.com" in calls
