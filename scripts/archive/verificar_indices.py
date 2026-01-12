import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    SELECT indexname, tablename 
    FROM pg_indexes 
    WHERE tablename IN ('parcerias', 'termos_rescisao') 
    AND schemaname = 'public'
    ORDER BY tablename, indexname
""")

for r in cur.fetchall():
    print(f"{r['tablename']}: {r['indexname']}")

cur.close()
conn.close()
