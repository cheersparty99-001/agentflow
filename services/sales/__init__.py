"""Sales Automation services package."""

from .scraper import scrape_leads
from .qualifier import qualify_lead, qualify_leads
from .message_gen import generate_message, TEMPLATES
from .outreach import send_outreach, run_campaign
from .reply_handler import handle_reply
from .gmail_client import GmailClient

__all__ = [
    "scrape_leads",
    "qualify_lead",
    "qualify_leads",
    "generate_message",
    "TEMPLATES",
    "send_outreach",
    "run_campaign",
    "handle_reply",
    "GmailClient",
]