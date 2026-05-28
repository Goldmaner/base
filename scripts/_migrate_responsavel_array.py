"""
Migração: converte visita_responsavel e monit_responsavel de varchar -> text[]
Execute uma única vez: python scripts/_migrate_responsavel_array.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = False
cur = conn.cursor()

try:
    cur.execute("""
        ALTER TABLE public.parcerias_monit
            ALTER COLUMN visita_responsavel TYPE text[]
            USING CASE
                WHEN visita_responsavel IS NOT NULL AND visita_responsavel <> ''
                THEN ARRAY[visita_responsavel]
                ELSE NULL
            END,
            ALTER COLUMN monit_responsavel TYPE text[]
            USING CASE
                WHEN monit_responsavel IS NOT NULL AND monit_responsavel <> ''
                THEN ARRAY[monit_responsavel]
                ELSE NULL
            END
    """)
    conn.commit()
    print("Migração concluída: colunas convertidas para text[]")
except Exception as e:
    conn.rollback()
    print(f"Erro: {e}")
finally:
    cur.close()
    conn.close()
