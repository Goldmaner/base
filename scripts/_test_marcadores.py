import sys; sys.path.insert(0,'.')
from app import app
with app.app_context():
    from db import get_cursor
    cur = get_cursor()
    cur.execute("SELECT informacao FROM categoricas.c_geral_tipo_contrato WHERE informacao IS NOT NULL LIMIT 8")
    print('tipo_contrato:', [r['informacao'] for r in cur.fetchall()])
    cur.execute("SELECT DISTINCT coordenacao FROM categoricas.c_geral_dotacoes WHERE coordenacao IS NOT NULL AND coordenacao != '' LIMIT 8")
    print('dotacao (coord):', [r['coordenacao'] for r in cur.fetchall()])
    cur.execute("SELECT DISTINCT alt_tipo FROM categoricas.c_alt_tipo WHERE alt_tipo IS NOT NULL LIMIT 8")
    print('alt_tipo:', [r['alt_tipo'] for r in cur.fetchall()])
    cur.close()
