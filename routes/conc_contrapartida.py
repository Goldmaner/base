# routes/conc_contrapartida.py
from flask import Blueprint, render_template, request, jsonify, session
from functools import wraps
from db import get_cursor, get_db

bp = Blueprint('conc_contrapartida', __name__, url_prefix='/conc_contrapartida')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Não autenticado'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
def index():
    """Renderiza a página de conciliação de contrapartida"""
    numero_termo = request.args.get('termo', '')
    return render_template('analises_pc/conc_contrapartida.html', numero_termo=numero_termo)


@bp.route('/api/contrapartidas', methods=['GET'])
@login_required
def listar_contrapartidas():
    """Lista todas as contrapartidas de um termo"""
    try:
        numero_termo = request.args.get('termo')
        
        if not numero_termo:
            return jsonify({'erro': 'Termo não informado'}), 400
        
        cur = get_cursor()
        
        # Buscar contrapartidas ordenadas por competência
        # Nota: created_at existe no banco, não precisa de atualizado_em
        query = """
            SELECT 
                id,
                numero_termo,
                competencia,
                categoria_despesa,
                valor_previsto,
                valor_executado,
                valor_considerado,
                guia,
                comprovante,
                observacoes,
                created_at
            FROM analises_pc.conc_contrapartida
            WHERE numero_termo = %s
            ORDER BY 
                CASE WHEN competencia = '2020-01-01' THEN 1 ELSE 0 END,
                competencia
        """
        
        cur.execute(query, (numero_termo,))
        contrapartidas = cur.fetchall()
        cur.close()
        
        # Converter para JSON, formatando datas e valores
        resultado = []
        for c in contrapartidas:
            resultado.append({
                'id': c['id'],
                'numero_termo': c['numero_termo'],
                'competencia': c['competencia'].isoformat() if c['competencia'] else None,
                'categoria_despesa': c['categoria_despesa'],
                'valor_previsto': float(c['valor_previsto']) if c['valor_previsto'] is not None else 0,
                'valor_executado': float(c['valor_executado']) if c['valor_executado'] is not None else 0,
                'valor_considerado': float(c['valor_considerado']) if c['valor_considerado'] is not None else 0,
                'guia': c['guia'],
                'comprovante': c['comprovante'],
                'observacoes': c['observacoes']
            })
        
        return jsonify({'contrapartidas': resultado}), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao listar contrapartidas: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/contrapartidas', methods=['POST'])
@login_required
def salvar_contrapartidas():
    """Salva ou atualiza contrapartidas (UPSERT)"""
    try:
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        contrapartidas = data.get('contrapartidas', [])
        
        if not numero_termo:
            return jsonify({'erro': 'Termo não informado'}), 400
        
        cur = get_cursor()
        ids_salvos = []
        
        for c in contrapartidas:
            contrapartida_id = c.get('id')
            competencia = c.get('competencia')
            categoria_despesa = c.get('categoria_despesa', '')
            valor_previsto = c.get('valor_previsto', 0)
            valor_executado = c.get('valor_executado', 0)
            valor_considerado = c.get('valor_considerado', 0)
            guia = c.get('guia', '')
            comprovante = c.get('comprovante', '')
            observacoes = c.get('observacoes', '')
            
            # Validar valores numéricos
            try:
                valor_previsto = float(valor_previsto) if valor_previsto is not None else 0
                valor_executado = float(valor_executado) if valor_executado is not None else 0
                valor_considerado = float(valor_considerado) if valor_considerado is not None else 0
            except (ValueError, TypeError):
                valor_previsto = 0
                valor_executado = 0
                valor_considerado = 0
            
            if contrapartida_id:
                # UPDATE - registro existente
                query = """
                    UPDATE analises_pc.conc_contrapartida
                    SET competencia = %s,
                        categoria_despesa = %s,
                        valor_previsto = %s,
                        valor_executado = %s,
                        valor_considerado = %s,
                        guia = %s,
                        comprovante = %s,
                        observacoes = %s
                    WHERE id = %s AND numero_termo = %s
                    RETURNING id
                """
                params = (
                    competencia,
                    categoria_despesa,
                    valor_previsto,
                    valor_executado,
                    valor_considerado,
                    guia,
                    comprovante,
                    observacoes,
                    contrapartida_id,
                    numero_termo
                )
            else:
                # INSERT - novo registro
                query = """
                    INSERT INTO analises_pc.conc_contrapartida
                    (numero_termo, competencia, categoria_despesa, valor_previsto, 
                     valor_executado, valor_considerado, guia, comprovante, observacoes)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
                params = (
                    numero_termo,
                    competencia,
                    categoria_despesa,
                    valor_previsto,
                    valor_executado,
                    valor_considerado,
                    guia,
                    comprovante,
                    observacoes
                )
            
            cur.execute(query, params)
            result = cur.fetchone()
            
            if result:
                ids_salvos.append(result['id'])
                # Atualizar ID no objeto se foi INSERT
                if not contrapartida_id:
                    c['id'] = result['id']
        
        get_db().commit()
        cur.close()
        
        return jsonify({
            'mensagem': f'{len(ids_salvos)} contrapartida(s) salva(s) com sucesso!',
            'ids': ids_salvos
        }), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao salvar contrapartidas: {str(e)}")
        import traceback
        traceback.print_exc()
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/contrapartidas/<int:id>', methods=['DELETE'])
@login_required
def excluir_contrapartida(id):
    """Exclui uma contrapartida"""
    try:
        cur = get_cursor()
        
        # Verificar se existe antes de excluir
        cur.execute("SELECT id FROM analises_pc.conc_contrapartida WHERE id = %s", (id,))
        if not cur.fetchone():
            return jsonify({'erro': 'Contrapartida não encontrada'}), 404
        
        # Excluir
        cur.execute("DELETE FROM analises_pc.conc_contrapartida WHERE id = %s", (id,))
        
        get_db().commit()
        cur.close()
        
        return jsonify({'mensagem': 'Contrapartida excluída com sucesso!'}), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao excluir contrapartida: {str(e)}")
        import traceback
        traceback.print_exc()
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/verificar-contrapartida/<path:numero_termo>', methods=['GET'])
@login_required
def verificar_contrapartida(numero_termo):
    """Verifica se o termo possui contrapartida"""
    try:
        cur = get_cursor()
        
        query = "SELECT contrapartida FROM public.parcerias WHERE numero_termo = %s"
        cur.execute(query, (numero_termo,))
        result = cur.fetchone()
        cur.close()
        
        tem_contrapartida = result and result['contrapartida'] == 1
        
        return jsonify({'tem_contrapartida': tem_contrapartida}), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao verificar contrapartida: {str(e)}")
        return jsonify({'erro': str(e)}), 500
