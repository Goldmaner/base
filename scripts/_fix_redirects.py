import sys, re

with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

# Fix 1: duplicata redirect in salvar_alteracao (~line 4571)
old1 = (
    b"        if duplicata and duplicata['total'] > 0:\r\n"
    b"            flash(f'J\xc3\xa1 existe uma altera\xc3\xa7\xc3\xa3o cadastrada para "
    b"{instrumento_alteracao} n\xc2\xba {alt_numero} do termo {numero_termo}. "
    b"Por favor, edite o registro existente.', 'warning')\r\n"
    b"            return redirect(url_for('parcerias.dgp_alteracoes'))\r\n"
)
new1 = (
    b"        if duplicata and duplicata['total'] > 0:\r\n"
    b"            flash(f'J\xc3\xa1 existe uma altera\xc3\xa7\xc3\xa3o cadastrada para "
    b"{instrumento_alteracao} n\xc2\xba {alt_numero} do termo {numero_termo}. "
    b"Por favor, edite o registro existente.', 'warning')\r\n"
    b"            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':\r\n"
    b"                return jsonify(success=False, message=f'J\xc3\xa1 existe uma altera\xc3\xa7\xc3\xa3o para este instrumento/n\xc3\xbamero.')\r\n"
    b"            return redirect(url_for('parcerias.dgp_kanban'))\r\n"
)

# Fix 2: tipos redirect in atualizar_alteracao (~line 5219)
old2 = (
    b"        if not tipos_alteracao or not any(tipos_alteracao):\r\n"
    b"            flash('Selecione pelo menos um tipo de altera\xc3\xa7\xc3\xa3o!', 'danger')\r\n"
    b"            return redirect(url_for('parcerias.dgp_alteracoes'))\r\n"
    b"        \r\n"
    b"        # L\xc3\x83\xe2\x80\x9cGICA DE REVERS\xc3\x83\xc6\x92O"
)
new2 = (
    b"        if not tipos_alteracao or not any(tipos_alteracao):\r\n"
    b"            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':\r\n"
    b"                return jsonify(success=False, message='Selecione pelo menos um tipo de altera\xc3\xa7\xc3\xa3o!')\r\n"
    b"            flash('Selecione pelo menos um tipo de altera\xc3\xa7\xc3\xa3o!', 'danger')\r\n"
    b"            return redirect(url_for('parcerias.dgp_kanban'))\r\n"
    b"        \r\n"
    b"        # L\xc3\x83\xe2\x80\x9cGICA DE REVERS\xc3\x83\xc6\x92O"
)

c1 = content.count(old1)
c2 = content.count(old2)
print(f'old1 count: {c1}')
print(f'old2 count: {c2}')

if c1 != 1 or c2 != 1:
    print('ERROR: counts not 1, aborting')
    sys.exit(1)

content = content.replace(old1, new1)
content = content.replace(old2, new2)

with open('routes/parcerias.py', 'wb') as f:
    f.write(content)

print('Done!')
