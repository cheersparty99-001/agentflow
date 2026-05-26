"""Qualifier — scores and qualifies sales leads based on business rules.

In DEMO_MODE, uses heuristic scoring on the lead data without external
enrichment. In production, would call Clearbit / Lusha / credit bureaus.
"""

import math
from datetime import datetime
from typing import Optional

import config as cfg

# ── Scoring weights ───────────────────────────────────────────────

WEIGHTS = {
    "employee_count": 0.25,
    "has_website": 0.15,
    "has_phone": 0.10,
    "has_email": 0.15,
    "industry": 0.20,
    "has_contact_name": 0.10,
    "has_social_url": 0.05,
}

# Industry scoring — industries more likely to need insurance
INDUSTRY_SCORES = {
    "Technology": 8,
    "Healthcare": 7,
    "Logistics": 9,
    "Retail": 7,
    "Education": 6,
    "Automotive": 8,
    "Construction": 9,
    "Manufacturing": 8,
    "Hospitality": 6,
    "Finance": 7,
    "Real Estate": 6,
    "Agriculture": 5,
    "Energy": 7,
    "Other": 4,
}

# ── Qualification thresholds ──────────────────────────────────────

SCORE_THRESHOLDS = {
    "hot": 80,       # 80+ → highly qualified, prioritize outreach
    "warm": 55,      # 55-79 → moderately qualified
    "cool": 30,      # 30-54 → low priority
    "cold": 0,       # <30 → unqualified for now
}


# ── Public API ────────────────────────────────────────────────────


def qualify_lead(
    lead: dict,
    account_id: str = "00000000-0000-0000-0000-000000000001",
) -> dict:
    """Score and qualify a single lead.

    In DEMO_MODE, scoring uses available fields and returns immediate
    results. In production, would enrich via external APIs first.

    Args:
        lead: Lead dict (must contain at minimum 'company_name').
        account_id: Account UUID for logging.

    Returns:
        Updated lead dict with 'score' and 'status' fields set,
        plus a 'qualification_factors' breakdown.
    """
    score = 0
    factors = []

    # ── Employee count score (0-25) ──────────────────────────────
    emp = lead.get("employee_count", 0)
    if emp >= 100:
        emp_score = 25
        factors.append({"factor": "employee_count", "value": emp, "score": emp_score, "note": "Large company"})
    elif emp >= 30:
        emp_score = 18
        factors.append({"factor": "employee_count", "value": emp, "score": emp_score, "note": "Medium company"})
    elif emp >= 5:
        emp_score = 10
        factors.append({"factor": "employee_count", "value": emp, "score": emp_score, "note": "Small company"})
    else:
        emp_score = 3
        factors.append({"factor": "employee_count", "value": emp, "score": emp_score, "note": "Very small/missing"})
    score += emp_score

    # ── Has website (0-15) ────────────────────────────────────────
    if lead.get("website"):
        score += 15
        factors.append({"factor": "has_website", "value": True, "score": 15})
    else:
        factors.append({"factor": "has_website", "value": False, "score": 0})

    # ── Has phone (0-10) ──────────────────────────────────────────
    if lead.get("phone"):
        score += 10
        factors.append({"factor": "has_phone", "value": True, "score": 10})
    else:
        factors.append({"factor": "has_phone", "value": False, "score": 0})

    # ── Has email (0-15) ──────────────────────────────────────────
    if lead.get("email"):
        score += 15
        factors.append({"factor": "has_email", "value": True, "score": 15})
    else:
        factors.append({"factor": "has_email", "value": False, "score": 0})

    # ── Industry fit (0-20) ───────────────────────────────────────
    industry = lead.get("industry", "Other")
    ind_score = INDUSTRY_SCORES.get(industry, 4)
    score += ind_score
    factors.append({"factor": "industry", "value": industry, "score": ind_score})

    # ── Has contact name (0-10) ───────────────────────────────────
    if lead.get("contact_name"):
        score += 10
        factors.append({"factor": "has_contact_name", "value": True, "score": 10})
    else:
        factors.append({"factor": "has_contact_name", "value": False, "score": 0})

    # ── Has social URL (0-5) ──────────────────────────────────────
    if lead.get("social_url"):
        score += 5
        factors.append({"factor": "has_social_url", "value": True, "score": 5})
    else:
        factors.append({"factor": "has_social_url", "value": False, "score": 0})

    # ── Clamp to 0-100 ────────────────────────────────────────────
    score = max(0, min(100, score))

    # ── Determine status ──────────────────────────────────────────
    if score >= SCORE_THRESHOLDS["hot"]:
        status = "qualified"
    elif score >= SCORE_THRESHOLDS["warm"]:
        status = "qualified"
    elif score >= SCORE_THRESHOLDS["cool"]:
        status = "new"
    else:
        status = "unqualified"

    # ── Build result ──────────────────────────────────────────────
    result = dict(lead)
    result["score"] = score
    result["status"] = status
    result["qualified_at"] = datetime.utcnow().isoformat()
    result["qualification_factors"] = factors
    result["updated_at"] = datetime.utcnow().isoformat()

    if cfg.DEMO_MODE:
        print(
            f"[Sales/Qualifier] DEMO -- Scored '{lead.get('company_name', 'Unknown')}' "
            f"at {score}/100 → {status}"
        )

    return result


def qualify_leads(
    leads: list[dict],
    account_id: str = "00000000-0000-0000-0000-000000000001",
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
        results = [r for r in results if r["score"] >= min_score]
    # Sort by score descending
    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def get_qualification_summary(leads: list[dict]) -> dict:
    """Get summary statistics for a batch of qualified leads."""
    if not leads:
        return {"total": 0, "hot": 0, "warm": 0, "cool": 0, "cold": 0, "avg_score": 0}

    counts = {"hot": 0, "warm": 0, "cool": 0, "cold": 0}
    total_score = 0
    for lead in leads:
        score = lead.get("score", 0)
        total_score += score
        for label, threshold in sorted(
            SCORE_THRESHOLDS.items(), key=lambda x: x[1], reverse=True
        ):
            if score >= threshold:
                counts[label] += 1
                break
        else:
            counts["cold"] += 1

    return {
        "total": len(leads),
        **counts,
        "avg_score": round(total_score / len(leads), 1),
    }