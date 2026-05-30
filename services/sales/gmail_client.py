"""Gmail Client — real Gmail API wrapper with demo fallback.

DEMO_MODE: uses in-memory simulation.
Production: uses Gmail API with OAuth2 refresh token.
"""

import base64
import uuid
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import config as cfg

# ── Demo state ──

_demo_inbox: list[dict] = []
_demo_watch_state: dict = {
    "history_id": "123456789",
    "is_active": False,
    "email_address": "",
    "last_sync": None,
}
_demo_tokens = {
    "access_token": "ya29.demo-access-token-xxxxx",
    "refresh_token": "1//demo-refresh-token-xxxxx",
    "expiry": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
}


def _seed_demo_inbox():
    if _demo_inbox:
        return
    now = datetime.utcnow()
    _demo_inbox.extend([
        {"id": "msg-001", "thread_id": "thread-001", "from_email": "rajesh@techvision.my", "from_name": "Rajesh Kumar", "to_email": "agent@agentflow.my", "subject": "Re: Quick question", "body": "Hi, I'd be interested in learning more about your solutions.", "snippet": "I'd be interested...", "received_at": (now - timedelta(hours=2)).isoformat(), "is_read": False, "labels": ["INBOX", "UNREAD"], "is_reply": True},
        {"id": "msg-002", "thread_id": "thread-002", "from_email": "ahmad@greenearth.my", "from_name": "Ahmad Ismail", "to_email": "agent@agentflow.my", "subject": "Re: Ideas for logistics", "body": "Happy to have a discussion. Can you call me?", "snippet": "Happy to have a discussion...", "received_at": (now - timedelta(days=1)).isoformat(), "is_read": True, "labels": ["INBOX"], "is_reply": True},
        {"id": "msg-003", "thread_id": "thread-003", "from_email": "noreply@somecompany.com", "from_name": "Some Company", "to_email": "agent@agentflow.my", "subject": "Business Inquiry", "body": "Please send me a quote.", "snippet": "Please send me a quote...", "received_at": (now - timedelta(hours=6)).isoformat(), "is_read": False, "labels": ["INBOX", "UNREAD"], "is_reply": False},
        {"id": "msg-004", "thread_id": "thread-004", "from_email": "michelle@eliteretail.my", "from_name": "Michelle Wong", "to_email": "agent@agentflow.my", "subject": "Unsubscribe", "body": "Please unsubscribe me.", "snippet": "Please unsubscribe me...", "received_at": (now - timedelta(days=3)).isoformat(), "is_read": False, "labels": ["INBOX", "UNREAD"], "is_reply": True},
    ])


def _is_demo() -> bool:
    return getattr(cfg, "DEMO_MODE", True)


def _get_gmail_creds():
    """Get Google OAuth2 credentials from config.
    Uses the scopes already encoded in the refresh token."""
    from google.oauth2.credentials import Credentials
    return Credentials(
        None,
        refresh_token=cfg.GMAIL_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=cfg.GMAIL_CLIENT_ID,
        client_secret=cfg.GMAIL_CLIENT_SECRET,
    )


