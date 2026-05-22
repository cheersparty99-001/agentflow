"""Supabase client singleton with demo fallback."""
from supabase import create_client, Client
import config as cfg

_supabase: Client | None = None


def get_supabase() -> Client | None:
    global _supabase
    if _supabase is None:
        url = cfg.SUPABASE_URL
        key = cfg.SUPABASE_SERVICE_KEY or cfg.SUPABASE_KEY
        if not url or not key:
            if cfg.DEMO_MODE:
                return None
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        try:
            _supabase = create_client(url, key)
        except Exception as e:
            print(f"[Supabase] Failed to create client: {e}")
            if cfg.DEMO_MODE:
                return None
            raise
    return _supabase


def safe_single(query_fn, default=None):
    """Execute a supabase single() query and return the data, or default on connection error."""
    try:
        return query_fn().data
    except Exception as e:
        if cfg.DEMO_MODE:
            return default
        raise


def safe_multi(query_fn, default=None):
    """Execute a supabase query and return data list, or default on connection error."""
    try:
        return query_fn().data or default or []
    except Exception as e:
        if cfg.DEMO_MODE:
            return default or []
        raise


def safe_count(query_fn, default=0):
    """Execute a supabase count query and return count, or default on connection error."""
    try:
        result = query_fn()
        return result.count
    except Exception as e:
        if cfg.DEMO_MODE:
            return default
        raise


def safe_insert(table_name: str, data: dict):
    """Execute a supabase insert, ignoring connection errors in demo mode."""
    sb = get_supabase()
    if sb is None:
        return
    try:
        sb.table(table_name).insert(data).execute()
    except Exception as e:
        if cfg.DEMO_MODE:
            pass  # silently accept in demo mode
        else:
            raise


def safe_update(table_name: str, data: dict, eq_field: str, eq_value: str):
    """Execute a supabase update, ignoring connection errors in demo mode."""
    sb = get_supabase()
    if sb is None:
        return
    try:
        sb.table(table_name).update(data).eq(eq_field, eq_value).execute()
    except Exception as e:
        if cfg.DEMO_MODE:
            pass
        else:
            raise


def safe_delete(table_name: str, eq_field: str, eq_value: str):
    """Execute a supabase delete, ignoring connection errors in demo mode."""
    sb = get_supabase()
    if sb is None:
        return
    try:
        sb.table(table_name).delete().eq(eq_field, eq_value).execute()
    except Exception as e:
        if cfg.DEMO_MODE:
            pass
        else:
            raise