"""Supabase client singleton."""
import os
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client

_client = None


def get_supabase():
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        _client = create_client(url, key)
    return _client


def safe_single(query_fn, default=None):
    try:
        return query_fn()
    except Exception:
        return default


def safe_multi(query_fn, default=None):
    """Execute a multi-row query safely. query_fn should return a query builder
    that must call .execute() internally."""
    try:
        return query_fn()
    except Exception:
        return default


def safe_count(table, column="id", filters: dict = None, default=0):
    """Count rows in a table with optional filters."""
    try:
        q = get_supabase().table(table).select(column, count="exact")
        if filters:
            for k, v in filters.items():
                q = q.eq(k, v)
        result = q.execute()
        return getattr(result, "count", 0) or 0
    except Exception as e:
        print(f"[DB] safe_count error: {e}")
        return default


def safe_insert(table, data, returning="representation"):
    """Insert data into a table safely."""
    try:
        q = get_supabase().table(table).insert(data)
        if returning == "minimal":
            q = q.execute()
            return None
        result = q.execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"[DB] safe_insert error: {e}")
        return None


def safe_update(table, data, id_field, id_value):
    try:
        get_supabase().table(table).update(data).eq(id_field, id_value).execute()
    except Exception as e:
        print(f"[DB] safe_update error: {e}")
