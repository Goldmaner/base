"""
Teste da função obter_dados para verificar o erro
"""

import sys
sys.path.insert(0, '..')

import psycopg2
import psycopg2.extras
from config import DB_CONFIG
import copy

# Simular a configuração
TABELAS_CONFIG = {
    'c_pessoa_gestora': {
        'nome': 'Pessoas Gestoras',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_pg', 'setor', 'numero_rf', 'status_pg', 'email_pg'],
        'labels': {'nome_pg': 'Nome', 'setor': 'Setor', 'numero_rf': 'Número do R.F.', 'status_pg': 'Status', 'email_pg': 'E-mail'},
        'ordem': 'nome_pg',
        'tipos_campo': {
            'setor': 'select_dinamico',
            'query_setor': 'SELECT DISTINCT setor FROM categoricas.c_pessoa_gestora WHERE setor IS NOT NULL ORDER BY setor',
            'status_pg': 'select',
            'opcoes_status_pg': ['Ativo', 'Inativo', 'Desconhecido']
        }
    }
}

print("=== Teste da função obter_dados ===\n")

try:
    config = TABELAS_CONFIG['c_pessoa_gestora']
    schema = config['schema']
    tabela = 'c_pessoa_gestora'
    colunas = ['id'] + config['colunas_editaveis']
    ordem = config['ordem']
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    query = f"""
        SELECT {', '.join(colunas)}
        FROM {schema}.{tabela}
        ORDER BY {ordem}
    """
    print(f"Query principal:\n{query}\n")
    cur.execute(query)
    dados = cur.fetchall()
    print(f"✅ Dados carregados: {len(dados)} registros\n")
    
    # Buscar opções dinâmicas para selects
    config_com_opcoes = copy.deepcopy(config)
    
    if 'tipos_campo' in config_com_opcoes:
        print("Processando tipos_campo...")
        items_list = list(config_com_opcoes['tipos_campo'].items())
        for campo, tipo in items_list:
            print(f"  Campo: {campo}, Tipo: {tipo}")
            if tipo == 'select_dinamico':
                query_key = f'query_{campo}'
                print(f"    Procurando chave: {query_key}")
                if query_key in config_com_opcoes['tipos_campo']:
                    query_dinamica = config_com_opcoes['tipos_campo'][query_key]
                    print(f"    Query dinâmica: {query_dinamica}")
                    
                    cur.execute(query_dinamica)
                    opcoes_raw = cur.fetchall()
                    
                    # Extrair valores da primeira coluna
                    opcoes = [list(row.values())[0] for row in opcoes_raw if list(row.values())[0]]
                    print(f"    ✅ Opções carregadas: {opcoes}")
                    config_com_opcoes['tipos_campo'][f'opcoes_{campo}'] = opcoes
    
    cur.close()
    conn.close()
    
    print("\n✅ Teste concluído com sucesso!")
    print(f"\nConfig final tem opcoes_setor: {'opcoes_setor' in config_com_opcoes.get('tipos_campo', {})}")
    if 'opcoes_setor' in config_com_opcoes.get('tipos_campo', {}):
        print(f"Opções: {config_com_opcoes['tipos_campo']['opcoes_setor']}")
    
except Exception as e:
    print(f"\n❌ ERRO: {str(e)}")
    import traceback
    traceback.print_exc()
