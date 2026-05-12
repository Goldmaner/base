"""Diagnóstico rápido do estado do banco — celebracao_metas / celebracao_objetivos."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DB_CONFIG
import psycopg2, psycopg2.extras as xe

conn = psycopg2.connect(**{k: v for k, v in DB_CONFIG.items()
                           if k in ('host','port','database','user','password','sslmode')})
cur = conn.cursor(cursor_factory=xe.RealDictCursor)

cur.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'celebracao'
    ORDER BY table_name
""")
print("TABELAS:", [r['table_name'] for r in cur.fetchall()])

cur.execute("SELECT COUNT(*) AS n FROM celebracao.celebracao_metas")
print("METAS COUNT:", cur.fetchone()['n'])

cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'celebracao' AND table_name = 'celebracao_metas'
    ORDER BY ordinal_position
""")
print("COLS METAS:", [r['column_name'] for r in cur.fetchall()])

# Verificar se objetivos existe
cur.execute("""
    SELECT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'celebracao' AND table_name = 'celebracao_objetivos'
    ) AS existe
""")
existe = cur.fetchone()['existe']
print("TABELA OBJETIVOS EXISTE:", existe)

if existe:
    cur.execute("SELECT COUNT(*) AS n FROM celebracao.celebracao_objetivos")
    print("OBJETIVOS COUNT:", cur.fetchone()['n'])

# Verificar se objetivo_id existe em metas
cur.execute("""
    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'celebracao' AND table_name = 'celebracao_metas'
        AND column_name = 'objetivo_id'
    ) AS existe
""")
print("COLUNA objetivo_id EM METAS:", cur.fetchone()['existe'])

# Amostra de metas existentes
cur.execute("SELECT id, sei_numero, meta_titulo FROM celebracao.celebracao_metas LIMIT 5")
rows = cur.fetchall()
print("AMOSTRA METAS:", [(r['id'], r['sei_numero'], r['meta_titulo']) for r in rows])

conn.close()
print("Diagnóstico concluído.")
