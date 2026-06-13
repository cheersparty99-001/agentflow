"""Simple in-memory rate limiter for production use."""
import time
from collections import defaultdict
from fastapi import HTTPException
from starlette.requests import Request

class RateLimiter:
    def __init__(self):
        self._stores = {}

    def _get_store(self, name: str) -> dict:
        if name not in self._stores:
            self._stores[name] = {}
        return self._stores[name]

    def check(self, name: str, key: str, max_requests: int, window_seconds: int):
        store = self._get_store(name)
        now = time.time()
        window_start = now - window_seconds

        # Clean old entries
        store[key] = [t for t in store.get(key, []) if t > window_start]

        if len(store.get(key, [])) >= max_requests:
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Try again in {window_seconds} seconds."
            )

        store[key].append(now)

rate_limiter = RateLimiter()
