"""Gmail Client — simulated Gmail API wrapper for reading and sending emails.

All methods work in DEMO_MODE without real Gmail API credentials.
Simulates watch, history tracking, inbox reading, and sending.
"""

import base64
import uuid
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Optional

import config as cfg

# ── Demo state ────────────────────────────────────────────────────

# Simulated inbox messages
_demo_inbox: list[dict] = []

# Simulated Gmail watch state
_demo_watch_state: dict = {
    "history_id": "123456789",
    "is_active": False,
    "email_address": "agent@agentflow.my",
    "last_sync": None,
}

# Demo OAuth tokens (simulated)
_demo_tokens = {
    "access_token": "ya29.demo-access-token-xxxxx",
    "refresh_token": "1//demo-refresh-token-xxxxx",
    "expiry": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
}


# ── Helper: seed demo inbox ───────────────────────────────────────


def _seed_demo_inbox():
    """Seed the demo inbox with sample messages."""
    if _demo_inbox:
        return
    now = datetime.utcnow()
    _demo_inbox.extend(
        [
            {
                "id": "msg-001",
                "thread_id": "thread-001",
                "from_email": "rajesh@techvision.my",
                "from_name": "Rajesh Kumar",
                "to_email": "agent@agentflow.my",
                "subject": "Re: Quick question about TechVision Solutions",
                "body": "Hi Alex, thanks for reaching out. I'd be interested "
                        "in learning more about your solutions. Could you send "
                        "over some information? We're particularly interested "
                        "in cyber insurance.",
                "snippet": "I'd be interested in learning more about your solutions...",
                "received_at": (now - timedelta(hours=2)).isoformat(),
                "is_read": False,
                "labels": ["INBOX", "UNREAD"],
                "is_reply": True,
            },
            {
                "id": "msg-002",
                "thread_id": "thread-002",
                "from_email": "ahmad@greenearth.my",
                "from_name": "Ahmad Ismail",
                "to_email": "agent@agentflow.my",
                "subject": "Re: Ideas for logistics businesses",
                "body": "Hi, thanks for the note. We're actually just about "
                        "to review our fleet insurance. Happy to have a "
                        "discussion. Can you call me at 60112223334?",
                "snippet": "Happy to have a discussion. Can you call me?...",
                "received_at": (now - timedelta(days=1)).isoformat(),
                "is_read": True,
                "labels": ["INBOX"],
                "is_reply": True,
            },
            {
                "id": "msg-003",
                "thread_id": "thread-003",
                "from_email": "noreply@somecompany.com",
                "from_name": "Some Company",
                "to_email": "agent@agentflow.my",
                "subject": "Business Inquiry",
                "body": "Hello, I'm looking for insurance for my new business. "
                        "Please send me a quote for general liability coverage.",
                "snippet": "Please send me a quote for general liability coverage...",
                "received_at": (now - timedelta(hours=6)).isoformat(),
                "is_read": False,
                "labels": ["INBOX", "UNREAD"],
                "is_reply": False,
            },
            {
                "id": "msg-004",
                "thread_id": "thread-004",
                "from_email": "michelle@eliteretail.my",
                "from_name": "Michelle Wong",
                "to_email": "agent@agentflow.my",
                "subject": "Unsubscribe",
                "body": "Please unsubscribe me from your mailing list. "
                        "I am not interested.",
                "snippet": "Please unsubscribe me from your mailing list...",
                "received_at": (now - timedelta(days=3)).isoformat(),
                "is_read": False,
                "labels": ["INBOX", "UNREAD"],
                "is_reply": True,
            },
        ]
    )


# ── GmailClient class ─────────────────────────────────────────────


