"""Diagnóstico e limpeza de duplicatas no dicionário (indicadores e meios de aferição).
Execução:
    python scripts/_diag_duplicatas_dicionario.py [--fix]
    
Sem --fix: só exibe o diagnóstico.
Com --fix: normaliza textos (strip pontuação final) e funde duplicatas.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app
from db import get_cursor, get_db

FIX = '--fix' in sys.argv

def diag_e_fix_tabela(tabela, campo_texto):
    cur = get_cursor()
    cur.execute(f"""
        SELECT REGEXP_REPLACE(LOWER(TRIM({campo_texto})), '[.,;]+$', '') AS norm,
               COUNT(*) AS qtd,
               ARRAY_AGG(id ORDER BY id) AS ids,
               ARRAY_AGG({campo_texto} ORDER BY id) AS textos
        FROM categoricas.{tabela}
        GROUP BY REGEXP_REPLACE(LOWER(TRIM({campo_texto})), '[.,;]+$', '')
        HAVING COUNT(*) > 1
            OR BOOL_OR({campo_texto} ~ '[.,;]$')
        ORDER BY qtd DESC, norm
    """)
    grupos = cur.fetchall()

    if not grupos:
        print(f"  [OK] {tabela}: nenhuma duplicata ou pontuação residual.")
        return

    print(f"\n  === {tabela} ({len(grupos)} grupo(s) a corrigir) ===")
    for g in grupos:
        print(f"    norm={g['norm']!r}  ids={g['ids']}  textos={g['textos']}")

    if not FIX:
        return

    # Para cada grupo: mantém o id mais baixo, atualiza referências, apaga os outros
    # Também normaliza o texto do registro mantido (remove pontuação final + strip)
    array_col_map = {
        'c_dgp_indicadores':   ('celebracao.celebracao_objetivos', 'indicadores_ids'),
        'c_dgp_meios_afericao': ('celebracao.celebracao_objetivos', 'meios_afericao_ids'),
    }
    ref_table, ref_col = array_col_map[tabela]

    for g in grupos:
        ids = g['ids']
        keep_id = ids[0]
        dup_ids = ids[1:]
        # Texto normalizado: sem pontuação final, strip
        import re
        texto_novo = re.sub(r'[.,;]+\s*$', '', g['textos'][0].strip())

        # 1. Atualizar o texto do registro mantido
        cur.execute(
            f"UPDATE categoricas.{tabela} SET {campo_texto} = %s WHERE id = %s",
            (texto_novo, keep_id)
        )

        # 2. Substituir IDs duplicados por keep_id em celebracao_objetivos
        for dup_id in dup_ids:
            cur.execute(f"""
                UPDATE {ref_table}
                SET {ref_col} = ARRAY_REPLACE({ref_col}, %s::integer, %s::integer)
                WHERE %s = ANY({ref_col})
            """, (dup_id, keep_id, dup_id))

        # 3. Remover o dup_id da lista se keep_id já estava lá (evitar duplicata no array)
        for dup_id in dup_ids:
            cur.execute(f"""
                UPDATE {ref_table}
                SET {ref_col} = ARRAY(
                    SELECT DISTINCT unnest
                    FROM unnest({ref_col}) AS unnest
                    ORDER BY unnest
                )
                WHERE array_position({ref_col}, %s::integer) IS NOT NULL
                  AND array_position({ref_col}, %s::integer) IS NOT NULL
                  AND array_position({ref_col}, %s::integer) < array_position({ref_col}, %s::integer)
            """, (keep_id, dup_id, keep_id, dup_id))

        # 4. Excluir registros duplicados
        if dup_ids:
            cur.execute(
                f"DELETE FROM categoricas.{tabela} WHERE id = ANY(%s::integer[])",
                (dup_ids,)
            )

        print(f"    FUNDIDO: keep={keep_id} ({texto_novo!r}), removidos={dup_ids}")

    get_db().commit()
    print(f"  [COMMIT] {tabela} atualizado.")


with app.app_context():
    print("=== Diagnóstico dicionário ===")
    diag_e_fix_tabela('c_dgp_indicadores',   'indicador')
    diag_e_fix_tabela('c_dgp_meios_afericao', 'meios_afericao')

    if not FIX:
        print("\nExecute com --fix para aplicar a correção:")
        print("  python scripts/_diag_duplicatas_dicionario.py --fix")
    else:
        print("\nLimpeza concluída!")
