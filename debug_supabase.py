from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Missing env vars")
    exit(1)

from supabase import create_client, ClientOptions

print("Imported ClientOptions")

try:
    token = "test-token"
    opts = ClientOptions(headers={"Authorization": f"Bearer {token}"})
    client_auth = create_client(url, key, options=opts)
    print("Created authenticated client")
    print(f"Auth headers: {client_auth.options.headers}")
except Exception as e:
    print(f"Error testing options: {e}")
