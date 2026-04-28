import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

nomes = [
    'idx_back_empenhos_dt_eph',
    'idx_back_empenhos_criado_em',
    'idx_c_geral_pg_nome',
    'idx_ultra_liq_termo_status',
    'idx_parcerias_pg_termo_data',
    'idx_parcerias_sei_termo_id',
    'idx_despesas_numero_termo',
    'idx_despesas_categoria_rubrica',
    'idx_log_recurso_tipo_id',
    'idx_log_detalhes_gin',
]

cur.execute(
    'SELECT schemaname, tablename, indexname FROM pg_indexes WHERE indexname = ANY(%s) ORDER BY schemaname, tablename, indexname',
    (nomes,)
)
rows = cur.fetchall()
print('%-25s %-35s %s' % ('Schema', 'Tabela', 'Indice'))
print('-' * 90)
for r in rows:
    print('%-25s %-35s %s' % (r[0], r[1], r[2]))
print('\nTotal: %d/%d indices encontrados' % (len(rows), len(nomes)))

faltando = set(nomes) - {r[2] for r in rows}
if faltando:
    print('FALTANDO: ' + str(faltando))
else:
    print('Todos os indices estao presentes.')

# Plano de MAX(criado_em) — deve usar Index Scan agora
cur.execute('EXPLAIN SELECT MAX(criado_em) FROM gestao_financeira.back_empenhos')
print('\n--- EXPLAIN MAX(criado_em) ---')
for r in cur.fetchall():
    print(r[0])

# Plano de SELECT * ORDER BY dt_eph — deve usar Index Scan agora
cur.execute('EXPLAIN SELECT * FROM gestao_financeira.back_empenhos ORDER BY dt_eph DESC NULLS LAST LIMIT 100')
print('\n--- EXPLAIN SELECT * ORDER BY dt_eph LIMIT 100 ---')
for r in cur.fetchall():
    print(r[0])

cur.close()
conn.close()
