"""
Blueprint de gerenciamento de listas/tabelas categóricas
"""

from flask import Blueprint, render_template, request, jsonify
from db import get_cursor, execute_query
from utils import login_required

listas_bp = Blueprint('listas', __name__, url_prefix='/listas')


# Configuração das tabelas gerenciáveis
TABELAS_CONFIG = {
    'c_analistas': {
        'nome': 'Analistas',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_analista'],
        'labels': {'nome_analista': 'Nome do Analista'},
        'ordem': 'nome_analista'
    },
    'c_pessoa_gestora': {
        'nome': 'Pessoas Gestoras',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_pg', 'setor', 'numero_rf', 'status_pg', 'email_pg'],
        'colunas_calculadas': ['total_pareceres', 'total_parcerias'],
        'labels': {
            'nome_pg': 'Nome', 
            'setor': 'Setor', 
            'numero_rf': 'Número do R.F.', 
            'status_pg': 'Status', 
            'email_pg': 'E-mail',
            'total_pareceres': 'Total de Pareceres',
            'total_parcerias': 'Total de Parcerias'
        },
        'colunas_filtro': ['nome_pg', 'setor', 'numero_rf', 'status_pg'],
        'ordem': 'nome_pg',
        'tipos_campo': {
            'setor': 'select_dinamico',
            'query_setor': 'SELECT DISTINCT setor FROM categoricas.c_pessoa_gestora WHERE setor IS NOT NULL ORDER BY setor',
            'status_pg': 'select',
            'opcoes_status_pg': ['Ativo', 'Inativo', 'Desconhecido']
        }
    },
    'c_responsabilidade_analise': {
        'nome': 'Responsabilidades de Análise',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_setor'],
        'labels': {'nome_setor': 'Nome do Setor'},
        'ordem': 'nome_setor'
    },
    'c_origem_recurso': {
        'nome': 'Origens de Recurso',
        'schema': 'categoricas',
        'colunas_editaveis': ['orgao', 'unidade', 'descricao'],
        'labels': {'orgao': 'Órgão', 'unidade': 'Unidade', 'descricao': 'Descrição'},
        'ordem': 'orgao, unidade'
    }
}


