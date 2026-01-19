
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: Env vars missing")
    exit(1)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Use the tester account details (assumed from app.py logic or manually set)
# We need a user ID. Let's try to sign in as tester if possible, or just use `auth.sign_in_with_password`
email = "tester@pocket.app"
password = "testerpassword123"

try:
    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    user_id = res.user.id
    token = res.session.access_token
    print(f"Logged in as {email}")
except Exception as e:
    print(f"Login failed: {e}")
    # If login fails, we might rely on existing token or just manual check? 
    # Let's abort if we can't login as we need RLS.
    exit(1)

# 1. Add Bank with Opening Balance
print("Testing Add Bank with Opening Balance...")
try:
    data = {
        'user_id': user_id,
        'bank_name': 'Test Bank OpenBal',
        'account_number': '1234567890',
        'ifsc_code': 'TEST0001',
        'opening_balance': 5000.50
    }
    # Using authenticated client
    auth_client = create_client(SUPABASE_URL, SUPABASE_KEY, options={'headers': {'Authorization': f'Bearer {token}'}})
    
    res = auth_client.table('bank_accounts').insert(data).execute()
    new_bank = res.data[0]
    print(f"Bank Added: {new_bank}")
    
    if new_bank.get('opening_balance') == 5000.50:
        print("SUCCESS: Opening balance matches.")
    else:
        print(f"FAILURE: Opening balance mismatch. Got {new_bank.get('opening_balance')}")

    # 2. Cleanup
    auth_client.table('bank_accounts').delete().eq('id', new_bank['id']).execute()
    print("Cleanup: Test bank deleted.")

except Exception as e:
    print(f"Test Failed: {e}")
