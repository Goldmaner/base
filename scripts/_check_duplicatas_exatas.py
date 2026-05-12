"""Verifica duplicatas exatas (case-insensitive) no dicionário."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from app import app

with app.app_context():
    from db import get_cursor
    cur = get_cursor()

    for tabela, campo in [('c_dgp_indicadores','indicador'), ('c_dgp_meios_afericao','meios_afericao')]:
        cur.execute(f"""
            SELECT LOWER(TRIM({campo})) AS norm,
                   COUNT(*) AS qtd,
                   ARRAY_AGG(id ORDER BY id) AS ids,
                   ARRAY_AGG({campo} ORDER BY id) AS textos
            FROM categoricas.{tabela}
            GROUP BY LOWER(TRIM({campo}))
            HAVING COUNT(*) > 1
            ORDER BY qtd DESC, norm
        """)
        rows = cur.fetchall()
        if rows:
            print(f"\n=== {tabela} — {len(rows)} duplicata(s) exata(s) ===")
            for r in rows:
                print(f"  ids={r['ids']}  textos={r['textos']}")
        else:
            print(f"\n=== {tabela} — sem duplicatas exatas ===")
