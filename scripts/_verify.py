with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

checks = [
    (b'termo_sei_doc, data_assinatura)', b'INSERT in atualizar_alteracao'),
    (b'alt_sei_documento = request.form.get', b'SEI vars in atualizar_alteracao'),
    (b'_salvar_sei_parcerias(cur, numero_termo', b'SEI helper call in atualizar_alteracao'),
    (b'Buscar SEI/data diretamente de termos_alteracoes', b'editar_alteracao read from termos_alteracoes'),
    (b'WHERE 1=1\r\n        """', b'api_termos_parcerias no rescisao filter'),
    (b'filtro_osc = request.args.get', b'filtro_osc in dgp_alteracoes'),
    (b'LEFT JOIN public.parcerias p ON t.numero_termo', b'LEFT JOIN in dgp_alteracoes'),
    (b'filtro_osc=filtro_osc', b'filtro_osc in render_template'),
]

for needle, desc in checks:
    found = needle in content
    print(f'[{"OK" if found else "MISSING"}] {desc}')