@listas_bp.route("/", methods=["GET"])
@login_required
def index():
    """
    Página principal de gerenciamento de listas
    """
    try:
        print("[DEBUG] Acessando rota /listas")
        print(f"[DEBUG] Tabelas config: {list(TABELAS_CONFIG.keys())}")
        return render_template('listas.html', tabelas=TABELAS_CONFIG)
    except Exception as e:
        print(f"[ERRO] Erro ao renderizar listas.html: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"Erro: {str(e)}", 500


@listas_bp.route("/api/dados/<tabela>", methods=["GET"])
@login_required
def obter_dados(tabela):
    """
    Retorna os dados de uma tabela específica
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        colunas = ['id'] + config['colunas_editaveis']
        ordem = config['ordem']
        
        cur = get_cursor()
        query = f"""
            SELECT {', '.join(colunas)}
            FROM {schema}.{tabela}
            ORDER BY {ordem}
        """
        cur.execute(query)
        dados = cur.fetchall()
        cur.close()
        
        # DEBUG: Verificar duplicação
        print(f"[DEBUG] Tabela {tabela}: {len(dados)} registros retornados")
        ids = [row['id'] for row in dados]
        print(f"[DEBUG] IDs únicos: {len(set(ids))}")
        if len(ids) != len(set(ids)):
            print(f"[ALERTA] DUPLICAÇÃO DETECTADA em {tabela}!")
            print(f"[DEBUG] IDs duplicados: {[i for i in ids if ids.count(i) > 1]}")
        
        # Converter para lista de dicionários
        resultado = []
        for row in dados:
            item = {'id': row['id']}
            for col in config['colunas_editaveis']:
                item[col] = row[col]
            resultado.append(item)
        
        # Se for pessoa_gestora, adicionar contagem de pareceres e parcerias
        if tabela == 'c_pessoa_gestora':
            cur = get_cursor()
            for item in resultado:
                # Contar pareceres
                cur.execute("""
                    SELECT COUNT(*) as total
                    FROM parcerias_analises
                    WHERE responsavel_pg = %s
                """, (item['nome_pg'],))
                contagem = cur.fetchone()
                item['total_pareceres'] = contagem['total'] if contagem else 0
                
                # Contar parcerias (somente a última atribuição de cada termo)
                cur.execute("""
                    SELECT COUNT(DISTINCT numero_termo) as total
                    FROM parcerias_pg pg1
                    WHERE pg1.nome_pg = %s
                    AND pg1.data_de_criacao = (
                        SELECT MAX(pg2.data_de_criacao)
                        FROM parcerias_pg pg2
                        WHERE pg2.numero_termo = pg1.numero_termo
                    )
                """, (item['nome_pg'],))
                contagem_parcerias = cur.fetchone()
                item['total_parcerias'] = contagem_parcerias['total'] if contagem_parcerias else 0
            cur.close()
        
        # Buscar opções dinâmicas para selects
        import copy
        config_com_opcoes = copy.deepcopy(config)
        if 'tipos_campo' in config_com_opcoes:
            # Criar lista de itens antes de iterar para evitar modificação durante iteração
            items_list = list(config_com_opcoes['tipos_campo'].items())
            for campo, tipo in items_list:
                if tipo == 'select_dinamico':
                    query_key = f'query_{campo}'
                    if query_key in config_com_opcoes['tipos_campo']:
                        cur = get_cursor()
                        cur.execute(config_com_opcoes['tipos_campo'][query_key])
                        opcoes_raw = cur.fetchall()
                        cur.close()
                        
                        # Extrair valores da primeira coluna
                        opcoes = [list(row.values())[0] for row in opcoes_raw if list(row.values())[0]]
                        config_com_opcoes['tipos_campo'][f'opcoes_{campo}'] = opcoes
        
        return jsonify({
            'dados': resultado,
            'config': config_com_opcoes
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/dados/<tabela>", methods=["POST"])
@login_required
def criar_registro(tabela):
    """
    Cria um novo registro na tabela
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        dados = request.json
        
        # Validar que todos os campos necessários foram enviados
        for col in config['colunas_editaveis']:
            if col not in dados:
                return jsonify({'erro': f'Campo {col} é obrigatório'}), 400
        
        # Montar query de inserção
        colunas = config['colunas_editaveis']
        placeholders = ', '.join(['%s'] * len(colunas))
        valores = [dados[col] for col in colunas]
        
        query = f"""
            INSERT INTO {schema}.{tabela} ({', '.join(colunas)})
            VALUES ({placeholders})
        """
        
        if execute_query(query, valores):
            return jsonify({
                'sucesso': True,
                'mensagem': 'Registro criado com sucesso'
            })
        else:
            return jsonify({'erro': 'Falha ao criar registro no banco'}), 500
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/dados/<tabela>/<int:id>", methods=["PUT"])
@login_required
def atualizar_registro(tabela, id):
    """
    Atualiza um registro existente
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        dados = request.json
        
        # Se for pessoa_gestora e o nome mudou, precisamos atualizar Parcerias também
        nome_antigo = None
        if tabela == 'c_pessoa_gestora' and 'nome_pg' in dados:
            cur = get_cursor()
            cur.execute(f"SELECT nome_pg FROM {schema}.{tabela} WHERE id = %s", (id,))
            resultado = cur.fetchone()
            if resultado:
                nome_antigo = resultado['nome_pg']
            cur.close()
        
        # Montar query de atualização apenas com campos editáveis
        colunas = config['colunas_editaveis']
        set_clause = ', '.join([f"{col} = %s" for col in colunas])
        valores = [dados.get(col) for col in colunas]
        valores.append(id)
        
        query = f"""
            UPDATE {schema}.{tabela}
            SET {set_clause}
            WHERE id = %s
        """
        
        if execute_query(query, valores):
            # Se alterou nome da pessoa gestora, atualizar também na tabela parcerias_analises
            if tabela == 'c_pessoa_gestora' and nome_antigo and nome_antigo != dados.get('nome_pg'):
                query_parcerias = """
                    UPDATE parcerias_analises
                    SET responsavel_pg = %s
                    WHERE responsavel_pg = %s
                """
                resultado_update = execute_query(query_parcerias, (dados.get('nome_pg'), nome_antigo))
                print(f"[INFO] Atualizado responsavel_pg de '{nome_antigo}' para '{dados.get('nome_pg')}' em parcerias_analises")
            
            return jsonify({
                'sucesso': True,
                'mensagem': 'Registro atualizado com sucesso'
            })
        else:
            return jsonify({'erro': 'Falha ao atualizar registro no banco'}), 500
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@listas_bp.route("/api/dados/<tabela>/<int:id>", methods=["DELETE"])
@login_required
def excluir_registro(tabela, id):
    """
    Exclui um registro
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        
        query = f"""
            DELETE FROM {schema}.{tabela}
            WHERE id = %s
        """
        
        if execute_query(query, (id,)):
            return jsonify({
                'sucesso': True,
                'mensagem': 'Registro excluído com sucesso'
            })
        else:
            return jsonify({'erro': 'Falha ao excluir registro no banco'}), 500
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
