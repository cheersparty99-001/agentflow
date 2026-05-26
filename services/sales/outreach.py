"""Outreach — orchestrates sending messages to qualified leads.

Manages campaign execution, message dispatch via appropriate channels,
and tracks delivery status. DEMO_MODE logs all actions without real sends.
"""

import uuid
from datetime import datetime
from typing import Optional

import config as cfg
from .message_gen import generate_message

# ── In-memory demo store ─────────────────────────────────────────

# Simulates sales_outreach_log table
_demo_outreach_log: list[dict] = []


# ── Channel dispatchers (all demo) ────────────────────────────────


def _send_email(message: dict, lead: dict) -> dict:
    """Simulate sending an email via SMTP/API.

    Returns delivery status.
    """
    if cfg.DEMO_MODE:
        return {
            "status": "sent",
            "delivery_detail": "DEMO -- Email logged, no SMTP call made",
            "sent_at": datetime.utcnow().isoformat(),
        }

    # Real implementation would go here
    return {"status": "failed", "delivery_detail": "Production mode not implemented"}


def _send_linkedin(message: dict, lead: dict) -> dict:
    """Simulate sending a LinkedIn message."""
    if cfg.DEMO_MODE:
        return {
            "status": "sent",
            "delivery_detail": "DEMO -- LinkedIn message logged, no API call made",
            "sent_at": datetime.utcnow().isoformat(),
        }
    return {"status": "failed", "delivery_detail": "Production mode not implemented"}


def _send_whatsapp(message: dict, lead: dict) -> dict:
    """Simulate sending a WhatsApp message."""
    if cfg.DEMO_MODE:
        return {
            "status": "sent",
            "delivery_detail": "DEMO -- WhatsApp message logged, no API call made",
            "sent_at": datetime.utcnow().isoformat(),
        }
    return {"status": "failed", "delivery_detail": "Production mode not implemented"}


_CHANNEL_DISPATCHERS = {
    "email": _send_email,
    "linkedin": _send_linkedin,
    "whatsapp": _send_whatsapp,
}


# ── Public API ────────────────────────────────────────────────────


def send_outreach(
    lead: dict,
    channel: str = "email",
    message_type: str = "cold",
    agent_name: str = "Alex",
    agent_title: str = "Business Development",
    campaign_id: Optional[str] = None,
    account_id: str = "00000000-0000-0000-0000-000000000001",
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
    delivery = dispatcher(message, lead)

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
        "delivered_at": delivery.get("sent_at"),  # same as sent in demo
        "error_message": delivery.get("delivery_detail", ""),
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "lead_name": lead.get("company_name", ""),
        "lead_email": lead.get("email", ""),
        "lead_phone": lead.get("phone", ""),
    }

    _demo_outreach_log.append(record)

    if cfg.DEMO_MODE:
        print(
            f"[Sales/Outreach] DEMO -- Sent {channel} ({message_type}) to "
            f"{lead.get('company_name', 'Unknown')} — status: {delivery['status']}"
        )

    return record


def run_campaign(
    campaign: dict,
    leads: list[dict],
    channel: str = "email",
    message_type: str = "cold",
    agent_name: str = "Alex",
    account_id: str = "00000000-0000-0000-0000-000000000001",
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

    if cfg.DEMO_MODE:
        print(
            f"[Sales/Outreach] DEMO -- Campaign '{campaign_name}': "
            f"{sent}/{total} sent, {failed} failed"
        )

    return summary


def get_outreach_log(
    campaign_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Retrieve outreach log entries.

    Args:
        campaign_id: Filter by campaign.
        status: Filter by status ('sent', 'pending', 'failed', 'replied').
        limit: Maximum entries to return.

    Returns:
        List of outreach log dicts.
    """
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