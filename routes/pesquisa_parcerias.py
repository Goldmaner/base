# routes/pesquisa_parcerias.py
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from decorators import requires_access
from datetime import datetime
from db import get_cursor, execute_query
import sys
import os

# Adicionar o diretório scripts ao path para importar funcoes_texto
scripts_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts')
if scripts_path not in sys.path:
    sys.path.insert(0, scripts_path)

try:
    from funcoes_texto import (
        processar_texto_automatico, 
        obter_modelo_texto, 
        verificar_osc_existe,
        verificar_osc_tem_pos2023,
        verificar_responsabilidades_mistas,
        gerar_encaminhamentos_pos2023,
        gerar_texto_misto
    )
except ImportError as e:
    print(f"[ERRO] Não foi possível importar funcoes_texto: {e}")
    print(f"[DEBUG] scripts_path = {scripts_path}")
    print(f"[DEBUG] sys.path = {sys.path}")
    # Importar inline se falhar
    processar_texto_automatico = None
    obter_modelo_texto = None
    verificar_osc_existe = None
    verificar_osc_tem_pos2023 = None
    verificar_responsabilidades_mistas = None
    gerar_encaminhamentos_pos2023 = None
    gerar_texto_misto = None

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
        print(f"\n🔍 [BACKEND DEBUG] Buscando CNPJ para OSC: '{nome_osc}'")
        print(f"🔍 [BACKEND DEBUG] Comprimento: {len(nome_osc)}")
        print(f"🔍 [BACKEND DEBUG] Bytes: {nome_osc.encode('utf-8')}")
        
        # Primeiro: buscar exatamente
        query_exata = """
            SELECT cnpj, osc
            FROM public.parcerias
            WHERE osc = %s
            LIMIT 1
        """
        
        cur = get_cursor()
        if cur is None:
            return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
        
        cur.execute(query_exata, (nome_osc,))
        resultados = cur.fetchall()
        
        if len(resultados) > 0:
            print(f"✅ [BACKEND DEBUG] Match exato encontrado!")
            cur.close()
            return jsonify({
                'sucesso': True,
                'cnpj': resultados[0]['cnpj']
            })
        
        print(f"⚠️ [BACKEND DEBUG] Match exato não encontrado. Buscando variações...")
        
        # Se não encontrou, buscar variações similares
        query_similar = """
            SELECT cnpj, osc, 
                   LENGTH(osc) as tamanho,
                   ENCODE(osc::bytea, 'hex') as hex
            FROM public.parcerias
            WHERE LOWER(TRIM(osc)) LIKE LOWER(%s)
            LIMIT 5
        """
        
        cur.execute(query_similar, (f'%{nome_osc}%',))
        similares = cur.fetchall()
        
        if len(similares) > 0:
            print(f"📋 [BACKEND DEBUG] Encontradas {len(similares)} OSCs similares:")
            for s in similares:
                print(f"   - '{s['osc']}' (len={s['tamanho']}, hex={s['hex'][:50]}...)")
            
            # Retornar a primeira similar (pode ajustar lógica depois)
            cur.close()
            return jsonify({
                'sucesso': True,
                'cnpj': similares[0]['cnpj'],
                'aviso': f"Match aproximado: '{similares[0]['osc']}'"
            })
        
        print(f"❌ [BACKEND DEBUG] Nenhuma OSC similar encontrada")
        cur.close()
        return jsonify({'erro': 'OSC não encontrada'}), 404
        
    except Exception as e:
        print(f"💥 [BACKEND DEBUG] Erro: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@pesquisa_parcerias_bp.route('/api/analistas-ativos')
@agente_dac_required
def listar_analistas_ativos():
    """Retorna lista de analistas ativos da tabela categoricas.c_analistas"""
    try:
        query = """
            SELECT nome_analista
            FROM categoricas.c_analistas
            WHERE status NOT IN ('Inativo', 'false') OR status IS NULL
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
        psei_pesquisa = dados.get('psei_pesquisa')  # Processo SEI da Pesquisa (NOVO CAMPO)
        
        if not all([sei_informado, nome_osc, nome_emissor, psei_pesquisa]):
            return jsonify({'erro': 'Campos obrigatórios: Processo SEI da Pesquisa, SEI Informado, Nome OSC e Emissor'}), 400
        
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
        
        # Inserir pesquisa com CNPJ e Processo SEI da Pesquisa
        query_insert = """
            INSERT INTO public.o_pesquisa_parcerias 
            (numero_pesquisa, psei_pesquisa, sei_informado, nome_osc, cnpj, nome_emissor, osc_identificada, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        
        sucesso = execute_query(
            query_insert, 
            (numero_pesquisa, psei_pesquisa, sei_informado, nome_osc, cnpj, nome_emissor, osc_identificada)
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
                psei_pesquisa,
                sei_informado,
                nome_osc,
                nome_emissor,
                osc_identificada,
                respondido,
                obs,
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


@pesquisa_parcerias_bp.route('/api/pesquisas/<int:numero_pesquisa>', methods=['PUT'])
@agente_dac_required
def atualizar_pesquisa(numero_pesquisa):
    """Atualiza os campos de uma pesquisa (sei_informado, nome_osc, respondido, obs)"""
    try:
        dados = request.json
        
        sei_informado = dados.get('sei_informado')
        nome_osc = dados.get('nome_osc')
        respondido = dados.get('respondido', False)
        obs = dados.get('obs')
        
        query = """
            UPDATE public.o_pesquisa_parcerias
            SET sei_informado = %s, 
                nome_osc = %s,
                respondido = %s, 
                obs = %s
            WHERE numero_pesquisa = %s
        """
        
        cur = get_cursor()
        if cur is None:
            return jsonify({'erro': 'Erro ao conectar com banco de dados'}), 500
        
        cur.execute(query, (sei_informado, nome_osc, respondido, obs, numero_pesquisa))
        cur.connection.commit()
        cur.close()
        
        return jsonify({
            'sucesso': True,
            'mensagem': f'Pesquisa {numero_pesquisa} atualizada com sucesso'
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
        psei_pesquisa = dados.get('psei_pesquisa')  # Processo SEI da Pesquisa
        cnpj_informado = cnpj if cnpj else 'não informado'  # Para o texto
        
        if not all([sei_informado, nome_osc, nome_emissor, psei_pesquisa]):
            return jsonify({'erro': 'Campos obrigatórios: Processo SEI da Pesquisa, SEI Informado, Nome OSC e Emissor'}), 400
        
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
        
        # Salvar pesquisa primeiro com CNPJ e Processo SEI
        query_insert = """
            INSERT INTO public.o_pesquisa_parcerias 
            (numero_pesquisa, psei_pesquisa, sei_informado, nome_osc, cnpj, nome_emissor, osc_identificada, criado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """
        
        sucesso = execute_query(
            query_insert, 
            (numero_pesquisa, psei_pesquisa, sei_informado, nome_osc, cnpj, nome_emissor, osc_identificada)
        )
        
        if not sucesso:
            return jsonify({'erro': 'Erro ao salvar pesquisa no banco de dados'}), 500
        
        # Verificar se OSC existe no banco de parcerias
        osc_existe = verificar_osc_existe(nome_osc)
        
        # Determinar qual modelo usar baseado em 4 casos:
        # Caso 1: OSC não existe → "OSC sem parcerias SMDHC"
        # Caso 2: OSC existe APENAS com termos pré-2023 (DP) → "Parcerias pré-2023"
        # Caso 3: OSC existe APENAS com termos pós-2023 (PG/Compartilhado) → "Parcerias pós-2023"
        # Caso 4: OSC existe com AMBOS (DP + Pós-2023) → Texto misto
        
        if not osc_existe:
            # Caso 1: OSC não existe
            titulo_modelo = "Pesquisa de Parcerias: OSC sem parcerias SMDHC"
            usar_multiplos_encaminhamentos = False
            usar_texto_misto = False
        else:
            # OSC existe - verificar responsabilidades
            resp = verificar_responsabilidades_mistas(nome_osc)
            
            print(f"[DEBUG verificar_responsabilidades_mistas] OSC: {nome_osc}")
            print(f"[DEBUG] tem_dp: {resp['tem_dp']}, tem_pos2023: {resp['tem_pos2023']}, misto: {resp['misto']}")
            
            if resp['misto']:
                # Caso 4: Responsabilidades mistas (DP + Pós-2023)
                print(f"[DEBUG] → Usando DROPDOWN (Caso 4: Misto)")
                usar_texto_misto = True
                usar_multiplos_encaminhamentos = False
                titulo_modelo = None  # Não usa modelo único
            elif resp['tem_pos2023']:
                # Caso 3: Apenas pós-2023 (responsabilidade 2 ou 3)
                print(f"[DEBUG] → Usando modelo pós-2023 (Caso 3)")
                titulo_modelo = "Pesquisa de Parcerias: Parcerias pós-2023"
                usar_multiplos_encaminhamentos = True
                usar_texto_misto = False
            elif resp['tem_dp']:
                # Caso 2: Apenas pré-2023 (responsabilidade 1)
                print(f"[DEBUG] → Usando modelo pré-2023 (Caso 2)")
                titulo_modelo = "Pesquisa de Parcerias: Parcerias pré-2023"
                usar_multiplos_encaminhamentos = False
                usar_texto_misto = False
            else:
                # Fallback: OSC existe mas não tem prestações (caso improvável)
                print(f"[DEBUG] → OSC existe mas sem prestações (fallback)")
                titulo_modelo = "Pesquisa de Parcerias: OSC sem parcerias SMDHC"
                usar_multiplos_encaminhamentos = False
                usar_texto_misto = False
        
        # Preparar variáveis para substituição
        variaveis = {
            'sei_informado_usuario': sei_informado,
            'osc_informado_usuario': nome_osc,
            'cnpj_informado_usuario': cnpj_informado,
            'nome_emissor': nome_emissor,
            'numero_pesquisa': str(numero_pesquisa)
        }
        
        # Processar texto automático baseado no caso
        if usar_texto_misto:
            # Caso 4: Gerar texto completo com múltiplos modelos
            texto_processado = gerar_texto_misto(variaveis)
        else:
            # Casos 1, 2 ou 3: Usar modelo único
            modelo = obter_modelo_texto(titulo_modelo)
            
            if not modelo:
                return jsonify({
                    'erro': f'Modelo de texto "{titulo_modelo}" não encontrado no banco de dados'
                }), 404
            
            # Se for Caso 3 (múltiplas coordenações pós-2023), usar função especial
            if usar_multiplos_encaminhamentos:
                texto_processado = gerar_encaminhamentos_pos2023(modelo['modelo_texto'], variaveis)
            else:
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
        
        # Verificar se OSC existe
        osc_existe = verificar_osc_existe(pesquisa['nome_osc'])
        
        # Determinar qual modelo usar baseado em 4 casos (MESMA LÓGICA de prosseguir_pesquisa)
        if not osc_existe:
            # Caso 1: OSC não existe
            titulo_modelo = "Pesquisa de Parcerias: OSC sem parcerias SMDHC"
            usar_multiplos_encaminhamentos = False
            usar_texto_misto = False
        else:
            # OSC existe - verificar responsabilidades
            resp = verificar_responsabilidades_mistas(pesquisa['nome_osc'])
            
            print(f"[DEBUG exibir_texto_automatico] OSC: {pesquisa['nome_osc']}")
            print(f"[DEBUG] tem_dp: {resp['tem_dp']}, tem_pos2023: {resp['tem_pos2023']}, misto: {resp['misto']}")
            
            if resp['misto']:
                # Caso 4: Responsabilidades mistas (DP + Pós-2023)
                print(f"[DEBUG] → Renderizando DROPDOWN (Caso 4: Misto)")
                usar_texto_misto = True
                usar_multiplos_encaminhamentos = False
                titulo_modelo = None  # Não usa modelo único
            elif resp['tem_pos2023']:
                # Caso 3: Apenas pós-2023 (responsabilidade 2 ou 3)
                print(f"[DEBUG] → Renderizando modelo pós-2023 (Caso 3)")
                titulo_modelo = "Pesquisa de Parcerias: Parcerias pós-2023"
                usar_multiplos_encaminhamentos = True
                usar_texto_misto = False
            elif resp['tem_dp']:
                # Caso 2: Apenas pré-2023 (responsabilidade 1)
                print(f"[DEBUG] → Renderizando modelo pré-2023 (Caso 2)")
                titulo_modelo = "Pesquisa de Parcerias: Parcerias pré-2023"
                usar_multiplos_encaminhamentos = False
                usar_texto_misto = False
            else:
                # Fallback: OSC existe mas não tem prestações
                print(f"[DEBUG] → OSC existe mas sem prestações (fallback)")
                titulo_modelo = "Pesquisa de Parcerias: OSC sem parcerias SMDHC"
                usar_multiplos_encaminhamentos = False
                usar_texto_misto = False
        
        # Preparar variáveis
        cnpj_texto = pesquisa.get('cnpj', '') or 'não informado'
        
        variaveis = {
            'sei_informado_usuario': pesquisa['sei_informado'],
            'osc_informado_usuario': pesquisa['nome_osc'],
            'cnpj_informado_usuario': cnpj_texto,
            'nome_emissor': pesquisa['nome_emissor'],
            'numero_pesquisa': str(pesquisa['numero_pesquisa'])
        }
        
        # Processar texto baseado no caso
        if usar_texto_misto:
            # Caso 4: Gerar texto com dropdown
            texto_processado = gerar_texto_misto(variaveis)
            titulo_exibicao = "Pesquisa de Parcerias: Parcerias pós-2023"  # Título genérico
        else:
            # Casos 1, 2 ou 3: Usar modelo único
            modelo = obter_modelo_texto(titulo_modelo)
            
            if not modelo:
                return f'Modelo "{titulo_modelo}" não encontrado', 404
            
            # Se for Caso 3 (múltiplas coordenações pós-2023), usar função especial
            if usar_multiplos_encaminhamentos:
                texto_processado = gerar_encaminhamentos_pos2023(modelo['modelo_texto'], variaveis)
            else:
                texto_processado = processar_texto_automatico(modelo['modelo_texto'], variaveis)
            
            titulo_exibicao = modelo['titulo_texto']
        
        # Renderizar template
        return render_template('pesquisa_parcerias_texto.html',
                               titulo_texto=titulo_exibicao,
                               numero_pesquisa=pesquisa['numero_pesquisa'],
                               sei_informado=pesquisa['sei_informado'],
                               nome_osc=pesquisa['nome_osc'],
                               nome_emissor=pesquisa['nome_emissor'],
                               texto_processado=texto_processado)
        
    except Exception as e:
        print(f"[ERRO exibir_texto_automatico] {e}")
        import traceback
        traceback.print_exc()
        return str(e), 500

