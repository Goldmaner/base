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


@analises_pc_bp.route('/api/buscar_dados_base', methods=['POST'])
def buscar_dados_base():
    """Busca dados base da parceria para preenchimento/conferência"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    
    print(f"[DEBUG] buscar_dados_base - numero_termo: '{numero_termo}'")
    
    if not numero_termo:
        return jsonify({'error': 'Número do termo não fornecido'}), 400
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Buscar dados da parceria
        cur.execute("""
            SELECT 
                numero_termo, osc, projeto, tipo_termo, portaria, cnpj,
                inicio, final, meses, total_previsto, total_pago, conta,
                transicao, sei_celeb, sei_pc, sei_plano, sei_orcamento, contrapartida
            FROM public.parcerias
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        parceria = cur.fetchone()
        
        if not parceria:
            cur.close()
            return jsonify({'error': 'Termo não encontrado'}), 404
        
        # Buscar pessoa gestora
        cur.execute("""
            SELECT nome_pg
            FROM public.parcerias_pg
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        pg_row = cur.fetchone()
        nome_pg = pg_row['nome_pg'] if pg_row else None
        
        # Verificar se é termo rescindido
        cur.execute("""
            SELECT 1
            FROM public.termos_rescisao
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        is_rescindido = cur.fetchone() is not None
        
        cur.close()
        
        # Converter data para string se necessário
        parceria_dict = dict(parceria)
        if parceria_dict.get('inicio'):
            parceria_dict['inicio'] = str(parceria_dict['inicio'])
        if parceria_dict.get('final'):
            parceria_dict['final'] = str(parceria_dict['final'])
        
        result = {
            'parceria': parceria_dict,
            'nome_pg': nome_pg,
            'is_rescindido': is_rescindido
        }
        
        print(f"[DEBUG] Dados retornados - rescindido: {is_rescindido}, nome_pg: {nome_pg}")
        
        return jsonify(result)
    
    except Exception as e:
        cur.close()
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"[ERRO] buscar_dados_base: {error_details}")
        return jsonify(error_details), 500


