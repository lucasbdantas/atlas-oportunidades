from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def smtp_configured() -> bool:
    return bool(os.getenv("SMTP_USER") and os.getenv("SMTP_PASS"))


def send_report(subject: str, body: str, report_path: Path | None = None) -> bool:
    if not smtp_configured():
        return False

    smtp_host = os.getenv("SMTP_HOST") or "smtp.gmail.com"
    smtp_port = int(os.getenv("SMTP_PORT") or "587")
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    smtp_to = os.getenv("SMTP_TO", smtp_user)
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = smtp_from
    message["To"] = smtp_to
    message.set_content(body)

    if report_path and report_path.exists():
        message.add_attachment(
            report_path.read_text(encoding="utf-8"),
            subtype="markdown",
            filename=report_path.name,
        )

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_pass)
        smtp.send_message(message)

    return True
