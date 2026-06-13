"""OAuth module for email provider connections (Google, Outlook, SMTP).

Stores per-account tokens in accounts.billing_notes as JSON.
This is a temporary store; migrate to email_connections table later.

Usage:
  from services.sales.oauth import GoogleOAuth
  oauth = GoogleOAuth()
  url = oauth.get_auth_url(account_id, redirect_uri)
  tokens = oauth.handle_callback(code, account_id, redirect_uri)
  service = oauth.get_gmail_service(account_id)
"""

import base64
import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from cryptography.fernet import Fernet

import config as cfg
from services.supabase_client import get_supabase


def _get_fernet() -> Fernet:
    """Derive a Fernet key from the SECRET_KEY."""
    key = hashlib.sha256(cfg.SECRET_KEY.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _encrypt_token(data: dict) -> str:
    """Encrypt a token dict as a Fernet-encrypted string."""
    return _get_fernet().encrypt(json.dumps(data).encode()).decode()


def _decrypt_token(encrypted: str) -> dict:
    """Decrypt a Fernet-encrypted token string back to a dict."""
    return json.loads(_get_fernet().decrypt(encrypted.encode()))

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
]


def _sb():
    return get_supabase()


def _load_billing_notes(raw) -> dict:
    """Parse raw billing_notes, detecting Fernet-encrypted blobs vs legacy JSON."""
    if not raw:
        return {}
    try:
        if isinstance(raw, str) and raw.startswith("gAAAAA"):
            return _decrypt_token(raw)
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _get_stored_connections(account_id: str) -> dict:
    """Read the billing_notes blob for email connections."""
    result = _sb().table("accounts").select("billing_notes").eq("id", account_id).single().execute()
    raw = result.data.get("billing_notes") if result.data else None
    data = _load_billing_notes(raw)
    return data.get("email_connections", {})


def _save_connections(account_id: str, connections: dict):
    """Overwrite the billing_notes blob with updated, encrypted connections."""
    # Read existing data first to not clobber other stored info
    result = _sb().table("accounts").select("billing_notes").eq("id", account_id).single().execute()
    raw = result.data.get("billing_notes") if result.data else None
    existing = _load_billing_notes(raw)
    existing["email_connections"] = connections
    _sb().table("accounts").update({"billing_notes": _encrypt_token(existing)}).eq("id", account_id).execute()


class GoogleOAuth:
    """Google OAuth 2.0 for Gmail/GWS per-account connections."""

    def __init__(self):
        self.client_id = getattr(cfg, "GMAIL_CLIENT_ID", "")
        self.client_secret = getattr(cfg, "GMAIL_CLIENT_SECRET", "")

    def get_auth_url(self, account_id: str, redirect_uri: str) -> str:
        """Generate the Google OAuth consent URL for a given account."""
        params = (
            f"client_id={self.client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={' '.join(SCOPES)}"
            f"&access_type=offline"
            f"&prompt=consent"  # force refresh_token every time
            f"&state={account_id}"
        )
        return f"{GOOGLE_AUTH_URL}?{params}"

    def handle_callback(self, code: str, account_id: str, redirect_uri: str) -> dict:
        """Exchange auth code for tokens and store them."""
        import httpx

        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            raise ValueError(f"Google OAuth error: {data.get('error_description', data['error'])}")

        access_token = data.get("access_token", "")
        refresh_token = data.get("refresh_token", "")
        expires_in = data.get("expires_in", 3600)
        expires_at = (datetime.utcnow() + timedelta(seconds=expires_in)).isoformat()

        # Fetch the user's email address from Google
        user_info = httpx.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        ).json()
        email = user_info.get("email", "")
        if not email:
            email = "unknown@google.com"

        # Build connection record
        conn = {
            "provider": "google",
            "email": email,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": expires_at,
            "scopes": " ".join(SCOPES),
            "connected_at": datetime.utcnow().isoformat(),
        }

        # Store in accounts table
        connections = _get_stored_connections(account_id)
        connections["google"] = conn
        _save_connections(account_id, connections)

        print(f"[OAuth] Google connected: {email} for account {account_id[:12]}...")
        return conn

    def get_connection(self, account_id: str) -> Optional[dict]:
        """Get the stored Google connection for an account, refreshing if needed."""
        connections = _get_stored_connections(account_id)
        conn = connections.get("google")
        if not conn:
            return None

        # Check if token is expired
        expires_at = conn.get("expires_at")
        if expires_at:
            try:
                exp = datetime.fromisoformat(expires_at)
                if datetime.utcnow() >= exp - timedelta(minutes=5):
                    # Refresh
                    conn = self._refresh_token(account_id, conn)
            except (ValueError, TypeError):
                pass

        return conn

    def _refresh_token(self, account_id: str, conn: dict) -> dict:
        """Refresh an expired access_token."""
        import httpx

        refresh_token = conn.get("refresh_token", "")
        if not refresh_token:
            return conn

        resp = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            timeout=15,
        )
        data = resp.json()
        if "error" in data:
            print(f"[OAuth] Token refresh failed: {data.get('error')}")
            return conn

        if "access_token" in data:
            conn["access_token"] = data["access_token"]
        if "expires_in" in data:
            conn["expires_at"] = (
                datetime.utcnow() + timedelta(seconds=data["expires_in"])
            ).isoformat()

        # Persist refreshed tokens
        connections = _get_stored_connections(account_id)
        connections["google"] = conn
        _save_connections(account_id, connections)
        print(f"[OAuth] Token refreshed for {conn['email']}")
        return conn

    def get_gmail_service(self, account_id: str):
        """Create an authenticated Gmail API service for this account's connection."""
        conn = self.get_connection(account_id)
        if not conn:
            raise RuntimeError(f"No Google connection found for account {account_id}")

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=conn["access_token"],
            refresh_token=conn.get("refresh_token"),
            token_uri=GOOGLE_TOKEN_URL,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=conn.get("scopes", " ".join(SCOPES)),
        )
        service = build("gmail", "v1", credentials=creds)
        return service, conn.get("email", "")

    def disconnect(self, account_id: str) -> bool:
        """Remove the Google connection for an account."""
        connections = _get_stored_connections(account_id)
        if "google" not in connections:
            return False
        del connections["google"]
        _save_connections(account_id, connections)
        print(f"[OAuth] Google disconnected for account {account_id[:12]}...")
        return True
