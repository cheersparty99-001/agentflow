"""Usage — monthly and daily usage limits for sales outreach.
DEMO_MODE: tracks in memory, no DB."""

from datetime import datetime, date
import config as cfg

# ── In-memory demo store ──
_demo_usage: dict = {
    'account_id': '00000000-0000-0000-0000-000000000001',
    'monthly_lead_limit': 200,
    'monthly_message_limit': 400,
    'daily_message_limit': 20,
    'current_month_leads': 0,
    'current_month_messages': 0,
    'current_day_messages': 0,
    'last_reset_date': date.today().isoformat(),
    'last_daily_reset': datetime.utcnow().isoformat(),
}

def _is_demo() -> bool:
    return getattr(cfg, 'DEMO_MODE', True)

def _ensure_reset():
    """Auto-reset daily/monthly counters if needed."""
    today = date.today()
    stored_date = _demo_usage.get('last_reset_date', '')
    if isinstance(stored_date, str) and stored_date:
        try:
            stored = date.fromisoformat(stored_date)
        except:
            stored = today
    else:
        stored = today
    
    # Monthly reset (1st of month)
    if today.month != stored.month:
        _demo_usage['current_month_leads'] = 0
        _demo_usage['current_month_messages'] = 0
        _demo_usage['current_day_messages'] = 0
        _demo_usage['last_reset_date'] = today.isoformat()
        if _is_demo():
            print(f'[Sales/Usage] DEMO -- Monthly reset (new month)')
    
    # Daily reset
    if today.day != stored.day:
        _demo_usage['current_day_messages'] = 0
        _demo_usage['last_daily_reset'] = datetime.utcnow().isoformat()
        if _is_demo():
            print(f'[Sales/Usage] DEMO -- Daily message counter reset')

def check_limits(account_id: str, action: str) -> dict:
    """Check if an action is allowed within usage limits.
    Returns: {'allowed': True/False, 'reason': ''}"""
    _ensure_reset()
    
    u = _demo_usage
    
    if action == 'lead':
        if u['current_month_leads'] >= u['monthly_lead_limit']:
            return {'allowed': False, 'reason': f'Monthly lead limit reached ({u["current_month_leads"]}/{u["monthly_lead_limit"]})'}
    
    if action == 'message':
        if u['current_month_messages'] >= u['monthly_message_limit']:
            return {'allowed': False, 'reason': f'Monthly message limit reached ({u["current_month_messages"]}/{u["monthly_message_limit"]})'}
        if u['current_day_messages'] >= u['daily_message_limit']:
            return {'allowed': False, 'reason': f'Daily message limit reached ({u["current_day_messages"]}/{u["daily_message_limit"]})'}
    
    return {'allowed': True, 'reason': ''}

def increment_usage(account_id: str, action: str):
    """Increment usage counter for an action."""
    if _is_demo():
        _ensure_reset()
        if action == 'lead':
            _demo_usage['current_month_leads'] += 1
        elif action == 'message':
            _demo_usage['current_month_messages'] += 1
            _demo_usage['current_day_messages'] += 1

def get_usage_summary(account_id: str) -> dict:
    """Get current usage summary with limits."""
    _ensure_reset()
    u = _demo_usage
    return {
        'leads': {
            'used': u['current_month_leads'],
            'limit': u['monthly_lead_limit'],
            'remaining': max(0, u['monthly_lead_limit'] - u['current_month_leads']),
            'percentage': round(u['current_month_leads'] / u['monthly_lead_limit'] * 100, 1) if u['monthly_lead_limit'] else 0,
        },
        'messages': {
            'monthly': {
                'used': u['current_month_messages'],
                'limit': u['monthly_message_limit'],
                'remaining': max(0, u['monthly_message_limit'] - u['current_month_messages']),
            },
            'daily': {
                'used': u['current_day_messages'],
                'limit': u['daily_message_limit'],
                'remaining': max(0, u['daily_message_limit'] - u['current_day_messages']),
            },
        },
    }

def set_limits(monthly_leads: int = 200, monthly_messages: int = 400, daily_messages: int = 20):
    """Set usage limits."""
    _demo_usage['monthly_lead_limit'] = monthly_leads
    _demo_usage['monthly_message_limit'] = monthly_messages
    _demo_usage['daily_message_limit'] = daily_messages
    if _is_demo():
        print(f'[Sales/Usage] DEMO -- Limits set: leads={monthly_leads}/mo, msgs={monthly_messages}/mo, {daily_messages}/day')