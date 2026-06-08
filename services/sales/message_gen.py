"""Message Generator — creates personalised outreach messages using AI (GPT-4o).

Supports multiple channels (email, LinkedIn, WhatsApp) and personalisation
based on lead data and active target profiles. Falls back to simple templates
if AI copywriting fails.
"""

import json
import logging
import random
import traceback
from datetime import datetime
from typing import Optional

import config as cfg

# ── Fallback templates (non-insurance, used when AI fails) ─────────

_FALLBACK_TEMPLATES = {
    "email": {
        "cold": {
            "subject": [
                "Quick question about {company_name}",
                "Ideas for {industry} businesses like yours",
                "{contact_name}, a thought on growth",
            ],
            "body": [
                "Hi {contact_name},\n\n"
                "I came across {company_name} while researching {industry} companies "
                "in {city} and was impressed by your work.\n\n"
                "Many {industry} businesses we work with have been looking for ways "
                "to automate repetitive tasks and save time. I'd love to share "
                "a few ideas on how we could help {company_name} "
                "streamline operations as you continue to grow.\n\n"
                "Would you be open to a quick 15-minute chat next week?\n\n"
                "Best regards,\n{agent_name}",
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
                "In the meantime, feel free to check out what we do.\n\n"
                "All the best,\n{agent_name}",
            ],
        },
    },
    "linkedin": {
        "cold": {
            "subject": [""],
            "body": [
                "Hi {contact_name}, I came across {company_name} and was "
                "impressed by what you're doing in the {industry} space. "
                "I help businesses like yours streamline operations with AI. "
                "Would you be open to connecting?",
            ],
        },
    },
    "whatsapp": {
        "cold": {
            "subject": [""],
            "body": [
                "Hi {contact_name}, this is {agent_name}. I help {industry} "
                "businesses like {company_name} save time with AI automation. "
                "Would you be open to a quick chat?",
            ],
        },
    },
}

logger = logging.getLogger(__name__)


# ── Profile & business info loaders (re-exported from qualifier) ──


def _load_active_profile(business_id: str, account_id: str) -> Optional[dict]:
    """Load the active target profile for a given business."""
    try:
        from services.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("target_profiles").select("*") \
            .eq("account_id", account_id) \
            .eq("business_id", business_id) \
            .eq("is_active", True) \
            .limit(1) \
            .execute()
        profiles = result.data or []
        return profiles[0] if profiles else None
    except Exception as e:
        logger.warning(f"[MessageGen] Load profile error: {e}")
        return None


def _load_business_info(business_id: str) -> Optional[dict]:
    """Load business info (description, value_proposition)."""
    try:
        from services.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("sales_businesses") \
            .select("id, name, description, value_proposition, target_industries") \
            .eq("id", business_id).single().execute()
        return result.data if result.data else None
    except Exception as e:
        logger.warning(f"[MessageGen] Load business info error: {e}")
        return None


# ── OpenRouter GPT-4o caller ────────────────────────────────────────


def _call_openrouter(system_prompt: str, user_prompt: str, timeout: int = 25) -> Optional[str]:
    """Call OpenRouter GPT-4o and return the response text."""
    if not cfg.OPENROUTER_API_KEY:
        logger.warning("[MessageGen] OPENROUTER_API_KEY not configured — cannot call AI")
        return None

    import httpx

    try:
        resp = httpx.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {cfg.OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "openai/gpt-4o",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.7,
                "max_tokens": 600,
                "response_format": {"type": "json_object"},
            },
            timeout=timeout,
        )
        data = resp.json()
        if "error" in data:
            logger.error(f"[MessageGen] OpenRouter API error: {data['error']}")
            return None
        choices = data.get("choices", [])
        if not choices:
            logger.error(f"[MessageGen] OpenRouter returned no choices: {data}")
            return None
        content = choices[0].get("message", {}).get("content", "")
        return content
    except httpx.TimeoutException:
        logger.error(f"[MessageGen] OpenRouter timeout after {timeout}s")
        return None
    except Exception as e:
        logger.error(f"[MessageGen] OpenRouter call error: {e}")
        traceback.print_exc()
        return None