def _create_message(to: str, subject: str, body: str, from_email: str) -> dict:
    """Create a MIME message for Gmail API."""
    msg = MIMEMultipart("alternative")
    msg["To"] = to
    msg["From"] = from_email
    msg["Subject"] = subject

    text_part = MIMEText(body, "plain", "utf-8")
    html_part = MIMEText(
        body.replace("\n", "<br>\n") + "<br><br><hr><small>Sent via AgentFlow Sales Automation</small>",
        "html", "utf-8",
    )
    msg.attach(text_part)
    msg.attach(html_part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


class GmailClient:
    """Gmail API client with demo mode fallback."""

    def __init__(self, email_address: str = ""):
        self.email_address = email_address or getattr(cfg, "GMAIL_FROM", "")
        self._authenticated = False
        self._service = None
        self._creds = None

        if _is_demo():
            _seed_demo_inbox()
            _demo_watch_state["email_address"] = self.email_address
            print(f"[Sales/GmailClient] DEMO -- Initialized for {self.email_address}")
        else:
            self.authenticate()

    # ── Auth ──

    def authenticate(self) -> bool:
        if _is_demo():
            self._authenticated = True
            return True

        if not all([cfg.GMAIL_CLIENT_ID, cfg.GMAIL_CLIENT_SECRET, cfg.GMAIL_REFRESH_TOKEN]):
            print("[Sales/GmailClient] ERROR: Missing Gmail credentials in config")
            return False

        try:
            from googleapiclient.discovery import build
            self._creds = _get_gmail_creds()
            self._service = build("gmail", "v1", credentials=self._creds)
            self._authenticated = True
            print(f"[Sales/GmailClient] Authenticated as {self.email_address}")
            return True
        except Exception as e:
            print(f"[Sales/GmailClient] Auth error: {e}")
            return False

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    # ── Sending ──

    def send_message(self, to_email: str, subject: str, body: str,
                     cc: Optional[str] = None, bcc: Optional[str] = None,
                     in_reply_to: Optional[str] = None) -> dict:
        """Send an email. Demo mode: logs. Production: real Gmail API call."""
        if _is_demo():
            msg_id = f"sent-{uuid.uuid4().hex[:12]}"
            print(f"[Sales/GmailClient] DEMO -- Would send email to {to_email}: '{subject}'")
            return {"id": msg_id, "status": "sent", "to": to_email, "subject": subject, "demo": True}

        if not self._authenticated or not self._service:
            return {"status": "error", "reason": "Not authenticated"}

        try:
            from_email = self.email_address or cfg.GMAIL_FROM
            message = _create_message(to_email, subject, body, from_email)
            sent = self._service.users().messages().send(userId="me", body=message).execute()
            msg_id = sent.get("id", "")
            print(f"[Sales/GmailClient] Email sent successfully — ID: {msg_id}, To: {to_email}, Subject: {subject}")
            return {"id": msg_id, "status": "sent", "to": to_email, "subject": subject, "message_id": msg_id}
        except Exception as e:
            error_msg = str(e)
            print(f"[Sales/GmailClient] Send error: {error_msg}")
            return {"status": "failed", "error": error_msg}

    def send_reply(self, original_message: dict, reply_body: str) -> dict:
        subject = original_message.get("subject", "")
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"
        return self.send_message(
            to_email=original_message.get("from_email", ""),
            subject=subject,
            body=reply_body,
            in_reply_to=original_message.get("id"),
        )

    # ── Inbox reading ──

    def list_messages(self, max_results: int = 20, query: str = "",
                      label_ids: Optional[list[str]] = None) -> list[dict]:
        if _is_demo():
            results = list(_demo_inbox)
            if query:
                q = query.lower()
                results = [m for m in results if q in m.get("subject", "").lower()
                           or q in m.get("from_email", "").lower()
                           or q in m.get("body", "").lower()]
            if label_ids:
                results = [m for m in results
                           if any(l in (m.get("labels") or []) for l in label_ids)]
            results.sort(key=lambda m: m.get("received_at", ""), reverse=True)
            return results[:max_results]

        if not self._service:
            return []
        try:
            response = self._service.users().messages().list(
                userId="me", maxResults=max_results, q=query,
                labelIds=label_ids or [],
            ).execute()
            return response.get("messages", [])
        except Exception as e:
            print(f"[Sales/GmailClient] List error: {e}")
            return []

    def get_message(self, message_id: str) -> Optional[dict]:
        if _is_demo():
            for msg in _demo_inbox:
                if msg["id"] == message_id:
                    return dict(msg)
            return None
        if not self._service:
            return None
        try:
            msg = self._service.users().messages().get(userId="me", id=message_id, format="full").execute()
            return msg
        except Exception as e:
            print(f"[Sales/GmailClient] Get message error: {e}")
            return None

    def mark_as_read(self, message_id: str) -> bool:
        if _is_demo():
            for msg in _demo_inbox:
                if msg["id"] == message_id:
                    msg["is_read"] = True
                    if "UNREAD" in (msg.get("labels") or []):
                        msg["labels"].remove("UNREAD")
                    return True
            return False
        if not self._service:
            return False
        try:
            self._service.users().messages().modify(
                userId="me", id=message_id, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except Exception:
            return False

    def mark_as_unread(self, message_id: str) -> bool:
        if _is_demo():
            for msg in _demo_inbox:
                if msg["id"] == message_id:
                    msg["is_read"] = False
                    if "UNREAD" not in (msg.get("labels") or []):
                        msg["labels"].append("UNREAD")
                    return True
            return False
        if not self._service:
            return False
        try:
            self._service.users().messages().modify(
                userId="me", id=message_id, body={"addLabelIds": ["UNREAD"]}
            ).execute()
            return True
        except Exception:
            return False

    # ── Watch / Push ──

    def start_watch(self) -> dict:
        _demo_watch_state["is_active"] = True
        _demo_watch_state["history_id"] = str(uuid.uuid4())
        _demo_watch_state["last_sync"] = datetime.utcnow().isoformat()
        if _is_demo():
            print("[Sales/GmailClient] DEMO -- Watch started")
        return dict(_demo_watch_state)

    def stop_watch(self) -> bool:
        _demo_watch_state["is_active"] = False
        _demo_watch_state["last_sync"] = datetime.utcnow().isoformat()
        return True

    def get_watch_state(self) -> dict:
        return dict(_demo_watch_state)

    def get_history(self, history_id: Optional[str] = None) -> list[dict]:
        if _is_demo():
            return [{"id": "hist-001", "messages_added": ["msg-001"], "timestamp": datetime.utcnow().isoformat()}]
        return []

    # ── Utility ──

    def get_unread_count(self) -> int:
        if _is_demo():
            return len([m for m in _demo_inbox if "UNREAD" in (m.get("labels") or [])])
        if not self._service:
            return 0
        try:
            profile = self._service.users().getProfile(userId="me").execute()
            return profile.get("messagesTotal", 0)
        except Exception:
            return 0

    def get_inbox_summary(self) -> dict:
        if _is_demo():
            total = len(_demo_inbox)
            unread = self.get_unread_count()
            replies = len([m for m in _demo_inbox if m.get("is_reply")])
            return {"total_messages": total, "unread": unread, "replies": replies,
                    "watch_active": _demo_watch_state["is_active"],
                    "email_address": self.email_address}
        return {"authenticated": self._authenticated, "email_address": self.email_address}
