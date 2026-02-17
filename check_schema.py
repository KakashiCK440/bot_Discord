import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cursor = conn.cursor()

# Get join_requests table columns
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'join_requests' 
    ORDER BY ordinal_position
""")

print("join_requests table columns:")
for row in cursor.fetchall():
    print(f"  - {row[0]}")

conn.close()
