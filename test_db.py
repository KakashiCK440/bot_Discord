"""
Test script to verify PostgreSQL connection and parameter binding
"""
import os
from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

print(f"DATABASE_URL found: {bool(DATABASE_URL)}")
print(f"DATABASE_URL preview: {DATABASE_URL[:50]}..." if DATABASE_URL else "No DATABASE_URL")

try:
    # Test connection
    print("\n1. Testing connection...")
    conn = psycopg2.connect(DATABASE_URL)
    print("[OK] Connection successful!")
    
    # Test simple query without parameters
    print("\n2. Testing query without parameters...")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 as test")
    result = cursor.fetchone()
    print(f"[OK] Query result: {result}")
    
    # Test query with parameters
    print("\n3. Testing query with parameters...")
    cursor.execute("SELECT %s as test_param", (123,))
    result = cursor.fetchone()
    print(f"[OK] Parameter query result: {result}")
    
    # Test table query with parameters
    print("\n4. Testing table query with parameters...")
    cursor.execute("""
        SELECT * FROM server_settings WHERE guild_id = %s
    """, (1234567890,))
    result = cursor.fetchone()
    print(f"[OK] Table query result: {result}")
    
    conn.close()
    print("\n[SUCCESS] All tests passed!")
    
except Exception as e:
    print(f"\n[ERROR] {e}")
    import traceback
    traceback.print_exc()
