"""Batch AI scoring for leads with ai_score=0.

Usage: OPENROUTER_API_KEY=<key> python scripts/run_ai_scoring.py
"""
import asyncio
import os
import sys
import time
import traceback

# Add the agentflow root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set the OpenRouter key from env before any imports
import config as cfg
or_key = os.environ.get("OPENROUTER_API_KEY", "")
if or_key:
    cfg.OPENROUTER_API_KEY = or_key
    print(f"[Scoring] OPENROUTER_API_KEY set (len={len(or_key)})")
else:
    print("[Scoring] ERROR: OPENROUTER_API_KEY not set")
    sys.exit(1)

from services.supabase_client import get_supabase
from services.sales.qualifier import qualify_lead

ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"

async def main():
    sb = get_supabase()

    # Fetch leads with ai_score=0
    result = sb.table("leads").select("*").eq("ai_score", 0).execute()
    leads = result.data or []
    print(f"[Scoring] Found {len(leads)} leads with ai_score=0")

    if not leads:
        print("[Scoring] No leads to score. Exiting.")
        return

    scored = 0
    errors = 0
    score_distribution = {}

    for i, lead in enumerate(leads):
        name = lead.get("company_name", "Unknown")
        lead_id = lead.get("id", "")
        print(f"\n[{i+1}/{len(leads)}] Scoring: {name}")

        try:
            result = await qualify_lead(lead, account_id=ACCOUNT_ID)

            ai_score = result.get("ai_score")
            ai_reason = result.get("ai_score_reason", "")
            status = result.get("status", "new")

            # Update the lead in Supabase
            sb.table("leads").update({
                "ai_score": ai_score,
                "ai_score_reason": ai_reason,
                "score": ai_score,
                "status": status,
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }).eq("id", lead_id).execute()

            # Record the score
            score_distribution[ai_score] = score_distribution.get(ai_score, 0) + 1
            scored += 1

            print(f"  -> score={ai_score}/10, status={status}")
            print(f"  -> reason: {ai_reason[:100]}...")

        except Exception as e:
            errors += 1
            print(f"  -> ERROR: {e}")
            traceback.print_exc()

        # Small delay between API calls to avoid rate limits
        if i < len(leads) - 1:
            time.sleep(1)

    # Summary
    print("\n" + "=" * 60)
    print("SCORING COMPLETE")
    print(f"Total leads processed: {len(leads)}")
    print(f"Successfully scored: {scored}")
    print(f"Errors: {errors}")
    print(f"\nScore distribution:")
    for s in sorted(score_distribution.keys()):
        print(f"  Score {s}: {score_distribution[s]} leads")
    avg = sum(k * v for k, v in score_distribution.items()) / scored if scored else 0
    print(f"Average score: {avg:.1f}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
