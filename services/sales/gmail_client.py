"""Gmail Client — real Gmail API wrapper.

Uses Gmail API with OAuth2 refresh token for all operations.
No demo/simulation branches.
"""

import base64
import uuid
import os
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import config as cfg


def _get_gmail_creds():
    """Get Google OAuth2 credentials from config."""
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
        body.replace("\n", "<br>\n") + "<br><br><hr><small>Sent via Flowreach Sales Automation</small>",
        "html", "utf-8",
    )
    msg.attach(text_part)
    msg.attach(html_part)

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


class GmailClient:
    """Gmail API client. Supports per-account OAuth tokens or config fallback."""

    def __init__(self, email_address: str = "", account_id: str = ""):
        self.email_address = email_address
        self._authenticated = False
        self._service = None
        self._creds = None
        self._account_id = account_id
        try:
            self.authenticate()
        except Exception as e:
            print(f"[Sales/GmailClient] Init auth error (non-fatal): {e}")

    # ── Auth ──

    def authenticate(self) -> bool:
        if self._authenticated and self._service:
            return True

        # Per-account OAuth (new flow)
        if self._account_id:
            try:
                from services.sales.oauth import GoogleOAuth
                service, email = GoogleOAuth().get_gmail_service(self._account_id)
                self._service = service
                self.email_address = email or self.email_address
                self._authenticated = True
                print(f"[Sales/GmailClient] Authenticated via OAuth: {self.email_address}")
                return True
            except Exception as e:
                print(f"[Sales/GmailClient] Per-account OAuth failed, falling back: {e}")

        # Config-based fallback (old flow)
        if not all([cfg.GMAIL_CLIENT_ID, cfg.GMAIL_CLIENT_SECRET, cfg.GMAIL_REFRESH_TOKEN]):
            print("[Sales/GmailClient] ERROR: Missing Gmail credentials in config")
            return False

        try:
            from googleapiclient.discovery import build
            self._creds = _get_gmail_creds()
            self._service = build("gmail", "v1", credentials=self._creds)
            self.email_address = self.email_address or getattr(cfg, "GMAIL_FROM", "")
            self._authenticated = True
            print(f"[Sales/GmailClient] Authenticated via config: {self.email_address}")
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
        """Send an email via Gmail API."""
        if not self._authenticated or not self._service:
            auth_ok = self.authenticate()
            if not auth_ok:
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
        if not self._service:
            return None
        try:
            msg = self._service.users().messages().get(userId="me", id=message_id, format="full").execute()
            return msg
        except Exception as e:
            print(f"[Sales/GmailClient] Get message error: {e}")
            return None

    def mark_as_read(self, message_id: str) -> bool:
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
        print("[Sales/GmailClient] Watch not implemented (requires Gmail push notifications setup)")
        return {}

    def stop_watch(self) -> bool:
        return True

    def get_watch_state(self) -> dict:
        return {"authenticated": self._authenticated, "email_address": self.email_address}

    def get_history(self, history_id: Optional[str] = None) -> list[dict]:
        return []

    # ── Reply Detection ──

    def check_replies(self, since_minutes: int = 60) -> list[dict]:
        """Check for replies to our sent emails in the last N minutes.

        Queries Gmail API for recent inbox messages that are replies.

        Returns list of reply dicts with: from, subject, body, thread_id, message_id.
        """
        if not self._service:
            return []

        import re
        from googleapiclient.errors import HttpError

        replies = []
        try:
            query = f"in:inbox subject:(Re:) newer_than:{since_minutes}m"
            response = self._service.users().messages().list(
                userId="me", q=query, maxResults=20
            ).execute()

            messages = response.get("messages", [])
            for msg_summary in messages:
                msg = self._service.users().messages().get(
                    userId="me", id=msg_summary["id"], format="full"
                ).execute()

                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                subject = headers.get("Subject", "")
                from_email = headers.get("From", "")
                to_email = headers.get("To", "")

                # Extract body
                body = ""
                payload = msg.get("payload", {})
                if "parts" in payload:
                    for part in payload["parts"]:
                        if part.get("mimeType") == "text/plain":
                            data = part.get("body", {}).get("data", "")
                            if data:
                                body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                                break
                elif "body" in payload:
                    data = payload.get("body", {}).get("data", "")
                    if data:
                        body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

                # Only keep actual replies (Re: prefix)
                if subject.startswith("Re:") or subject.startswith("RE:"):
                    from_name = from_email
                    match = re.match(r'^"?([^"<]*)"?\s*<', from_email)
                    if match:
                        from_name = match.group(1).strip() or from_email

                    replies.append({
                        "from_email": from_email,
                        "from_name": from_name,
                        "subject": subject,
                        "body": body[:1000],
                        "thread_id": msg.get("threadId", ""),
                        "message_id": msg["id"],
                        "received_at": datetime.utcnow().isoformat(),
                    })

            if replies:
                print(f"[Sales/GmailClient] Found {len(replies)} reply/replies in inbox")
                for r in replies:
                    print(f"  From: {r['from_name']} <{r['from_email']}> — Subject: {r['subject']}")
            else:
                print(f"[Sales/GmailClient] No replies found in last {since_minutes} minutes")

        except HttpError as e:
            print(f"[Sales/GmailClient] Reply check error: {e}")

        return replies

    def get_unread_count(self) -> int:
        if not self._service:
            return 0
        try:
            profile = self._service.users().getProfile(userId="me").execute()
            return profile.get("messagesTotal", 0)
        except Exception:
            return 0

    def get_inbox_summary(self) -> dict:
        return {"authenticated": self._authenticated, "email_address": self.email_address}