"""Reply Handler — processes inbound replies from outreach targets.

Analyses sentiment, categorises responses, generates auto-replies
for common patterns, and updates the outreach log.
"""

import re
import uuid
from datetime import datetime
from typing import Optional

import config as cfg

# ── Sentiment analysis keywords ───────────────────────────────────

_POSITIVE_KEYWORDS = [
    "interested", "yes", "sure", "let's talk", "call me", "send more",
    "tell me more", "quote", "price", "sounds good", "ok", "okay",
    "go ahead", "proceed", "schedule", "book", "available",
]

_NEGATIVE_KEYWORDS = [
    "not interested", "no", "stop", "unsubscribe", "remove", "don't contact",
    "leave me alone", "spam", "do not email", "block", "never",
]

_UNSUBSCRIBE_KEYWORDS = [
    "unsubscribe", "opt out", "opt-out", "remove me", "stop email",
    "no more emails", "do not send",
]

_INTEREST_KEYWORDS = [
    "how much", "quote", "pricing", "cost", "premium", "coverage",
    "what do you offer", "details", "brochure", "proposal",
]


# ── Sentiment analysis ────────────────────────────────────────────


def _analyze_sentiment(text: str) -> str:
    """Classify reply text sentiment.

    Returns 'positive', 'negative', 'unsubscribe', or 'neutral'.
    """
    text_lower = text.lower().strip()

    # Check unsubscribe first (highest priority)
    for kw in _UNSUBSCRIBE_KEYWORDS:
        if kw in text_lower:
            return "unsubscribe"

    # Check strong negative signals
    for kw in _NEGATIVE_KEYWORDS:
        if kw in text_lower:
            return "negative"

    # Check interest signals
    for kw in _INTEREST_KEYWORDS:
        if kw in text_lower:
            return "positive"

    # Check positive keywords
    for kw in _POSITIVE_KEYWORDS:
        if kw in text_lower:
            return "positive"

    return "neutral"


# ── Auto-reply generation ─────────────────────────────────────────


def _generate_auto_reply(
    sentiment: str,
    lead: Optional[dict] = None,
    outreach_record: Optional[dict] = None,
) -> str:
    """Generate an appropriate auto-reply based on sentiment.

    Args:
        sentiment: Classified sentiment ('positive', 'negative',
                   'unsubscribe', 'neutral').
        lead: Lead dict for personalisation.
        outreach_record: Original outreach message for context.

    Returns:
        Auto-reply text, or empty string if no reply needed.
    """
    contact_name = ""
    if lead:
        contact_name = lead.get("contact_name", "")

    if sentiment == "positive":
        return (
            f"Hi {contact_name},\n\n"
            "Thank you for your interest! I'll have one of our specialists "
            "reach out to you within 24 hours with more details and a "
            "tailored proposal.\n\n"
            "In the meantime, feel free to let me know if you have any "
            "specific questions.\n\n"
            "Best regards,\nAlex\nFlowreach Sales"
        )

    if sentiment == "unsubscribe":
        return (
            f"Hi {contact_name},\n\n"
            "You've been unsubscribed from our outreach list. We will "
            "not contact you again regarding this campaign.\n\n"
            "If you change your mind in the future, feel free to reach out.\n\n"
            "Thank you."
        )

    if sentiment == "negative":
        return (
            f"Hi {contact_name},\n\n"
            "Thank you for your reply. We respect your decision and have "
            "noted your preference. You will not receive further messages "
            "from us on this topic.\n\n"
            "Wishing you all the best."
        )

    # Neutral — no auto-reply, needs human review
    return ""


# ── Public API ────────────────────────────────────────────────────

# In-memory demo store for reply tracker
_demo_reply_tracker: list[dict] = []


