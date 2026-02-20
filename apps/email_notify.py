"""Email notification for evaluation completion."""

#  KBDiag
#
#  Copyright (c) 2026
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

#  KBDiag
#
#
#  @author: Viet-Man Le (v.m.le@tugraz.at)

import os
import smtplib
from email.mime.text import MIMEText
from typing import Dict


def load_email_env() -> Dict[str, str]:
    """Load email config from environment (dotenv)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    return {
        "sender": os.getenv("EMAIL_SENDER", ""),
        "password": os.getenv("EMAIL_PASSWORD", ""),
        "recipient": os.getenv("EMAIL_RECIPIENT", ""),
        "smtp_host": os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
    }


def send_evaluation_email(subject: str, body: str) -> None:
    """Send email with evaluation results. Fails silently with warning."""
    env = load_email_env()
    if not env["sender"] or not env["password"] or not env["recipient"]:
        print("Warning: Email credentials not configured. Skipping.")
        return
    try:
        msg = MIMEText(body, "plain")
        msg["Subject"] = subject
        msg["From"] = env["sender"]
        msg["To"] = env["recipient"]
        with smtplib.SMTP(env["smtp_host"], env["smtp_port"]) as server:
            server.starttls()
            server.login(env["sender"], env["password"])
            server.send_message(msg)
        print(f"Email sent to {env['recipient']}")
    except Exception as e:
        print(f"Warning: Failed to send email: {e}")
