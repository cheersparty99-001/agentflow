"""AI Chat Assistant router for Flowreach.

POST /api/ai-chat — main chat endpoint backed by Claude via OpenRouter.
GET  /api/ai-chat/init — returns account data for the frontend widget init.
GET  /api/ai-chat/conversations — list saved conversations for this user.
POST /api/ai-chat/conversations — save/update a conversation.
POST /api/ai-chat/conversations/load — load a specific conversation.

Enhancements:
- Conversation persistence (save/load from Supabase)
- Auto-naming conversations based on first message
- Follow-up awareness (reads followup_settings)
"""

import json
import re
import uuid
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from routers.auth import get_current_user
from services.supabase_client import get_supabase, safe_single
import config as cfg

router = APIRouter()

CLAUDE_MODEL = "anthropic/claude-sonnet-4"


def _sb():
    return get_supabase()


async def require_user(request: Request):
    user = await get_current_user(request)
    if not user:
        return None
    return user


# ── Follow-up Settings Loader ──────────────────────────────────────────


def load_followup_settings(account_id: str) -> dict:
    """Load follow-up settings for the account, with sensible defaults."""
    sb = _sb()
    settings = safe_single(
        lambda: sb.table("followup_settings").select("*").eq("account_id", account_id).single(),
        default=None,
    )
    if not settings:
        return {
            "is_enabled": True,
            "followup_delay_days": 2,
            "max_followups": 3,
            "followup_interval_days": 3,
            "channels": ["email"],
            "auto_schedule": True,
            "followup_template": "",
        }
    return settings


# ── Account data loader ──────────────────────────────────────────────────────


