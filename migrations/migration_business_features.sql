-- Add business specific columns to bank_accounts table
alter table public.bank_accounts 
add column if not exists investment_amount numeric default 0,
add column if not exists holding_amount numeric default 0,
add column if not exists access_pin text;

-- Security note: access_pin should ideally be hashed, but for this feature we'll store as text initially as requested.