# ── Prompt builders ─────────────────────────────────────────────────


def _build_generation_prompt(
    lead: dict,
    profile: Optional[dict],
    business: Optional[dict],
    agent_name: str,
    agent_title: str,
    channel: str,
    message_type: str,
) -> tuple[str, str]:
    """Build system + user prompts for AI copy generation."""

    company_name = lead.get("company_name", "Unknown Company")
    contact_name = lead.get("contact_name", "there")
    industry = lead.get("industry", "business")
    city = lead.get("city", lead.get("location", ""))
    notes = lead.get("notes", "")

    # Business info from profile
    biz_name = (business or {}).get("name", "our company")
    biz_desc = (profile or {}).get("business_description", "") or (business or {}).get("description", "")
    biz_vp = (profile or {}).get("business_value_proposition", "") or (business or {}).get("value_proposition", "")
    target_industries = ", ".join((profile or {}).get("industries", [])) or ", ".join((business or {}).get("target_industries", []))
    target_locations = ", ".join((profile or {}).get("locations", []))

    system_prompt = """You are a B2B sales copywriter. Generate a professional outreach email that is personalised and conversational.

Rules:
- Subject: short, under 8 words, no exclamation marks, no ALL CAPS
- Body: 100-150 words, professional but conversational tone
- Middle: one sentence on what we can do for them (our value proposition)
- Closing: clear CTA — suggest a 15-min call or demo
- Do NOT use corporate jargon, buzzword soup, or clichés
- Do NOT use "I hope this email finds you well" or similar filler openers
- Write in English only
- If the lead has News signals / notes, incorporate them naturally as a hook in the opening
- Opening sentence: NEVER use "I'm reaching out to introduce" or any variant of it. Every email must start differently — pick one of these approaches:
   (a) A specific observation or question about the prospect's company or industry
   (b) A relevant pain point their industry faces
   (c) A direct question about how they currently handle sales
  Vary the opening across every email. No two should start the same way.
- Signature: sign off with only the sender's name. Do NOT include job title, department, or company name in the signature. The body already mentions the company naturally.

Return ONLY valid JSON in this exact format:
{"subject": "...", "body": "..."}"""

    user_prompt = f"""Generate a {message_type} outreach message for the {channel} channel.

=== Our Company ===
Name: {biz_name}
What we do: {biz_desc}
Value proposition: {biz_vp}
Target industries: {target_industries}
Target locations: {target_locations}

=== Sender ===
Name: {agent_name}
Title: {agent_title}

=== Lead / Prospect ===
Company: {company_name}
Contact: {contact_name}
Industry: {industry}
Location: {city}
News signals / Notes: {notes if notes else "(none)"}

Generate a personalised {message_type} outreach message that feels tailored to this specific prospect."""

    return system_prompt, user_prompt


# ── AI generation ──────────────────────────────────────────────────


def _ai_generate_message(
    lead: dict,
    profile: Optional[dict],
    business: Optional[dict],
    agent_name: str,
    agent_title: str,
    channel: str,
    message_type: str,
) -> Optional[dict]:
    """Generate a message using GPT-4o. Returns {{subject, body}} or None."""
    system_prompt, user_prompt = _build_generation_prompt(
        lead, profile, business, agent_name, agent_title, channel, message_type,
    )
    response = _call_openrouter(system_prompt, user_prompt)

    if not response:
        return None

    try:
        parsed = json.loads(response)
        subject = parsed.get("subject", "").strip()
        body = parsed.get("body", "").strip()
        if not subject or not body:
            logger.warning(f"[MessageGen] AI returned empty subject or body: {parsed}")
            return None
        return {"subject": subject, "body": body}
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        logger.warning(f"[MessageGen] AI response parse error: {e}")
        logger.warning(f"[MessageGen] Raw response: {response}")
        return None


# ── Fallback message generation ────────────────────────────────────


