import os
import sys
from dotenv import load_dotenv
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from supabase import create_client, Client

load_dotenv()
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(url, key)

try:
    res = supabase.table('ent_investments').select('id, firm').limit(1).execute()
    print("Investments firm check success.")
except Exception as e:
    print("ent_investments error:", e)

try:
    res2 = supabase.table('ent_holding_payments').select('id, firm').limit(1).execute()
    print("Holding payments firm check success.")
except Exception as e:
    print("ent_holding_payments error:", e)
