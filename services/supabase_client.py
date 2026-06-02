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


def safe_update(table, data, id_field, id_value):
    try:
        get_supabase().table(table).update(data).eq(id_field, id_value).execute()
    except Exception as e:
        print(f"[DB] safe_update error: {e}")
