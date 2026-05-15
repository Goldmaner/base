"""Corrige c_geral_status: visita_avaliacao estava com valores errados; visita_status estava faltando."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_CONFIG
import psycopg2

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

# 1) Remover visita_avaliacao errada (tinha valores de visita_status misturados)
cur.execute(
    "DELETE FROM categoricas.c_geral_status "
    "WHERE schema_table_coluna_r = 'public.parcerias_monit.visita_avaliacao'"
)
print(f'Deletadas: {cur.rowcount} linhas de visita_avaliacao incorretas')

# 2) Inserir visita_avaliacao correto (valores reais vindos do banco)
visita_aval_values = [
    ('public.parcerias_monit.visita_avaliacao', 'Satisfatório'),
    ('public.parcerias_monit.visita_avaliacao', 'Parcial'),
    ('public.parcerias_monit.visita_avaliacao', 'Insatisfatória'),
    ('public.parcerias_monit.visita_avaliacao', '-'),
]
cur.executemany(
    "INSERT INTO categoricas.c_geral_status (schema_table_coluna_r, status) VALUES (%s, %s)",
    visita_aval_values
)
print(f'Inseridas: {cur.rowcount} linhas de visita_avaliacao corretas')

# 3) Inserir visita_status (estava completamente faltando)
visita_status_values = [
    ('public.parcerias_monit.visita_status', 'Visita não realizada - Encerrado'),
    ('public.parcerias_monit.visita_status', 'Não analisado'),
    ('public.parcerias_monit.visita_status', 'Visita Realizada'),
    ('public.parcerias_monit.visita_status', 'Finalizado'),
    ('public.parcerias_monit.visita_status', 'Notificação respondida'),
    ('public.parcerias_monit.visita_status', 'Notificado'),
    ('public.parcerias_monit.visita_status', '-'),
]
cur.executemany(
    "INSERT INTO categoricas.c_geral_status (schema_table_coluna_r, status) VALUES (%s, %s)",
    visita_status_values
)
print(f'Inseridas: {cur.rowcount} linhas de visita_status')

conn.commit()
conn.close()
print('Concluído.')
