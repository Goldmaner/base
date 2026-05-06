with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

idx_func = content.find(b'def dgp_alteracoes')

# PATCH A: Add filtro_osc and filtro_processo after filtro_status read
old_a = b"        filtro_status = request.args.get('filtro_status', '').strip()\r\n"
new_a = (
    b"        filtro_status = request.args.get('filtro_status', '').strip()\r\n"
    b"        filtro_osc = request.args.get('filtro_osc', '').strip()\r\n"
    b"        filtro_processo = request.args.get('filtro_processo', '').strip()\r\n"
)
idx_a = content.find(old_a, idx_func)
print('PATCH A at:', idx_a)
if idx_a >= 0:
    content = content[:idx_a] + new_a + content[idx_a + len(old_a):]
    print('PATCH A applied')

# PATCH B: Add LEFT JOIN parcerias in the FROM clause
old_b = b'FROM public.termos_alteracoes t\r\n            WHERE 1=1\r\n'
new_b = (
    b'FROM public.termos_alteracoes t\r\n'
    b'            LEFT JOIN public.parcerias p ON t.numero_termo = p.numero_termo\r\n'
    b'            WHERE 1=1\r\n'
)
idx_b = content.find(old_b, idx_func)
print('PATCH B at:', idx_b)
if idx_b >= 0:
    content = content[:idx_b] + new_b + content[idx_b + len(old_b):]
    print('PATCH B applied')

# PATCH C: Add filter conditions after filtro_status if block
old_c = (
    b'        if filtro_status:\r\n'
    b'            query_base += " AND t.alt_status = %s"\r\n'
    b'            params.append(filtro_status)\r\n'
    b'        \r\n'
    b'        query_base += """\r\n'
    b'            GROUP BY t.numero_termo, t.instrumento_alteracao, t.alt_numero\r\n'
)
new_c = (
    b'        if filtro_status:\r\n'
    b'            query_base += " AND t.alt_status = %s"\r\n'
    b'            params.append(filtro_status)\r\n'
    b'        \r\n'
    b'        if filtro_osc:\r\n'
    b'            query_base += " AND p.osc ILIKE %s"\r\n'
    b'            params.append(f"%{filtro_osc}%")\r\n'
    b'        \r\n'
    b'        if filtro_processo:\r\n'
    b'            query_base += " AND (p.sei_celeb ILIKE %s OR p.sei_pc ILIKE %s)"\r\n'
    b'            params.extend([f"%{filtro_processo}%", f"%{filtro_processo}%"])\r\n'
    b'        \r\n'
    b'        query_base += """\r\n'
    b'            GROUP BY t.numero_termo, t.instrumento_alteracao, t.alt_numero\r\n'
)
idx_c = content.find(old_c, idx_func)
print('PATCH C at:', idx_c)
if idx_c >= 0:
    content = content[:idx_c] + new_c + content[idx_c + len(old_c):]
    print('PATCH C applied')

# PATCH D: Add filtro_osc/filtro_processo to render_template call
# Find the render_template('dgp_alteracoes.html' call
idx_render = content.find(b"render_template('dgp_alteracoes.html'", idx_func)
if idx_render < 0:
    idx_render = content.find(b'render_template(\'dgp_alteracoes.html\'', idx_func)
print('render_template at:', idx_render)

# Find 'filtro_status=filtro_status' in that call
old_d = b'filtro_status=filtro_status,\r\n'
idx_d = content.find(old_d, idx_render)
if idx_d < 0:
    # Try without trailing comma
    old_d = b'filtro_status=filtro_status\r\n'
    idx_d = content.find(old_d, idx_render)
print('filtro_status= at:', idx_d)

if idx_d >= 0:
    new_d = (
        b'filtro_status=filtro_status,\r\n'
        b'            filtro_osc=filtro_osc,\r\n'
        b'            filtro_processo=filtro_processo,\r\n'
    )
    content = content[:idx_d] + new_d + content[idx_d + len(old_d):]
    print('PATCH D applied')
else:
    # Try finding the render_template area differently
    print('Trying alternate pattern...')
    ctx = content[idx_render:idx_render+1000] if idx_render >= 0 else b''
    print(repr(ctx[:500]))

with open('routes/parcerias.py', 'wb') as f:
    f.write(content)
print('Done')
