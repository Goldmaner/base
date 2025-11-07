import sys, os
sys.path.insert(0, os.getcwd())
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)
cur.execute('SELECT * FROM categoricas.c_analistas_dgp ORDER BY nome_analista')
rows = cur.fetchall()

print(f'\n✅ Total: {len(rows)} agentes\n')
for r in rows:
    status = '✓ Ativo' if r['status'] else '✗ Inativo'
    print(f"• {r['nome_analista']:<30} RF: {r['rf']:<10} Email: {r['email']:<40} Status: {status}")

cur.close()
conn.close()
