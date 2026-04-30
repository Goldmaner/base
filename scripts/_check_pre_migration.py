"""Verifica estado das tabelas antes e depois da migration de schema."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import psycopg2, psycopg2.extras
from config import DB_CONFIG

conn = psycopg2.connect(**{k:v for k,v in DB_CONFIG.items() if k not in ('keepalives','keepalives_idle','keepalives_interval','keepalives_count','connect_timeout')}, cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

TABLES = ('datas_importantes', 'datas_eventos', 'datas_eventos_responsaveis')

cur.execute("""
    SELECT schemaname, tablename
    FROM pg_tables
    WHERE tablename = ANY(%s)
    ORDER BY tablename
""", (list(TABLES),))
rows = cur.fetchall()

print("=== Estado das tabelas ===")
for r in rows:
    schema = r['schemaname']
    table  = r['tablename']
    cur.execute(f"SELECT COUNT(*) AS n FROM {schema}.{table}")
    n = cur.fetchone()['n']
    print(f"  {schema}.{table}: {n} linhas")

cur.close()
conn.close()
