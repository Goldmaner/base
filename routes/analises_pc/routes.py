from flask import render_template, request, jsonify, g
from . import analises_pc_bp
from db import get_db
import psycopg2
import psycopg2.extras
import traceback

@analises_pc_bp.route('/')
def index():
    """Página inicial do checklist de análise de prestação de contas"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Buscar lista de termos para o dropdown
    cur.execute("SELECT DISTINCT numero_termo FROM public.parcerias ORDER BY numero_termo")
    termos = cur.fetchall()
    
    # Buscar lista de analistas
    cur.execute("SELECT DISTINCT nome_analista FROM categoricas.c_analistas ORDER BY nome_analista")
    analistas = cur.fetchall()
    
    cur.close()
    
    return render_template('analises_pc/index.html', termos=termos, analistas=analistas)


@analises_pc_bp.route('/api/buscar_meses', methods=['POST'])
def buscar_meses():
    """Busca meses já analisados para um termo específico"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    
    if not numero_termo:
        return jsonify({'error': 'Número do termo não fornecido'}), 400
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("""
            SELECT DISTINCT meses_analisados 
            FROM analises_pc.checklist_termo 
            WHERE numero_termo = %s
            ORDER BY meses_analisados DESC
        """, (numero_termo,))
        
        meses = [row['meses_analisados'] for row in cur.fetchall()]
        cur.close()
        
        return jsonify({'meses': meses})
    
    except Exception as e:
        cur.close()
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"[ERRO] Erro ao buscar meses: {error_details}")
        return jsonify(error_details), 500


@analises_pc_bp.route('/api/carregar_checklist', methods=['POST'])
def carregar_checklist():
    """Carrega dados do checklist para um termo e meses específicos"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    meses_analisados = data.get('meses_analisados')
    
    if not numero_termo or not meses_analisados:
        return jsonify({'error': 'Dados incompletos'}), 400
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Buscar dados do checklist principal
        cur.execute("""
            SELECT * FROM analises_pc.checklist_termo 
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        checklist = cur.fetchone()
        
        # Buscar analistas responsáveis
        cur.execute("""
            SELECT nome_analista FROM analises_pc.checklist_analista 
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        analistas = [row['nome_analista'] for row in cur.fetchall()]
        
        # Buscar recursos (se houver)
        cur.execute("""
            SELECT * FROM analises_pc.checklist_recursos 
            WHERE numero_termo = %s AND meses_analisados = %s
            ORDER BY tipo_recurso
        """, (numero_termo, meses_analisados))
        recursos = cur.fetchall()
        
        cur.close()
        
        return jsonify({
            'checklist': checklist,
            'analistas': analistas,
            'recursos': recursos
        })
    
    except Exception as e:
        cur.close()
        # Log detalhado do erro
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"[ERRO] Erro ao carregar checklist: {error_details}")
        return jsonify(error_details), 500


@analises_pc_bp.route('/api/salvar_checklist', methods=['POST'])
def salvar_checklist():
    """Salva ou atualiza o checklist"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    meses_analisados = data.get('meses_analisados')
    nome_analista = data.get('nome_analista')
    analistas = data.get('analistas', [])
    checklist_data = data.get('checklist', {})
    recursos = data.get('recursos', [])
    
    if not numero_termo or not meses_analisados:
        return jsonify({'error': 'Dados incompletos'}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Verificar se já existe registro
        cur.execute("""
            SELECT id FROM analises_pc.checklist_termo 
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        existing = cur.fetchone()
        
        # Inserir ou atualizar checklist_termo
        if existing:
            cur.execute("""
                UPDATE analises_pc.checklist_termo SET
                    avaliacao_celebracao = %s,
                    avaliacao_prestacao_contas = %s,
                    preenchimento_dados_base = %s,
                    preenchimento_orcamento_anual = %s,
                    preenchimento_conciliacao_bancaria = %s,
                    avaliacao_dados_bancarios = %s,
                    documentos_sei_1 = %s,
                    avaliacao_resposta_inconsistencia = %s,
                    emissao_parecer = %s,
                    documentos_sei_2 = %s,
                    tratativas_restituicao = %s,
                    encaminhamento_encerramento = %s
                WHERE numero_termo = %s AND meses_analisados = %s
            """, (
                checklist_data.get('avaliacao_celebracao', False),
                checklist_data.get('avaliacao_prestacao_contas', False),
                checklist_data.get('preenchimento_dados_base', False),
                checklist_data.get('preenchimento_orcamento_anual', False),
                checklist_data.get('preenchimento_conciliacao_bancaria', False),
                checklist_data.get('avaliacao_dados_bancarios', False),
                checklist_data.get('documentos_sei_1', False),
                checklist_data.get('avaliacao_resposta_inconsistencia', False),
                checklist_data.get('emissao_parecer', False),
                checklist_data.get('documentos_sei_2', False),
                checklist_data.get('tratativas_restituicao', False),
                checklist_data.get('encaminhamento_encerramento', False),
                numero_termo,
                meses_analisados
            ))
        else:
            cur.execute("""
                INSERT INTO analises_pc.checklist_termo (
                    numero_termo, meses_analisados,
                    avaliacao_celebracao, avaliacao_prestacao_contas,
                    preenchimento_dados_base, preenchimento_orcamento_anual,
                    preenchimento_conciliacao_bancaria, avaliacao_dados_bancarios,
                    documentos_sei_1, avaliacao_resposta_inconsistencia,
                    emissao_parecer, documentos_sei_2,
                    tratativas_restituicao, encaminhamento_encerramento
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                numero_termo, meses_analisados,
                checklist_data.get('avaliacao_celebracao', False),
                checklist_data.get('avaliacao_prestacao_contas', False),
                checklist_data.get('preenchimento_dados_base', False),
                checklist_data.get('preenchimento_orcamento_anual', False),
                checklist_data.get('preenchimento_conciliacao_bancaria', False),
                checklist_data.get('avaliacao_dados_bancarios', False),
                checklist_data.get('documentos_sei_1', False),
                checklist_data.get('avaliacao_resposta_inconsistencia', False),
                checklist_data.get('emissao_parecer', False),
                checklist_data.get('documentos_sei_2', False),
                checklist_data.get('tratativas_restituicao', False),
                checklist_data.get('encaminhamento_encerramento', False)
            ))
        
        # Atualizar analistas - deletar e reinserir
        cur.execute("""
            DELETE FROM analises_pc.checklist_analista 
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        
        for analista in analistas:
            cur.execute("""
                INSERT INTO analises_pc.checklist_analista (numero_termo, meses_analisados, nome_analista)
                VALUES (%s, %s, %s)
            """, (numero_termo, meses_analisados, analista))
        
        # Atualizar recursos - deletar e reinserir
        cur.execute("""
            DELETE FROM analises_pc.checklist_recursos 
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        
        for recurso in recursos:
            cur.execute("""
                INSERT INTO analises_pc.checklist_recursos (
                    numero_termo, meses_analisados, tipo_recurso,
                    avaliacao_resposta_recursal, emissao_parecer_recursal, documentos_sei
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                numero_termo, meses_analisados,
                recurso.get('tipo_recurso', 1),
                recurso.get('avaliacao_resposta_recursal', False),
                recurso.get('emissao_parecer_recursal', False),
                recurso.get('documentos_sei', False)
            ))
        
        conn.commit()
        cur.close()
        
        return jsonify({'success': True, 'message': 'Checklist salvo com sucesso!'})
    
    except Exception as e:
        conn.rollback()
        cur.close()
        # Log detalhado do erro
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"[ERRO] Erro ao salvar checklist: {error_details}")
        return jsonify(error_details), 500
