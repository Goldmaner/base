"""Verifica constraints e dados de gestao_pessoas.datas_ferias antes da migration."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import psycopg2, psycopg2.extras
from config import DB_CONFIG

cfg = {k: v for k, v in DB_CONFIG.items()
       if k not in ('keepalives','keepalives_idle','keepalives_interval','keepalives_count','connect_timeout')}
conn = psycopg2.connect(**cfg, cursor_factory=psycopg2.extras.RealDictCursor)
cur = conn.cursor()

cur.execute("""
    SELECT c.conname, c.contype, pg_get_constraintdef(c.oid) AS def
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE n.nspname = 'gestao_pessoas' AND t.relname = 'datas_ferias'
    ORDER BY c.contype
""")
rows = cur.fetchall()
print("Constraints em gestao_pessoas.datas_ferias:")
for r in rows:
    print(f"  type={r['contype']} name={r['conname']}: {r['def']}")

# FKs de OUTRAS tabelas apontando para datas_ferias
cur.execute("""
    SELECT c.conname, n2.nspname||'.'||t2.relname AS origem,
           pg_get_constraintdef(c.oid) AS def
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.confrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    JOIN pg_class t2 ON t2.oid = c.conrelid
    JOIN pg_namespace n2 ON n2.oid = t2.relnamespace
    WHERE n.nspname = 'gestao_pessoas' AND t.relname = 'datas_ferias'
""")
refs = cur.fetchall()
print("\nOutras tabelas com FK apontando para datas_ferias:")
if refs:
    for r in refs:
        print(f"  {r['origem']}: {r['def']}")
else:
    print("  (nenhuma)")

cur.execute("SELECT COUNT(*) AS n FROM gestao_pessoas.datas_ferias")
print(f"\nTotal de linhas: {cur.fetchone()['n']}")
cur.close()
conn.close()
