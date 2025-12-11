from flask import render_template, request, jsonify, g, send_from_directory, session, redirect, url_for, Response
from . import analises_pc_bp
from db import get_db
import psycopg2
import psycopg2.extras
import traceback
import audit_log  # Módulo de auditoria
import os
from werkzeug.utils import secure_filename
import re
from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer


def normalizar_rf(rf):
    """
    Normaliza o R.F. para comparação, extraindo apenas os primeiros 6 dígitos.
    Ignora o dígito verificador (último número após o hífen).
    
    Exemplos:
        'd843702' -> '843702'
        '843.702-5' -> '843702'
        'D843.702-5' -> '843702'
        '843702' -> '843702'
    """
    if not rf:
        return None
    rf_str = str(rf).lower().strip()
    # Remove o 'd' inicial se existir
    rf_str = re.sub(r'^d', '', rf_str)
    # Extrai apenas dígitos
    digitos = re.sub(r'[^\d]', '', rf_str)
    # Retorna apenas os primeiros 6 dígitos (ignora dígito verificador)
    return digitos[:6] if len(digitos) >= 6 else digitos


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


@analises_pc_bp.route('/meus_processos')
def meus_processos():
    """Página que lista os processos atribuídos ao usuário logado, processos de analista específico ou processos não atribuídos (admin)"""
    
    # Verificar se usuário está logado
    if 'email' not in session:
        return redirect(url_for('auth.login'))
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Verificar se o usuário é admin
        cur.execute("""
            SELECT tipo_usuario 
            FROM public.usuarios 
            WHERE email = %s
        """, (session['email'],))
        
        user_data = cur.fetchone()
        is_admin = user_data and user_data['tipo_usuario'] == 'Agente Público'
        
        # Buscar todos os analistas para o filtro (se for admin)
        cur.execute("""
            SELECT DISTINCT nome_analista 
            FROM categoricas.c_analistas 
            WHERE status NOT IN ('Inativo', 'false') OR status IS NULL
            ORDER BY nome_analista
        """)
        todos_analistas = cur.fetchall()
        
        # Verificar se foi solicitado visualização de processos não atribuídos
        mostrar_nao_atribuidos = request.args.get('nao_atribuidos') == 'true' and is_admin
        ocultar_encerrados = request.args.get('ocultar_encerrados', 'true') == 'true'
        responsabilidade_filtro = request.args.get('responsabilidade', '')
        filtro_termo = request.args.get('filtro_termo', '').strip()
        
        if mostrar_nao_atribuidos:
            # Admin visualizando processos não atribuídos
            # Usar apenas registros do tipo_prestacao = 'Final' para evitar duplicatas
            query = """
                SELECT DISTINCT
                    pa.numero_termo,
                    '' as meses_analisados,
                    '' as analistas,
                    0 as total_analistas,
                    pa.e_notificacao as documentos_sei_1,
                    pa.e_parecer as emissao_parecer,
                    pa.e_encerramento as encaminhamento_encerramento,
                    pa.responsabilidade_analise,
                    p.sei_pc,
                    pa.responsavel_dp,
                    ca.nome_analista as responsavel_previo,
                    pa.tipo_prestacao
                FROM public.parcerias_analises pa
                LEFT JOIN public.parcerias p ON pa.numero_termo = p.numero_termo
                LEFT JOIN categoricas.c_analistas ca ON pa.responsavel_dp = ca.id
                WHERE pa.tipo_prestacao = 'Final'
                  AND NOT EXISTS (
                    SELECT 1 FROM analises_pc.checklist_analista ch
                    WHERE ch.numero_termo = pa.numero_termo
                )
            """
            
            conditions = []
            params = []
            
            # Filtro: ocultar encerrados
            if ocultar_encerrados:
                conditions.append("pa.e_encerramento = false")
            
            # Filtro: responsabilidade
            if responsabilidade_filtro and responsabilidade_filtro.isdigit():
                conditions.append("pa.responsabilidade_analise = %s")
                params.append(int(responsabilidade_filtro))
            
            # Filtro: número do termo
            if filtro_termo:
                conditions.append("pa.numero_termo ILIKE %s")
                params.append(f'%{filtro_termo}%')
            
            if conditions:
                query += " AND " + " AND ".join(conditions)
            
            query += " ORDER BY pa.numero_termo DESC"
            
            cur.execute(query, params)
            processos_raw = cur.fetchall()
            
            processos = [dict(proc) for proc in processos_raw]
            mensagem_contexto = "Visualizando processos não atribuídos"
            
        else:
            # Lógica original: processos atribuídos
            # Verificar se foi solicitado filtro por analista específico (apenas para admin)
            analista_filtro = request.args.get('analista')
            
            if analista_filtro and is_admin:
                # Admin visualizando processos de um analista específico
                analistas_correspondentes = [analista_filtro]
                mensagem_contexto = f"Visualizando processos de: {analista_filtro}"
            else:
                # Usuário normal ou admin sem filtro - buscar por R.F.
                cur.execute("""
                    SELECT d_usuario 
                    FROM public.usuarios 
                    WHERE email = %s
                """, (session['email'],))
                
                usuario_row = cur.fetchone()
                
                if not usuario_row or not usuario_row['d_usuario']:
                    # Usuário sem R.F. cadastrado
                    cur.close()
                    return render_template('analises_pc/meus_processos.html', 
                                           processos=[], 
                                           todos_analistas=todos_analistas if is_admin else [],
                                           is_admin=is_admin,
                                           mostrar_nao_atribuidos=mostrar_nao_atribuidos,
                                           mensagem="Você não possui R.F. cadastrado. Entre em contato com o administrador.")
                
                rf_usuario = normalizar_rf(usuario_row['d_usuario'])
                print(f"[DEBUG] R.F. do usuário {session['email']}: {usuario_row['d_usuario']} -> normalizado: {rf_usuario}")
                
                # Buscar analistas que correspondem ao R.F. do usuário
                cur.execute("""
                    SELECT nome_analista, d_usuario
                    FROM categoricas.c_analistas
                """)
                
                analistas_correspondentes = []
                for row in cur.fetchall():
                    rf_analista = normalizar_rf(row['d_usuario'])
                    if rf_analista and rf_analista == rf_usuario:
                        analistas_correspondentes.append(row['nome_analista'])
                        print(f"[DEBUG] Analista correspondente: {row['nome_analista']} (R.F.: {row['d_usuario']} -> {rf_analista})")
                
                if not analistas_correspondentes:
                    # Nenhum analista corresponde ao R.F. do usuário
                    cur.close()
                    return render_template('analises_pc/meus_processos.html', 
                                           processos=[], 
                                           todos_analistas=todos_analistas if is_admin else [],
                                           is_admin=is_admin,
                                           mostrar_nao_atribuidos=mostrar_nao_atribuidos,
                                           mensagem="Nenhum analista cadastrado corresponde ao seu R.F.")
                
                mensagem_contexto = None
            
            # Buscar processos onde o(s) analista(s) está(ão) atribuído(s)
            # Incluindo apenas as principais etapas do checklist
            placeholders = ','.join(['%s'] * len(analistas_correspondentes))
            
            query_conditions = []
            query_params = list(analistas_correspondentes)
            
            # Filtro: número do termo
            if filtro_termo:
                query_conditions.append("ct.numero_termo ILIKE %s")
                query_params.append(f'%{filtro_termo}%')
            
            where_clause = f"WHERE ca.nome_analista IN ({placeholders})"
            if query_conditions:
                where_clause += " AND " + " AND ".join(query_conditions)
            
            query = f"""
                SELECT 
                    ct.numero_termo,
                    ct.meses_analisados,
                    STRING_AGG(DISTINCT ca.nome_analista, ', ' ORDER BY ca.nome_analista) as analistas,
                    COUNT(DISTINCT ca.nome_analista) as total_analistas,
                    BOOL_OR(COALESCE(pa_final.e_notificacao, false)) as documentos_sei_1,
                    BOOL_OR(COALESCE(pa_final.e_parecer, false)) as emissao_parecer,
                    BOOL_OR(COALESCE(pa_final.e_encerramento, false)) as encaminhamento_encerramento,
                    MAX(p.sei_pc) as sei_pc
                FROM analises_pc.checklist_termo ct
                INNER JOIN analises_pc.checklist_analista ca 
                    ON ct.numero_termo = ca.numero_termo 
                    AND ct.meses_analisados = ca.meses_analisados
                LEFT JOIN public.parcerias p ON ct.numero_termo = p.numero_termo
                LEFT JOIN public.parcerias_analises pa_final 
                    ON ct.numero_termo = pa_final.numero_termo 
                    AND pa_final.tipo_prestacao = 'Final'
                {where_clause}
                GROUP BY ct.numero_termo, ct.meses_analisados
                ORDER BY ct.numero_termo DESC, ct.meses_analisados DESC
            """
            
            cur.execute(query, query_params)
            processos_raw = cur.fetchall()
            
            # Calcular percentual de conclusão para cada processo (baseado nas 3 etapas principais)
            processos = []
            etapas_principais = ['documentos_sei_1', 'emissao_parecer', 'encaminhamento_encerramento']
            
            for proc in processos_raw:
                proc_dict = dict(proc)
                
                # Contar etapas concluídas
                etapas_concluidas = sum(1 for etapa in etapas_principais if proc_dict.get(etapa, False))
                total_etapas = len(etapas_principais)
                percentual = round((etapas_concluidas / total_etapas) * 100) if total_etapas > 0 else 0
                
                proc_dict['etapas_concluidas'] = etapas_concluidas
                proc_dict['total_etapas'] = total_etapas
                proc_dict['percentual_conclusao'] = percentual
                
                processos.append(proc_dict)
            
            mensagem_contexto = mensagem_contexto or None
        
        print(f"[DEBUG] Encontrados {len(processos)} processos para o(s) analista(s)")
        
        cur.close()
        
        return render_template('analises_pc/meus_processos.html', 
                               processos=processos,
                               todos_analistas=todos_analistas if is_admin else [],
                               is_admin=is_admin,
                               mostrar_nao_atribuidos=mostrar_nao_atribuidos,
                               ocultar_encerrados=ocultar_encerrados,
                               responsabilidade_filtro=responsabilidade_filtro,
                               filtro_termo=filtro_termo,
                               analista_selecionado=analista_filtro if not mostrar_nao_atribuidos else '',
                               mensagem=mensagem_contexto)
    
    except Exception as e:
        cur.close()
        print(f"[ERRO] Erro ao buscar meus processos: {e}")
        import traceback
        traceback.print_exc()
        return render_template('analises_pc/meus_processos.html', 
                               processos=[], 
                               todos_analistas=[],
                               is_admin=False,
                               mostrar_nao_atribuidos=False,
                               mensagem=f"Erro ao carregar processos: {str(e)}")


