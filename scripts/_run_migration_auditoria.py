"""
Executa a migration de colunas de auditoria em celebracao.celebracao_parcerias
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

sql = open(os.path.join(os.path.dirname(__file__), 'adicionar_colunas_auditoria_celebracao.sql')).read()
cur.execute(sql)
conn.commit()
print('Migration executada com sucesso.')

# Verificar colunas
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'celebracao'
      AND table_name   = 'celebracao_parcerias'
      AND column_name IN ('criado_por', 'atualizado_at', 'atualizado_por', 'created_at')
    ORDER BY column_name;
""")
rows = cur.fetchall()
print("Colunas encontradas:")
for r in rows:
    print(f"  {r[0]:20s} | {r[1]}")
conn.close()
