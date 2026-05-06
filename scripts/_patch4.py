with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

old = (
    b'        query = """\r\n'
    b'            SELECT DISTINCT p.numero_termo \r\n'
    b'            FROM public.parcerias p\r\n'
    b'            WHERE p.numero_termo NOT IN (\r\n'
    b'                SELECT numero_termo FROM public.termos_rescisao\r\n'
    b'            )\r\n'
    b'        """\r\n'
)

new = (
    b'        query = """\r\n'
    b'            SELECT DISTINCT p.numero_termo \r\n'
    b'            FROM public.parcerias p\r\n'
    b'            WHERE 1=1\r\n'
    b'        """\r\n'
)

idx_func = content.find(b'def api_termos_parcerias')
idx_match = content.find(old, idx_func)
print('Match at:', idx_match)
if idx_match >= 0:
    content = content[:idx_match] + new + content[idx_match + len(old):]
    print('Replaced')
else:
    print('Not found')

with open('routes/parcerias.py', 'wb') as f:
    f.write(content)
print('Done')
