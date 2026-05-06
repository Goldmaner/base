with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

# Remove the duplicate original params block:
# From `            """, (\r\n` (after our new ))\r\n) through the old `            ))\r\n`
# The duplicate block starts immediately after our new closing ))\r\n

old_dupe = (
    b'            ))\r\n'
    b'            """, (\r\n'
    b'                numero_termo,\r\n'
    b'                instrumento_alteracao,\r\n'
    b'                alt_numero,\r\n'
    b'                alt_tipo.strip(),\r\n'
    b'                alt_status,\r\n'
    b'                alt_info,\r\n'
    b'                alt_old_info,\r\n'
    b'                alt_responsavel,\r\n'
    b'                alt_observacao if alt_observacao else None,\r\n'
    b'                usuario_atual,\r\n'
    b'                usuario_atual\r\n'
    b'            ))\r\n'
)

# This should be replaced by just the first ))\r\n
new = b'            ))\r\n'

cnt = content.count(old_dupe)
print('occurrences:', cnt)
if cnt == 1:
    content = content.replace(old_dupe, new)
    print('Removed duplicate params block')

with open('routes/parcerias.py', 'wb') as f:
    f.write(content)
print('Done')