def load_account_data(account_id: str) -> dict:
    """Gather real-time account data for the system prompt."""
    sb = _sb()
    data = {}

    # Account info
    account = safe_single(
        lambda: sb.table("accounts").select("agency_name, email, phone, billing_notes, plan").eq("id", account_id).single(),
        default={"agency_name": "Your Company"},
    )
    data["company_name"] = (account or {}).get("agency_name", "Your Company")
    data["plan"] = (account or {}).get("plan", "Starter")

    # Target profiles
    profiles = []
    try:
        result = sb.table("target_profiles").select("*").eq("account_id", account_id).execute()
        profiles = result.data or []
    except Exception:
        profiles = []
    data["target_profiles"] = profiles
    data["has_profile"] = len(profiles) > 0

    # Leads count by status
    statuses = ["cold", "contacted", "replied", "interested", "closed_won", "closed_lost"]
    pipeline = {}
    total_leads = 0
    for s in statuses:
        try:
            q = sb.table("leads").select("id", count="exact").eq("account_id", account_id).eq("status", s).execute()
            count = q.count or 0
        except Exception:
            count = 0
        pipeline[s] = count
        total_leads += count
    data["total_leads"] = total_leads
    data["pipeline"] = pipeline

    # Emails sent this month
    try:
        first_of_month = datetime.utcnow().replace(day=1).isoformat()
        msg_result = (
            sb.table("sales_messages")
            .select("id", count="exact")
            .eq("account_id", account_id)
            .gte("created_at", first_of_month)
            .execute()
        )
        emails_sent = msg_result.count or 0
    except Exception:
        emails_sent = 0
    data["emails_sent_this_month"] = emails_sent

    # Recent activities
    try:
        acts_result = (
            sb.table("lead_activities")
            .select("*")
            .eq("account_id", account_id)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        data["recent_activities"] = acts_result.data or []
    except Exception:
        data["recent_activities"] = []

    # Leads that replied
    try:
        replied = sb.table("leads").select("id", count="exact").eq("account_id", account_id).eq("status", "replied").execute()
        data["replied_leads"] = replied.count or 0
    except Exception:
        data["replied_leads"] = 0

    # Interested leads
    try:
        interested = sb.table("leads").select("id", count="exact").eq("account_id", account_id).eq("status", "interested").execute()
        data["interested_leads"] = interested.count or 0
    except Exception:
        data["interested_leads"] = 0

    return data


# ── Build the system prompt ──────────────────────────────────────────────────


def build_system_prompt(account_data: dict, user_name: str) -> str:
    """Build the system prompt with account data injected."""
    company = account_data.get("company_name", "Your Company")
    total = account_data.get("total_leads", 0)
    pipeline = account_data.get("pipeline", {})
    emails = account_data.get("emails_sent_this_month", 0)
    replied = account_data.get("replied_leads", 0)
    interested = account_data.get("interested_leads", 0)

    profiles = account_data.get("target_profiles", [])
    if profiles:
        p = profiles[0]
        profile_desc = (
            f"Name: {p.get('name', 'N/A')}\n"
            f"Industries: {', '.join(p.get('industries', []) or [])}\n"
            f"Locations: {', '.join(p.get('locations', []) or [])}\n"
            f"Company size target: {p.get('company_size', 'any')}\n"
            f"Min AI score: {p.get('min_ai_score', 5)}"
        )
    else:
        profile_desc = "Not set up yet — no target profile exists."

    activities = account_data.get("recent_activities", [])
    activities_text = ""
    if activities:
        lines = []
        for a in activities:
            t = a.get("activity_type", "note")
            d = a.get("description", "")
            lines.append(f"  - [{t}] {d[:100]}")
        activities_text = "\n".join(lines)

    prompt = f"""You are a helpful AI assistant for Flowreach, a B2B sales automation platform. You are talking to {user_name} from {company}.

Current account data:
- Total leads: {total}
- Pipeline: Cold({pipeline.get('cold', 0)}), Contacted({pipeline.get('contacted', 0)}), Replied({pipeline.get('replied', 0)}), Interested({pipeline.get('interested', 0)}), Closed Won({pipeline.get('closed_won', 0)}), Closed Lost({pipeline.get('closed_lost', 0)})
- Emails sent this month: {emails}
- Leads that replied: {replied}
- Leads interested: {interested}
- Target profile: {profile_desc}

Recent activities:
{activities_text if activities_text else "  (none)"}

You can help the user:
1. Answer any questions about their account — lead counts, pipeline stats, outreach performance, lead quality
2. Set up or update their target profile (always show a draft and ask for confirmation first)
3. Trigger finding new leads (tell them you're searching, then do it in background)

Available actions you can execute:
- SETUP_PROFILE: Create a new target profile with industries, locations, company size, business description
- UPDATE_PROFILE: Update an existing target profile (industries, locations, etc.)
- FIND_LEADS: Run the lead scraper to find new leads. ALWAYS include the search terms:
  "query": what type of business to search for (e.g. "accounting firm", "software development", "marketing agency")
  "location": where to search (e.g. "Kuala Lumpur", "Penang", "Johor Bahru")

Important rules:
- Detect and reply in the user's language automatically
- Be conversational and helpful, not robotic
- Never say "I cannot help with that" — if you don't know something, say so naturally
- For any action that changes data, ALWAYS confirm with the user first. Show a clear draft of what you'll do.
- Keep responses concise — this is a chat, not an essay
- When showing a draft for confirmation, format it clearly with bullet points
- When you need to perform an action (after user confirms), tell the user what you're doing and include action JSON in your response

ACTION MARSHALLING:
When you need to execute an action after the user confirms, output on a new line:
===ACTION===
{{"type": "SETUP_PROFILE"|"UPDATE_PROFILE"|"FIND_LEADS", "data": {{...params}}}}
===END===

For SETUP_PROFILE or UPDATE_PROFILE, data should include:
  "name": "Profile name",
  "industries": ["Accounting", "Tax"],
  "locations": ["Kuala Lumpur", "Selangor"],
  "company_size": "small"|"medium"|"large"|"any",
  "description": "Business description",
  "value_proposition": "Value proposition"

For FIND_LEADS, data MUST include:
  "query": "accounting firm" (what business type to search for — derive from user's natural language)
  "location": "Kuala Lumpur" (where to search — derive from user's natural language)
  
  Example: user says "帮我找 KL 的会计所" -> query="accounting firm", location="Kuala Lumpur"
  Example: user says "find software companies in Penang" -> query="software company", location="Penang"
  Example: user says "我要找槟城的 marketing agency" -> query="marketing agency", location="Penang"

Only output ===ACTION=== when the user has given explicit confirmation.
If the user hasn't confirmed yet, just explain what you'd do and ask."""
    return prompt


# ── Call Claude via OpenRouter ──────────────────────────────────────────────


async def call_claude(system_prompt: str, messages: list[dict]) -> str:
    """Call Claude via OpenRouter and return the response text."""
    api_key = cfg.OPENROUTER_API_KEY
    if not api_key:
        return "AI service is not configured. Please set OPENROUTER_API_KEY in your environment."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    openrouter_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        openrouter_messages.append({"role": m["role"], "content": m["content"]})

    payload = {
        "model": CLAUDE_MODEL,
        "messages": openrouter_messages,
        "temperature": 0.7,
        "max_tokens": 1024,
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                error_text = resp.text[:200]
                print(f"[AI Chat] OpenRouter error {resp.status_code}: {error_text}")
                return f"Sorry, I encountered an error: {resp.status_code}. Please try again."

            data = resp.json()
            choice = data.get("choices", [{}])[0]
            return choice.get("message", {}).get("content", "")
    except httpx.TimeoutException:
        return "Sorry, the AI service timed out. Please try again."
    except Exception as e:
        print(f"[AI Chat] Error calling Claude: {e}")
        return "Sorry, I encountered an unexpected error. Please try again."


# ── Execute action ──────────────────────────────────────────────────────────


async def execute_action(action: dict, account_id: str) -> dict:
    """Execute an action from the AI and return result info."""
    action_type = action.get("type", "")
    data = action.get("data", {})
    sb = _sb()

    if action_type == "SETUP_PROFILE":
        # Create a target profile
        # First, find or create a default business line
        businesses = []
        try:
            biz_result = sb.table("sales_businesses").select("*").eq("account_id", account_id).execute()
            businesses = biz_result.data or []
        except Exception:
            pass

        business_id = None
        if businesses:
            business_id = businesses[0]["id"]
        else:
            # Create a default business line
            biz_id = str(uuid.uuid4())
            try:
                sb.table("sales_businesses").insert({
                    "id": biz_id,
                    "account_id": account_id,
                    "name": data.get("name", "My Business"),
                    "description": data.get("description", ""),
                    "value_proposition": data.get("value_proposition", ""),
                }).execute()
                business_id = biz_id
            except Exception as e:
                print(f"[AI Chat] Error creating business: {e}")
                return {"success": False, "message": str(e)}

        profile_record = {
            "id": str(uuid.uuid4()),
            "account_id": account_id,
            "business_id": business_id,
            "name": data.get("name", "AI-Generated Profile"),
            "industries": data.get("industries", []),
            "locations": data.get("locations", []),
            "company_size": data.get("company_size", "any"),
            "min_ai_score": 5,
            "is_active": True,
            "created_at": datetime.utcnow().isoformat(),
        }

        try:
            result = sb.table("target_profiles").insert(profile_record).execute()
            created = result.data[0] if result.data else profile_record
            return {"success": True, "message": "Target profile created", "profile": created}
        except Exception as e:
            print(f"[AI Chat] Error creating profile: {e}")
            return {"success": False, "message": str(e)}

    elif action_type == "UPDATE_PROFILE":
        # Update existing profile
        profiles = []
        try:
            result = sb.table("target_profiles").select("*").eq("account_id", account_id).execute()
            profiles = result.data or []
        except Exception:
            pass

        if not profiles:
            return {"success": False, "message": "No profile to update. Create one first."}

        profile_id = profiles[0]["id"]
        updates = {}
        if data.get("industries"):
            updates["industries"] = data["industries"]
        if data.get("locations"):
            updates["locations"] = data["locations"]
        if data.get("company_size"):
            updates["company_size"] = data["company_size"]

        if updates:
            try:
                sb.table("target_profiles").update(updates).eq("id", profile_id).eq("account_id", account_id).execute()
                return {"success": True, "message": "Profile updated", "updates": updates}
            except Exception as e:
                print(f"[AI Chat] Error updating profile: {e}")
                return {"success": False, "message": str(e)}
        return {"success": True, "message": "No changes needed"}

    elif action_type == "FIND_LEADS":
        # Trigger the scraper using AI-generated search terms
        try:
            from services.sales.scraper import scrape_google_maps
            from data import leads as data_leads

            # Use AI-generated terms if provided, otherwise fall back to profile
            ai_query = data.get("query", "").strip()
            ai_location = data.get("location", "").strip()

            if ai_query and ai_location:
                # AI provided specific search terms — use them directly
                queries = [ai_query]
                locs = [ai_location]
            else:
                # Fall back to active profile for search parameters
                profiles = []
                try:
                    result = sb.table("target_profiles").select("*").eq("account_id", account_id).eq("is_active", True).execute()
                    profiles = result.data or []
                except Exception:
                    pass

                if profiles:
                    profile = profiles[0]
                    industries = profile.get("industries", [])
                    locations = profile.get("locations", [])
                    queries = industries if industries else ["business"]
                    locs = locations if locations else ["Kuala Lumpur"]
                else:
                    queries = ["business"]
                    locs = ["Kuala Lumpur"]

            total_found = 0
            lead_ids = []
            for query in queries[:3]:
                for loc in locs[:2]:
                    try:
                        leads = await scrape_google_maps(query, loc, max_results=5, account_id=account_id)
                        for ld in leads:
                            # Use the data layer for consistent insertion
                            lead_data = {
                                "company_name": ld.get("company_name", ""),
                                "contact_name": ld.get("contact_name", ""),
                                "phone": ld.get("phone", ""),
                                "email": ld.get("email", ""),
                                "city": ld.get("city", ""),
                                "location": ld.get("city", "") or loc,
                                "industry": query.lower().replace(" ", "_"),
                                "source": "google_maps_ai",
                                "notes": ld.get("notes", f"Found via AI Chat — {query} in {loc}"),
                                "ai_score": min(10, int(ld.get("rating", 0) * 2)),
                                "score": min(10, int(ld.get("rating", 0) * 2)),
                                "status": "cold",
                                "website": ld.get("website", ""),
                                "rating": ld.get("rating", 0),
                            }
                            # Set business_id from first available business
                            try:
                                biz_result = sb.table("sales_businesses").select("id").eq("account_id", account_id).limit(1).execute()
                                if biz_result.data:
                                    lead_data["business_id"] = biz_result.data[0]["id"]
                            except Exception:
                                pass
                            new_lead = data_leads.create_lead(lead_data)
                            if new_lead:
                                lead_ids.append(new_lead.get("id"))
                                total_found += 1
                    except Exception as e:
                        print(f"[AI Chat] Scraper error for {query} in {loc}: {e}")

            return {
                "success": True,
                "message": f"Found {total_found} qualified leads for {ai_query or 'your profile'} in {ai_location or 'target locations'}",
                "lead_count": total_found,
                "lead_ids": lead_ids,
            }
        except Exception as e:
            print(f"[AI Chat] Error running scraper: {e}")
            return {"success": False, "message": str(e)}

    return {"success": False, "message": f"Unknown action type: {action_type}"}


# ── Parse action from AI response ───────────────────────────────────────────


def parse_action_from_response(response: str) -> tuple[str, dict | None]:
    """Parse ===ACTION=== block from AI response.
    Returns (cleaned_response, action_dict_or_None).
    """
    marker = "===ACTION==="
    end_marker = "===END==="
    if marker not in response:
        return response, None

    parts = response.split(marker)
    clean = parts[0].strip()
    remaining = marker.join(parts[1:])
    end_idx = remaining.find(end_marker)
    if end_idx == -1:
        # Malformed, return clean
        return clean, None

    action_text = remaining[:end_idx].strip()
    after = remaining[end_idx + len(end_marker):].strip()

    try:
        action = json.loads(action_text)
    except json.JSONDecodeError as e:
        print(f"[AI Chat] Failed to parse action JSON: {e}")
        return response, None

    return clean + ("\n" + after if after else ""), action


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/api/ai-chat/init")
async def ai_chat_init(request: Request):
    """Return account data needed by the frontend widget."""
    user = await require_user(request)
    if not user:
        return JSONResponse({"authenticated": False}, status_code=401)

    account_id = user.get("account_id")
    if not account_id:
        return JSONResponse({"authenticated": True, "has_profile": False, "company_name": "", "user_name": ""})

    sb = _sb()
    account = safe_single(
        lambda: sb.table("accounts").select("agency_name").eq("id", account_id).single(),
        default={"agency_name": "Your Company"},
    )
    company_name = (account or {}).get("agency_name", "Your Company")

    # Count target profiles
    profiles = []
    try:
        result = sb.table("target_profiles").select("id", count="exact").eq("account_id", account_id).execute()
        profiles = result.data or []
    except Exception:
        pass

    # User name from email
    email = user.get("email", "")
    user_name = email.split("@")[0].replace(".", " ").title() if email else "there"

    return JSONResponse({
        "authenticated": True,
        "has_profile": len(profiles) > 0,
        "company_name": company_name,
        "user_name": user_name,
        "account_id": account_id,
    })


@router.post("/api/ai-chat")
async def ai_chat(request: Request):
    """Main chat endpoint.

    Request body:
    {
        "message": str,
        "conversation_history": [{"role": "user"|"ai", "text": str, "pending_action": null|{...}}]
    }

    Response:
    {
        "reply": str,
        "pending_action": null | { "type": "...", "data": {...} },
        "action_result": null | { "success": bool, "message": str, ... }
    }
    """
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id")
    if not account_id:
        return JSONResponse({"error": "No account found"}, status_code=400)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    user_message = body.get("message", "").strip()
    conversation_history = body.get("conversation_history", [])

    if not user_message:
        return JSONResponse({"error": "Message is required"}, status_code=400)

    # Get user name
    email = user.get("email", "")
    user_name = email.split("@")[0].replace(".", " ").title() if email else "there"

    # Load account data for the system prompt
    account_data = load_account_data(account_id)

    # Check if the user is confirming a pending action from the AI
    pending_action = None
    if conversation_history:
        last_ai_msg = None
        for m in reversed(conversation_history):
            if m.get("role") == "ai" and m.get("pending_action"):
                last_ai_msg = m
                break
        if last_ai_msg:
            pending_action = last_ai_msg.get("pending_action")

    # Check for confirmation keywords
    confirmation_words = ["yes", "confirm", "yeah", "yep", "sure", "go ahead", "do it",
                          "对", "好", "确认", "可以", "ya", "ok", "okay", "correct", "right"]
    is_confirmation = any(user_message.lower().strip().rstrip(".!?") == word
                          for word in confirmation_words) or \
                      any(user_message.lower().strip() in [w, w + ".", w + "!", w + "?"]
                          for w in ["yes", "confirm", "yeah", "yep", "sure", "ok", "okay", "correct"])

    # If user confirmed a pending action, execute it
    if is_confirmation and pending_action:
        action_result = await execute_action(pending_action, account_id)
        # Build a follow-up response based on the result
        if action_result.get("success"):
            if pending_action["type"] in ("SETUP_PROFILE", "UPDATE_PROFILE"):
                reply = (
                    f"Done! Your target profile has been set up successfully.\n"
                    f"I'm now searching for leads that match your profile. This takes about 30 seconds."
                )
                # Also trigger finding leads as a background step
                find_result = await execute_action({"type": "FIND_LEADS", "data": {}}, account_id)
                if find_result.get("success"):
                    count = find_result.get("lead_count", 0)
                    # Count how many leads have email addresses
                    lead_ids = find_result.get("lead_ids", [])
                    email_count = 0
                    if lead_ids:
                        try:
                            sb = _sb()
                            email_result = sb.table("leads").select("email").in_("id", lead_ids).execute()
                            email_count = sum(1 for ld in (email_result.data or []) if ld.get("email"))
                        except Exception:
                            pass
                    reply += (
                        f"\n\nFound {count} qualified leads! {email_count} of them have email addresses "
                        f"ready for outreach. Head to your Leads page to see them."
                    )
                else:
                    reply += f"\n\nNote: Lead search encountered an issue: {find_result.get('message')}"
            elif pending_action["type"] == "FIND_LEADS":
                count = action_result.get("lead_count", 0)
                # Count how many leads have email addresses
                lead_ids = action_result.get("lead_ids", [])
                email_count = 0
                if lead_ids:
                    try:
                        sb = _sb()
                        email_result = sb.table("leads").select("email").in_("id", lead_ids).execute()
                        email_count = sum(1 for ld in (email_result.data or []) if ld.get("email"))
                    except Exception:
                        pass
                reply = (
                    f"Found {count} qualified leads! {email_count} of them have email addresses "
                    f"ready for outreach. Head to your Leads page to see them."
                )
            else:
                reply = f"Done! {action_result.get('message', 'Action completed.')}"
        else:
            reply = f"Sorry, I couldn't complete that action: {action_result.get('message', 'Unknown error')}. Please try again or contact support."

        return JSONResponse({
            "reply": reply,
            "pending_action": None,
            "action_result": action_result,
        })

    # ── Website scraping ────────────────────────────────────────────
    # If user shares a URL, fetch and extract business info
    if user_message.startswith('http://') or user_message.startswith('https://'):
        url = user_message
        try:
            import httpx
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    html = resp.text
                    # Strip HTML tags to extract readable text
                    text = re.sub(r'<[^>]+>', ' ', html)
                    text = re.sub(r'\s+', ' ', text).strip()
                    text = text[:5000]  # Limit to 5000 chars
                    # Prepend scraped content as a system-style instruction
                    user_message = (
                        f"The user shared their company website URL: {url}\n\n"
                        f"Website content extracted:\n{text}\n\n"
                        f"Based on the above website content, extract: company name, what they do, "
                        f"value proposition, target customers. Then generate a target profile draft "
                        f"and ask the user to confirm."
                    )
        except Exception as e:
            print(f"[AI Chat] Website scrape error: {e}")
            # On error, proceed with normal message — Claude will handle it

    # Build messages for Claude
    claude_messages = []
    for m in conversation_history:
        # Skip messages that have already been actioned
        claude_messages.append({
            "role": "assistant" if m["role"] == "ai" else "user",
            "content": m.get("text", ""),
        })
    claude_messages.append({"role": "user", "content": user_message})

    # Build system prompt
    system_prompt = build_system_prompt(account_data, user_name)

    # Call Claude
    response_text = await call_claude(system_prompt, claude_messages)

    # Parse any action from the response
    clean_response, action = parse_action_from_response(response_text)

    return JSONResponse({
        "reply": clean_response,
        "pending_action": action,
        "action_result": None,
    })


# ── Conversation Persistence Endpoints ──────────────────────────────────────


@router.get("/api/ai-chat/conversations")
async def list_conversations(request: Request):
    """List saved conversations for the current user."""
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    user_id = user.get("user_id")
    account_id = user.get("account_id")
    if not user_id or not account_id:
        return JSONResponse({"conversations": []})

    sb = _sb()
    try:
        result = (
            sb.table("chat_conversations")
            .select("id, title, created_at, updated_at, is_archived")
            .eq("account_id", account_id)
            .eq("user_id", user_id)
            .eq("is_archived", False)
            .order("updated_at", desc=True)
            .limit(50)
            .execute()
        )
        return JSONResponse({"conversations": result.data or []})
    except Exception as e:
        print(f"[AI Chat] List conversations error: {e}")
        return JSONResponse({"conversations": []})


@router.post("/api/ai-chat/conversations/save")
async def save_conversation(request: Request):
    """Save/update a conversation. Returns the conversation id.

    Request body:
    {
        \"conversation_id\": \"...\" (optional, omit for new),
        \"title\": \"Conversation title\",
        \"messages\": [...]
    }
    """
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    user_id = user.get("user_id")
    account_id = user.get("account_id")
    if not user_id or not account_id:
        return JSONResponse({"error": "No account found"}, status_code=400)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    conv_id = body.get("conversation_id", "")
    title = body.get("title", "New Conversation")
    messages = body.get("messages", [])
    now = datetime.utcnow().isoformat()

    sb = _sb()

    if conv_id:
        # Update existing conversation
        try:
            sb.table("chat_conversations").update({
                "title": title,
                "messages": json.dumps(messages),
                "updated_at": now,
            }).eq("id", conv_id).eq("account_id", account_id).eq("user_id", user_id).execute()
            return JSONResponse({"conversation_id": conv_id, "saved": True})
        except Exception as e:
            print(f"[AI Chat] Update conversation error: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)
    else:
        # Create new conversation
        new_id = str(uuid.uuid4())
        try:
            sb.table("chat_conversations").insert({
                "id": new_id,
                "account_id": account_id,
                "user_id": user_id,
                "title": title,
                "messages": json.dumps(messages),
                "created_at": now,
                "updated_at": now,
            }).execute()
            return JSONResponse({"conversation_id": new_id, "saved": True})
        except Exception as e:
            print(f"[AI Chat] Create conversation error: {e}")
            return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/ai-chat/conversations/load")
async def load_conversation(request: Request):
    """Load a specific conversation by id."""
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id")
    if not account_id:
        return JSONResponse({"error": "No account found"}, status_code=400)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    conv_id = body.get("conversation_id", "")
    if not conv_id:
        return JSONResponse({"error": "conversation_id required"}, status_code=400)

    sb = _sb()
    try:
        result = sb.table("chat_conversations").select("*").eq("id", conv_id).eq("account_id", account_id).single().execute()
        conv = result.data if result else None
        if not conv:
            return JSONResponse({"error": "Conversation not found"}, status_code=404)

        # Parse messages JSONB
        messages = conv.get("messages", [])
        if isinstance(messages, str):
            messages = json.loads(messages)

        return JSONResponse({
            "conversation_id": conv["id"],
            "title": conv.get("title", "New Conversation"),
            "messages": messages,
            "created_at": conv.get("created_at", ""),
            "updated_at": conv.get("updated_at", ""),
        })
    except Exception as e:
        print(f"[AI Chat] Load conversation error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/api/ai-chat/conversations/delete")
async def delete_conversation(request: Request):
    """Archive a conversation (soft delete)."""
    user = await require_user(request)
    if not user:
        return JSONResponse({"error": "Not authenticated"}, status_code=401)

    account_id = user.get("account_id")
    user_id = user.get("user_id")

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON"}, status_code=400)

    conv_id = body.get("conversation_id", "")

    sb = _sb()
    try:
        sb.table("chat_conversations").update({"is_archived": True}).eq("id", conv_id).eq("account_id", account_id).eq("user_id", user_id).execute()
        return JSONResponse({"deleted": True})
    except Exception as e:
        print(f"[AI Chat] Delete conversation error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)