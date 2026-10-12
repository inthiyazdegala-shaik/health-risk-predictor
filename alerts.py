"""Emergency alert delivery.

Channels (each is used only if configured through environment variables):
  * Email  - SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, ALERT_FROM
  * SMS    - TWILIO_SID, TWILIO_TOKEN, TWILIO_FROM  (Twilio REST API)

If nothing is configured the alert runs in SIMULATED mode: it is printed to
the console and saved in the database, so the feature can be demoed offline.
"""
import os
import smtplib
from email.message import EmailMessage

import requests


def _send_email(to_addr, subject, body):
    host = os.getenv("SMTP_HOST")
    if not (host and to_addr):
        return None
    msg = EmailMessage()
    msg["From"] = os.getenv("ALERT_FROM", os.getenv("SMTP_USER", "alerts@localhost"))
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=15) as s:
            s.starttls()
            if os.getenv("SMTP_USER"):
                s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
            s.send_message(msg)
        return "sent"
    except Exception as exc:  # network/auth errors must not crash the app
        return f"failed: {exc}"


def _send_sms(to_phone, body):
    sid, token, sender = (os.getenv("TWILIO_SID"), os.getenv("TWILIO_TOKEN"),
                          os.getenv("TWILIO_FROM"))
    if not (sid and token and sender and to_phone):
        return None
    try:
        r = requests.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data={"To": to_phone, "From": sender, "Body": body},
            auth=(sid, token), timeout=15)
        return "sent" if r.status_code in (200, 201) else f"failed: HTTP {r.status_code}"
    except Exception as exc:
        return f"failed: {exc}"


def build_message(patient_name, level, reasons, vitals):
    lines = [
        f"Health screening notification for {patient_name or 'a user'}",
        "An automated screening check met a configured high-priority rule.",
        "This is not a diagnosis or confirmation of a medical emergency.",
    ]
    lines.append("Please check in with them and encourage appropriate medical advice.")
    lines.append("If they report severe symptoms, contact local emergency services.")
    return "\n".join(lines)


def dispatch(contact, message):
    """Send via every configured channel. Returns {channel: status}."""
    results = {}
    email_status = _send_email(contact.get("email"), "Emergency health alert", message)
    sms_status = _send_sms(contact.get("phone"), message)
    if email_status:
        results["email"] = email_status
    if sms_status:
        results["sms"] = sms_status
    if not results:
        print("\n===== SIMULATED EMERGENCY ALERT =====")
        print(f"To: {contact.get('name') or 'contact'} "
              f"({contact.get('phone') or contact.get('email') or 'no contact'})")
        print(message)
        print("=====================================\n")
        results["simulated"] = "logged (configure SMTP/Twilio for real delivery)"
    return results
