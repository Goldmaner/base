"""
Blueprint de gerenciamento de listas/tabelas categóricas
"""

from flask import Blueprint, render_template, request, jsonify
from db import get_cursor, execute_dual
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
        'colunas_editaveis': ['nome_pg', 'setor'],
        'labels': {'nome_pg': 'Nome', 'setor': 'Setor'},
        'ordem': 'nome_pg'
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
        
        # Converter para lista de dicionários
        resultado = []
        for row in dados:
            item = {'id': row['id']}
            for col in config['colunas_editaveis']:
                item[col] = row[col]
            resultado.append(item)
        
        return jsonify({
            'dados': resultado,
            'config': config
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
        
        if execute_dual(query, valores):
            return jsonify({
                'sucesso': True,
                'mensagem': 'Registro criado com sucesso'
            })
        else:
            return jsonify({'erro': 'Falha ao criar registro em ambos os bancos'}), 500
        
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
        
        if execute_dual(query, valores):
            return jsonify({
                'sucesso': True,
                'mensagem': 'Registro atualizado com sucesso'
            })
        else:
            return jsonify({'erro': 'Falha ao atualizar registro em ambos os bancos'}), 500
        
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
        
        if execute_dual(query, (id,)):
            return jsonify({
                'sucesso': True,
                'mensagem': 'Registro excluído com sucesso'
            })
        else:
            return jsonify({'erro': 'Falha ao excluir registro em ambos os bancos'}), 500
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
