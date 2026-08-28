"""
Sends dunning emails via Resend's free tier. Falls back to logging the email
to the console if RESEND_API_KEY isn't set, so recovery_engine.py is runnable
and demoable without any email provider configured.
"""
import os
import requests

RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_ADDRESS = os.getenv("RESEND_FROM_ADDRESS", "billing@sudhar.example")


def send_dunning_email(to_email: str, subject: str, body_text: str) -> bool:
    if not RESEND_API_KEY:
        print(f"[email:offline-mode] To: {to_email} | Subject: {subject}\n{body_text}\n")
        return True

    try:
        res = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
            json={
                "from": FROM_ADDRESS,
                "to": [to_email],
                "subject": subject,
                "text": body_text,
            },
            timeout=10,
        )
        return res.status_code < 300
    except requests.RequestException as e:
        print(f"[email:error] Failed to send to {to_email}: {e}")
        return False
