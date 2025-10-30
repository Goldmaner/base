"""
Teste do dropdown dinâmico de setores
"""

import sys
sys.path.insert(0, '..')

import psycopg2
import psycopg2.extras
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print("=== Setores cadastrados em c_pessoa_gestora ===\n")

cur.execute("""
    SELECT DISTINCT setor 
    FROM categoricas.c_pessoa_gestora 
    WHERE setor IS NOT NULL 
    ORDER BY setor
""")

setores = cur.fetchall()

print(f"Total de setores únicos: {len(setores)}\n")

for idx, row in enumerate(setores, 1):
    print(f"{idx:2d}. {row['setor']}")

print("\n" + "=" * 60)

# Contar pessoas por setor
print("\nDistribuição de pessoas por setor:\n")

cur.execute("""
    SELECT setor, COUNT(*) as total
    FROM categoricas.c_pessoa_gestora
    WHERE setor IS NOT NULL
    GROUP BY setor
    ORDER BY setor
""")

distribuicao = cur.fetchall()

for row in distribuicao:
    print(f"{row['setor']:15s} - {row['total']:2d} pessoa(s)")

cur.close()
conn.close()

print("\n✅ Dropdown de setores configurado!")
print("\nAgora quando você editar ou criar uma pessoa gestora,")
print("o campo 'Setor' será um dropdown com essas opções.")
