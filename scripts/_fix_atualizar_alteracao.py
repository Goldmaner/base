"""Script para corrigir atualizar_alteracao"""
import re

filepath = r'routes/parcerias.py'

with open(filepath, 'rb') as f:
    content = f.read()

# Replace the INSERT in atualizar_alteracao to include termo_sei_doc and data_assinatura
old_insert = b"""                INSERT INTO public.termos_alteracoes 
                (numero_termo, instrumento_alteracao, alt_numero, alt_tipo, alt_status,
                 alt_info, alt_old_info, alt_responsavel, alt_observacao,
                 alt_data_cadastro_inicio, alt_data_cadastro_fim,
                 criado_por, atualizado_por, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), {data_fim}, %s, %s, NOW())
            \"\"\", (
                numero_termo,
                instrumento_alteracao,
                alt_numero,
                alt_tipo.strip(),
                alt_status,
                alt_info,
                alt_old_info,
                alt_responsavel,
                alt_observacao if alt_observacao else None,
                usuario_atual,
                usuario_atual
            ))"""

new_insert = b"""                INSERT INTO public.termos_alteracoes 
                (numero_termo, instrumento_alteracao, alt_numero, alt_tipo, alt_status,
                 alt_info, alt_old_info, alt_responsavel, alt_observacao,
                 alt_data_cadastro_inicio, alt_data_cadastro_fim,
                 criado_por, atualizado_por, atualizado_em,
                 termo_sei_doc, data_assinatura)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), {data_fim}, %s, %s, NOW(), %s, %s)
            \"\"\", (
                numero_termo,
                instrumento_alteracao,
                alt_numero,
                alt_tipo.strip(),
                alt_status,
                alt_info,
                alt_old_info,
                alt_responsavel,
                alt_observacao if alt_observacao else None,
                usuario_atual,
                usuario_atual,
                alt_sei_documento if alt_status == 'Conclu\\xc3\\xaddo' else None,
                alt_data_assinatura if alt_status == 'Conclu\\xc3\\xaddo' else None
            ))"""

# Actually, let's use the proper encoding
new_insert = ("""                INSERT INTO public.termos_alteracoes 
                (numero_termo, instrumento_alteracao, alt_numero, alt_tipo, alt_status,
                 alt_info, alt_old_info, alt_responsavel, alt_observacao,
                 alt_data_cadastro_inicio, alt_data_cadastro_fim,
                 criado_por, atualizado_por, atualizado_em,
                 termo_sei_doc, data_assinatura)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), {data_fim}, %s, %s, NOW(), %s, %s)
            \"\"\", (
                numero_termo,
                instrumento_alteracao,
                alt_numero,
                alt_tipo.strip(),
                alt_status,
                alt_info,
                alt_old_info,
                alt_responsavel,
                alt_observacao if alt_observacao else None,
                usuario_atual,
                usuario_atual,
                alt_sei_documento if alt_status == 'Conclu\u00c3\u00addo' else None,
                alt_data_assinatura if alt_status == 'Conclu\u00c3\u00addo' else None
            ))""").encode('utf-8')

count = content.count(old_insert)
print(f'Found old_insert: {count} times')

if count == 1:
    content = content.replace(old_insert, new_insert)
    print('INSERT replaced successfully')

# Now replace the SEI/parcerias block in atualizar_alteracao
# Find the line "        # === SALVAR/ATUALIZAR..." after the loop
old_sei_block_start = b"        # === SALVAR/ATUALIZAR N\xc3\x83\xc5\xa1MERO SEI DO DOCUMENTO E DATA DE ASSINATURA (se status = Conclu\xc3\x83\xc2\xaddo) ===\r\n        alt_sei_documento = request.form.get('alt_sei_documento', '').strip()\r\n        alt_data_assinatura = request.form.get('alt_data_assinatura', '').strip()\r\n        \r\n        if alt_status == 'Conclu\xc3\x83\xc2\xaddo' and (alt_sei_documento or alt_data_assinatura):\r\n            try:\r\n                # Determinar as colunas baseadas no instrumento\r\n                aditamento = None\r\n                apostilamento = None\r\n                termo_tipo_sei = None\r\n                \r\n                if instrumento_alteracao == 'Termo de Aditamento':\r\n                    aditamento = alt_numero\r\n                elif instrumento_alteracao == 'Termo de Apostilamento':\r\n                    apostilamento = alt_numero\r\n                elif instrumento_alteracao == 'Termo de Apostilamento do Aditamento':\r\n                    apostilamento = alt_numero // 100\r\n                    aditamento = alt_numero % 100\r\n                else:\r\n                    termo_tipo_sei = instrumento_alteracao"

print('Searching for sei block...')
count2 = content.count(b"=== SALVAR/ATUALIZAR")
print(f'Found SEI/atualizar marker: {count2} times')

# Find the exact position
idx = content.find(b"=== SALVAR/ATUALIZAR")
if idx > 0:
    print('Found at position:', idx)
    print('Context around it:', repr(content[idx-20:idx+100]))

with open(filepath, 'wb') as f:
    f.write(content)

print('Done writing')
