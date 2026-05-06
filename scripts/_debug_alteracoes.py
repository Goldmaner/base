"""Script de diagnóstico para alterações DGP"""
import sys
sys.path.insert(0, '.')

from app import app
from db import get_cursor, get_db

app.app_context().push()

cur = get_cursor()

# 1. Verificar se TCL/044/2023/SMDHC/SESANA está em parcerias
cur.execute("SELECT numero_termo FROM public.parcerias WHERE numero_termo ILIKE '%TCL%044%'")
rows = cur.fetchall()
print('Em parcerias (TCL%044):', [r['numero_termo'] for r in rows])

# 2. Verificar se está rescindido
cur.execute("SELECT numero_termo FROM public.termos_rescisao WHERE numero_termo ILIKE '%TCL%044%'")
rows = cur.fetchall()
print('Rescindidos (TCL%044):', [r['numero_termo'] for r in rows])

# 3. Colunas de parcerias_sei
cur.execute("""
    SELECT column_name, data_type, character_maximum_length 
    FROM information_schema.columns 
    WHERE table_name='parcerias_sei' AND table_schema='public' 
    ORDER BY ordinal_position
""")
rows = cur.fetchall()
print('Colunas parcerias_sei:', [(r['column_name'], r['data_type'], r['character_maximum_length']) for r in rows])

# 4. Verificar constraints de parcerias_sei
cur.execute("""
    SELECT constraint_name, constraint_type
    FROM information_schema.table_constraints
    WHERE table_name='parcerias_sei' AND table_schema='public'
""")
rows = cur.fetchall()
print('Constraints parcerias_sei:', [(r['constraint_name'], r['constraint_type']) for r in rows])

# 5. Verificar colunas de termos_alteracoes
cur.execute("""
    SELECT column_name, data_type, character_maximum_length 
    FROM information_schema.columns 
    WHERE table_name='termos_alteracoes' AND table_schema='public' 
    ORDER BY ordinal_position
""")
rows = cur.fetchall()
print('Colunas termos_alteracoes:', [(r['column_name'], r['data_type'], r['character_maximum_length']) for r in rows])

# 6. Verificar conteúdo de parcerias_sei
cur.execute("SELECT * FROM public.parcerias_sei ORDER BY criado_em DESC LIMIT 10")
rows = cur.fetchall()
print('Últimas parcerias_sei:')
for r in rows:
    print(dict(r))

# 7. Verificar DEFAULT de criado_em em parcerias_sei
cur.execute("""
    SELECT column_name, column_default, is_nullable
    FROM information_schema.columns 
    WHERE table_name='parcerias_sei' AND table_schema='public' 
    ORDER BY ordinal_position
""")
rows = cur.fetchall()
print('Colunas com defaults:', [(r['column_name'], r['column_default'], r['is_nullable']) for r in rows])

# 8. Check constraint details
cur.execute("""
    SELECT pg_get_constraintdef(oid) as def, conname
    FROM pg_constraint
    WHERE conrelid = 'public.parcerias_sei'::regclass
""")
rows = cur.fetchall()
print('Constraints detalhados:', [(r['conname'], r['def']) for r in rows])

# 9. Tentar inserir linha de teste na parcerias_sei
try:
    cur.execute("""
        INSERT INTO public.parcerias_sei 
        (numero_termo, termo_sei_doc, data_assinatura, aditamento, apostilamento, termo_tipo_sei)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, ('TFM/103/2025/SMDHC/SESANA', '123456789', '2025-01-01', '1', '-', None))
    row = cur.fetchone()
    print('INSERT teste bem-sucedido, id:', row['id'])
    get_db().rollback()  # não salvar o teste
except Exception as e:
    print('ERRO no INSERT teste:', repr(e))
    get_db().rollback()

# 10. Verificar se existe linha com aditamento='1' para TFM/103
cur.execute("""
    SELECT id, aditamento, apostilamento, termo_sei_doc, data_assinatura 
    FROM public.parcerias_sei 
    WHERE numero_termo = 'TFM/103/2025/SMDHC/SESANA'
""")
rows = cur.fetchall()
print('SEI TFM/103:', [dict(r) for r in rows])

cur.close()
