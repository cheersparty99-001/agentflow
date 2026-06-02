# Flowreach Simplification Plan

## Current structure
Flowreach was built for insurance agencies but pivoted to B2B Sales Automation.

## Files to DELETE
- /root/agentflow/routers/policies.py (entire file)
- /root/agentflow/routers/agents.py (entire file)
- /root/agentflow/templates/policies.html (entire file)
- /root/agentflow/templates/agents.html (entire file)

## Files to MODIFY

### /root/agentflow/main.py
- Remove `policies` and `agents` from the import line
- Remove `app.include_router(policies.router)` 
- Remove `app.include_router(agents.router)`
- Remove all insurance demo data seeding (demo_logs, demo_policies, rich_logs)
- Remove Telegram webhook setup (that was for the insurance bot)
- Keep Sales Automation seed data

### /root/agentflow/templates/base.html
- Change subtitle from "Insurance Agent Platform" to "B2B Sales Automation Platform"
- Remove "Policies" link from sidebar
- Remove "Agents" link from sidebar
- Remove "Sales Automation" subheading (since everything IS sales now)
- Keep: Dashboard, Sales Dashboard, Leads, Pipeline, Settings, Admin
- Make sure all href paths point correctly

### /root/agentflow/templates/dashboard.html
- This is the old insurance dashboard. Replace with a redirect to /sales/dashboard OR
- Make it show Sales Automation stats instead of insurance stats
- Remove all references to policies, insurance types, renewal counts

### /root/agentflow/routers/dashboard.py
- This serves the old insurance dashboard. Replace to redirect to /sales/dashboard OR
- Replace to render sales dashboard template with sales data

### /root/agentflow/database/schema.sql
- Remove insurance tables: policies, agent_logs insurance parts
- Keep accounts, users tables (needed for auth/login)

### /root/agentflow/routers/admin.py
- Remove any insurance-specific admin sections
- Keep account management

## Sidebar structure (after changes)
```
Flowreach
[DEMO MODE]
EN BM 中文

Dashboard        -> /dashboard (shows sales stats)
Sales Dashboard  -> /sales/dashboard
Leads            -> /sales/leads
Pipeline         -> /sales/pipeline
Settings         -> /settings
Admin            -> /admin (admin only)

[user email]
Logout
```

## IMPORTANT
- Do NOT delete sales-related files
- Do NOT delete auth, admin, settings routers
- Do NOT delete login template
- Keep all sales services (services/sales/ folder)
- Keep all sales templates (templates/sales/ folder)
- Keep sales router (routers/sales.py)
- After changes, verify the app starts with `python -c "import main"`