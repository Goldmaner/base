"""
Script para verificar a sincronização realizada
"""

import sys
sys.path.insert(0, '..')

import psycopg2
import psycopg2.extras
from config import DB_CONFIG

print("=== Verificação da Sincronização ===\n")

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Verificar registros da Adriana em parcerias_analises
print("Registros de Adriana em parcerias_analises:")
print("=" * 80)

cur.execute("""
    SELECT id, responsavel_pg, data_parecer_dp
    FROM parcerias_analises
    WHERE responsavel_pg LIKE '%Adriana%'
    ORDER BY id
""")

registros = cur.fetchall()

if registros:
    for reg in registros:
        print(f"ID: {reg['id']}")
        print(f"  Responsável PG: {reg['responsavel_pg']}")
        print(f"  Data Parecer DP: {reg['data_parecer_dp']}")
        print()
    
    print(f"Total: {len(registros)} registro(s)")
else:
    print("Nenhum registro encontrado")

print("\n" + "=" * 80)

# Verificar o nome atual na tabela c_pessoa_gestora
print("\nNome cadastrado em c_pessoa_gestora:")
print("=" * 80)

cur.execute("""
    SELECT id, nome_pg, setor, numero_rf, status_pg
    FROM categoricas.c_pessoa_gestora
    WHERE nome_pg LIKE '%Adriana%'
""")

pessoa = cur.fetchone()

if pessoa:
    print(f"ID: {pessoa['id']}")
    print(f"Nome: {pessoa['nome_pg']}")
    print(f"Setor: {pessoa['setor']}")
    print(f"Número RF: {pessoa['numero_rf']}")
    print(f"Status: {pessoa['status_pg']}")
else:
    print("Nenhum registro encontrado")

print("\n" + "=" * 80)

# Verificar se ainda existem inconsistências
print("\nVerificação de consistência:")
print("=" * 80)

cur.execute("""
    SELECT DISTINCT responsavel_pg
    FROM parcerias_analises
    WHERE responsavel_pg NOT IN (
        SELECT nome_pg FROM categoricas.c_pessoa_gestora
    )
    AND responsavel_pg IS NOT NULL
    ORDER BY responsavel_pg
""")

inconsistencias = cur.fetchall()

if inconsistencias:
    print("⚠️ Ainda existem nomes inconsistentes:")
    for incons in inconsistencias:
        print(f"  - {incons['responsavel_pg']}")
else:
    print("✅ Todos os nomes estão sincronizados!")

cur.close()
conn.close()

print("\n=== Verificação concluída ===")
