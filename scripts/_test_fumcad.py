import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from db import get_cursor
from app import app

with app.app_context():
    cur = get_cursor()

    # 1. Testa cálculo de cutoff
    cur.execute("""
        SELECT MAKE_DATE(%(ano)s, %(mes)s, 1) + INTERVAL '2 months' - INTERVAL '1 day' AS cutoff
    """, {'mes': 1, 'ano': 2026})
    print("Cutoff jan/2026:", cur.fetchone()['cutoff'])

    # 2. Executa a query principal para março/2026
    sql = """
        SELECT
            CASE
                WHEN ul.numero_termo ILIKE 'TFM%%' OR ul.numero_termo ILIKE 'TCL%%' THEN 'TFM'
                WHEN ul.numero_termo ILIKE 'TCV%%' THEN 'TCV'
            END AS tipo,
            COUNT(*) AS qtd,
            SUM(CASE WHEN ul.valor_pago > 0 THEN ul.valor_previsto - ul.valor_pago
                     ELSE ul.valor_previsto END) AS valor_indisponivel
        FROM gestao_financeira.ultra_liquidacoes ul
        LEFT JOIN (
            SELECT numero_termo, data_assinatura
            FROM public.parcerias_sei
            WHERE aditamento = '-' AND apostilamento = '-'
        ) ps ON ps.numero_termo = ul.numero_termo
        WHERE
            ul.numero_termo ILIKE '%%FUMCAD%%'
            AND ul.parcela_tipo IN ('Programada', 'Projetada')
            AND ul.parcela_status IN ('Encaminhado para Pagamento', 'Não Pago')
            AND (
                ul.parcela_status_secundario IS NULL
                OR ul.parcela_status_secundario = ''
                OR ul.parcela_status_secundario = '-'
            )
            AND (
                ps.data_assinatura IS NULL
                OR ps.data_assinatura <= MAKE_DATE(%(ano)s, %(mes)s, 1)
                                        + INTERVAL '2 months'
                                        - INTERVAL '1 day'
            )
        GROUP BY tipo
    """
    for mes, ano in [(3, 2026), (1, 2026)]:
        cur.execute(sql, {'mes': mes, 'ano': ano})
        rows = cur.fetchall()
        print(f"\n=== {mes}/{ano} ===")
        for r in rows:
            print(dict(r))
