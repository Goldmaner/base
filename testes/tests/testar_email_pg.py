"""
Verificar registros com a coluna email_pg
"""

import sys
sys.path.insert(0, '..')

import psycopg2
import psycopg2.extras
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print("=== Pessoas Gestoras (primeiros 5 registros) ===\n")

cur.execute("""
    SELECT id, nome_pg, setor, numero_rf, status_pg, email_pg
    FROM categoricas.c_geral_pessoa_gestora
    ORDER BY id
    LIMIT 5
""")

registros = cur.fetchall()

for reg in registros:
    print(f"ID: {reg['id']}")
    print(f"  Nome: {reg['nome_pg']}")
    print(f"  Setor: {reg['setor']}")
    print(f"  Número RF: {reg['numero_rf']}")
    print(f"  Status: {reg['status_pg']}")
    print(f"  E-mail: {reg['email_pg']}")
    print()

cur.close()
conn.close()

print("✅ Configuração concluída!")
print("\nAgora você pode:")
print("1. Acessar /listas no navegador")
print("2. Selecionar 'Pessoas Gestoras'")
print("3. Editar qualquer registro para adicionar/modificar o e-mail")
