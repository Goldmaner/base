"""
Executa a migration de criacao da tabela public.datas_eventos
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

sql = open(os.path.join(os.path.dirname(__file__), 'criar_datas_eventos.sql'), encoding='utf-8').read()
cur.execute(sql)
conn.commit()
print('Tabela public.datas_eventos criada com sucesso.')

cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name   = 'datas_eventos'
    ORDER BY ordinal_position;
""")
rows = cur.fetchall()
print(f'Total de colunas: {len(rows)}')
for r in rows:
    print(f'  {r[0]:<35} {r[1]}')

cur.close()
conn.close()
