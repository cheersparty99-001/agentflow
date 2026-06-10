-- Flowreach Onboarding Schema
-- Invite-only registration system

CREATE TABLE IF NOT EXISTS onboarding_tokens (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  token UUID DEFAULT gen_random_uuid() UNIQUE,
  created_by TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  used BOOLEAN DEFAULT FALSE,
  account_id TEXT
);

ALTER TABLE accounts ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'active';
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS plan TEXT;