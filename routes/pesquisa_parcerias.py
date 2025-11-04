# routes/pesquisa_parcerias.py
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from db import get_cursor, execute_query
import sys
import os

# Adicionar o diretório scripts ao path para importar funcoes_texto
scripts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

try:
    from funcoes_texto import processar_texto_automatico, obter_modelo_texto, verificar_osc_existe
except ImportError as e:
    print(f"[ERRO] Não foi possível importar funcoes_texto: {e}")
    print(f"[DEBUG] scripts_path = {scripts_path}")
    print(f"[DEBUG] sys.path = {sys.path}")
    # Importar inline se falhar
    processar_texto_automatico = None
    obter_modelo_texto = None
    verificar_osc_existe = None

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
    user = {
        'tipo_usuario': session.get('tipo_usuario'),
        'email': session.get('email')
    }
    return render_template('pesquisa_parcerias.html', user=user)


@pesquisa_parcerias_bp.route('/relatorio')
@agente_dac_required
def relatorio():
    """Renderiza a página de relatório de pesquisas"""
    return render_template('pesquisa_parcerias_relatorio.html')


@pesquisa_parcerias_bp.route('/api/proximo-numero')
@agente_dac_required
def obter_proximo_numero():
    """Retorna o próximo número de pesquisa (reseta anualmente)"""
    try:
        from datetime import datetime
        ano_atual = datetime.now().year
        
        query = """
            SELECT COALESCE(MAX(numero_pesquisa), 0) + 1 as proximo_numero
            FROM public.o_pesquisa_parcerias
            WHERE EXTRACT(YEAR FROM criado_em) = %s
        """
        
        cur = get_cursor()
        if cur is None:
            return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
        
        cur.execute(query, (ano_atual,))
        resultado = cur.fetchall()
        cur.close()
        
        if len(resultado) == 0:
            proximo_numero = 1
        else:
            proximo_numero = resultado[0]['proximo_numero']
        
        return jsonify({
            'sucesso': True,
            'proximo_numero': proximo_numero,
            'ano': ano_atual
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


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
        cnpj = dados.get('cnpj', '')  # CNPJ pode ser vazio
        osc_identificada = dados.get('osc_identificada', True)  # Default True
        numero_pesquisa = dados.get('numero_pesquisa')  # Pode vir editado do frontend
        
        if not all([sei_informado, nome_osc, nome_emissor]):
            return jsonify({'erro': 'Campos obrigatórios: SEI, Nome OSC e Emissor'}), 400
        
        # Se não veio número da pesquisa ou é inválido, gerar automaticamente
        if not numero_pesquisa or numero_pesquisa < 1:
            from datetime import datetime
            ano_atual = datetime.now().year
            
            query_numero = """
                SELECT COALESCE(MAX(numero_pesquisa), 0) + 1 as proximo_numero
                FROM public.o_pesquisa_parcerias
                WHERE EXTRACT(YEAR FROM criado_em) = %s
            """
            
            cur = get_cursor()
            if cur is None:
                return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
            
            cur.execute(query_numero, (ano_atual,))
            resultado_numero = cur.fetchall()
            cur.close()
            
            if len(resultado_numero) == 0:
                numero_pesquisa = 1
            else:
                numero_pesquisa = resultado_numero[0]['proximo_numero']
        
        # Inserir pesquisa com CNPJ
        query_insert = """
            INSERT INTO public.o_pesquisa_parcerias 
            (numero_pesquisa, sei_informado, nome_osc, cnpj, nome_emissor, osc_identificada, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        
        sucesso = execute_query(
            query_insert, 
            (numero_pesquisa, sei_informado, nome_osc, cnpj, nome_emissor, osc_identificada)
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
                osc_identificada,
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


@pesquisa_parcerias_bp.route('/api/pesquisas/<int:numero_pesquisa>', methods=['DELETE'])
@agente_dac_required
def excluir_pesquisa(numero_pesquisa):
    """Exclui uma pesquisa pelo número"""
    try:
        query = """
            DELETE FROM public.o_pesquisa_parcerias
            WHERE numero_pesquisa = %s
        """
        
        cur = get_cursor()
        if cur is None:
            return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
        
        cur.execute(query, (numero_pesquisa,))
        cur.connection.commit()
        cur.close()
        
        return jsonify({
            'sucesso': True,
            'mensagem': f'Pesquisa {numero_pesquisa} excluída com sucesso'
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@pesquisa_parcerias_bp.route('/api/prosseguir-pesquisa', methods=['POST'])
@agente_dac_required
def prosseguir_pesquisa():
    """
    Salva a pesquisa e gera texto automático baseado no modelo
    """
    try:
        # Verificar se funções foram importadas corretamente
        if processar_texto_automatico is None or obter_modelo_texto is None or verificar_osc_existe is None:
            return jsonify({
                'erro': 'Módulo de funções de texto não foi carregado corretamente. Verifique o arquivo scripts/funcoes_texto.py'
            }), 500
        
        dados = request.json
        
        sei_informado = dados.get('sei_informado')
        nome_osc = dados.get('nome_osc')
        nome_emissor = dados.get('nome_emissor')
        cnpj = dados.get('cnpj', '')  # CNPJ pode ser vazio
        osc_identificada = dados.get('osc_identificada', True)
        numero_pesquisa = dados.get('numero_pesquisa')
        cnpj_informado = cnpj if cnpj else 'não informado'  # Para o texto
        
        if not all([sei_informado, nome_osc, nome_emissor]):
            return jsonify({'erro': 'Campos obrigatórios: SEI, Nome OSC e Emissor'}), 400
        
        # Se não veio número ou é inválido, gerar automaticamente
        if not numero_pesquisa or numero_pesquisa < 1:
            from datetime import datetime
            ano_atual = datetime.now().year
            
            query_numero = """
                SELECT COALESCE(MAX(numero_pesquisa), 0) + 1 as proximo_numero
                FROM public.o_pesquisa_parcerias
                WHERE EXTRACT(YEAR FROM criado_em) = %s
            """
            
            cur = get_cursor()
            if cur is None:
                return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
            
            cur.execute(query_numero, (ano_atual,))
            resultado_numero = cur.fetchall()
            cur.close()
            
            if len(resultado_numero) == 0:
                numero_pesquisa = 1
            else:
                numero_pesquisa = resultado_numero[0]['proximo_numero']
        
        # Salvar pesquisa primeiro com CNPJ
        query_insert = """
            INSERT INTO public.o_pesquisa_parcerias 
            (numero_pesquisa, sei_informado, nome_osc, cnpj, nome_emissor, osc_identificada, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        
        sucesso = execute_query(
            query_insert, 
            (numero_pesquisa, sei_informado, nome_osc, cnpj, nome_emissor, osc_identificada)
        )
        
        if not sucesso:
            return jsonify({'erro': 'Erro ao salvar pesquisa no banco de dados'}), 500
        
        # Verificar se OSC existe no banco de parcerias
        osc_existe = verificar_osc_existe(nome_osc)
        
        # Determinar qual modelo usar
        if osc_existe:
            # OSC existe - usar modelo com tabela de termos
            titulo_modelo = "Pesquisa de Parcerias: Parcerias pré-2023"
        else:
            # OSC não existe - usar modelo sem parcerias
            titulo_modelo = "Pesquisa de Parcerias: OSC sem parcerias SMDHC"
        
        modelo = obter_modelo_texto(titulo_modelo)
        
        if not modelo:
            return jsonify({
                'erro': f'Modelo de texto "{titulo_modelo}" não encontrado no banco de dados'
            }), 404
        
        # Preparar variáveis para substituição
        variaveis = {
            'sei_informado_usuario': sei_informado,
            'osc_informado_usuario': nome_osc,
            'cnpj_informado_usuario': cnpj_informado,
            'nome_emissor': nome_emissor,
            'numero_pesquisa': str(numero_pesquisa)
        }
        
        # Processar texto automático
        texto_processado = processar_texto_automatico(modelo['modelo_texto'], variaveis)
        
        # Retornar dados para renderizar no template
        return jsonify({
            'sucesso': True,
            'redirect': url_for('pesquisa_parcerias.exibir_texto_automatico',
                                numero_pesquisa=numero_pesquisa)
        })
        
    except Exception as e:
        print(f"[ERRO prosseguir_pesquisa] {e}")
        return jsonify({'erro': str(e)}), 500


@pesquisa_parcerias_bp.route('/texto/<int:numero_pesquisa>')
@agente_dac_required
def exibir_texto_automatico(numero_pesquisa):
    """
    Exibe o texto automático processado para uma pesquisa específica
    """
    try:
        # Buscar dados da pesquisa
        query_pesquisa = """
            SELECT 
                numero_pesquisa,
                sei_informado,
                nome_osc,
                cnpj,
                nome_emissor,
                osc_identificada
            FROM public.o_pesquisa_parcerias
            WHERE numero_pesquisa = %s
            ORDER BY criado_em DESC
            LIMIT 1
        """
        
        cur = get_cursor()
        if cur is None:
            return "Erro ao conectar com banco de dados", 500
        
        cur.execute(query_pesquisa, (numero_pesquisa,))
        pesquisa = cur.fetchone()
        cur.close()
        
        if not pesquisa:
            return "Pesquisa não encontrada", 404
        
        # Verificar se OSC existe no banco para determinar modelo
        osc_existe = verificar_osc_existe(pesquisa['nome_osc'])
        
        if osc_existe:
            titulo_modelo = "Pesquisa de Parcerias: Parcerias pré-2023"
        else:
            titulo_modelo = "Pesquisa de Parcerias: OSC sem parcerias SMDHC"
        
        modelo = obter_modelo_texto(titulo_modelo)
        
        if not modelo:
            return f'Modelo "{titulo_modelo}" não encontrado', 404
        
        # Preparar variáveis
        cnpj_texto = pesquisa.get('cnpj', '') or 'não informado'
        
        variaveis = {
            'sei_informado_usuario': pesquisa['sei_informado'],
            'osc_informado_usuario': pesquisa['nome_osc'],
            'cnpj_informado_usuario': cnpj_texto,
            'nome_emissor': pesquisa['nome_emissor'],
            'numero_pesquisa': str(pesquisa['numero_pesquisa'])
        }
        
        # Processar texto
        texto_processado = processar_texto_automatico(modelo['modelo_texto'], variaveis)
        
        # Renderizar template
        return render_template('pesquisa_parcerias_texto.html',
                               titulo_texto=modelo['titulo_texto'],
                               numero_pesquisa=pesquisa['numero_pesquisa'],
                               sei_informado=pesquisa['sei_informado'],
                               nome_osc=pesquisa['nome_osc'],
                               nome_emissor=pesquisa['nome_emissor'],
                               texto_processado=texto_processado)
        
    except Exception as e:
        print(f"[ERRO exibir_texto_automatico] {e}")
        return str(e), 500

