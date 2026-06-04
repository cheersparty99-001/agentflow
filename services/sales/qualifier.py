"""Qualifier — scores sales leads using AI (GPT-4o) with heuristic fallback.

Primary: Calls OpenRouter GPT-4o with lead info + target profile.
Fallback: Old heuristic algorithm if AI fails (timeout/error).
"""
import json
import math
import traceback
from datetime import datetime
from typing import Optional

import config as cfg

# ── Heuristic scoring weights (fallback) ──────────────────────────

WEIGHTS = {
    "employee_count": 0.25,
    "has_website": 0.15,
    "has_phone": 0.10,
    "has_email": 0.15,
    "industry": 0.20,
    "has_contact_name": 0.10,
    "has_social_url": 0.05,
}

INDUSTRY_SCORES = {
    "Technology": 8, "Healthcare": 7, "Logistics": 9, "Retail": 7,
    "Education": 6, "Automotive": 8, "Construction": 9, "Manufacturing": 8,
    "Hospitality": 6, "Finance": 7, "Real Estate": 6, "Agriculture": 5,
    "Energy": 7, "Other": 4,
}

SCORE_THRESHOLDS = {"hot": 80, "warm": 55, "cool": 30, "cold": 0}


# ── Target profile loader ──────────────────────────────────────────


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
        if profiles:
            return profiles[0]
        return None
    except Exception as e:
        print(f"[Qualifier] Load profile error: {e}")
        return None


def _load_business_info(business_id: str) -> Optional[dict]:
    """Load business info (description, value_proposition)."""
    try:
        from services.supabase_client import get_supabase
        sb = get_supabase()
        result = sb.table("sales_businesses").select("id, name, description, value_proposition, target_industries") \
            .eq("id", business_id).single().execute()
        return result.data if result.data else None
    except Exception as e:
        print(f"[Qualifier] Load business info error: {e}")
        return None


# ── AI scoring via OpenRouter GPT-4o ────────────────────────────────


def _call_openrouter(system_prompt: str, user_prompt: str, timeout: int = 25) -> Optional[str]:
    """Call OpenRouter GPT-4o and return the response text."""
    if not cfg.OPENROUTER_API_KEY:
        print("[Qualifier] OPENROUTER_API_KEY not configured — cannot call AI")
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
                "temperature": 0.3,
                "max_tokens": 500,
                "response_format": {"type": "json_object"},
            },
            timeout=timeout,
        )
        data = resp.json()
        if "error" in data:
            print(f"[Qualifier] OpenRouter API error: {data['error']}")
            return None
        choices = data.get("choices", [])
        if not choices:
            print(f"[Qualifier] OpenRouter returned no choices: {data}")
            return None
        content = choices[0].get("message", {}).get("content", "")
        return content
    except httpx.TimeoutException:
        print(f"[Qualifier] OpenRouter timeout after {timeout}s")
        return None
    except Exception as e:
        print(f"[Qualifier] OpenRouter call error: {e}")
        traceback.print_exc()
        return None


def _build_ai_scoring_prompt(lead: dict, profile: dict, business: dict) -> tuple[str, str]:
    """Build system + user prompts for AI scoring."""
    # Business info
    biz_name = (business or {}).get("name", "Unknown Business")
    biz_desc = (profile or {}).get("business_description", "") or (business or {}).get("description", "")
    biz_vp = (profile or {}).get("business_value_proposition", "") or (business or {}).get("value_proposition", "")

    # Target criteria from profile
    target_industries = ", ".join((profile or {}).get("industries", [])) or ", ".join((business or {}).get("target_industries", []))
    target_locations = ", ".join((profile or {}).get("locations", []))
    target_size = (profile or {}).get("company_size", "any")

    # Lead info
    lead_name = lead.get("company_name", "Unknown")
    lead_industry = lead.get("industry", "")
    lead_city = lead.get("city", "") or lead.get("location", "") or lead.get("address", "")
    lead_website = "Yes" if lead.get("website") else "No"
    lead_email = "Yes" if lead.get("email") else "No"

    system_prompt = """You are a lead scoring assistant. Your job is to evaluate whether a potential customer fits our target profile.

Scoring rules:
- 7-10: Strong fit — matches target, worth outreach
- 4-6: Partial fit — some overlap, consider
- 1-3: Poor fit — does not match, skip

Return ONLY valid JSON in this exact format:
{"score": <int 1-10>, "reason": "<2-3 sentence explanation in English>"}

Be specific about WHY the score was given. Mention actual company details."""

    user_prompt = f"""=== Our Company: {biz_name} ===
What we do: {biz_desc}
Value proposition: {biz_vp}

=== Target Customer Profile ===
Industries: {target_industries}
Locations: {target_locations}
Company size: {target_size}

=== Lead to Score ===
Company: {lead_name}
Industry: {lead_industry}
Location: {lead_city}
Has website: {lead_website}
Has email: {lead_email}

Score 1-10 and give specific reasons."""

    return system_prompt, user_prompt


