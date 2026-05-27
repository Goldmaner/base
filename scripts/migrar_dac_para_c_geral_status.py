"""Migra c_dac_despesas_provisao e c_dac_parcela_andamento_status para c_geral_status."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)

migracoes = [
    {
        'campo_r': 'gestao_financeira.despesas.categoria_provisao',
        'nome': 'DAC \u203a Despesas \u2014 Provis\u00e3o',
        'query': 'SELECT despesa_provisao AS status, descricao FROM categoricas.c_dac_despesas_provisao ORDER BY id',
        'col_status': None,
    },
    {
        'campo_r': 'gestao_financeira.ultra_liquidacoes.parcela_andamento',
        'nome': 'DAC \u203a Parcela \u2014 Status de Andamento',
        'query': 'SELECT status_parcela AS status, descricao, status_status FROM categoricas.c_dac_parcela_andamento_status ORDER BY id',
        'col_status': 'status_status',
    },
]

for m in migracoes:
    cur.execute('SELECT COUNT(*) AS cnt FROM categoricas.c_geral_status WHERE schema_table_coluna_r = %s', (m['campo_r'],))
    if cur.fetchone()['cnt'] > 0:
        print(f'Ja migrado: {m["campo_r"]}')
        continue

    cur.execute(m['query'])
    rows = cur.fetchall()
    for r in rows:
        ativo = True
        if m['col_status']:
            ativo = (r.get(m['col_status']) or '').lower() in ('ativo', 'true')
        cur.execute(
            'INSERT INTO categoricas.c_geral_status (schema_table_coluna_r, status, descricao, ativo, nome_item_fantasia) VALUES (%s, %s, %s, %s, %s)',
            (m['campo_r'], r['status'], r.get('descricao'), ativo, m['nome'])
        )
    conn.commit()
    print(f'Inseridos {len(rows)} registros -> {m["nome"]}')

    # Confirmar
    cur.execute('SELECT id, status, ativo FROM categoricas.c_geral_status WHERE schema_table_coluna_r = %s ORDER BY id', (m['campo_r'],))
    for r in cur.fetchall():
        print(f'  [{r["id"]}] ativo={r["ativo"]} | {r["status"][:60]}')

cur.close()
conn.close()
print('Concluido.')