def _fallback_generate_message(
    lead: dict,
    channel: str = "email",
    message_type: str = "cold",
    agent_name: str = "Alex",
    agent_title: str = "Business Development",
) -> dict:
    """Generate a message using fallback templates (non-insurance)."""
    channel_templates = _FALLBACK_TEMPLATES.get(channel, _FALLBACK_TEMPLATES["email"])
    type_templates = channel_templates.get(message_type, channel_templates["cold"])

    ctx = {
        "contact_name": lead.get("contact_name", lead.get("company_name", "there")),
        "company_name": lead.get("company_name", "your company"),
        "industry": lead.get("industry", "business"),
        "city": lead.get("city", lead.get("location", "your area")),
        "agent_name": agent_name,
        "agent_title": agent_title,
    }

    subjects = type_templates["subject"]
    bodies = type_templates["body"]

    if subjects and subjects[0]:
        subject = random.choice(subjects).format(**ctx)
    else:
        subject = ""

    body = random.choice(bodies).format(**ctx)

    return {"subject": subject, "body": body}


# ── Public API ────────────────────────────────────────────────────


def generate_message(
    lead: dict,
    channel: str = "email",
    message_type: str = "cold",
    agent_name: str = "Alex",
    agent_title: str = "Business Development",
    company_name_override: str = "",
    account_id: str = "",
) -> dict:
    """Generate a personalised outreach message for a lead using AI (GPT-4o).

    Uses the active target profile and business info to craft a relevant,
    professional message. Falls back to simple templates if AI fails.

    Args:
        lead: Lead dict with keys like 'contact_name', 'company_name',
              'industry', 'city', 'notes', etc.
        channel: 'email', 'linkedin', or 'whatsapp'.
        message_type: 'cold', 'follow_up', etc.
        agent_name: Name of the agent sending the message.
        agent_title: Title of the agent.
        company_name_override: Sender's company name (overrides profile).
        account_id: Account UUID for loading target profile and business info.

    Returns:
        Dict with 'subject', 'body', 'channel', 'message_type',
        'personalisation_used', 'generated_by' fields.
    """
    business_id = lead.get("business_id", "")

    # Try AI generation
    ai_result = None
    profile = None
    business_info = None

    if account_id and business_id:
        profile = _load_active_profile(business_id, account_id)
        business_info = _load_business_info(business_id)

    if cfg.OPENROUTER_API_KEY:
        ai_result = _ai_generate_message(
            lead, profile, business_info, agent_name, agent_title, channel, message_type,
        )
        if ai_result:
            logger.info(
                f"[MessageGen] AI generated {channel} ({message_type}) for "
                f"{lead.get('company_name', 'Unknown')}"
            )
        else:
            logger.warning(
                f"[MessageGen] AI copywriting failed for "
                f"{lead.get('company_name', 'Unknown')}, using fallback"
            )
    else:
        logger.warning("[MessageGen] No API key — using fallback templates")

    # Fallback if AI failed or not available
    if not ai_result:
        fallback = _fallback_generate_message(lead, channel, message_type, agent_name, agent_title)
        subject = fallback["subject"]
        body = fallback["body"]
        generated_by = "fallback"
    else:
        subject = ai_result["subject"]
        body = ai_result["body"]
        generated_by = "gpt-4o"

    result = {
        "subject": subject,
        "body": body,
        "channel": channel,
        "message_type": message_type,
        "personalisation_used": ["company_name", "contact_name", "industry", "city", "notes"],
        "generated_at": datetime.utcnow().isoformat(),
        "generated_by": generated_by,
    }

    print(
        f"[Sales/MessageGen] Generated {channel} ({message_type}) for "
        f"{lead.get('company_name', 'Unknown')} — via {generated_by}"
    )

    return result


def generate_campaign_messages(
    leads: list[dict],
    channel: str = "email",
    message_type: str = "cold",
    agent_name: str = "Alex",
    account_id: str = "",
) -> list[dict]:
    """Generate personalised messages for a list of leads.

    Args:
        leads: List of lead dicts.
        channel: Communication channel.
        message_type: Type of message.
        agent_name: Name of the agent.
        account_id: Account UUID for profile loading.

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
            account_id=account_id,
        )
        msg["lead_id"] = lead.get("id", "")
        msg["lead_name"] = lead.get("company_name", "")
        messages.append(msg)
    return messages