
from app import get_db, supabase
import os

# Login as tester to get token
try:
    email = "tester@pocket.app"
    password = "testerpassword123"
    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
    token = res.session.access_token
    user_id = res.user.id
    print(f"Logged in. User ID: {user_id}")
    
    # Fetch banks using get_db helper
    print("Fetching banks...")
    res = get_db(token).table('bank_accounts').select('*').eq('user_id', user_id).execute()
    banks = res.data
    
    print(f"Count: {len(banks)}")
    for bank in banks:
        print(f"Bank: {bank.get('bank_name')}, Opening Balance: {bank.get('opening_balance')}")
        
except Exception as e:
    print(f"Error: {e}")