@analises_pc_bp.route('/api/criar_pasta_modelo', methods=['POST'])
def criar_pasta_modelo():
    """Cria estrutura de pastas modelo para análise de prestação de contas"""
    if 'email' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Buscar R.F. do usuário logado
        cur.execute("""
            SELECT d_usuario 
            FROM public.usuarios 
            WHERE email = %s
        """, (session['email'],))
        
        usuario_row = cur.fetchone()
        
        if not usuario_row or not usuario_row['d_usuario']:
            cur.close()
            return jsonify({'error': 'Usuário sem R.F. cadastrado. Entre em contato com o administrador.'}), 400
        
        # Normalizar R.F. (remover 'd' e pegar apenas dígitos)
        rf_usuario_raw = usuario_row['d_usuario'].lower().strip()
        
        # Extrair apenas dígitos para o nome de usuário do Windows
        if rf_usuario_raw.startswith('d'):
            rf_numeros = rf_usuario_raw[1:]  # Remove o 'd'
        else:
            rf_numeros = rf_usuario_raw
        rf_numeros = re.sub(r'[^\d]', '', rf_numeros)  # Remove tudo que não é dígito
        
        # Montar o username completo (d + números)
        username_windows = f"d{rf_numeros}"
        
        # Pegar número do termo e substituir / por -
        data = request.get_json()
        numero_termo = data.get('numero_termo', '')
        
        if not numero_termo:
            cur.close()
            return jsonify({'error': 'Número do termo não informado'}), 400
        
        # Substituir / por - no nome da pasta
        nome_pasta_termo = numero_termo.replace('/', '-')
        
        # Construir caminho base usando OneDrive
        caminho_base = f"C:\\Users\\{username_windows}\\OneDrive - rede.sp\\DIVISÃO DE ANALISE DE CONTAS\\Análises Novas\\Termos"
        
        # Verificar se o caminho base existe
        if not os.path.exists(caminho_base):
            cur.close()
            return jsonify({
                'error': f'Caminho base não encontrado. Verifique se a pasta existe: {caminho_base}'
            }), 400
        
        caminho_termo = os.path.join(caminho_base, nome_pasta_termo)
        caminho_celebracao = os.path.join(caminho_termo, "Celebracao")
        caminho_prestacao = os.path.join(caminho_termo, "Prestacao")
        
        print(f"[DEBUG] Username Windows: {username_windows}")
        print(f"[DEBUG] Caminho base: {caminho_base}")
        print(f"[DEBUG] Caminho termo: {caminho_termo}")
        print(f"[DEBUG] Caminho base existe: {os.path.exists(caminho_base)}")
        
        # Verificar se a pasta já existe
        if os.path.exists(caminho_termo):
            cur.close()
            return jsonify({
                'error': f'Pasta já existe para o termo {numero_termo}',
                'caminho': caminho_termo
            }), 400
        
        # Criar estrutura de pastas
        print(f"[DEBUG] Criando pasta celebração: {caminho_celebracao}")
        os.makedirs(caminho_celebracao, exist_ok=True)
        print(f"[DEBUG] Criando pasta prestação: {caminho_prestacao}")
        os.makedirs(caminho_prestacao, exist_ok=True)
        print(f"[DEBUG] Pastas criadas com sucesso!")
        
        cur.close()
        
        return jsonify({
            'message': f'Pasta modelo criada com sucesso para o termo {numero_termo}!',
            'caminho': caminho_termo,
            'subpastas': ['Celebracao', 'Prestacao']
        }), 200
        
    except PermissionError as e:
        cur.close()
        print(f"[ERRO] Permissão negada: {e}")
        traceback.print_exc()
        return jsonify({
            'error': 'Sem permissão para criar pastas no diretório especificado',
            'detalhes': str(e)
        }), 500
    except Exception as e:
        cur.close()
        print(f"[ERRO] Erro ao criar pasta modelo: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Erro ao criar pasta modelo: {str(e)}'}), 500


@analises_pc_bp.route('/api/atribuir_processo', methods=['POST'])
def atribuir_processo():
    """Atribui analistas a um processo não atribuído"""
    if 'email' not in session:
        return jsonify({'error': 'Não autenticado'}), 401
    
    # Verificar se é admin
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("SELECT tipo_usuario FROM public.usuarios WHERE email = %s", (session['email'],))
        user_data = cur.fetchone()
        
        if not user_data or user_data['tipo_usuario'] != 'Agente Público':
            cur.close()
            return jsonify({'error': 'Acesso negado. Apenas administradores podem atribuir processos.'}), 403
        
        data = request.get_json()
        numero_termo = data.get('numero_termo')
        meses_analisados = data.get('meses_analisados')
        analistas = data.get('analistas', [])  # Lista de analistas
        
        if not numero_termo or not meses_analisados or not analistas:
            cur.close()
            return jsonify({'error': 'Dados incompletos'}), 400
        
        # Buscar informações do processo em parcerias_analises
        cur.execute("""
            SELECT e_notificacao, e_parecer, e_encerramento 
            FROM public.parcerias_analises 
            WHERE numero_termo = %s
        """, (numero_termo,))
        
        processo_info = cur.fetchone()
        
        if not processo_info:
            cur.close()
            return jsonify({'error': 'Processo não encontrado em parcerias_analises'}), 404
        
        # Verificar se já existe esse termo + meses em checklist_termo
        cur.execute("""
            SELECT id FROM analises_pc.checklist_termo 
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        
        termo_existe = cur.fetchone()
        
        if not termo_existe:
            # Inserir em checklist_termo com colunas baseadas nos booleans
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
                # e_notificacao = true: preenche as 7 primeiras etapas
                processo_info['e_notificacao'], processo_info['e_notificacao'],
                processo_info['e_notificacao'], processo_info['e_notificacao'],
                processo_info['e_notificacao'], processo_info['e_notificacao'],
                processo_info['e_notificacao'],
                # e_parecer = true: preenche as 3 etapas de parecer
                processo_info['e_parecer'], processo_info['e_parecer'], processo_info['e_parecer'],
                # e_encerramento = true: preenche as 2 últimas etapas
                processo_info['e_encerramento'], processo_info['e_encerramento']
            ))
        
        # Inserir analistas em checklist_analista
        for analista in analistas:
            # Verificar se já existe
            cur.execute("""
                SELECT id FROM analises_pc.checklist_analista 
                WHERE numero_termo = %s AND meses_analisados = %s AND nome_analista = %s
            """, (numero_termo, meses_analisados, analista))
            
            if not cur.fetchone():
                cur.execute("""
                    INSERT INTO analises_pc.checklist_analista (numero_termo, meses_analisados, nome_analista)
                    VALUES (%s, %s, %s)
                """, (numero_termo, meses_analisados, analista))
        
        conn.commit()
        cur.close()
        
        return jsonify({
            'success': True,
            'message': f'Processo {numero_termo} atribuído a {len(analistas)} analista(s) com sucesso!'
        })
    
    except Exception as e:
        conn.rollback()
        cur.close()
        print(f"[ERRO] Erro ao atribuir processo: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


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


@analises_pc_bp.route('/api/buscar_info_adicional', methods=['POST'])
def buscar_info_adicional():
    """Busca informações adicionais para o checklist (instrução + SEI celebração)"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    
    print(f"[DEBUG] buscar_info_adicional - numero_termo recebido: '{numero_termo}'")
    
    if not numero_termo:
        return jsonify({'error': 'Número do termo não fornecido'}), 400
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Buscar instrução de celebração da tabela categoricas.c_modelo_textos
        cur.execute("""
            SELECT titulo_texto, modelo_texto 
            FROM categoricas.c_modelo_textos 
            WHERE titulo_texto = 'Instrução: Avaliação do processo de celebração'
            LIMIT 1
        """)
        instrucao_row = cur.fetchone()
        instrucao = instrucao_row['modelo_texto'] if instrucao_row else None
        print(f"[DEBUG] Instrução celebração encontrada: {bool(instrucao)}")
        
        # Buscar instrução de prestação de contas
        cur.execute("""
            SELECT titulo_texto, modelo_texto 
            FROM categoricas.c_modelo_textos 
            WHERE titulo_texto = 'Instrução: Avaliação do processo de prestação de contas'
            LIMIT 1
        """)
        instrucao_pc_row = cur.fetchone()
        instrucao_pc = instrucao_pc_row['modelo_texto'] if instrucao_pc_row else None
        print(f"[DEBUG] Instrução PC encontrada: {bool(instrucao_pc)}")
        
        # Buscar SEI de celebração e SEI de PC da tabela public.parcerias
        # Primeiro verificar se o termo existe
        cur.execute("""
            SELECT numero_termo, sei_celeb, sei_pc 
            FROM public.parcerias 
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        sei_row = cur.fetchone()
        
        print(f"[DEBUG] Resultado da busca SEI: {sei_row}")
        
        sei_celeb = sei_row['sei_celeb'] if sei_row else None
        sei_pc = sei_row['sei_pc'] if sei_row else None
        
        # Se não encontrou, tentar busca case-insensitive
        if not sei_row:
            print(f"[DEBUG] Tentando busca case-insensitive...")
            cur.execute("""
                SELECT numero_termo, sei_celeb, sei_pc 
                FROM public.parcerias 
                WHERE UPPER(TRIM(numero_termo)) = UPPER(TRIM(%s))
                LIMIT 1
            """, (numero_termo,))
            sei_row = cur.fetchone()
            print(f"[DEBUG] Resultado case-insensitive: {sei_row}")
            sei_celeb = sei_row['sei_celeb'] if sei_row else None
            sei_pc = sei_row['sei_pc'] if sei_row else None
        
        cur.close()
        
        result = {
            'instrucao': instrucao,
            'sei_celeb': sei_celeb,
            'instrucao_pc': instrucao_pc,
            'sei_pc': sei_pc,
            'debug': {
                'numero_termo_buscado': numero_termo,
                'termo_encontrado': sei_row['numero_termo'] if sei_row else None
            }
        }
        
        print(f"[DEBUG] Retornando: {result}")
        
        return jsonify(result)
    
    except Exception as e:
        cur.close()
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"[ERRO] Erro ao buscar informações adicionais: {error_details}")
        return jsonify(error_details), 500


# === ROTAS DE DADOS E FORMULÁRIOS MOVIDAS PARA routes_dados.py ===
# buscar_dados_base, listar_portarias, listar_pessoas_gestoras, 
# salvar_dados_base, exportar_dados_base_pdf agora estão em routes_dados.py


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
    """Salva ou atualiza o checklist com auditoria"""
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
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # 🔍 BUSCAR DADOS ANTIGOS PARA AUDITORIA
        cur.execute("""
            SELECT * FROM analises_pc.checklist_termo 
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        dados_antigos_termo = cur.fetchone()
        
        # Buscar analistas antigos
        cur.execute("""
            SELECT nome_analista FROM analises_pc.checklist_analista 
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        analistas_antigos = [row['nome_analista'] for row in cur.fetchall()]
        
        # Buscar recursos antigos
        cur.execute("""
            SELECT * FROM analises_pc.checklist_recursos 
            WHERE numero_termo = %s AND meses_analisados = %s
            ORDER BY tipo_recurso
        """, (numero_termo, meses_analisados))
        recursos_antigos = cur.fetchall()
        
        # Verificar se já existe registro
        existing = dados_antigos_termo is not None
        
        # 💾 Inserir ou atualizar checklist_termo
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
        
        # 📝 AUDITORIA: Registrar todas as alterações
        try:
            # Auditar checklist_termo
            audit_log.audit_checklist_termo(
                conn, numero_termo, meses_analisados,
                dados_antigos_termo, checklist_data
            )
            
            # Auditar analistas
            audit_log.audit_checklist_analistas(
                conn, numero_termo, meses_analisados,
                analistas_antigos, analistas
            )
            
            # Auditar recursos
            audit_log.audit_checklist_recursos(
                conn, numero_termo, meses_analisados,
                recursos_antigos, recursos
            )
        except Exception as audit_error:
            print(f"[AVISO] Erro na auditoria (não crítico): {audit_error}")
            # Continua mesmo se auditoria falhar
        
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


@analises_pc_bp.route('/api/historico_auditoria', methods=['POST'])
def historico_auditoria():
    """Retorna histórico de alterações de um checklist"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    meses_analisados = data.get('meses_analisados')
    limit = data.get('limit', 100)
    
    if not numero_termo:
        return jsonify({'error': 'Número do termo não fornecido'}), 400
    
    conn = get_db()
    
    try:
        historico = audit_log.get_audit_history(
            conn, numero_termo, meses_analisados, limit
        )
        
        return jsonify({
            'success': True,
            'historico': historico,
            'total': len(historico)
        })
    
    except Exception as e:
        error_details = {
            'error': str(e),
            'type': type(e).__name__
        }
        print(f"[ERRO] Erro ao buscar histórico: {error_details}")
        return jsonify(error_details), 500


# === FUNÇÃO exportar_dados_base_pdf MOVIDA PARA routes_dados.py ===


@analises_pc_bp.route('/central_modelos')
def central_modelos():
    """Página da Central de Modelos de Documentos"""
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Verificar se tabela existe, senão criar
        cur.execute("""
            CREATE TABLE IF NOT EXISTS categoricas.central_modelos (
                id SERIAL PRIMARY KEY,
                nome VARCHAR(255) NOT NULL,
                arquivo VARCHAR(255) NOT NULL,
                icone VARCHAR(10) DEFAULT '📄',
                descricao TEXT,
                ordem INTEGER DEFAULT 0,
                ativo BOOLEAN DEFAULT true,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Buscar modelos ativos ordenados
        cur.execute("""
            SELECT id, nome, arquivo, icone, descricao, ordem
            FROM categoricas.central_modelos
            WHERE ativo = true
            ORDER BY ordem ASC, nome ASC
        """)
        modelos = cur.fetchall()
        
        cur.close()
        
        # Se não houver modelos, inserir os padrões
        if not modelos:
            inserir_modelos_padrao()
            return redirect(url_for('analises_pc.central_modelos'))
        
        is_admin = session.get('tipo_usuario') == 'Agente Público'
        return render_template('analises_pc/central_modelos.html', modelos=modelos, is_admin=is_admin)
        
    except Exception as e:
        cur.close()
        print(f"[ERRO] central_modelos: {str(e)}")
        return render_template('analises_pc/central_modelos.html', modelos=[], is_admin=False)


def inserir_modelos_padrao():
    """Insere modelos padrão no banco de dados"""
    conn = get_db()
    cur = conn.cursor()
    
    modelos_padrao = [
        ('Termo Celebrado', 'modelo_termo_celebrado.pdf', '📄', 'Modelo de termo de colaboração/fomento/parceria', 1),
        ('Termo de Aditamento', 'modelo_termo_aditamento.pdf', '📝', 'Instrumentos formais utilizados para alterar, prorrogar ou suplementar cláusulas do termo celebrado original.', 2),
        ('Termo de Apostilamento', 'modelo_termo_apostilamento.pdf', '📋', 'Registros administrativos de ajustes que não modificam o objeto principal do termo.', 3),
        ('Plano de Trabalho', 'modelo_plano_trabalho.pdf', '📊', 'Documento detalhado das atividades, metas, prazos e responsabilidades.', 4),
        ('Orçamento Anual', 'modelo_orcamento_anual.xlsx', '💰', 'Relação detalhada dos recursos financeiros previstos.', 5),
        ('FACC', 'modelo_facc.pdf', '🏦', 'Ficha de Atualização de Cadastro de Credores.', 6),
        ('Memória de Cálculo', 'modelo_memoria_calculo.xlsx', '🧮', 'Documento que detalha os cálculos realizados.', 7),
    ]
    
    for nome, arquivo, icone, descricao, ordem in modelos_padrao:
        cur.execute("""
            INSERT INTO categoricas.central_modelos (nome, arquivo, icone, descricao, ordem)
            VALUES (%s, %s, %s, %s, %s)
        """, (nome, arquivo, icone, descricao, ordem))
    
    conn.commit()
    cur.close()


@analises_pc_bp.route('/download_modelo/<filename>')
def download_modelo(filename):
    """Download de arquivo modelo"""
    try:
        # Diretório dos modelos (na raiz do projeto)
        modelos_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'modelos')
        
        # Validar que o arquivo existe e está na lista permitida
        arquivos_permitidos = [
            'modelo_termo_celebrado.pdf',
            'modelo_solicitacao_alteracao.pdf',
            'modelo_termo_aditamento.pdf',
            'modelo_termo_apostilamento.pdf',
            'modelo_manifestacao_plano.pdf',
            'modelo_cronograma_desembolso.xlsx',
            'modelo_plano_trabalho.pdf',
            'modelo_orcamento_anual.xlsx',
            'modelo_facc.pdf',
            'modelo_memoria_calculo.xlsx'
        ]
        
        if filename not in arquivos_permitidos:
            return "Arquivo não autorizado", 403
        
        return send_from_directory(modelos_dir, filename, as_attachment=True)
    
    except Exception as e:
        print(f"[ERRO] Erro ao fazer download: {e}")
        return f"Erro ao baixar arquivo: {str(e)}", 500


@analises_pc_bp.route('/upload_modelo', methods=['POST'])
def upload_modelo():
    """Upload de arquivo modelo (apenas Agente Público)"""
    
    # Verificar permissão
    if session.get('tipo_usuario') != 'Agente Público':
        return jsonify({'error': 'Acesso negado. Apenas Agentes Públicos podem fazer upload.'}), 403
    
    try:
        # Verificar se arquivo foi enviado
        if 'arquivo' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
        arquivo = request.files['arquivo']
        
        if arquivo.filename == '':
            return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
        
        # Validar extensão
        extensao = arquivo.filename.rsplit('.', 1)[1].lower() if '.' in arquivo.filename else ''
        
        if extensao not in ['pdf', 'xlsx']:
            return jsonify({'error': 'Apenas arquivos PDF ou XLSX são permitidos'}), 400
        
        # Tornar nome seguro
        filename = secure_filename(arquivo.filename)
        
        # Validar que o nome segue o padrão modelo_*.pdf ou modelo_*.xlsx
        if not filename.startswith('modelo_'):
            return jsonify({
                'error': 'O nome do arquivo deve começar com "modelo_" (ex: modelo_novo_documento.pdf)'
            }), 400
        
        # Diretório de destino
        modelos_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'modelos')
        
        # Criar diretório se não existir
        os.makedirs(modelos_dir, exist_ok=True)
        
        # Caminho completo do arquivo
        filepath = os.path.join(modelos_dir, filename)
        
        # Verificar se arquivo já existe
        if os.path.exists(filepath):
            return jsonify({
                'error': f'Arquivo "{filename}" já existe. Renomeie ou exclua o arquivo existente primeiro.'
            }), 409
        
        # Salvar arquivo
        arquivo.save(filepath)
        
        print(f"[INFO] Upload realizado: {filename} por {session.get('email')}")
        
        return jsonify({
            'mensagem': 'Arquivo enviado com sucesso!',
            'filename': filename,
            'tamanho': os.path.getsize(filepath),
            'usuario': session.get('email')
        }), 200
    
    except Exception as e:
        print(f"[ERRO] Erro ao fazer upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao fazer upload: {str(e)}'}), 500


@analises_pc_bp.route('/api/modelo_texto', methods=['GET'])
def buscar_modelo_texto():
    """Busca um modelo de texto pelo título"""
    try:
        titulo = request.args.get('titulo')
        
        if not titulo:
            return jsonify({'error': 'Título não fornecido'}), 400
        
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Buscar modelo de texto
        cur.execute("""
            SELECT id, titulo_texto, modelo_texto, oculto
            FROM categoricas.c_modelo_textos
            WHERE titulo_texto = %s AND (oculto IS NULL OR oculto = FALSE)
        """, (titulo,))
        
        modelo = cur.fetchone()
        
        if not modelo:
            return jsonify({'error': 'Modelo não encontrado'}), 404
        
        return jsonify({
            'id': modelo['id'],
            'titulo': modelo['titulo_texto'],
            'conteudo': modelo['modelo_texto']
        }), 200
    
    except Exception as e:
        print(f"[ERRO] Erro ao buscar modelo de texto: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao buscar modelo: {str(e)}'}), 500


@analises_pc_bp.route('/api/modelos', methods=['GET'])
def listar_modelos_api():
    """API para listar todos os modelos (incluindo inativos para admin)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        is_admin = session.get('tipo_usuario') == 'Agente Público'
        
        if is_admin:
            cur.execute("""
                SELECT id, nome, arquivo, icone, descricao, ordem, ativo
                FROM categoricas.central_modelos
                ORDER BY ordem ASC, nome ASC
            """)
        else:
            cur.execute("""
                SELECT id, nome, arquivo, icone, descricao, ordem
                FROM categoricas.central_modelos
                WHERE ativo = true
                ORDER BY ordem ASC, nome ASC
            """)
        
        modelos = cur.fetchall()
        cur.close()
        
        return jsonify({'modelos': modelos})
        
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/modelos/<int:modelo_id>', methods=['GET', 'PUT', 'DELETE'])
def gerenciar_modelo(modelo_id):
    """API para gerenciar um modelo específico"""
    if session.get('tipo_usuario') != 'Agente Público':
        return jsonify({'error': 'Acesso negado'}), 403
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        if request.method == 'GET':
            cur.execute("""
                SELECT id, nome, arquivo, icone, descricao, ordem, ativo
                FROM categoricas.central_modelos
                WHERE id = %s
            """, (modelo_id,))
            modelo = cur.fetchone()
            cur.close()
            
            if not modelo:
                return jsonify({'error': 'Modelo não encontrado'}), 404
            
            return jsonify(dict(modelo))
        
        elif request.method == 'PUT':
            data = request.get_json()
            cur.execute("""
                UPDATE categoricas.central_modelos
                SET nome = %s, arquivo = %s, icone = %s, descricao = %s, ordem = %s
                WHERE id = %s
            """, (data['nome'], data['arquivo'], data['icone'], data['descricao'], data.get('ordem', 0), modelo_id))
            conn.commit()
            cur.close()
            
            return jsonify({'mensagem': 'Modelo atualizado com sucesso'})
        
        elif request.method == 'DELETE':
            # Soft delete
            cur.execute("""
                UPDATE categoricas.central_modelos
                SET ativo = false
                WHERE id = %s
            """, (modelo_id,))
            conn.commit()
            cur.close()
            
            return jsonify({'mensagem': 'Modelo removido com sucesso'})
    
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/modelos', methods=['POST'])
def criar_modelo():
    """API para criar um novo modelo"""
    if session.get('tipo_usuario') != 'Agente Público':
        return jsonify({'error': 'Acesso negado'}), 403
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        data = request.get_json()
        cur.execute("""
            INSERT INTO categoricas.central_modelos (nome, arquivo, icone, descricao, ordem)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
        """, (data['nome'], data['arquivo'], data['icone'], data['descricao'], data.get('ordem', 999)))
        
        novo_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        
        return jsonify({'mensagem': 'Modelo criado com sucesso', 'id': novo_id})
    
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/arquivos-disponiveis', methods=['GET'])
def listar_arquivos_disponiveis():
    """Lista arquivos disponíveis na pasta modelos/"""
    if session.get('tipo_usuario') != 'Agente Público':
        return jsonify({'error': 'Acesso negado'}), 403
    
    import os
    modelos_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'modelos')
    
    try:
        arquivos = []
        for arquivo in os.listdir(modelos_dir):
            if arquivo.endswith(('.pdf', '.xlsx', '.xls', '.docx', '.doc')):
                arquivos.append(arquivo)
        
        return jsonify({'arquivos': sorted(arquivos)})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/conc_inconsistencias')
def conc_inconsistencias():
    """Página de Relatório de Inconsistências da Conciliação Bancária"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Buscar modelo de texto
        cur.execute("""
            SELECT titulo_texto, modelo_texto
            FROM categoricas.c_modelo_textos
            WHERE titulo_texto = 'Análise de Contas: Relatório de Inconsistências'
            LIMIT 1
        """)
        
        modelo = cur.fetchone()
        cur.close()
        
        if not modelo:
            # Se não encontrar, criar placeholder
            modelo = {
                'titulo_texto': 'Análise de Contas: Relatório de Inconsistências',
                'modelo_texto': '<p>Modelo de texto ainda não cadastrado. Acesse Modelos de Texto para criar.</p>'
            }
        
        return render_template('analises_pc/conc_inconsistencias.html', modelo=modelo)
    
    except Exception as e:
        cur.close()
        print(f"[ERRO] conc_inconsistencias: {str(e)}")
        return render_template('analises_pc/conc_inconsistencias.html', 
                             modelo={'titulo_texto': 'Erro', 'modelo_texto': f'<p>Erro ao carregar modelo: {str(e)}</p>'})
