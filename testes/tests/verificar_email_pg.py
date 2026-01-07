"""
Verificar se a coluna email_pg existe
"""

import sys
sys.path.insert(0, '..')

import psycopg2
import psycopg2.extras
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'categoricas'
    AND table_name = 'c_geral_pessoa_gestora'
    AND column_name = 'email_pg'
""")

result = cur.fetchone()

if result:
    print(f"✅ Coluna email_pg existe!")
    print(f"   Tipo: {result['data_type']}")
    print(f"   Nullable: {result['is_nullable']}")
else:
    print("❌ Coluna email_pg NÃO EXISTE no banco de dados")
    print("\nVocê precisa criar a coluna executando:")
    print("ALTER TABLE categoricas.c_geral_pessoa_gestora ADD COLUMN email_pg TEXT;")

cur.close()
conn.close()
