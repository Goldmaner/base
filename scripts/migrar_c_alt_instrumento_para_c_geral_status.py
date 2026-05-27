"""
Migra categoricas.c_alt_instrumento → categoricas.c_geral_status
schema_table_coluna_r = 'public.termos_alteracoes.instrumento_alteracao'
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

CAMPO_REF = 'public.termos_alteracoes.instrumento_alteracao'

conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = False
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute(
    "SELECT COUNT(*) AS cnt FROM categoricas.c_geral_status WHERE schema_table_coluna_r = %s",
    (CAMPO_REF,)
)
existentes = cur.fetchone()['cnt']
print(f"Registros já existentes para '{CAMPO_REF}': {existentes}")

if existentes > 0:
    print("Já migrado. Nenhuma ação necessária.")
    cur.close()
    conn.close()
    sys.exit(0)

cur.execute("""
    INSERT INTO categoricas.c_geral_status
        (schema_table_coluna_r, status, descricao, ativo)
    SELECT
        %s,
        instrumento_alteracao,
        descricao,
        (status IN ('ativo', 'true'))
    FROM categoricas.c_alt_instrumento
    ORDER BY id
""", (CAMPO_REF,))

inseridos = cur.rowcount
conn.commit()
print(f"Inseridos {inseridos} registros com sucesso.")

cur.execute(
    "SELECT id, status, descricao, ativo FROM categoricas.c_geral_status WHERE schema_table_coluna_r = %s ORDER BY id",
    (CAMPO_REF,)
)
rows = cur.fetchall()
print("\nRegistros inseridos:")
for r in rows:
    print(f"  [{r['id']}] ativo={r['ativo']} | {r['status']} — {r['descricao'] or '(sem descrição)'}")

cur.close()
conn.close()
