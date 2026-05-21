"""Telegram Bot Webhook — receives messages from Telegram and routes to EnquiryHandler."""

import json
from fastapi import APIRouter, Request, HTTPException
import config as cfg
from services.enquiry_handler import handle_enquiry
from services.telegram_bot import send_message

router = APIRouter()


@router.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """
    Receive incoming Telegram update via webhook.
    Verifies secret_token if configured.
    """
    # Optional: verify secret token in X-Telegram-Bot-Api-Secret-Token header
    if cfg.TELEGRAM_BOT_WEBHOOK_SECRET:
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if secret != cfg.TELEGRAM_BOT_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid secret token")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Only handle messages
    message = body.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")

    if not chat_id or not text:
        return {"ok": True, "skipped": "no message text"}

    print(f"[TelegramBot] Received from {chat_id}: {text[:80]}")

    # Ignore bot's own messages
    if message.get("from", {}).get("is_bot"):
        return {"ok": True, "skipped": "bot message"}

    # Route to enquiry handler
    reply = handle_enquiry(text, chat_id)

    # Send reply
    sent = send_message(chat_id, reply)
    return {"ok": True, "replied": sent, "chat_id": chat_id}


@router.get("/telegram/webhook")
async def telegram_webhook_info():
    """Return webhook info (GET for healthcheck)."""
    return {
        "status": "active",
        "bot_token_configured": bool(cfg.TELEGRAM_BOT_TOKEN),
        "secret_configured": bool(cfg.TELEGRAM_BOT_WEBHOOK_SECRET),
    }