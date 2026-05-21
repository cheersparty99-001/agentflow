"""Telegram Bot sender — sends messages via Telegram Bot API."""

import httpx
import config as cfg

TG_API = "https://api.telegram.org/bot"


def get_bot_token() -> str:
    token = cfg.TELEGRAM_BOT_TOKEN
    if not token:
        print("[TelegramBot] WARNING: TELEGRAM_BOT_TOKEN not configured")
    return token


def send_message(chat_id: int, text: str) -> bool:
    """Send a plain text message to a Telegram chat. Returns True on success."""
    token = get_bot_token()
    if not token:
        return False

    url = f"{TG_API}{token}/sendMessage"
    try:
        resp = httpx.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            print(f"[TelegramBot] API error: {data}")
            return False
        return True
    except Exception as e:
        print(f"[TelegramBot] send_message error: {e}")
        return False


def set_webhook(webhook_url: str, secret_token: str = "") -> bool:
    """Register webhook URL with Telegram. Call on startup."""
    token = get_bot_token()
    if not token:
        return False

    url = f"{TG_API}{token}/setWebhook"
    payload = {"url": webhook_url}
    if secret_token:
        payload["secret_token"] = secret_token

    try:
        resp = httpx.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("ok"):
            print(f"[TelegramBot] Webhook set to {webhook_url}")
            return True
        else:
            print(f"[TelegramBot] setWebhook failed: {data}")
            return False
    except Exception as e:
        print(f"[TelegramBot] setWebhook error: {e}")
        return False


def delete_webhook() -> bool:
    """Remove webhook registration."""
    token = get_bot_token()
    if not token:
        return False
    try:
        resp = httpx.post(f"{TG_API}{token}/deleteWebhook", timeout=15)
        return resp.json().get("ok", False)
    except Exception:
        return False