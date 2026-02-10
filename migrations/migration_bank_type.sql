-- Add account_type column to bank_accounts table
alter table public.bank_accounts 
add column if not exists account_type text default 'Personal' check (account_type in ('Personal', 'Business'));

-- Update existing records to default 'Personal' (already handled by default, but good to be explicit if needed)
-- update public.bank_accounts set account_type = 'Personal' where account_type is null;
