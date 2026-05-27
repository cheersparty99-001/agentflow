# AgentFlow Project

## Stack
- FastAPI + Jinja2 + Tailwind CSS
- Supabase (PostgreSQL)
- DEMO_MODE=true in .env — all data in-memory

## Patterns
- Templates: `env = Environment(loader=FileSystemLoader("templates"))`, then `template.render(...)` returning `HTMLResponse(html)`
- Demo data: stored in `request.app.state.*` dictionaries/lists
- Auth: `get_current_user(request)` returns user dict with `account_id`, `email`
- Demo account_id: `00000000-0000-0000-0000-000000000001`
- All routers use `from routers.auth import get_current_user`

## IMPORTANT RULES
- DO NOT modify ANY existing insurance-related code (routers/policies.py, services/renewal_reminder.py, services/enquiry_handler.py, database/schema.sql)
- Sales Automation is a standalone module — no cross-dependencies with insurance
- All sales features must work in DEMO_MODE=true without Supabase
- Use the same Jinja2 pattern as existing routers