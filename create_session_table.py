import asyncio
from src.database import get_supabase

def create_sessions_table():
    supabase = get_supabase()
    
    # SQL to create the table
    # Note: supabase-py doesn't support direct SQL execution easily on the free tier via the client 
    # unless using the rpc call or if we use the postgres connection string.
    # However, we can try to use the dashboard or a workaround.
    # Actually, for this agent, let's just instruct the user or try to use a simple key-value store if possible.
    # But wait, we can use the API to create a table? No.
    
    print("Please run the following SQL in your Supabase SQL Editor:")
    print("""
    CREATE TABLE IF NOT EXISTS chat_sessions (
        phone_number TEXT PRIMARY KEY,
        context JSONB DEFAULT '{}'::jsonb,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """)

if __name__ == "__main__":
    create_sessions_table()
