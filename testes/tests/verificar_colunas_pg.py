"""
Script para verificar as colunas da tabela c_pessoa_gestora
"""

import sys
sys.path.insert(0, '..')

import psycopg2
import psycopg2.extras
from config import DB_CONFIG

print("=== Verificando estrutura da tabela c_pessoa_gestora ===\n")

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Buscar informações das colunas
cur.execute("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns
    WHERE table_schema = 'categoricas'
    AND table_name = 'c_pessoa_gestora'
    ORDER BY ordinal_position
""")

colunas = cur.fetchall()

print("Colunas encontradas:")
print("-" * 60)
for col in colunas:
    print(f"  {col['column_name']:20s} | {col['data_type']:15s} | Nullable: {col['is_nullable']}")

print("\n" + "=" * 60)

# Verificar se as colunas numero_rf e status_pg existem
colunas_necessarias = ['numero_rf', 'status_pg']
colunas_existentes = [col['column_name'] for col in colunas]

print("\nVerificação de colunas necessárias:")
for col in colunas_necessarias:
    if col in colunas_existentes:
        print(f"  ✅ {col} existe")
    else:
        print(f"  ❌ {col} NÃO EXISTE - precisa ser criada!")

print("\n" + "=" * 60)

# Mostrar alguns registros de exemplo
print("\nRegistros de exemplo (primeiros 5):")
cur.execute("""
    SELECT * FROM categoricas.c_pessoa_gestora
    ORDER BY id
    LIMIT 5
""")

registros = cur.fetchall()
if registros:
    print("\nColunas disponíveis:", list(registros[0].keys()))
    for reg in registros:
        print(f"\nID {reg['id']}:")
        for chave, valor in reg.items():
            print(f"  {chave}: {valor}")
else:
    print("  (Nenhum registro encontrado)")

cur.close()
conn.close()

print("\n=== Verificação concluída ===")
