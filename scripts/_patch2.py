with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

idx_func = content.find(b'def atualizar_alteracao')

# Insert sei vars after tipos_alteracao = request.form.getlist
marker = b'tipos_alteracao = request.form.getlist'
idx_tipos = content.find(marker, idx_func)
idx_eol = content.find(b'\r\n', idx_tipos) + 2

already_there = b'alt_sei_documento = request.form.get' in content[idx_func:idx_func+3000]
if not already_there:
    new_lines = (
        b"        alt_sei_documento = request.form.get('alt_sei_documento', '').strip() or None\r\n"
        b"        alt_data_assinatura = request.form.get('alt_data_assinatura', '').strip() or None\r\n"
    )
    content = content[:idx_eol] + new_lines + content[idx_eol:]
    print('SEI vars added')
else:
    print('SEI vars already present')

# Now replace the SEI block
sei_marker = b'=== SALVAR/ATUALIZAR N\xc3\x83\xc5\xa1MERO SEI'
idx_sei_comment = content.find(sei_marker)
if idx_sei_comment >= 0:
    # Go back to find start of line
    idx_block_start = content.rfind(b'\r\n', 0, idx_sei_comment) + 2
    # Find end - look for a line that closes the except block
    # The block ends after: print(f"[ERRO] Falha ao salvar SEI na atualiza
    end_anchor = b'Falha ao salvar SEI na atualiza'
    idx_end_anchor = content.find(end_anchor, idx_sei_comment)
    if idx_end_anchor >= 0:
        idx_block_end = content.find(b'\r\n', idx_end_anchor) + 2
        
        old_block = content[idx_block_start:idx_block_end]
        print('Old sei block len:', len(old_block))
        
        concluido = b'Conclu\xc3\x83\xc2\xaddo'
        new_block = (
            b'        # === SALVAR SEI E DATA EM parcerias_sei ===\r\n'
            b"        if alt_status == '" + concluido + b"' and (alt_sei_documento or alt_data_assinatura):\r\n"
            b'            try:\r\n'
            b'                _salvar_sei_parcerias(cur, numero_termo, instrumento_alteracao, alt_numero,\r\n'
            b'                                      alt_sei_documento, alt_data_assinatura)\r\n'
            b'            except Exception as e:\r\n'
            b'                print(f"[ERRO] Falha ao salvar SEI em parcerias_sei: {e}")\r\n'
        )
        content = content[:idx_block_start] + new_block + content[idx_block_end:]
        print('SEI block replaced')
    else:
        print('End anchor not found, looking for other marker...')
        # Try to find the closing of the block
        idx_next_section = content.find(b'\r\n\r\n        #', idx_sei_comment)
        print('Next section at:', idx_next_section)
        ctx = content[idx_sei_comment:idx_sei_comment+1500]
        print(repr(ctx))
else:
    print('SEI marker not found')

with open('routes/parcerias.py', 'wb') as f:
    f.write(content)

print('Done')
