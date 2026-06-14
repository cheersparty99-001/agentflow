"""Usage — monthly and daily usage limits for sales outreach.

Delegates to the Supabase-backed data.usage layer for persistence.
Multi-tenant: account_id flows through from check_limits / get_usage_summary
to the data layer — no hardcoded IDs.
"""

from datetime import datetime, date
import config as cfg
from data import usage as data_usage


def check_limits(account_id: str, action: str) -> dict:
    """Check if an action is allowed within usage limits.

    Returns: {'allowed': True/False, 'reason': ''}
    """
    limits = data_usage.get_limits(account_id)
    if not limits:
        return {"allowed": True, "reason": ""}

    monthly_lead_limit = limits.get("monthly_lead_limit", 500)
    monthly_message_limit = limits.get("monthly_message_limit", 1000)
    daily_message_limit = limits.get("daily_message_limit", 50)

    if action == "lead":
        used = data_usage.get_leads_count_this_month(account_id)
        if used >= monthly_lead_limit:
            return {
                "allowed": False,
                "reason": f"Monthly lead limit reached ({used}/{monthly_lead_limit})",
            }

    if action == "message":
        used_month = data_usage.get_messages_count_this_month(account_id)
        if used_month >= monthly_message_limit:
            return {
                "allowed": False,
                "reason": f"Monthly message limit reached ({used_month}/{monthly_message_limit})",
            }
        used_today = data_usage.get_today_messages(account_id)
        if used_today >= daily_message_limit:
            return {
                "allowed": False,
                "reason": f"Daily message limit reached ({used_today}/{daily_message_limit})",
            }

    return {"allowed": True, "reason": ""}


def increment_usage(account_id: str, action: str):
    """Increment usage counter for an action.

    Note: counters in usage_limits table are currently updated
    by the daily scheduler. Manual increment is a no-op for now
    since the data layer reads actual counts from leads/sales_messages tables.
    """
    pass


def get_usage_summary(account_id: str) -> dict:
    """Get current usage summary with limits."""
    limits = data_usage.get_limits(account_id)
    if not limits:
        return {
            "leads": {"used": 0, "limit": 500, "remaining": 500, "percentage": 0},
            "messages": {
                "monthly": {"used": 0, "limit": 1000, "remaining": 1000},
                "daily": {"used": 0, "limit": 50, "remaining": 50},
            },
        }

    used_leads = data_usage.get_leads_count_this_month(account_id)
    used_msgs = data_usage.get_messages_count_this_month(account_id)
    used_today = data_usage.get_today_messages(account_id)

    monthly_lead_limit = limits.get("monthly_lead_limit", 500)
    monthly_msg_limit = limits.get("monthly_message_limit", 1000)
    daily_msg_limit = limits.get("daily_message_limit", 50)

    return {
        "leads": {
            "used": used_leads,
            "limit": monthly_lead_limit,
            "remaining": max(0, monthly_lead_limit - used_leads),
            "percentage": round(used_leads / monthly_lead_limit * 100, 1) if monthly_lead_limit else 0,
        },
        "messages": {
            "monthly": {
                "used": used_msgs,
                "limit": monthly_msg_limit,
                "remaining": max(0, monthly_msg_limit - used_msgs),
            },
            "daily": {
                "used": used_today,
                "limit": daily_msg_limit,
                "remaining": max(0, daily_msg_limit - used_today),
            },
        },
    }


def set_limits(account_id: str, monthly_leads: int = 500, monthly_messages: int = 1000, daily_messages: int = 50):
    """Set usage limits for an account in Supabase."""
    from services.supabase_client import get_supabase

    existing = data_usage.get_limits(account_id)
    if existing:
        get_supabase().table("usage_limits").update({
            "monthly_lead_limit": monthly_leads,
            "monthly_message_limit": monthly_messages,
            "daily_message_limit": daily_messages,
        }).eq("account_id", account_id).execute()
    else:
        get_supabase().table("usage_limits").insert({
            "account_id": account_id,
            "monthly_lead_limit": monthly_leads,
            "monthly_message_limit": monthly_messages,
            "daily_message_limit": daily_messages,
        }).execute()
    print(f"[Sales/Usage] Limits set for {account_id}: leads={monthly_leads}/mo, msgs={monthly_messages}/mo, {daily_messages}/day")