"""
Rotas para Conciliação de Rendimentos de Ativos Financeiros - Análise PC
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor, get_db
from functools import wraps
from decorators import requires_access
from datetime import datetime, date
import calendar

bp = Blueprint('conc_rendimentos', __name__, url_prefix='/conc_rendimentos')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Sessão expirada'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
@requires_access('conc_rendimentos')
def index():
    """Página principal de conciliação de rendimentos"""
    return render_template('analises_pc/conc_rendimentos.html')


@bp.route('/api/rendimentos', methods=['GET'])
@login_required
@requires_access('conc_rendimentos')
def api_listar_rendimentos():
    """
    API para listar rendimentos de um termo
    Query params: numero_termo
    """
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400
        
        query = """
            SELECT 
                id,
                numero_termo,
                rendimento_bruto,
                rendimento_ir,
                rendimento_iof,
                data_referencia,
                observacoes
            FROM analises_pc.conc_rendimentos
            WHERE numero_termo = %s
            ORDER BY data_referencia ASC
        """
        
        cur.execute(query, (numero_termo,))
        rendimentos = cur.fetchall()
        
        # Processar dados
        resultado = []
        for item in rendimentos:
            row = dict(item)
            
            # Converter data para string ISO
            if row.get('data_referencia'):
                row['data_referencia'] = row['data_referencia'].isoformat()
            
            # Converter valores numéricos para float
            if row.get('rendimento_bruto'):
                row['rendimento_bruto'] = float(row['rendimento_bruto'])
            if row.get('rendimento_ir'):
                row['rendimento_ir'] = float(row['rendimento_ir'])
            if row.get('rendimento_iof'):
                row['rendimento_iof'] = float(row['rendimento_iof'])
            
            resultado.append(row)
        
        return jsonify(resultado), 200
        
    except Exception as e:
        print(f"[ERRO] ao listar rendimentos: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/rendimentos', methods=['POST'])
@login_required
@requires_access('conc_rendimentos')
def api_salvar_rendimentos():
    """API para salvar rendimentos"""
    try:
        dados = request.get_json()
        rendimentos = dados.get('rendimentos', [])
        numero_termo = dados.get('numero_termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400
        
        cur = get_cursor()
        db = get_db()
        
        ids_processados = []
        
        for rendimento in rendimentos:
            rendimento_id = rendimento.get('id')
            data_referencia = rendimento.get('data_referencia')
            
            if not data_referencia:
                continue  # Pular linhas sem data de referência
            
            rendimento_bruto = rendimento.get('rendimento_bruto') or 0
            rendimento_ir = rendimento.get('rendimento_ir') or 0
            rendimento_iof = rendimento.get('rendimento_iof') or 0
            observacoes = rendimento.get('observacoes') or ''
            
            if rendimento_id:
                # UPDATE: registro já existe
                cur.execute("""
                    UPDATE analises_pc.conc_rendimentos SET
                        rendimento_bruto = %s,
                        rendimento_ir = %s,
                        rendimento_iof = %s,
                        observacoes = %s
                    WHERE id = %s AND numero_termo = %s
                    RETURNING id
                """, (
                    rendimento_bruto,
                    rendimento_ir,
                    rendimento_iof,
                    observacoes,
                    rendimento_id,
                    numero_termo
                ))
                result = cur.fetchone()
                if result:
                    ids_processados.append(result['id'])
            else:
                # INSERT: novo registro
                cur.execute("""
                    INSERT INTO analises_pc.conc_rendimentos (
                        numero_termo, rendimento_bruto, rendimento_ir,
                        rendimento_iof, data_referencia, observacoes
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    numero_termo,
                    rendimento_bruto,
                    rendimento_ir,
                    rendimento_iof,
                    data_referencia,
                    observacoes
                ))
                novo_id = cur.fetchone()['id']
                ids_processados.append(novo_id)
        
        db.commit()
        
        return jsonify({
            'mensagem': f'{len(ids_processados)} rendimentos salvos com sucesso',
            'ids': ids_processados
        }), 200
        
    except Exception as e:
        print(f"[ERRO] ao salvar rendimentos: {e}")
        import traceback
        traceback.print_exc()
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/periodo-termo', methods=['GET'])
@login_required
@requires_access('conc_rendimentos')
def api_periodo_termo():
    """API para obter período (datas início e final) de um termo"""
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
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500
