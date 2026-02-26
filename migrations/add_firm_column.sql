-- Add firm column to track associated firms for transactions
ALTER TABLE public.ent_revenue ADD COLUMN IF NOT EXISTS firm TEXT;
ALTER TABLE public.ent_expenses ADD COLUMN IF NOT EXISTS firm TEXT;
ALTER TABLE public.ent_investments ADD COLUMN IF NOT EXISTS firm TEXT;
ALTER TABLE public.ent_holding_payments ADD COLUMN IF NOT EXISTS firm TEXT;
