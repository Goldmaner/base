# routes/pesquisa_parcerias.py
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from db import get_cursor, execute_query

pesquisa_parcerias_bp = Blueprint('pesquisa_parcerias', __name__, url_prefix='/pesquisa-parcerias')


def login_required(f):
    """Decorator para proteger rotas que requerem login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


def agente_dac_required(f):
    """Decorator para proteger rotas que requerem ser Agente DAC ou Agente Público"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        if session.get('tipo_usuario') not in ['Agente DAC', 'Agente Público']:
            return "Acesso negado. Apenas Agente DAC ou Agente Público podem acessar esta página.", 403
        return f(*args, **kwargs)
    return decorated_function


@pesquisa_parcerias_bp.route('/')
@agente_dac_required
def index():
    """Renderiza a página principal de pesquisa de parcerias"""
    return render_template('pesquisa_parcerias.html')


@pesquisa_parcerias_bp.route('/relatorio')
@agente_dac_required
def relatorio():
    """Renderiza a página de relatório de pesquisas"""
    return render_template('pesquisa_parcerias_relatorio.html')


@pesquisa_parcerias_bp.route('/api/oscs')
@agente_dac_required
def listar_oscs():
    """Retorna lista única de OSCs da tabela public.parcerias"""
    try:
        query = """
            SELECT DISTINCT osc
            FROM public.parcerias
            WHERE osc IS NOT NULL
            ORDER BY osc
        """
        
        cur = get_cursor()
        if cur is None:
            return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
        
        cur.execute(query)
        resultados = cur.fetchall()
        cur.close()
        
        oscs = [row['osc'] for row in resultados]
        
        return jsonify({
            'sucesso': True,
            'oscs': oscs
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@pesquisa_parcerias_bp.route('/api/cnpj/<nome_osc>')
@agente_dac_required
def buscar_cnpj(nome_osc):
    """Retorna o CNPJ de uma OSC específica"""
    try:
        query = """
            SELECT cnpj
            FROM public.parcerias
            WHERE osc = %s
            LIMIT 1
        """
        
        cur = get_cursor()
        if cur is None:
            return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
        
        cur.execute(query, (nome_osc,))
        resultados = cur.fetchall()
        cur.close()
        
        if len(resultados) == 0:
            return jsonify({'erro': 'OSC não encontrada'}), 404
        
        return jsonify({
            'sucesso': True,
            'cnpj': resultados[0]['cnpj']
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@pesquisa_parcerias_bp.route('/api/analistas-ativos')
@agente_dac_required
def listar_analistas_ativos():
    """Retorna lista de analistas ativos da tabela categoricas.c_analistas"""
    try:
        query = """
            SELECT nome_analista
            FROM categoricas.c_analistas
            WHERE status = 'Ativo'
            ORDER BY nome_analista
        """
        
        cur = get_cursor()
        if cur is None:
            return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
        
        cur.execute(query)
        resultados = cur.fetchall()
        cur.close()
        
        return jsonify({
            'sucesso': True,
            'analistas': resultados
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@pesquisa_parcerias_bp.route('/api/salvar', methods=['POST'])
@agente_dac_required
def salvar_pesquisa():
    """Salva uma nova pesquisa na tabela public.o_pesquisa_parcerias"""
    try:
        dados = request.json
        
        sei_informado = dados.get('sei_informado')
        nome_osc = dados.get('nome_osc')
        nome_emissor = dados.get('nome_emissor')
        
        if not all([sei_informado, nome_osc, nome_emissor]):
            return jsonify({'erro': 'Todos os campos são obrigatórios'}), 400
        
        # Gerar próximo número de pesquisa
        query_numero = """
            SELECT COALESCE(MAX(numero_pesquisa), 0) + 1 as proximo_numero
            FROM public.o_pesquisa_parcerias
        """
        
        cur = get_cursor()
        if cur is None:
            return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
        
        cur.execute(query_numero)
        resultado_numero = cur.fetchall()
        cur.close()
        
        if len(resultado_numero) == 0:
            return jsonify({'erro': 'Erro ao gerar número de pesquisa'}), 500
        
        numero_pesquisa = resultado_numero[0]['proximo_numero']
        
        # Inserir pesquisa
        query_insert = """
            INSERT INTO public.o_pesquisa_parcerias 
            (numero_pesquisa, sei_informado, nome_osc, nome_emissor, criado_em)
            VALUES (%s, %s, %s, %s, NOW())
            RETURNING id
        """
        
        sucesso = execute_query(
            query_insert, 
            (numero_pesquisa, sei_informado, nome_osc, nome_emissor)
        )
        
        if not sucesso:
            return jsonify({'erro': 'Erro ao salvar pesquisa no banco de dados'}), 500
        
        return jsonify({
            'sucesso': True,
            'mensagem': 'Pesquisa registrada com sucesso',
            'numero_pesquisa': numero_pesquisa
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@pesquisa_parcerias_bp.route('/api/pesquisas')
@agente_dac_required
def listar_pesquisas():
    """Retorna todas as pesquisas registradas"""
    try:
        query = """
            SELECT 
                id,
                numero_pesquisa,
                sei_informado,
                nome_osc,
                nome_emissor,
                criado_em
            FROM public.o_pesquisa_parcerias
            ORDER BY criado_em DESC
        """
        
        cur = get_cursor()
        if cur is None:
            return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
        
        cur.execute(query)
        resultados = cur.fetchall()
        cur.close()
        
        return jsonify({
            'sucesso': True,
            'pesquisas': resultados
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