class GmailClient:
    """Simulated Gmail API client.

    All methods work in DEMO_MODE without real Gmail credentials.
    In production, this would use google-auth and google-api-python-client.
    """

    def __init__(
        self,
        credentials_path: str = "",
        token_path: str = "",
        email_address: str = "agent@agentflow.my",
    ):
        """Initialize the Gmail client.

        Args:
            credentials_path: Path to OAuth client secrets JSON (prod only).
            token_path: Path to stored token JSON (prod only).
            email_address: The Gmail address to operate on.
        """
        self.email_address = email_address
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._authenticated = cfg.DEMO_MODE  # auto-authenticated in demo
        self._service = None  # would be googleapiclient.discovery.build in prod

        if cfg.DEMO_MODE:
            _seed_demo_inbox()
            _demo_watch_state["email_address"] = email_address
            print(f"[Sales/GmailClient] DEMO -- Initialized for {email_address}")

    # ── Authentication ────────────────────────────────────────────

    def authenticate(self) -> bool:
        """Simulate OAuth authentication flow.

        Returns True if authenticated (always True in DEMO_MODE).
        """
        if cfg.DEMO_MODE:
            self._authenticated = True
            return True

        # Real implementation would use:
        #   from google.oauth2.credentials import Credentials
        #   creds = Credentials.from_authorized_user_file(self._token_path)
        #   self._service = build('gmail', 'v1', credentials=creds)
        raise NotImplementedError("Production Gmail auth not implemented")

    @property
    def is_authenticated(self) -> bool:
        return self._authenticated

    def get_token_info(self) -> dict:
        """Return simulated OAuth token info."""
        return dict(_demo_tokens)

    # ── Watch / Push notifications ────────────────────────────────

    def start_watch(self) -> dict:
        """Start watching the inbox for new messages (push notifications).

        Returns the watch state.
        """
        _demo_watch_state["is_active"] = True
        _demo_watch_state["history_id"] = str(uuid.uuid4())
        _demo_watch_state["last_sync"] = datetime.utcnow().isoformat()

        if cfg.DEMO_MODE:
            print("[Sales/GmailClient] DEMO -- Watch started on inbox")

        return dict(_demo_watch_state)

    def stop_watch(self) -> bool:
        """Stop watching the inbox."""
        _demo_watch_state["is_active"] = False
        _demo_watch_state["last_sync"] = datetime.utcnow().isoformat()
        return True

    def get_watch_state(self) -> dict:
        """Get current watch state."""
        return dict(_demo_watch_state)

    def get_history(self, history_id: Optional[str] = None) -> list[dict]:
        """Get history changes since a given history_id.

        In DEMO_MODE, returns simulated history entries.
        """
        if cfg.DEMO_MODE:
            return [
                {
                    "id": "hist-001",
                    "messages_added": ["msg-001"],
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
        return []

    # ── Inbox reading ─────────────────────────────────────────────

    def list_messages(
        self,
        max_results: int = 20,
        query: str = "",
        label_ids: Optional[list[str]] = None,
    ) -> list[dict]:
        """List messages in the inbox.

        Args:
            max_results: Maximum messages to return.
            query: Gmail search query (simulated in demo mode).
            label_ids: Filter by label IDs.

        Returns:
            List of message metadata dicts.
        """
        if not cfg.DEMO_MODE:
            raise NotImplementedError("Production Gmail list not implemented")

        results = list(_demo_inbox)

        if query:
            query_lower = query.lower()
            results = [
                m
                for m in results
                if query_lower in m.get("subject", "").lower()
                or query_lower in m.get("from_email", "").lower()
                or query_lower in m.get("body", "").lower()
            ]

        if label_ids:
            results = [
                m
                for m in results
                if any(label in (m.get("labels", []) or []) for label in label_ids)
            ]

        results.sort(key=lambda m: m.get("received_at", ""), reverse=True)
        return results[:max_results]

    def get_message(self, message_id: str) -> Optional[dict]:
        """Get a single message by ID.

        Args:
            message_id: Gmail message ID.

        Returns:
            Full message dict or None if not found.
        """
        if not cfg.DEMO_MODE:
            raise NotImplementedError("Production Gmail get_message not implemented")

        for msg in _demo_inbox:
            if msg["id"] == message_id:
                return dict(msg)
        return None

    def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read.

        Args:
            message_id: Gmail message ID.

        Returns:
            True on success.
        """
        for msg in _demo_inbox:
            if msg["id"] == message_id:
                msg["is_read"] = True
                if "UNREAD" in (msg.get("labels") or []):
                    msg["labels"].remove("UNREAD")
                return True
        return False

    def mark_as_unread(self, message_id: str) -> bool:
        """Mark a message as unread."""
        for msg in _demo_inbox:
            if msg["id"] == message_id:
                msg["is_read"] = False
                if "UNREAD" not in (msg.get("labels") or []):
                    msg["labels"].append("UNREAD")
                return True
        return False

    # ── Sending ───────────────────────────────────────────────────

    def send_message(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        in_reply_to: Optional[str] = None,
    ) -> dict:
        """Send an email via Gmail.

        In DEMO_MODE, logs the message to the demo inbox as sent.

        Args:
            to_email: Recipient email address.
            subject: Email subject.
            body: Email body (plain text).
            cc: Carbon copy recipients (comma-separated).
            bcc: Blind carbon copy recipients (comma-separated).
            in_reply_to: Message ID to reply to (for threading).

        Returns:
            Dict with message ID and status.
        """
        if cfg.DEMO_MODE:
            msg_id = f"sent-{uuid.uuid4().hex[:12]}"
            sent_record = {
                "id": msg_id,
                "thread_id": in_reply_to or f"thread-{uuid.uuid4().hex[:12]}",
                "from_email": self.email_address,
                "from_name": "Alex (AgentFlow)",
                "to_email": to_email,
                "subject": subject,
                "body": body,
                "snippet": body[:100],
                "received_at": datetime.utcnow().isoformat(),
                "is_read": True,
                "labels": ["SENT"],
                "is_reply": bool(in_reply_to),
            }
            # Don't add to demo_inbox (it's in SENT, not INBOX)
            print(
                f"[Sales/GmailClient] DEMO -- Sent email to {to_email}: "
                f"'{subject[:50]}...'"
            )
            return {
                "id": msg_id,
                "status": "sent",
                "to": to_email,
                "subject": subject,
            }

        # Real implementation would use:
        #   message = MIMEText(body)
        #   message['to'] = to_email
        #   message['subject'] = subject
        #   raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        #   self._service.users().messages().send(userId='me', body={'raw': raw}).execute()
        raise NotImplementedError("Production Gmail send not implemented")

    def send_reply(
        self,
        original_message: dict,
        reply_body: str,
    ) -> dict:
        """Send a reply to an existing message.

        Args:
            original_message: The message dict being replied to.
            reply_body: Reply text.

        Returns:
            Dict with message ID and status.
        """
        subject = original_message.get("subject", "")
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"

        return self.send_message(
            to_email=original_message.get("from_email", ""),
            subject=subject,
            body=reply_body,
            in_reply_to=original_message.get("id"),
        )

    # ── Utility ───────────────────────────────────────────────────

    def get_unread_count(self) -> int:
        """Get count of unread inbox messages."""
        if not cfg.DEMO_MODE:
            raise NotImplementedError("Production not implemented")
        return len(
            [m for m in _demo_inbox if "UNREAD" in (m.get("labels") or [])]
        )

    def get_inbox_summary(self) -> dict:
        """Get a summary of the inbox state."""
        if not cfg.DEMO_MODE:
            raise NotImplementedError("Production not implemented")
        total = len(_demo_inbox)
        unread = self.get_unread_count()
        replies = len([m for m in _demo_inbox if m.get("is_reply")])
        return {
            "total_messages": total,
            "unread": unread,
            "replies": replies,
            "watch_active": _demo_watch_state["is_active"],
            "email_address": self.email_address,
        }