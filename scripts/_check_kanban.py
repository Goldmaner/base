import sys; sys.path.insert(0,'.')
from app import app
with app.app_context():
    from db import get_cursor
    cur = get_cursor()
    cur.execute('SELECT COUNT(*) as n FROM public.termos_alteracoes WHERE alt_oculto = FALSE OR alt_oculto IS NULL')
    print('Cards visiveis:', cur.fetchone()['n'])
    cur.execute('SELECT COUNT(*) as n FROM categoricas.c_alt_status_alteracao')
    print('Status categoricos:', cur.fetchone()['n'])
    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name='termos_alteracoes'
        AND column_name IN ('alt_prioridade','alt_data_inicio','alt_data_conclusao','alt_oculto','alt_marcadores')
        ORDER BY column_name
    """)
    print('New columns:', [r['column_name'] for r in cur.fetchall()])
    cur.close()
print('DB checks OK')
