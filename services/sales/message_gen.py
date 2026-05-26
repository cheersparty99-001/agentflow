"""Message Generator — creates personalised outreach messages using templates.

Supports multiple channels (email, LinkedIn, WhatsApp) and personalisation
based on lead data. Demo mode returns simulated message content.
"""

import random
from datetime import datetime
from typing import Optional

import config as cfg

# ── Template pools ────────────────────────────────────────────────

TEMPLATES = {
    "email": {
        "cold": {
            "subject": [
                "Quick question about {company_name}",
                "Protection solutions for {company_name}",
                "Ideas for {industry} businesses like yours",
                "{contact_name}, a thought on risk management",
            ],
            "body": [
                "Hi {contact_name},\n\n"
                "I came across {company_name} while researching {industry} companies "
                "in {city} and was impressed by your work.\n\n"
                "Many {industry} businesses we work with have been reviewing their "
                "insurance coverage given recent market changes. I'd love to share "
                "a few insights on how comprehensive protection could benefit "
                "{company_name} as you continue to grow.\n\n"
                "Would you be open to a quick 10-minute chat next week?\n\n"
                "Best regards,\n{agent_name}",

                "Hi {contact_name},\n\n"
                "I hope this note finds you well. I'm reaching out because "
                "{company_name} seems like an innovative player in the {industry} "
                "space, and I thought you might appreciate some ideas on optimising "
                "your insurance portfolio.\n\n"
                "We've been helping businesses similar to yours reduce costs while "
                "improving coverage. Happy to share a few examples.\n\n"
                "Would you have 15 minutes for a brief call?\n\n"
                "Warmly,\n{agent_name}",
            ],
        },
        "follow_up": {
            "subject": [
                "Following up: {company_name}",
                "Did you see my previous message?",
                "Quick follow-up, {contact_name}",
            ],
            "body": [
                "Hi {contact_name},\n\n"
                "Just following up on my previous email. I know how busy things "
                "get in the {industry} space!\n\n"
                "If timing isn't right, I'm happy to circle back in a few months. "
                "In the meantime, I've attached a quick overview of the solutions "
                "we discussed.\n\n"
                "All the best,\n{agent_name}",

                "Hi {contact_name},\n\n"
                "I wanted to check in and see if you had any questions about "
                "the insurance solutions I mentioned previously.\n\n"
                "No pressure at all — just wanted to leave the door open.\n\n"
                "Cheers,\n{agent_name}",
            ],
        },
    },
    "linkedin": {
        "cold": {
            "subject": [""],
            "body": [
                "Hi {contact_name}, I came across {company_name} and was "
                "impressed by what you're doing in the {industry} space. "
                "I help businesses like yours with tailored insurance solutions. "
                "Would you be open to connecting?",

                "Hi {contact_name}, great to see {company_name}'s growth in "
                "{city}! I specialise in risk management for {industry} "
                "companies. Would love to connect and share ideas.",
            ],
        },
    },
    "whatsapp": {
        "cold": {
            "subject": [""],
            "body": [
                "Hi {contact_name}, this is {agent_name}. I help {industry} "
                "businesses like {company_name} get better insurance coverage "
                "at competitive rates. Would you be open to a quick chat?",

                "Hi {contact_name}, {agent_name} here. Noticed {company_name} "
                "is doing great things in {city}. Any interest in reviewing "
                "your insurance coverage to make sure you're fully protected?",
            ],
        },
    },
}


# ── Public API ────────────────────────────────────────────────────


def generate_message(
    lead: dict,
    channel: str = "email",
    message_type: str = "cold",
    agent_name: str = "Alex",
    agent_title: str = "Business Development",
    company_name_override: str = "AgentFlow Insurance",
) -> dict:
    """Generate a personalised outreach message for a lead.

    In DEMO_MODE, selects a random template and fills in the lead's details.
    In production, would use LLM-driven personalisation.

    Args:
        lead: Lead dict with keys like 'contact_name', 'company_name',
              'industry', 'city', etc.
        channel: 'email', 'linkedin', or 'whatsapp'.
        message_type: 'cold', 'follow_up', etc.
        agent_name: Name of the agent sending the message.
        agent_title: Title of the agent.
        company_name_override: Sender's company name.

    Returns:
        Dict with 'subject', 'body', 'channel', 'message_type',
        'personalisation_used' fields.
    """
    channel_templates = TEMPLATES.get(channel, TEMPLATES["email"])
    type_templates = channel_templates.get(message_type, channel_templates["cold"])

    # Build personalisation context
    ctx = {
        "contact_name": lead.get("contact_name", lead.get("company_name", "there")),
        "company_name": lead.get("company_name", "your company"),
        "industry": lead.get("industry", "business"),
        "city": lead.get("city", "your area"),
        "agent_name": agent_name,
        "agent_title": agent_title,
        "agent_company": company_name_override,
    }

    # Select random subject and body
    subjects = type_templates["subject"]
    bodies = type_templates["body"]

    if subjects and subjects[0]:
        subject_template = random.choice(subjects)
        subject = subject_template.format(**ctx)
    else:
        subject = ""

    body_template = random.choice(bodies)
    body = body_template.format(**ctx)

    result = {
        "subject": subject,
        "body": body,
        "channel": channel,
        "message_type": message_type,
        "personalisation_used": list(ctx.keys()),
        "generated_at": datetime.utcnow().isoformat(),
    }

    if cfg.DEMO_MODE:
        print(
            f"[Sales/MessageGen] DEMO -- Generated {channel}/{message_type} "
            f"message for {lead.get('company_name', 'Unknown')}"
        )

    return result


def generate_campaign_messages(
    leads: list[dict],
    channel: str = "email",
    message_type: str = "cold",
    agent_name: str = "Alex",
) -> list[dict]:
    """Generate personalised messages for a list of leads.

    Args:
        leads: List of lead dicts.
        channel: Communication channel.
        message_type: Type of message.
        agent_name: Name of the agent.

    Returns:
        List of message dicts with subject, body, lead_id, etc.
    """
    messages = []
    for lead in leads:
        msg = generate_message(
            lead=lead,
            channel=channel,
            message_type=message_type,
            agent_name=agent_name,
        )
        msg["lead_id"] = lead.get("id", "")
        msg["lead_name"] = lead.get("company_name", "")
        messages.append(msg)
    return messages


def list_available_templates() -> dict:
    """Return a summary of available template channels and message types."""
    summary = {}
    for channel, types in TEMPLATES.items():
        summary[channel] = list(types.keys())
    return summary