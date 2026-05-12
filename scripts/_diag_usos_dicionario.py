"""Diagnóstico: contagem de usos de cada indicador e meio de aferição."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import app

with app.app_context():
    from db import get_cursor
    cur = get_cursor()

    for tabela, campo, ref_col in [
        ('c_dgp_indicadores',   'indicador',      'indicadores_ids'),
        ('c_dgp_meios_afericao','meios_afericao',  'meios_afericao_ids'),
    ]:
        cur.execute(f"""
            SELECT t.id, t.{campo} AS nome,
                   COUNT(co.id) AS qtd_objetivos
            FROM categoricas.{tabela} t
            LEFT JOIN celebracao.celebracao_objetivos co ON t.id = ANY(co.{ref_col})
            GROUP BY t.id, t.{campo}
            ORDER BY qtd_objetivos, t.{campo}
        """)
        rows = cur.fetchall()
        sem = [r for r in rows if r['qtd_objetivos'] == 0]
        com = [r for r in rows if r['qtd_objetivos'] > 0]
        print(f"\n=== {tabela} — total: {len(rows)}, sem uso: {len(sem)} ===")
        print("  SEM objetivo vinculado:")
        for r in sem:
            print(f"    id={r['id']:3d}  {r['nome']}")
        print("  COM objetivo vinculado:")
        for r in com:
            print(f"    id={r['id']:3d}  qtd={r['qtd_objetivos']}  {r['nome']}")
