"""
Rotas para Conciliação Bancária - Análise de Prestação de Contas
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor, get_db
from functools import wraps

bp = Blueprint('conc_bancaria', __name__, url_prefix='/conc_bancaria')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Sessão expirada'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
def index():
    """Página principal de conciliação bancária"""
    return render_template('conc_bancaria.html')


@bp.route('/api/extrato', methods=['GET'])
@login_required
def api_listar_extrato():
    """
    API para listar movimentações do extrato
    Query params: numero_termo, limite
    """
    try:
        cur = get_cursor()
        
        numero_termo = request.args.get('numero_termo', '').strip()
        limite = request.args.get('limite', '100').strip()
        
        query = """
            SELECT 
                id,
                indice,
                data,
                credito,
                debito,
                discriminacao,
                cat_transacao,
                competencia,
                origem_destino,
                cat_avaliacao,
                avaliacao_analista,
                mesclado_com,
                numero_termo
            FROM analises_pc.conc_extrato
            WHERE 1=1
        """
        
        params = []
        
        if numero_termo:
            query += " AND numero_termo = %s"
            params.append(numero_termo)
        
        # Ordenar por índice
        query += " ORDER BY indice ASC, id ASC"
        
        # Adicionar limite
        if limite.lower() != 'todas':
            try:
                limite_num = int(limite)
                query += f" LIMIT {limite_num}"
            except ValueError:
                query += " LIMIT 100"
        
        cur.execute(query, params)
        extrato = cur.fetchall()
        
        # Processar dados
        resultado = []
        for item in extrato:
            row = dict(item)
            
            # Converter datas para string ISO
            if row.get('data'):
                row['data'] = row['data'].isoformat()
            if row.get('competencia'):
                row['competencia'] = row['competencia'].isoformat()
            
            # Converter valores numéricos para float
            if row.get('credito'):
                row['credito'] = float(row['credito'])
            if row.get('debito'):
                row['debito'] = float(row['debito'])
            if row.get('discriminacao'):
                row['discriminacao'] = float(row['discriminacao'])
            
            # Converter mesclado_com (array PostgreSQL para lista Python)
            if row.get('mesclado_com'):
                row['mesclado_com'] = list(row['mesclado_com'])
            else:
                row['mesclado_com'] = []
            
            resultado.append(row)
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar extrato: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/extrato', methods=['POST'])
@login_required
def api_salvar_extrato():
    """API para salvar múltiplas linhas do extrato de uma vez"""
    try:
        dados = request.get_json()
        linhas = dados.get('linhas', [])
        numero_termo = dados.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400
        
        cur = get_cursor()
        db = get_db()
        
        # Coletar IDs das linhas enviadas para identificar quais manter
        ids_enviados = [linha.get('id') for linha in linhas if linha.get('id')]
        
        # Deletar apenas linhas que foram removidas (não estão mais na lista)
        if ids_enviados:
            placeholders = ','.join(['%s'] * len(ids_enviados))
            cur.execute(f"""
                DELETE FROM analises_pc.conc_extrato 
                WHERE numero_termo = %s AND id NOT IN ({placeholders})
            """, [numero_termo] + ids_enviados)
        else:
            # Se não há IDs (todas linhas novas), deletar tudo do termo
            cur.execute("DELETE FROM analises_pc.conc_extrato WHERE numero_termo = %s", (numero_termo,))
        
        # UPSERT: UPDATE se existe, INSERT se não existe
        ids_processados = []
        for linha in linhas:
            # Validar campos obrigatórios
            if not linha.get('indice'):
                continue  # Pular linhas sem índice
            
            # Validar: não pode ter crédito e débito ao mesmo tempo
            credito = linha.get('credito')
            debito = linha.get('debito')
            
            if credito and debito:
                return jsonify({'erro': 'Não é possível ter crédito e débito na mesma linha'}), 400
            
            linha_id = linha.get('id')
            
            if linha_id:
                # UPDATE: linha já existe
                cur.execute("""
                    UPDATE analises_pc.conc_extrato SET
                        indice = %s,
                        data = %s,
                        credito = %s,
                        debito = %s,
                        discriminacao = %s,
                        cat_transacao = %s,
                        competencia = %s,
                        origem_destino = %s,
                        cat_avaliacao = %s,
                        avaliacao_analista = %s,
                        mesclado_com = %s
                    WHERE id = %s AND numero_termo = %s
                    RETURNING id
                """, (
                    linha.get('indice'),
                    linha.get('data') or None,
                    credito or None,
                    debito or None,
                    linha.get('discriminacao') or None,
                    linha.get('cat_transacao') or None,
                    linha.get('competencia') or None,
                    linha.get('origem_destino') or None,
                    linha.get('cat_avaliacao') or None,
                    linha.get('avaliacao_analista') or None,
                    linha.get('mesclado_com') or None,
                    linha_id,
                    numero_termo
                ))
                result = cur.fetchone()
                if result:
                    ids_processados.append(result['id'])
            else:
                # INSERT: nova linha
                cur.execute("""
                    INSERT INTO analises_pc.conc_extrato (
                        indice, data, credito, debito, discriminacao,
                        cat_transacao, competencia, origem_destino,
                        cat_avaliacao, avaliacao_analista, mesclado_com, numero_termo
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    RETURNING id
                """, (
                    linha.get('indice'),
                    linha.get('data') or None,
                    credito or None,
                    debito or None,
                    linha.get('discriminacao') or None,
                    linha.get('cat_transacao') or None,
                    linha.get('competencia') or None,
                    linha.get('origem_destino') or None,
                    linha.get('cat_avaliacao') or None,
                    linha.get('avaliacao_analista') or None,
                    linha.get('mesclado_com') or None,
                    numero_termo
                ))
                novo_id = cur.fetchone()['id']
                ids_processados.append(novo_id)
        
        db.commit()
        
        return jsonify({
            'mensagem': f'{len(ids_processados)} linhas salvas com sucesso',
            'ids': ids_processados
        }), 200
        
    except Exception as e:
        print(f"[ERRO] ao salvar extrato: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/extrato/<int:extrato_id>', methods=['DELETE'])
@login_required
def api_excluir_extrato(extrato_id):
    """API para excluir uma linha do extrato"""
    try:
        cur = get_cursor()
        db = get_db()
        
        cur.execute("DELETE FROM analises_pc.conc_extrato WHERE id = %s", (extrato_id,))
        db.commit()
        
        return jsonify({'mensagem': 'Linha excluída com sucesso'}), 200
        
    except Exception as e:
        print(f"[ERRO] ao excluir linha {extrato_id}: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/termos', methods=['GET'])
@login_required
def api_listar_termos():
    """API para listar números de termos disponíveis"""
    try:
        cur = get_cursor()
        
        cur.execute("""
            SELECT DISTINCT numero_termo 
            FROM public.parcerias 
            WHERE numero_termo IS NOT NULL 
            ORDER BY numero_termo
        """)
        
        termos = [row['numero_termo'] for row in cur.fetchall()]
        
        return jsonify(termos), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar termos: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-despesas', methods=['GET'])
@login_required
def api_categorias_despesas():
    """API para listar categorias de despesas de um termo específico"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        filtro = request.args.get('filtro', '').strip()
        
        if not numero_termo:
            return jsonify([]), 200
        
        query = """
            SELECT DISTINCT categoria_despesa 
            FROM public.parcerias_despesas 
            WHERE numero_termo = %s 
              AND categoria_despesa IS NOT NULL
        """
        params = [numero_termo]
        
        if filtro:
            query += " AND categoria_despesa ILIKE %s"
            params.append(f'%{filtro}%')
        
        query += " ORDER BY categoria_despesa"
        
        cur.execute(query, params)
        
        categorias = [{'categoria_despesa': row['categoria_despesa']} for row in cur.fetchall()]
        
        return jsonify(categorias), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar categorias de despesas: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-analise', methods=['GET'])
@login_required
def api_categorias_analise():
    """API para listar categorias de análise"""
    try:
        cur = get_cursor()
        filtro = request.args.get('filtro', '').strip()
        
        query = """
            SELECT categoria_extra, tipo_transacao, descricao, correspondente
            FROM categoricas.c_despesas_analise
        """
        params = []
        
        if filtro:
            query += " WHERE categoria_extra ILIKE %s"
            params.append(f'%{filtro}%')
        
        query += " ORDER BY categoria_extra"
        
        cur.execute(query, params)
        
        categorias = [dict(row) for row in cur.fetchall()]
        
        return jsonify(categorias), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar categorias de análise: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/periodo-termo', methods=['GET'])
@login_required
def api_periodo_termo():
    """API para obter período (datas início e final) de um termo de parceria"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        query = """
            SELECT inicio, final
            FROM public.parcerias
            WHERE numero_termo = %s
        """
        
        cur.execute(query, (numero_termo,))
        resultado = cur.fetchone()
        
        if not resultado:
            return jsonify({'erro': 'Termo não encontrado'}), 404
        
        periodo = dict(resultado)
        
        # Converter datas para string ISO
        if periodo.get('inicio'):
            periodo['inicio'] = periodo['inicio'].isoformat()
        if periodo.get('final'):
            periodo['final'] = periodo['final'].isoformat()
        
        return jsonify(periodo), 200
        
    except Exception as e:
        print(f"[ERRO] ao buscar período do termo: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/banco', methods=['GET'])
@login_required
def api_get_banco():
    """API para obter o banco do extrato de um termo"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        query = """
            SELECT banco_extrato
            FROM analises_pc.conc_banco
            WHERE numero_termo = %s
        """
        
        cur.execute(query, (numero_termo,))
        resultado = cur.fetchone()
        
        if not resultado:
            return jsonify({'banco_extrato': None}), 200
        
        return jsonify(dict(resultado)), 200
        
    except Exception as e:
        print(f"[ERRO] ao buscar banco: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/banco', methods=['POST'])
@login_required
def api_save_banco():
    """API para salvar o banco do extrato de um termo"""
    try:
        dados = request.get_json()
        numero_termo = dados.get('numero_termo')
        banco_extrato = dados.get('banco_extrato')
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        cur = get_cursor()
        db = get_db()
        
        # Verificar se já existe
        cur.execute("""
            SELECT id FROM analises_pc.conc_banco 
            WHERE numero_termo = %s
        """, (numero_termo,))
        
        existe = cur.fetchone()
        
        if existe:
            # Atualizar
            cur.execute("""
                UPDATE analises_pc.conc_banco 
                SET banco_extrato = %s
                WHERE numero_termo = %s
            """, (banco_extrato, numero_termo))
        else:
            # Inserir
            cur.execute("""
                INSERT INTO analises_pc.conc_banco (numero_termo, banco_extrato)
                VALUES (%s, %s)
            """, (numero_termo, banco_extrato))
        
        db.commit()
        
        return jsonify({'mensagem': 'Banco salvo com sucesso'}), 200
        
    except Exception as e:
        print(f"[ERRO] ao salvar banco: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500
