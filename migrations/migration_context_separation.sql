-- Add context column to expenses table to separate Personal vs Business
alter table public.expenses 
add column if not exists context text default 'Personal' check (context in ('Personal', 'Business'));

-- Update existing expenses to 'Business' if they are linked to a Business bank account
update public.expenses
set context = 'Business'
from public.bank_accounts
where public.expenses.bank_account_id = public.bank_accounts.id
and public.bank_accounts.account_type = 'Business';
