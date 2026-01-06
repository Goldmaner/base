import psycopg2
from psycopg2.extras import RealDictCursor
import sys
sys.path.insert(0, '..')
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Check for tables
print("=== Tables starting with 'c_' ===")
cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'c_%'")
tables = cur.fetchall()
for table in tables:
    print(table['table_name'])

print("\n=== c_tipo_contrato structure ===")
try:
    cur.execute("SELECT * FROM categoricas.c_tipo_contrato LIMIT 5")
    rows = cur.fetchall()
    if rows:
        print("Columns:", rows[0].keys())
        for row in rows:
            print(row)
except Exception as e:
    print(f"Error: {e}")

print("\n=== c_geral_modelo_textos structure ===")
try:
    cur.execute("SELECT * FROM categoricas.c_geral_modelo_textos LIMIT 5")
    rows = cur.fetchall()
    if rows:
        print("Columns:", rows[0].keys())
        for row in rows:
            print(row)
except Exception as e:
    print(f"Error: {e}")

cur.close()
conn.close()