@analises_pc_bp.route('/api/listar_portarias', methods=['GET'])
def listar_portarias():
    """Lista todas as portarias/legislações do sistema"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("""
            SELECT DISTINCT lei
            FROM categoricas.c_legislacao
            WHERE lei IS NOT NULL AND lei != ''
            ORDER BY lei
        """)
        portarias = cur.fetchall()
        cur.close()
        
        return jsonify({
            'portarias': portarias
        })
    
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/listar_pessoas_gestoras', methods=['GET'])
def listar_pessoas_gestoras():
    """Lista todas as pessoas gestoras únicas do sistema (incluindo inativas)"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        cur.execute("""
            SELECT DISTINCT nome_pg
            FROM public.parcerias_pg
            WHERE nome_pg IS NOT NULL AND nome_pg != ''
            ORDER BY nome_pg
        """)
        pessoas_gestoras = cur.fetchall()
        cur.close()
        
        return jsonify({
            'pessoas_gestoras': pessoas_gestoras
        })
    
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/salvar_dados_base', methods=['POST'])
def salvar_dados_base():
    """Salva/atualiza dados base da parceria"""
    data = request.get_json()
    numero_termo = data.get('numero_termo')
    dados = data.get('dados', {})
    
    print(f"[DEBUG] salvar_dados_base - numero_termo: '{numero_termo}'")
    print(f"[DEBUG] Dados recebidos: {dados}")
    
    if not numero_termo:
        return jsonify({'error': 'Número do termo não fornecido'}), 400
    
    conn = get_db()
    cur = conn.cursor()
    
    try:
        # Construir UPDATE apenas com campos que têm valores
        campos_update = []
        valores = []
        
        # Mapeamento de campos do formulário para colunas do banco
        campos_permitidos = {
            'osc': 'osc',
            'projeto': 'projeto',
            'tipo_termo': 'tipo_termo',
            'portaria': 'portaria',
            'cnpj': 'cnpj',
            'inicio': 'inicio',
            'final': 'final',
            'total_previsto': 'total_previsto',
            'total_pago': 'total_pago',
            'conta': 'conta',
            'transicao': 'transicao',
            'sei_celeb': 'sei_celeb',
            'sei_pc': 'sei_pc',
            'sei_plano': 'sei_plano',
            'sei_orcamento': 'sei_orcamento',
            'contrapartida': 'contrapartida'
        }
        
        for campo_form, campo_db in campos_permitidos.items():
            if campo_form in dados and dados[campo_form] != '':
                campos_update.append(f"{campo_db} = %s")
                
                # Converter valores especiais
                valor = dados[campo_form]
                if campo_form in ['transicao', 'contrapartida']:
                    valor = int(valor) if valor else 0
                elif campo_form in ['total_previsto', 'total_pago']:
                    # Remover formatação monetária se houver
                    valor = valor.replace('.', '').replace(',', '.') if isinstance(valor, str) else valor
                    valor = float(valor) if valor else None
                
                valores.append(valor)
        
        if campos_update:
            valores.append(numero_termo)
            query = f"""
                UPDATE public.parcerias
                SET {', '.join(campos_update)}
                WHERE TRIM(numero_termo) = TRIM(%s)
            """
            print(f"[DEBUG] Query UPDATE: {query}")
            print(f"[DEBUG] Valores: {valores}")
            cur.execute(query, valores)
        
        # Atualizar pessoa gestora se fornecida
        if 'nome_pg' in dados and dados['nome_pg']:
            # Verificar se já existe registro
            cur.execute("""
                SELECT 1 FROM public.parcerias_pg
                WHERE TRIM(numero_termo) = TRIM(%s)
            """, (numero_termo,))
            
            if cur.fetchone():
                cur.execute("""
                    UPDATE public.parcerias_pg
                    SET nome_pg = %s
                    WHERE TRIM(numero_termo) = TRIM(%s)
                """, (dados['nome_pg'], numero_termo))
            else:
                cur.execute("""
                    INSERT INTO public.parcerias_pg (numero_termo, nome_pg)
                    VALUES (%s, %s)
                """, (numero_termo, dados['nome_pg']))
        
        conn.commit()
        cur.close()
        
        print(f"[DEBUG] Dados salvos com sucesso!")
        
        return jsonify({
            'success': True,
            'message': 'Dados atualizados com sucesso'
        })
    
    except Exception as e:
        conn.rollback()
        cur.close()
        error_details = {
            'error': str(e),
            'type': type(e).__name__,
            'traceback': traceback.format_exc()
        }
        print(f"[ERRO] salvar_dados_base: {error_details}")
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


@analises_pc_bp.route('/api/exportar_dados_base_pdf', methods=['GET'])
def exportar_dados_base_pdf():
    """Exporta os dados base da parceria para PDF"""
    try:
        # Obter número do termo da query string
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return "Número do termo não informado", 400
        
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Buscar dados da parceria
        cur.execute("""
            SELECT 
                numero_termo, osc, projeto, tipo_termo, portaria, cnpj,
                inicio, final, meses, total_previsto, total_pago, conta,
                transicao, sei_celeb, sei_pc, sei_plano, sei_orcamento, contrapartida
            FROM public.parcerias
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        parceria = cur.fetchone()
        
        if not parceria:
            cur.close()
            return "Termo não encontrado", 404
        
        # Buscar pessoa gestora
        cur.execute("""
            SELECT nome_pg
            FROM public.parcerias_pg
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        pg_row = cur.fetchone()
        nome_pg = pg_row['nome_pg'] if pg_row else None
        
        # Verificar se é termo rescindido
        cur.execute("""
            SELECT 1
            FROM public.termos_rescisao
            WHERE TRIM(numero_termo) = TRIM(%s)
            LIMIT 1
        """, (numero_termo,))
        is_rescindido = cur.fetchone() is not None
        
        cur.close()
        
        # Criar PDF em memória
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4, 
                               rightMargin=2*cm, leftMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
        
        # Container para os elementos do PDF
        elements = []
        styles = getSampleStyleSheet()
        
        # Estilo personalizado para o título
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=colors.HexColor('#17a2b8'),  # cor bg-info
            spaceAfter=20,
            alignment=1  # Centralizado
        )
        
        # Estilo para subtítulos de seção
        section_style = ParagraphStyle(
            'SectionTitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=colors.HexColor('#ffffff'),
            backColor=colors.HexColor('#6c757d'),
            spaceAfter=12,
            spaceBefore=12,
            leftIndent=5,
            rightIndent=5,
            leading=16
        )
        
        # Título principal
        titulo = Paragraph("✏️ Dados Base da Parceria", title_style)
        elements.append(titulo)
        
        # Alerta de rescisão (se aplicável)
        if is_rescindido:
            alerta_style = ParagraphStyle(
                'Alert',
                parent=styles['Normal'],
                fontSize=10,
                textColor=colors.HexColor('#842029'),
                backColor=colors.HexColor('#f8d7da'),
                borderColor=colors.HexColor('#f5c2c7'),
                borderWidth=1,
                borderPadding=10,
                spaceAfter=20
            )
            alerta = Paragraph("<b>⚠ ATENÇÃO:</b> Este termo consta como <b>RESCINDIDO</b> no sistema.", alerta_style)
            elements.append(alerta)
        
        elements.append(Spacer(1, 0.3*cm))
        
        # SEÇÃO 1: Identificação
        elements.append(Paragraph("IDENTIFICAÇÃO DO TERMO", section_style))
        dados_identificacao = [
            ['Número do Termo:', parceria['numero_termo'] or '-'],
            ['Tipo de Termo:', parceria['tipo_termo'] or '-'],
            ['OSC:', parceria['osc'] or '-'],
            ['Projeto:', parceria['projeto'] or '-'],
            ['Portaria:', parceria['portaria'] or '-'],
            ['CNPJ:', parceria['cnpj'] or '-']
        ]
        
        tabela_id = Table(dados_identificacao, colWidths=[5*cm, 12*cm])
        tabela_id.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(tabela_id)
        elements.append(Spacer(1, 0.5*cm))
        
        # SEÇÃO 2: Vigência e Valores
        elements.append(Paragraph("VIGÊNCIA E VALORES", section_style))
        
        data_inicio_fmt = parceria['inicio'].strftime('%d/%m/%Y') if parceria['inicio'] else '-'
        data_final_fmt = parceria['final'].strftime('%d/%m/%Y') if parceria['final'] else '-'
        total_previsto = float(parceria['total_previsto'] or 0)
        total_pago = float(parceria['total_pago'] or 0)
        total_previsto_fmt = f"R$ {total_previsto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        total_pago_fmt = f"R$ {total_pago:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        dados_vigencia = [
            ['Data de Início:', data_inicio_fmt],
            ['Data de Término:', data_final_fmt],
            ['Meses:', str(parceria['meses']) if parceria['meses'] is not None else '-'],
            ['Total Previsto:', total_previsto_fmt],
            ['Total Pago:', total_pago_fmt]
        ]
        
        tabela_vig = Table(dados_vigencia, colWidths=[5*cm, 12*cm])
        tabela_vig.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(tabela_vig)
        elements.append(Spacer(1, 0.5*cm))
        
        # SEÇÃO 3: Dados Bancários e Características
        elements.append(Paragraph("DADOS BANCÁRIOS E CARACTERÍSTICAS", section_style))
        
        transicao_txt = 'Sim' if parceria['transicao'] == 1 else 'Não' if parceria['transicao'] == 0 else '-'
        contrapartida_txt = 'Sim' if parceria['contrapartida'] == 1 else 'Não' if parceria['contrapartida'] == 0 else '-'
        
        dados_bancarios = [
            ['Conta:', parceria['conta'] or '-'],
            ['É transição de Portaria?', transicao_txt],
            ['Tem contrapartida?', contrapartida_txt]
        ]
        
        tabela_banc = Table(dados_bancarios, colWidths=[5*cm, 12*cm])
        tabela_banc.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(tabela_banc)
        elements.append(Spacer(1, 0.5*cm))
        
        # SEÇÃO 4: Processos SEI
        elements.append(Paragraph("PROCESSOS SEI", section_style))
        
        dados_sei = [
            ['SEI Celebração:', parceria['sei_celeb'] or '-'],
            ['SEI Prestação de Contas:', parceria['sei_pc'] or '-'],
            ['SEI Plano de Trabalho:', parceria['sei_plano'] or '-'],
            ['SEI Orçamento:', parceria['sei_orcamento'] or '-']
        ]
        
        tabela_sei = Table(dados_sei, colWidths=[5*cm, 12*cm])
        tabela_sei.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(tabela_sei)
        elements.append(Spacer(1, 0.5*cm))
        
        # SEÇÃO 5: Pessoa Gestora
        if nome_pg:
            elements.append(Paragraph("PESSOA GESTORA", section_style))
            
            dados_pg = [
                ['Nome da Pessoa Gestora:', nome_pg]
            ]
            
            tabela_pg = Table(dados_pg, colWidths=[5*cm, 12*cm])
            tabela_pg.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
                ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            elements.append(tabela_pg)
            elements.append(Spacer(1, 0.5*cm))
        
        # Rodapé
        elements.append(Spacer(1, 1*cm))
        data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M')
        rodape = Paragraph(f"<i>Documento gerado em {data_geracao}</i>", 
                          ParagraphStyle('Footer', parent=styles['Normal'], 
                                       fontSize=8, textColor=colors.grey))
        elements.append(rodape)
        
        # Gerar PDF
        doc.build(elements)
        
        # Preparar resposta
        buffer.seek(0)
        filename = f'dados_base_{numero_termo.replace("/", "-")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao gerar PDF: {e}")
        traceback.print_exc()
        return f"Erro ao gerar PDF: {str(e)}", 500


@analises_pc_bp.route('/central_modelos')
def central_modelos():
    """Página da Central de Modelos de Documentos"""
    
    # Lista de modelos disponíveis
    modelos = [
        {
            'nome': 'Termo Celebrado',
            'arquivo': 'modelo_termo_celebrado.pdf',
            'icone': '📄',
            'descricao': 'Modelo de termo de colaboração/fomento/parceria'
        },
        {
            'nome': 'Solicitações de Alterações',
            'arquivo': 'modelo_solicitacao_alteracao.pdf',
            'icone': '📨',
            'descricao': 'Documentos que registram pedidos de modificação em cláusulas, cronogramas, valores ou demais aspectos do termo celebrado.'
        },
        {
            'nome': 'Termo de Aditamento',
            'arquivo': 'modelo_termo_aditamento.pdf',
            'icone': '📝',
            'descricao': 'Instrumentos formais utilizados para alterar, prorrogar ou suplementar cláusulas do termo celebrado original.'
        },
        {
            'nome': 'Termo de Apostilamento',
            'arquivo': 'modelo_termo_apostilamento.pdf',
            'icone': '📋',
            'descricao': 'Registros administrativos de ajustes que não modificam o objeto principal do termo, como correções de dados ou atualizações cadastrais.'
        },
        {
            'nome': 'Manifestações - Plano de Trabalho',
            'arquivo': 'modelo_manifestacao_plano.pdf',
            'icone': '�',
            'descricao': 'Pareceres, comunicações ou documentos que resultem em mudanças relevantes no cronograma, atividades ou objetivos do plano de trabalho.'
        },
        {
            'nome': 'Cronograma de Desembolso',
            'arquivo': 'modelo_cronograma_desembolso.xlsx',
            'icone': '�',
            'descricao': 'Documento que apresenta as datas e valores previstos para liberação dos recursos financeiros ao longo da execução do termo.'
        },
        {
            'nome': 'Plano de Trabalho',
            'arquivo': 'modelo_plano_trabalho.pdf',
            'icone': '📊',
            'descricao': 'Documento detalhado das atividades, metas, prazos e responsabilidades para a execução do objeto do termo celebrado.'
        },
        {
            'nome': 'Orçamento Anual',
            'arquivo': 'modelo_orcamento_anual.xlsx',
            'icone': '💰',
            'descricao': 'Relação detalhada dos recursos financeiros previstos para o exercício, com a discriminação das fontes e aplicações.'
        },
        {
            'nome': 'FACC',
            'arquivo': 'modelo_facc.pdf',
            'icone': '🏦',
            'descricao': 'Ficha de Atualização de Cadastro de Credores: Formulário utilizado para atualizar ou confirmar os dados cadastrais dos credores envolvidos no processo.'
        },
        {
            'nome': 'Memória de Cálculo',
            'arquivo': 'modelo_memoria_calculo.xlsx',
            'icone': '🧮',
            'descricao': 'Documento que detalha e justifica os cálculos realizados para apuração de valores, quantitativos e estimativas financeiras relacionadas ao termo.'
        }
    ]
    
    return render_template('analises_pc/central_modelos.html', modelos=modelos)


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
