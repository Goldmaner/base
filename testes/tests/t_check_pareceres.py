"""
Teste da contagem de pareceres por pessoa gestora
"""

import sys
sys.path.insert(0, '..')

import psycopg2
import psycopg2.extras
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

print("=== Contagem de Pareceres por Pessoa Gestora ===\n")

# Buscar contagem de pareceres
cur.execute("""
    SELECT 
        pg.id,
        pg.nome_pg,
        pg.setor,
        pg.status_pg,
        COUNT(pa.id) as total_pareceres
    FROM categoricas.c_geral_pessoa_gestora pg
    LEFT JOIN parcerias_analises pa ON pa.responsavel_pg = pg.nome_pg
    GROUP BY pg.id, pg.nome_pg, pg.setor, pg.status_pg
    ORDER BY total_pareceres DESC, pg.nome_pg
""")

resultados = cur.fetchall()

print(f"{'ID':<5} {'Nome':<40} {'Setor':<15} {'Status':<15} {'Pareceres':>10}")
print("=" * 90)

for row in resultados:
    status = row['status_pg'] or 'Não definido'
    print(f"{row['id']:<5} {row['nome_pg']:<40} {row['setor']:<15} {status:<15} {row['total_pareceres']:>10}")

print("\n" + "=" * 90)

# Estatísticas
total_pessoas = len(resultados)
pessoas_com_parecer = len([r for r in resultados if r['total_pareceres'] > 0])
total_pareceres = sum(r['total_pareceres'] for r in resultados)

print(f"\nTotal de pessoas gestoras: {total_pessoas}")
print(f"Pessoas com pelo menos 1 parecer: {pessoas_com_parecer}")
print(f"Total de pareceres emitidos: {total_pareceres}")
print(f"Média de pareceres por pessoa: {total_pareceres / total_pessoas:.2f}")

# Top 5
print("\n=== Top 5 Pessoas com Mais Pareceres ===")
top5 = sorted(resultados, key=lambda x: x['total_pareceres'], reverse=True)[:5]
for idx, row in enumerate(top5, 1):
    print(f"{idx}. {row['nome_pg']} ({row['setor']}) - {row['total_pareceres']} pareceres")

cur.close()
conn.close()

print("\n✅ Teste concluído!")
