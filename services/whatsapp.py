"""WhatsApp sender using Twilio API."""

from twilio.rest import Client
import config as cfg


def send_message(config_dict: dict, phone: str, message: str) -> bool:
    """Send a WhatsApp message via Twilio. Returns True on success."""

    sid = config_dict.get("twilio_sid") or cfg.TWILIO_ACCOUNT_SID
    token = config_dict.get("twilio_token") or cfg.TWILIO_AUTH_TOKEN
    from_number = config_dict.get("whatsapp_from") or cfg.TWILIO_WHATSAPP_FROM

    if not sid or not token or not from_number:
        print(f"[Flowreach] WhatsApp: Missing Twilio credentials")
        return False

    try:
        client = Client(sid, token)
        to_number = f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone
        from_whatsapp = f"whatsapp:{from_number}" if not from_number.startswith("whatsapp:") else from_number
        client.messages.create(body=message, from_=from_whatsapp, to=to_number)
        return True
    except Exception as e:
        print(f"[Flowreach] WhatsApp send error: {e}")
        return False