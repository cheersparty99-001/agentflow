-- Sales Automation Module Schema for Supabase

-- Sales leads scraped or imported
CREATE TABLE IF NOT EXISTS sales_leads (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id),
  source TEXT NOT NULL DEFAULT 'manual',          -- 'linkedin', 'google_maps', 'facebook', 'manual', 'import'
  company_name TEXT,
  website TEXT,
  phone TEXT,
  email TEXT,
  address TEXT,
  city TEXT,
  state TEXT,
  country TEXT DEFAULT 'Malaysia',
  industry TEXT,
  employee_count INTEGER,
  contact_name TEXT,
  contact_title TEXT,
  social_url TEXT,
  notes TEXT,
  raw_data JSONB DEFAULT '{}',
  status TEXT DEFAULT 'new',                      -- 'new', 'qualified', 'contacted', 'replied', 'converted', 'unqualified'
  score INTEGER DEFAULT 0,
  qualified_at TIMESTAMP,
  contacted_at TIMESTAMP,
  converted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Outreach campaigns
CREATE TABLE IF NOT EXISTS sales_campaigns (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id),
  name TEXT NOT NULL,
  description TEXT,
  target_industry TEXT[],
  target_city TEXT[],
  min_employees INTEGER DEFAULT 0,
  max_employees INTEGER DEFAULT 999999,
  template_subject TEXT,
  template_body TEXT,
  status TEXT DEFAULT 'draft',                    -- 'draft', 'active', 'paused', 'completed'
  total_leads INTEGER DEFAULT 0,
  sent_count INTEGER DEFAULT 0,
  reply_count INTEGER DEFAULT 0,
  conversion_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Individual outreach messages sent
CREATE TABLE IF NOT EXISTS sales_outreach_log (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id),
  campaign_id UUID REFERENCES sales_campaigns(id),
  lead_id UUID REFERENCES sales_leads(id),
  channel TEXT NOT NULL DEFAULT 'email',          -- 'email', 'linkedin', 'whatsapp'
  subject TEXT,
  body TEXT,
  status TEXT DEFAULT 'pending',                  -- 'pending', 'sent', 'delivered', 'bounced', 'replied', 'failed'
  sent_at TIMESTAMP,
  delivered_at TIMESTAMP,
  reply_at TIMESTAMP,
  reply_text TEXT,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Inbound reply handling status
CREATE TABLE IF NOT EXISTS sales_reply_tracker (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id),
  outreach_id UUID REFERENCES sales_outreach_log(id),
  lead_id UUID REFERENCES sales_leads(id),
  from_email TEXT,
  from_name TEXT,
  subject TEXT,
  body TEXT,
  sentiment TEXT DEFAULT 'neutral',               -- 'positive', 'neutral', 'negative', 'unsubscribe'
  auto_reply TEXT,
  auto_reply_sent BOOLEAN DEFAULT false,
  handled_at TIMESTAMP DEFAULT NOW(),
  created_at TIMESTAMP DEFAULT NOW()
);

-- Gmail watch / history tracking
CREATE TABLE IF NOT EXISTS sales_gmail_watch (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id),
  email_address TEXT NOT NULL,
  history_id TEXT,
  is_active BOOLEAN DEFAULT true,
  last_sync TIMESTAMP,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Agent logs for sales module
CREATE TABLE IF NOT EXISTS sales_agent_logs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  account_id UUID REFERENCES accounts(id),
  module TEXT NOT NULL,                           -- 'scraper', 'qualifier', 'message_gen', 'outreach', 'reply_handler', 'gmail_client'
  action TEXT NOT NULL,
  lead_id UUID REFERENCES sales_leads(id),
  campaign_id UUID REFERENCES sales_campaigns(id),
  status TEXT,
  message TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Seed demo sales leads
INSERT INTO sales_leads (account_id, source, company_name, website, phone, email, industry, employee_count, contact_name, contact_title, city, status, score)
VALUES
  ('00000000-0000-0000-0000-000000000001', 'linkedin', 'TechVision Solutions', 'https://techvision.my', '60123456789', 'info@techvision.my', 'Technology', 50, 'Rajesh Kumar', 'CTO', 'Kuala Lumpur', 'new', 85),
  ('00000000-0000-0000-0000-000000000001', 'google_maps', 'MediCare Clinic', 'https://medicare.com.my', '60198765432', 'admin@medicare.com.my', 'Healthcare', 15, 'Dr. Sarah Tan', 'Director', 'Penang', 'new', 72),
  ('00000000-0000-0000-0000-000000000001', 'facebook', 'Green Earth Logistics', 'https://greenearthlogistics.my', '60112223334', 'contact@greenearth.my', 'Logistics', 120, 'Ahmad Ismail', 'Operations Manager', 'Selangor', 'new', 91),
  ('00000000-0000-0000-0000-000000000001', 'linkedin', 'Elite Retail Group', 'https://eliteretail.my', '60167778889', 'hello@eliteretail.my', 'Retail', 200, 'Michelle Wong', 'CEO', 'Johor Bahru', 'new', 78),
  ('00000000-0000-0000-0000-000000000001', 'manual', 'SmartStart Academy', 'https://smartstart.edu.my', '60134445556', 'info@smartstart.edu.my', 'Education', 30, 'Prof. David Ng', 'Principal', 'Ipoh', 'new', 65)
ON CONFLICT DO NOTHING;