def handle_reply(
    reply_text: str,
    from_email: str,
    from_name: str = "",
    subject: str = "",
    outreach_id: Optional[str] = None,
    lead_id: Optional[str] = None,
    lead: Optional[dict] = None,
    account_id: str = "00000000-0000-0000-0000-000000000001",
    auto_reply_enabled: bool = True,
) -> dict:
    """Process an inbound reply to an outreach message.

    Analyses sentiment, optionally sends an auto-reply, and updates
    the outreach log and reply tracker.

    Args:
        reply_text: The inbound message body.
        from_email: Sender's email address.
        from_name: Sender's display name.
        subject: Reply subject line.
        outreach_id: UUID of the original outreach message (if known).
        lead_id: UUID of the lead (if known).
        lead: Lead dict for personalisation (optional, used if lead_id not given).
        account_id: Account UUID.
        auto_reply_enabled: Whether to generate automatic replies.

    Returns:
        Dict with analysis results and auto-reply (if sent).
    """
    sentiment = _analyze_sentiment(reply_text)

    auto_reply = ""
    auto_reply_sent = False
    if auto_reply_enabled and sentiment in ("positive", "negative", "unsubscribe"):
        auto_reply = _generate_auto_reply(sentiment, lead)
        if auto_reply:
            auto_reply_sent = True

    # Build reply tracker record
    tracker_id = str(uuid.uuid4())
    tracker_record = {
        "id": tracker_id,
        "account_id": account_id,
        "outreach_id": outreach_id or "",
        "lead_id": lead_id or "",
        "from_email": from_email,
        "from_name": from_name,
        "subject": subject,
        "body": reply_text,
        "sentiment": sentiment,
        "auto_reply": auto_reply,
        "auto_reply_sent": auto_reply_sent,
        "handled_at": datetime.utcnow().isoformat(),
        "created_at": datetime.utcnow().isoformat(),
    }
    _demo_reply_tracker.append(tracker_record)

    # Update the outreach log to reflect reply
    if outreach_id:
        for record in _outreach_module._demo_outreach_log:
            if record.get("id") == outreach_id:
                record["status"] = "replied"
                record["reply_at"] = datetime.utcnow().isoformat()
                record["reply_text"] = reply_text
                record["updated_at"] = datetime.utcnow().isoformat()
                break

    result = {
        "tracker_id": tracker_id,
        "sentiment": sentiment,
        "auto_reply": auto_reply,
        "auto_reply_sent": auto_reply_sent,
        "handled_at": tracker_record["handled_at"],
    }

    if cfg.DEMO_MODE:
        print(
            f"[Sales/ReplyHandler] DEMO -- Processed reply from {from_email}: "
            f"sentiment={sentiment}, auto_reply={'yes' if auto_reply_sent else 'no'}"
        )

    return result


def get_reply_tracker(
    sentiment: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Retrieve reply tracker entries.

    Args:
        sentiment: Filter by sentiment ('positive', 'negative', etc.).
        limit: Maximum entries.

    Returns:
        List of reply tracker dicts.
    """
    results = list(_demo_reply_tracker)
    if sentiment:
        results = [r for r in results if r.get("sentiment") == sentiment]
    results.sort(key=lambda r: r.get("handled_at", ""), reverse=True)
    return results[:limit]


def get_reply_stats() -> dict:
    """Get summary statistics from reply tracker."""
    total = len(_demo_reply_tracker)
    positive = len([r for r in _demo_reply_tracker if r["sentiment"] == "positive"])
    negative = len([r for r in _demo_reply_tracker if r["sentiment"] == "negative"])
    neutral = len([r for r in _demo_reply_tracker if r["sentiment"] == "neutral"])
    unsub = len([r for r in _demo_reply_tracker if r["sentiment"] == "unsubscribe"])
    auto_replied = len([r for r in _demo_reply_tracker if r.get("auto_reply_sent")])
    return {
        "total": total,
        "positive": positive,
        "negative": negative,
        "neutral": neutral,
        "unsubscribe": unsub,
        "auto_replied": auto_replied,
        "positive_rate": round(positive / total * 100, 1) if total else 0.0,
    }


# Import outreach log reference from outreach module
from . import outreach as _outreach_module