def _ai_score_lead(lead: dict, profile: dict, business: dict) -> Optional[dict]:
    """Score a lead using AI. Returns {score, reason} or None on failure."""
    system_prompt, user_prompt = _build_ai_scoring_prompt(lead, profile, business)
    response = _call_openrouter(system_prompt, user_prompt)

    if not response:
        return None

    try:
        parsed = json.loads(response)
        score = parsed.get("score")
        reason = parsed.get("reason", "")
        if not isinstance(score, int) or score < 1 or score > 10:
            print(f"[Qualifier] AI returned invalid score: {parsed}")
            return None
        return {"score": score, "reason": reason}
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"[Qualifier] AI response parse error: {e}")
        print(f"[Qualifier] Raw response: {response}")
        return None


# ── Heuristic fallback (original algorithm) ──────────────────────


def _heuristic_score(lead: dict) -> dict:
    """Score a lead using heuristic rules. Returns {score (1-10), reason}."""
    s = 3  # base
    factors = []

    # Has phone
    if lead.get("phone"):
        s += 1
        factors.append("has phone")
    # Has website
    if lead.get("website"):
        s += 1
        factors.append("has website")
    # Has email
    if lead.get("email"):
        s += 2
        factors.append("has email")
    # Rating (if available)
    rating = lead.get("rating", 0) or 0
    if rating >= 4.5:
        s += 2
        factors.append(f"high rating ({rating})")
    elif rating >= 4.0:
        s += 1
        factors.append(f"good rating ({rating})")
    # Has address
    if lead.get("address") or lead.get("city"):
        s += 1
        factors.append("has location")

    s = max(1, min(10, s))
    reason = f"Heuristic scoring: base 3 + {', '.join(factors)} = {s}/10" if factors else f"Heuristic scoring: base {s}/10"
    return {"score": s, "reason": reason}


# ── Public API ──────────────────────────────────────────────────────


def qualify_lead(
    lead: dict,
    account_id: str = "",
) -> dict:
    """Score and qualify a single lead using AI, with heuristic fallback.

    Args:
        lead: Lead dict (must have 'company_name', 'industry', etc.).
        account_id: Account UUID for loading target profile and business info.

    Returns:
        Updated lead dict with ai_score, ai_score_reason, score, status fields.
    """
    business_id = lead.get("business_id", "")

    # Try AI scoring
    ai_result = None
    profile = None
    business_info = None

    if account_id and business_id:
        profile = _load_active_profile(business_id, account_id)
        business_info = _load_business_info(business_id)
        if profile and cfg.OPENROUTER_API_KEY:
            ai_result = _ai_score_lead(lead, profile, business_info)
            if ai_result:
                print(f"[Qualifier] AI scored '{lead.get('company_name', 'Unknown')}' at {ai_result['score']}/10 — {ai_result['reason']}")
            else:
                print(f"[Qualifier] AI scoring failed for '{lead.get('company_name', 'Unknown')}' — using fallback")
        else:
            reason = []
            if not profile:
                reason.append("no active target profile")
            if not cfg.OPENROUTER_API_KEY:
                reason.append("no API key")
            print(f"[Qualifier] AI scoring skipped ({'; '.join(reason)}) — using fallback")

    # Fallback: heuristic if AI failed or skipped
    if not ai_result:
        heuristic = _heuristic_score(lead)
        score = heuristic["score"]
        reason = heuristic["reason"]
        print(f"[Qualifier] Fallback: '{lead.get('company_name', 'Unknown')}' scored {score}/10 — {reason}")
    else:
        score = ai_result["score"]
        reason = ai_result["reason"]

    # Determine qualification status
    if score >= 7:
        status = "qualified"
    elif score >= 4:
        status = "new"
    else:
        status = "unqualified"

    result = dict(lead)
    result["ai_score"] = score
    result["ai_score_reason"] = reason
    result["score"] = score
    result["status"] = status
    result["qualified_at"] = datetime.utcnow().isoformat()
    result["updated_at"] = datetime.utcnow().isoformat()

    print(f"[Qualifier] Final: '{lead.get('company_name', 'Unknown')}' — score={score}/10, status={status}")
    return result


def qualify_leads(
    leads: list[dict],
    account_id: str = "",
    min_score: int = 0,
) -> list[dict]:
    """Score a batch of leads, optionally filtering by minimum score.

    Args:
        leads: List of lead dicts.
        account_id: Account UUID.
        min_score: Only return leads with score >= this value.

    Returns:
        List of scored and qualified lead dicts.
    """
    results = [qualify_lead(lead, account_id) for lead in leads]
    if min_score > 0:
        results = [r for r in results if r.get("score", 0) >= min_score]
    results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return results


def get_qualification_summary(leads: list[dict]) -> dict:
    """Get summary statistics for a batch of qualified leads."""
    if not leads:
        return {"total": 0, "hot": 0, "warm": 0, "cool": 0, "cold": 0, "avg_score": 0}

    counts = {"hot": 0, "warm": 0, "cool": 0, "cold": 0}
    total_score = 0
    for lead in leads:
        s = lead.get("score", 0)
        total_score += s
        for label, threshold in sorted(SCORE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True):
            if s >= threshold:
                counts[label] += 1
                break
        else:
            counts["cold"] += 1

    return {"total": len(leads), **counts, "avg_score": round(total_score / len(leads), 1)}