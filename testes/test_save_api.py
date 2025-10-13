from app import app
import json

payload = {
    'numero_termo': 'TFM/072/2022/SMDHC/CPM',
    'despesas': [
        {'rubrica':'Serviços de Terceiros','quantidade':'1','categoria_despesa':'Coordenador (PJ)','valores_por_mes':{'1':'7225.00','2':'7225.00','3':'7225.00','4':'7225.00'}},
        {'rubrica':'Serviços de Terceiros','quantidade':'1','categoria_despesa':'Assistente Administrativo (PJ)','valores_por_mes':{'1':'2200.00','2':'2200.00','3':'2200.00','4':'2200.00'}},
        {'rubrica':'Serviços de Terceiros','quantidade':'1','categoria_despesa':'Palestrante (PJ)','valores_por_mes':{'1':'6200.00','2':'6200.00','3':'6200.00','4':'6200.00'}},
        {'rubrica':'Outras Despesas','quantidade':'5','categoria_despesa':'Kit Absorventes Reutilizáveis','valores_por_mes':{'1':'21875.00','2':'21875.00','3':'21875.00','4':'21875.00'}}
    ]
}

with app.test_client() as c:
    with c.session_transaction() as sess:
        sess['user_id'] = 1
        sess['email'] = 'test@example.com'
    rv = c.post('/api/despesa', data=json.dumps(payload), content_type='application/json')
    print('Status:', rv.status_code)
    print('Response:', rv.get_data(as_text=True))
    
    # Testar também o endpoint de carregar despesas
    print('\n--- Testando carregamento de despesas ---')
    rv2 = c.get(f'/api/despesas/{payload["numero_termo"]}')
    print('Status GET:', rv2.status_code)
    print('Response GET:', rv2.get_data(as_text=True))