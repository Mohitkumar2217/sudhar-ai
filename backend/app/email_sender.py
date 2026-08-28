"""
Sends dunning emails via Resend's free tier. Falls back to logging the email
to the console if RESEND_API_KEY isn't set, so recovery_engine.py is runnable
and demoable without any email provider configured.
"""
import os
import requests
from dotenv import load_dotenv
 
load_dotenv()

FROM_ADDRESS = os.getenv("RESEND_FROM_ADDRESS", "onboarding@resend.dev")


def send_dunning_email(to_email: str, subject: str, body_text: str) -> bool:
    # Read dynamically at call time and strip whitespace
    resend_api_key = (os.getenv("RESEND_API_KEY") or "").strip()

    # Fall back to offline console logging if key is missing or a placeholder
    if not resend_api_key or resend_api_key.startswith("your_") or resend_api_key == "None":
        print(f"[email:offline-mode] To: {to_email} | Subject: {subject}\n{body_text}\n")
        return True

    try:
        res = requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {resend_api_key}"},
            json={
                "from": FROM_ADDRESS,
                "to": [to_email],
                "subject": subject,
                "text": body_text,
            },
            timeout=10,
        )

        if res.status_code >= 400:
            print(f"[email:error] Resend returned {res.status_code}: {res.text}")
            return False

        return res.status_code < 300

    except requests.RequestException as e:
        print(f"[email:error] Failed to send to {to_email}: {e}")
        return False