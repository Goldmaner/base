with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

idx_func = content.find(b'def editar_alteracao')
idx_sei = content.find(b'parcerias_sei', idx_func)

# Find start of the if/else block
# Find the 'if aditamento or apostilamento:' line
old_block_start_marker = b'                if aditamento or apostilamento:\r\n'
idx_old_block = content.find(old_block_start_marker, idx_func)
print('Old block start at:', idx_old_block)

# Find end: 'except Exception as e:' after this
# Actually the block ends with data_assinatura = data_assinatura_obj.strftime
end_marker = b"                    if data_assinatura_obj:\r\n                        data_assinatura = data_assinatura_obj.strftime('%Y-%m-%d')\r\n"
idx_old_block_end = content.find(end_marker, idx_old_block)
if idx_old_block_end >= 0:
    idx_old_block_end += len(end_marker)
    print('Old block end at:', idx_old_block_end)
    
    old_block = content[idx_old_block:idx_old_block_end]
    print('Old block len:', len(old_block))
    
    # Replace with a simpler direct read from termos_alteracoes
    # We need alt_numero - let's check if it's available at this point
    # It should be, as editar_alteracao reads it from request.args or similar
    
    new_block = (
        b"                # Buscar SEI/data diretamente de termos_alteracoes\r\n"
        b"                cur.execute(\"\"\"\r\n"
        b"                    SELECT termo_sei_doc, data_assinatura\r\n"
        b"                    FROM public.termos_alteracoes\r\n"
        b"                    WHERE numero_termo = %s AND instrumento_alteracao = %s AND alt_numero = %s\r\n"
        b"                    ORDER BY id DESC LIMIT 1\r\n"
        b"                \"\"\", (numero_termo, instrumento, alt_numero))\r\n"
        b"                resultado = cur.fetchone()\r\n"
        b"                if resultado:\r\n"
        b"                    sei_documento = resultado['termo_sei_doc']\r\n"
        b"                    data_assinatura_obj = resultado['data_assinatura']\r\n"
        b"                    if data_assinatura_obj:\r\n"
        b"                        data_assinatura = data_assinatura_obj.strftime('%Y-%m-%d')\r\n"
    )
    
    content = content[:idx_old_block] + new_block + content[idx_old_block_end:]
    print('Block replaced successfully')
else:
    print('End marker not found')
    print(repr(content[idx_old_block:idx_old_block+1000]))

with open('routes/parcerias.py', 'wb') as f:
    f.write(content)
print('Done')
