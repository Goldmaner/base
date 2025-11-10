"""
Blueprint de gerenciamento de listas/tabelas categóricas
"""

from flask import Blueprint, render_template, request, jsonify
from db import get_cursor, execute_query
from utils import login_required

listas_bp = Blueprint('listas', __name__, url_prefix='/listas')


def converter_valor_para_db(valor, campo, config):
    """
    Converte valores do frontend para o formato do banco de dados
    """
    # Se o campo for 'status' e valor for string, converter para boolean
    if campo == 'status' and isinstance(valor, str):
        return valor.lower() in ['ativo', 'true', '1', 'sim']
    
    # Se o campo for 'status_pg' e valor for string, manter string
    if campo == 'status_pg':
        return valor
    
    # Se o campo for 'status_c' e valor for string, manter string
    if campo == 'status_c':
        return valor
    
    return valor


def converter_valor_para_frontend(valor, campo):
    """
    Converte valores do banco de dados para o formato do frontend
    """
    # Se o campo for 'status' e valor for boolean, converter para string
    if campo == 'status' and isinstance(valor, bool):
        return 'Ativo' if valor else 'Inativo'
    
    return valor


# Configuração das tabelas gerenciáveis
TABELAS_CONFIG = {
    'c_analistas': {
        'nome': 'Analistas',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_analista', 'd_usuario', 'status'],
        'labels': {'nome_analista': 'Nome do Analista', 'd_usuario': 'R.F.', 'status': 'Status'},
        'ordem': 'nome_analista',
        'tipos_campo': {
            'status': ['Ativo', 'Inativo']
        },
        'inline_edit': True,  # Habilita edição inline
        'inline_columns': ['status']  # Colunas que podem ser editadas inline
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
    'c_coordenadores': {
        'nome': 'Coordenadores',
        'schema': 'categoricas',
        'colunas_editaveis': ['secretaria', 'coordenacao', 'nome_c', 'pronome', 'rf_c', 'status_c', 'e_mail_c', 'setor_sei'],
        'labels': {
            'secretaria': 'Secretaria',
            'coordenacao': 'Coordenação',
            'nome_c': 'Nome',
            'pronome': 'Pronome',
            'rf_c': 'R.F.',
            'status_c': 'Status',
            'e_mail_c': 'E-mail',
            'setor_sei': 'Setor SEI'
        },
        'colunas_filtro': ['secretaria', 'coordenacao', 'nome_c', 'status_c'],
        'ordem': 'nome_c',
        'tipos_campo': {
            'secretaria': 'select_dinamico',
            'query_secretaria': 'SELECT DISTINCT secretaria FROM categoricas.c_coordenadores WHERE secretaria IS NOT NULL ORDER BY secretaria',
            'coordenacao': 'text_com_datalist',
            'query_coordenacao': 'SELECT DISTINCT coordenacao FROM categoricas.c_coordenadores WHERE coordenacao IS NOT NULL ORDER BY coordenacao',
            'status_c': 'select',
            'opcoes_status_c': ['Ativo', 'Afastado', 'Inativo'],
            'pronome': 'select',
            'opcoes_pronome': ['Sr.', 'Sra.', 'Sr.(a)']
        }
    },
    'c_origem_recurso': {
        'nome': 'Origens de Recurso',
        'schema': 'categoricas',
        'colunas_editaveis': ['orgao', 'unidade', 'descricao'],
        'labels': {'orgao': 'Órgão', 'unidade': 'Unidade', 'descricao': 'Descrição'},
        'ordem': 'orgao, unidade'
    },
    'c_analistas_dgp': {
        'nome': 'Agentes DGP',
        'schema': 'categoricas',
        'colunas_editaveis': ['nome_analista', 'rf', 'email', 'status'],
        'labels': {
            'nome_analista': 'Nome do Agente',
            'rf': 'R.F.',
            'email': 'E-mail',
            'status': 'Status'
        },
        'colunas_filtro': ['nome_analista', 'rf', 'email', 'status'],
        'ordem': 'nome_analista',
        'tipos_campo': {
            'status': 'select',
            'opcoes_status': ['Ativo', 'Inativo']
        },
        'inline_edit': True,
        'inline_columns': ['status']
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
                # Converter valores booleanos para formato frontend
                valor = row[col]
                item[col] = converter_valor_para_frontend(valor, col)
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
        
        # Converter valores para formato do banco de dados
        valores = [converter_valor_para_db(dados[col], col, config) for col in colunas]
        
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
        
        # Verificar se veio 'campos' (edição inline) ou dados diretos (edição modal)
        campos_a_atualizar = dados.get('campos', dados)
        
        print(f"[DEBUG atualizar_registro] Tabela: {tabela}, ID: {id}")
        print(f"[DEBUG atualizar_registro] Dados recebidos: {dados}")
        print(f"[DEBUG atualizar_registro] Campos a atualizar: {campos_a_atualizar}")
        
        # Se for pessoa_gestora e o nome mudou, precisamos atualizar Parcerias também
        nome_antigo = None
        if tabela == 'c_pessoa_gestora' and 'nome_pg' in campos_a_atualizar:
            cur = get_cursor()
            cur.execute(f"SELECT nome_pg FROM {schema}.{tabela} WHERE id = %s", (id,))
            resultado = cur.fetchone()
            if resultado:
                nome_antigo = resultado['nome_pg']
            cur.close()
        
        # Montar query de atualização APENAS com os campos enviados
        colunas_validas = []
        valores = []
        
        for campo, valor in campos_a_atualizar.items():
            # Verificar se o campo está nas colunas editáveis
            if campo in config['colunas_editaveis']:
                colunas_validas.append(campo)
                # Converter valor para formato do banco de dados
                valor_convertido = converter_valor_para_db(valor, campo, config)
                valores.append(valor_convertido)
                print(f"[DEBUG atualizar_registro] Campo válido: {campo} = {valor} -> {valor_convertido}")
        
        if not colunas_validas:
            return jsonify({'erro': 'Nenhum campo válido para atualizar'}), 400
        
        set_clause = ', '.join([f"{col} = %s" for col in colunas_validas])
        valores.append(id)
        
        query = f"""
            UPDATE {schema}.{tabela}
            SET {set_clause}
            WHERE id = %s
        """
        
        print(f"[DEBUG atualizar_registro] Query: {query}")
        print(f"[DEBUG atualizar_registro] Valores: {valores}")
        
        if execute_query(query, valores):
            # Se alterou nome da pessoa gestora, atualizar também na tabela parcerias_analises
            if tabela == 'c_pessoa_gestora' and nome_antigo and nome_antigo != campos_a_atualizar.get('nome_pg'):
                query_parcerias = """
                    UPDATE parcerias_analises
                    SET responsavel_pg = %s
                    WHERE responsavel_pg = %s
                """
                resultado_update = execute_query(query_parcerias, (campos_a_atualizar.get('nome_pg'), nome_antigo))
                print(f"[INFO] Atualizado responsavel_pg de '{nome_antigo}' para '{campos_a_atualizar.get('nome_pg')}' em parcerias_analises")
            
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


@listas_bp.route("/api/dados/<tabela>/salvar-lote", methods=["POST"])
@login_required
def salvar_lote(tabela):
    """
    Salva múltiplos registros de uma vez (edição inline em lote)
    """
    if tabela not in TABELAS_CONFIG:
        return jsonify({'erro': 'Tabela inválida'}), 400
    
    try:
        dados = request.json
        registros = dados.get('registros', [])
        
        print(f"[DEBUG salvar_lote] Tabela: {tabela}")
        print(f"[DEBUG salvar_lote] Registros recebidos: {registros}")
        
        if not registros:
            return jsonify({'erro': 'Nenhum registro para salvar'}), 400
        
        config = TABELAS_CONFIG[tabela]
        schema = config['schema']
        
        # Processar cada registro
        erros = []
        sucesso_count = 0
        
        for registro in registros:
            reg_id = registro.get('id')
            campos = registro.get('campos', {})
            
            print(f"[DEBUG salvar_lote] Processando ID {reg_id}, campos: {campos}")
            
            if not reg_id or not campos:
                continue
            
            # Montar query de update
            sets = []
            valores = []
            for campo, valor in campos.items():
                if campo in config['colunas_editaveis']:
                    sets.append(f"{campo} = %s")
                    valores.append(valor)
                    print(f"[DEBUG salvar_lote] Campo {campo} = {valor} (tipo: {type(valor)})")
            
            if not sets:
                continue
            
            valores.append(reg_id)
            query = f"""
                UPDATE {schema}.{tabela}
                SET {', '.join(sets)}
                WHERE id = %s
            """
            
            print(f"[DEBUG salvar_lote] Query: {query}")
            print(f"[DEBUG salvar_lote] Valores: {tuple(valores)}")
            
            if execute_query(query, tuple(valores)):
                sucesso_count += 1
            else:
                erros.append(f"Falha ao atualizar registro ID {reg_id}")
        
        if erros:
            return jsonify({
                'sucesso': True,
                'parcial': True,
                'sucesso_count': sucesso_count,
                'mensagem': f'{sucesso_count} registros salvos. Alguns falharam.',
                'erros': erros
            })
        else:
            return jsonify({
                'sucesso': True,
                'sucesso_count': sucesso_count,
                'mensagem': f'{sucesso_count} registro(s) salvo(s) com sucesso'
            })
        
    except Exception as e:
        print(f"[ERRO salvar_lote] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500

