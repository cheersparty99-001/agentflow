"""Simple CSRF protection using itsdangerous signed tokens."""
from itsdangerous import URLSafeTimedSerializer
import config as cfg

_serializer = URLSafeTimedSerializer(cfg.SECRET_KEY, salt="csrf-token")


def generate_csrf_token() -> str:
    return _serializer.dumps("csrf")


def validate_csrf_token(token: str) -> bool:
    try:
        _serializer.loads(token, max_age=3600)
        return True
    except Exception:
        return False
