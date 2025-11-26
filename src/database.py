import os
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")

if not url or not key:
    print("Warning: SUPABASE_URL or SUPABASE_KEY not found in environment variables.")
    # For local testing without env vars, we might want to handle this gracefully or fail hard.
    # We'll assume the user will provide them.

supabase: Client = create_client(url, key) if url and key else None

def get_supabase() -> Client:
    if not supabase:
        raise Exception("Supabase client not initialized. Check environment variables.")
    return supabase
