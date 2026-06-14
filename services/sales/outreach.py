"""Outreach — orchestrates sending messages to qualified leads.

Manages campaign execution, message dispatch via appropriate channels,
and tracks delivery status.
"""

import uuid
from datetime import datetime
from typing import Optional

from .message_gen import generate_message
from .gmail_client import GmailClient

# ── Outreach log (in-memory, used by reply_handler import) ──
_demo_outreach_log: list[dict] = []


# ── Channel dispatchers ──


def _send_email(message: dict, lead: dict, account_id: str = "") -> dict:
    """Send an email via Gmail API."""
    to_email = lead.get("email", "")
    if not to_email:
        return {"status": "failed", "delivery_detail": "No email address for lead"}

    try:
        gmail = GmailClient(account_id=account_id)
        if not gmail.is_authenticated:
            return {"status": "failed", "delivery_detail": "Gmail not authenticated"}

        result = gmail.send_message(
            to_email=to_email,
            subject=message.get("subject", ""),
            body=message.get("body", ""),
        )

        if result.get("status") == "sent":
            return {
                "status": "sent",
                "delivery_detail": f"Email sent to {to_email} — ID: {result.get('message_id', 'unknown')}",
                "sent_at": datetime.utcnow().isoformat(),
            }
        else:
            return {"status": "failed", "delivery_detail": result.get("error", "Send failed")}
    except Exception as e:
        return {"status": "failed", "delivery_detail": str(e)}


def _send_linkedin(message: dict, lead: dict) -> dict:
    """LinkedIn messaging not yet implemented."""
    return {"status": "failed", "delivery_detail": "LinkedIn messaging not implemented"}


def _send_whatsapp(message: dict, lead: dict) -> dict:
    """WhatsApp messaging not yet implemented."""
    return {"status": "failed", "delivery_detail": "WhatsApp messaging not implemented"}


_CHANNEL_DISPATCHERS = {
    "email": _send_email,
    "linkedin": _send_linkedin,
    "whatsapp": _send_whatsapp,
}


# ── Public API ──


def send_outreach(
    lead: dict,
    channel: str = "email",
    message_type: str = "cold",
    agent_name: str = "Alex",
    agent_title: str = "Business Development",
    campaign_id: Optional[str] = None,
    account_id: str = "",
) -> dict:
    """Send an outreach message to a single lead.

    Generates the message, dispatches via the chosen channel, and
    records the result in the outreach log.

    Args:
        lead: Lead dict (must have 'id', 'company_name', 'contact_name',
              'email' for email, 'phone' for WhatsApp, etc.).
        channel: 'email', 'linkedin', or 'whatsapp'.
        message_type: 'cold' or 'follow_up'.
        agent_name: Name of sending agent.
        agent_title: Title of sending agent.
        campaign_id: Optional campaign UUID for tracking.
        account_id: Account UUID.

    Returns:
        Dict with outreach record including status, sent_at, etc.
    """
    # Generate message
    message = generate_message(
        lead=lead,
        channel=channel,
        message_type=message_type,
        agent_name=agent_name,
        agent_title=agent_title,
    )

    # Dispatch
    dispatcher = _CHANNEL_DISPATCHERS.get(channel, _send_email)
    delivery = dispatcher(message, lead, account_id=account_id)

    # Build outreach log record
    outreach_id = str(uuid.uuid4())
    record = {
        "id": outreach_id,
        "account_id": account_id,
        "campaign_id": campaign_id or "",
        "lead_id": lead.get("id", ""),
        "channel": channel,
        "subject": message["subject"],
        "body": message["body"],
        "status": delivery["status"],
        "sent_at": delivery.get("sent_at", datetime.utcnow().isoformat()),
        "delivered_at": delivery.get("sent_at"),
        "error_message": delivery.get("delivery_detail", ""),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "lead_name": lead.get("company_name", ""),
        "lead_email": lead.get("email", ""),
        "lead_phone": lead.get("phone", ""),
    }

    _demo_outreach_log.append(record)

    print(
        f"[Sales/Outreach] Sent {channel} ({message_type}) to "
        f"{lead.get('company_name', 'Unknown')} — status: {delivery['status']}"
    )

    return record


def run_campaign(
    campaign: dict,
    leads: list[dict],
    channel: str = "email",
    message_type: str = "cold",
    agent_name: str = "Alex",
    account_id: str = "",
) -> dict:
    """Execute an outreach campaign against a list of leads.

    Args:
        campaign: Campaign dict (must have 'id' and 'name').
        leads: List of qualified lead dicts.
        channel: Communication channel.
        message_type: Message type.
        agent_name: Sending agent name.
        account_id: Account UUID.

    Returns:
        Dict with campaign execution results.
    """
    campaign_id = campaign.get("id", str(uuid.uuid4()))
    campaign_name = campaign.get("name", "Unnamed Campaign")
    total = len(leads)
    sent = 0
    failed = 0
    results = []

    for lead in leads:
        try:
            result = send_outreach(
                lead=lead,
                channel=channel,
                message_type=message_type,
                agent_name=agent_name,
                campaign_id=campaign_id,
                account_id=account_id,
            )
            if result["status"] == "sent":
                sent += 1
            else:
                failed += 1
            results.append(result)
        except Exception as e:
            failed += 1
            results.append(
                {
                    "lead_id": lead.get("id", ""),
                    "status": "failed",
                    "error": str(e),
                }
            )

    summary = {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "channel": channel,
        "total_leads": total,
        "sent": sent,
        "failed": failed,
        "results": results,
        "executed_at": datetime.utcnow().isoformat(),
    }

    print(
        f"[Sales/Outreach] Campaign '{campaign_name}': "
        f"{sent}/{total} sent, {failed} failed"
    )

    return summary


def get_outreach_log(
    campaign_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Retrieve outreach log entries."""
    results = list(_demo_outreach_log)
    if campaign_id:
        results = [r for r in results if r.get("campaign_id") == campaign_id]
    if status:
        results = [r for r in results if r.get("status") == status]
    results.sort(key=lambda r: r.get("sent_at", ""), reverse=True)
    return results[:limit]


def get_outreach_stats() -> dict:
    """Get summary stats from the outreach log."""
    total = len(_demo_outreach_log)
    sent = len([r for r in _demo_outreach_log if r["status"] == "sent"])
    failed = len([r for r in _demo_outreach_log if r["status"] == "failed"])
    replied = len([r for r in _demo_outreach_log if r["status"] == "replied"])
    return {
        "total": total,
        "sent": sent,
        "failed": failed,
        "replied": replied,
        "reply_rate": round(replied / total * 100, 1) if total else 0.0,
    }