"""Notification — sends alerts to Edwin via WhatsApp/template.
DEMO_MODE: prints to console.
"""

import config as cfg

EDWIN_PHONE = getattr(cfg, 'EDWIN_NOTIFY_WHATSAPP', '')

def _is_demo() -> bool:
    return getattr(cfg, 'DEMO_MODE', True)

def _build_alert_text(lead: dict, message: str, intent: str, confidence: float, suggested_reply: str) -> str:
    return f'''Sales Alert - Reply Received

Business: {lead.get("business", lead.get("company_name", ""))}
Company: {lead.get("company_name", "")}
Contact: {lead.get("contact_name", "") or lead.get("contact", "")}
Industry: {lead.get("industry", "")}

Their message:
""{message}""

Intent: {intent} ({confidence*100:.0f}%)

AI suggested reply:
""{suggested_reply}""

View lead: /sales/leads/{lead.get("id", "")}

Reply NOW while they''re warm.'''

def notify_edwin_reply(lead: dict, message: str, intent: str, confidence: float, suggested_reply: str):
    """Notify Edwin about a lead reply via WhatsApp."""
    alert = _build_alert_text(lead, message, intent, confidence, suggested_reply)
    
    if _is_demo():
        print(f'[Sales/Notification] DEMO -- Would send WhatsApp to {EDWIN_PHONE or "Edwin"}')
        print(f'---\n{alert}\n---')
        return {"status": "logged", "to": EDWIN_PHONE}
    
    # Production: Send via Twilio WhatsApp
    if not EDWIN_PHONE:
        print('[Sales/Notification] ERROR: EDWIN_NOTIFY_WHATSAPP not configured')
        return {"status": "error", "reason": "Missing EDWIN_NOTIFY_WHATSAPP"}
    
    try:
        from twilio.rest import Client
        account_sid = getattr(cfg, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(cfg, 'TWILIO_AUTH_TOKEN', '')
        twilio_from = getattr(cfg, 'TWILIO_WHATSAPP_FROM', '')
        
        if not all([account_sid, auth_token, twilio_from]):
            return {"status": "error", "reason": "Twilio not configured"}
        
        client = Client(account_sid, auth_token)
        msg = client.messages.create(
            body=alert,
            from_=twilio_from,
            to=f'whatsapp:{EDWIN_PHONE}',
        )
        return {"status": "sent", "sid": msg.sid}
    except Exception as e:
        print(f'[Sales/Notification] ERROR: {e}')
        return {"status": "failed", "error": str(e)}

def get_alert_preview(lead: dict, message: str, intent: str, confidence: float, suggested_reply: str) -> str:
    """Return alert text without sending (for preview/display in UI)."""
    return _build_alert_text(lead, message, intent, confidence, suggested_reply)