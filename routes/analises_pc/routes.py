from flask import render_template, request, jsonify, g, send_from_directory, send_file, session, redirect, url_for, Response
from . import analises_pc_bp
from db import get_db
from utils import login_required
from decorators import requires_access, requires_write_access
import psycopg2
import psycopg2.extras
import requests
from psycopg2.extras import execute_values
import traceback
import core.audit_log as audit_log  # Módulo de auditoria
import os
from werkzeug.utils import secure_filename
import re
import unicodedata
from io import BytesIO
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
import utils_storage as storage


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


def _normalizar_texto_comparacao(valor):
    if not valor:
        return ''
    texto = unicodedata.normalize('NFD', str(valor).strip().lower())
    return ''.join(ch for ch in texto if unicodedata.category(ch) != 'Mn')


def _usuario_e_admin(user_data):
    return _normalizar_texto_comparacao(user_data.get('tipo_usuario') if user_data else '') == 'agente publico'


@analises_pc_bp.route('/')
@login_required
@requires_access('analises')
def index():
    """Página inicial do checklist de análise de prestação de contas"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Buscar lista de termos para o dropdown
    cur.execute("SELECT DISTINCT numero_termo FROM public.parcerias ORDER BY numero_termo")
    termos = cur.fetchall()
    
    # Buscar lista de analistas
    cur.execute("SELECT DISTINCT nome_analista FROM categoricas.c_dac_analistas ORDER BY nome_analista")
    analistas = cur.fetchall()
    
    cur.close()
    
    return render_template('analises_pc/index.html', termos=termos, analistas=analistas)


@analises_pc_bp.route('/meus_processos')
@login_required
@requires_access('analises')
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
            FROM gestao_pessoas.usuarios 
            WHERE email = %s
        """, (session['email'],))
        
        user_data = cur.fetchone()
        is_admin = _usuario_e_admin(user_data)
        
        # Buscar todos os analistas para o filtro (se for admin)
        cur.execute("""
            SELECT DISTINCT nome_analista 
            FROM categoricas.c_dac_analistas 
            WHERE status NOT IN ('Inativo', 'false') OR status IS NULL
            ORDER BY nome_analista
        """)
        todos_analistas = cur.fetchall()
        
        # Buscar tipos de contrato disponíveis (para todos os usuários)
        cur.execute("""
            SELECT DISTINCT tipo_termo 
            FROM public.parcerias 
            WHERE tipo_termo IS NOT NULL 
            ORDER BY tipo_termo
        """)
        tipos_contrato = cur.fetchall()
        
        # Buscar áreas temáticas únicas (extrair após última barra do número do termo)
        cur.execute("""
            SELECT DISTINCT UPPER(SUBSTRING(numero_termo FROM '/([^/]+)$')) as area_tematica
            FROM public.parcerias
            WHERE numero_termo LIKE '%/%'
              AND SUBSTRING(numero_termo FROM '/([^/]+)$') IS NOT NULL
            ORDER BY area_tematica
        """)
        areas_tematicas = cur.fetchall()
        
        # Modo gerenciar: admin edita analistas de todos os processos atribuídos
        modo_gerenciar = request.args.get('modo') == 'gerenciar' and is_admin
        if modo_gerenciar:
            cur.execute("""
                SELECT 
                    ct.numero_termo,
                    ct.meses_analisados,
                    STRING_AGG(DISTINCT ca.nome_analista, ', ' ORDER BY ca.nome_analista) as analistas,
                    COUNT(DISTINCT ca.nome_analista) as total_analistas,
                    ARRAY_AGG(DISTINCT ca.nome_analista ORDER BY ca.nome_analista) as analistas_arr,
                    MAX(p.sei_pc) as sei_pc
                FROM analises_pc.checklist_termo ct
                LEFT JOIN analises_pc.checklist_analista ca 
                    ON ct.numero_termo = ca.numero_termo 
                    AND ct.meses_analisados = ca.meses_analisados
                LEFT JOIN public.parcerias p ON ct.numero_termo = p.numero_termo
                GROUP BY ct.numero_termo, ct.meses_analisados
                ORDER BY ct.numero_termo DESC, ct.meses_analisados DESC
            """)
            processos = []
            for r in cur.fetchall():
                proc = dict(r)
                arr = proc.get('analistas_arr') or []
                proc['analistas_arr'] = [a for a in arr if a is not None]
                processos.append(proc)
            cur.close()
            return render_template('analises_pc/meus_processos.html',
                                   processos=processos,
                                   todos_analistas=todos_analistas,
                                   tipos_contrato=tipos_contrato,
                                   areas_tematicas=areas_tematicas,
                                   is_admin=is_admin,
                                   modo_gerenciar=True,
                                   mostrar_nao_atribuidos=False,
                                   ocultar_encerrados=False,
                                   responsabilidade_filtro='',
                                   filtro_termo='',
                                   filtro_tipo_contrato='',
                                   filtro_area_tematica='',
                                   analista_selecionado='',
                                   mensagem=None)

        # Verificar se foi solicitado visualização de processos não atribuídos
        mostrar_nao_atribuidos = request.args.get('nao_atribuidos') == 'true' and is_admin
        ocultar_encerrados = request.args.get('ocultar_encerrados', 'true') == 'true'
        responsabilidade_filtro = request.args.get('responsabilidade', '')
        filtro_termo = request.args.get('filtro_termo', '').strip()
        filtro_tipo_contrato = request.args.get('tipo_contrato', '').strip()
        filtro_area_tematica = request.args.get('area_tematica', '').strip()
        
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
                    pa.tipo_prestacao,
                    p.tipo_termo
                FROM public.parcerias_analises pa
                LEFT JOIN public.parcerias p ON pa.numero_termo = p.numero_termo
                LEFT JOIN categoricas.c_dac_analistas ca ON pa.responsavel_dp = ca.id
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
            
            # Filtro: tipo de contrato
            if filtro_tipo_contrato:
                conditions.append("p.tipo_termo = %s")
                params.append(filtro_tipo_contrato)
            
            # Filtro: área temática (extraída do número do termo após última barra)
            if filtro_area_tematica:
                conditions.append("UPPER(SUBSTRING(pa.numero_termo FROM '/([^/]+)$')) = %s")
                params.append(filtro_area_tematica.upper())
            
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
                    FROM gestao_pessoas.usuarios 
                    WHERE email = %s
                """, (session['email'],))
                
                usuario_row = cur.fetchone()
                
                if not usuario_row or not usuario_row['d_usuario']:
                    # Usuário sem R.F. cadastrado
                    cur.close()
                    return render_template('analises_pc/meus_processos.html', 
                                           processos=[], 
                                           todos_analistas=todos_analistas if is_admin else [],
                                           tipos_contrato=tipos_contrato,
                                           areas_tematicas=areas_tematicas,
                                           is_admin=is_admin,
                                           modo_gerenciar=False,
                                           mostrar_nao_atribuidos=mostrar_nao_atribuidos,
                                           mensagem="Você não possui R.F. cadastrado. Entre em contato com o administrador.")
                
                rf_usuario = normalizar_rf(usuario_row['d_usuario'])
                print(f"[DEBUG] R.F. do usuário {session['email']}: {usuario_row['d_usuario']} -> normalizado: {rf_usuario}")
                
                # Buscar analistas que correspondem ao R.F. do usuário
                # OTIMIZADO: Filtro movido para SQL (evita N+1 Query)
                cur.execute("""
                    SELECT nome_analista, d_usuario
                    FROM categoricas.c_dac_analistas
                    WHERE REGEXP_REPLACE(LOWER(d_usuario), '[^0-9]', '', 'g') LIKE %s || '%%'
                    LIMIT 10
                """, (rf_usuario,))
                
                analistas_correspondentes = []
                for row in cur.fetchall():
                    analistas_correspondentes.append(row['nome_analista'])
                    print(f"[DEBUG] Analista correspondente: {row['nome_analista']} (R.F.: {row['d_usuario']})")
                
                if not analistas_correspondentes:
                    # Nenhum analista corresponde ao R.F. do usuário
                    cur.close()
                    return render_template('analises_pc/meus_processos.html', 
                                           processos=[], 
                                           todos_analistas=todos_analistas if is_admin else [],
                                           tipos_contrato=tipos_contrato,
                                           areas_tematicas=areas_tematicas,
                                           is_admin=is_admin,
                                           modo_gerenciar=False,
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
            
            # Filtro: tipo de contrato
            if filtro_tipo_contrato:
                query_conditions.append("p.tipo_termo = %s")
                query_params.append(filtro_tipo_contrato)
            
            # Filtro: área temática
            if filtro_area_tematica:
                query_conditions.append("UPPER(SUBSTRING(ct.numero_termo FROM '/([^/]+)$')) = %s")
                query_params.append(filtro_area_tematica.upper())
            
            where_clause = f"WHERE ca_filtro.nome_analista IN ({placeholders})"
            if query_conditions:
                where_clause += " AND " + " AND ".join(query_conditions)
            
            query = f"""
                SELECT 
                    ct.numero_termo,
                    ct.meses_analisados,
                    STRING_AGG(DISTINCT ca.nome_analista, ', ' ORDER BY ca.nome_analista) as analistas,
                    COUNT(DISTINCT ca.nome_analista) as total_analistas,
                    ARRAY_AGG(DISTINCT ca.nome_analista ORDER BY ca.nome_analista) as analistas_arr,
                    BOOL_OR(COALESCE(pa_final.e_notificacao, false)) as documentos_sei_1,
                    BOOL_OR(COALESCE(pa_final.e_parecer, false)) as emissao_parecer,
                    BOOL_OR(COALESCE(pa_final.e_encerramento, false)) as encaminhamento_encerramento,
                    MAX(p.sei_pc) as sei_pc,
                    MAX(p.tipo_termo) as tipo_termo
                FROM analises_pc.checklist_termo ct
                INNER JOIN analises_pc.checklist_analista ca_filtro
                    ON ct.numero_termo = ca_filtro.numero_termo
                    AND ct.meses_analisados = ca_filtro.meses_analisados
                LEFT JOIN analises_pc.checklist_analista ca
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
                arr = proc_dict.get('analistas_arr') or []
                proc_dict['analistas_arr'] = [a for a in arr if a is not None]
                
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
                               tipos_contrato=tipos_contrato,
                               areas_tematicas=areas_tematicas,
                               is_admin=is_admin,
                               modo_gerenciar=False,
                               mostrar_nao_atribuidos=mostrar_nao_atribuidos,
                               ocultar_encerrados=ocultar_encerrados,
                               responsabilidade_filtro=responsabilidade_filtro,
                               filtro_termo=filtro_termo,
                               filtro_tipo_contrato=filtro_tipo_contrato,
                               filtro_area_tematica=filtro_area_tematica,
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
                               tipos_contrato=[],
                               areas_tematicas=[],
                               is_admin=False,
                               modo_gerenciar=False,
                               mostrar_nao_atribuidos=False,
                               mensagem=f"Erro ao carregar processos: {str(e)}")


@analises_pc_bp.route('/api/atualizar_analistas', methods=['POST'])
def atualizar_analistas():
    """Atualiza os analistas atribuídos a um processo já existente (somente admin)"""
    if 'email' not in session:
        return jsonify({'error': 'Não autenticado'}), 401

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cur.execute("SELECT tipo_usuario FROM gestao_pessoas.usuarios WHERE email = %s", (session['email'],))
        user_data = cur.fetchone()
        if not _usuario_e_admin(user_data):
            cur.close()
            return jsonify({'error': 'Acesso negado. Apenas administradores podem gerenciar atribuições.'}), 403

        data = request.get_json()
        numero_termo = data.get('numero_termo')
        meses_analisados_original = (data.get('meses_analisados_original') or data.get('meses_analisados') or '').strip()
        meses_analisados = (data.get('meses_analisados') or '').strip()
        analistas = data.get('analistas', [])

        if not numero_termo or not meses_analisados_original or not meses_analisados:
            cur.close()
            return jsonify({'error': 'Dados incompletos'}), 400

        if not analistas:
            cur.close()
            return jsonify({'error': 'É necessário ao menos um analista'}), 400

        cur.execute("""
            SELECT id FROM analises_pc.checklist_termo
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados_original))
        if not cur.fetchone():
            cur.close()
            return jsonify({'error': 'Checklist original nao encontrado'}), 404

        if meses_analisados != meses_analisados_original:
            cur.execute("""
                SELECT id FROM analises_pc.checklist_termo
                WHERE numero_termo = %s AND meses_analisados = %s
            """, (numero_termo, meses_analisados))
            if cur.fetchone():
                cur.close()
                return jsonify({'error': f'Ja existe checklist para o periodo {meses_analisados}.'}), 409

        # Buscar analistas atuais para auditoria
        cur.execute("""
            SELECT nome_analista FROM analises_pc.checklist_analista
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados_original))
        analistas_antigos = [r['nome_analista'] for r in cur.fetchall()]

        if meses_analisados != meses_analisados_original:
            for tabela in ('checklist_termo', 'checklist_recursos'):
                cur.execute(
                    f"UPDATE analises_pc.{tabela} SET meses_analisados = %s "
                    f"WHERE numero_termo = %s AND meses_analisados = %s",
                    (meses_analisados, numero_termo, meses_analisados_original)
                )

        # Deletar e reinserir
        cur.execute("""
            DELETE FROM analises_pc.checklist_analista
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados_original))

        values_placeholders = ','.join(['(%s, %s, %s)'] * len(analistas))
        params = []
        for analista in analistas:
            params.extend([numero_termo, meses_analisados, analista])
        cur.execute(f"""
            INSERT INTO analises_pc.checklist_analista (numero_termo, meses_analisados, nome_analista)
            VALUES {values_placeholders}
        """, params)

        try:
            audit_log.audit_checklist_analistas(conn, numero_termo, meses_analisados, analistas_antigos, analistas)
        except Exception as audit_e:
            print(f"[AVISO] Auditoria falhou (não crítico): {audit_e}")

        conn.commit()
        cur.close()
        return jsonify({'success': True, 'message': f'Analistas de {numero_termo} ({meses_analisados}) atualizados com sucesso!'})

    except Exception as e:
        conn.rollback()
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/excluir_atribuicao', methods=['DELETE'])
def excluir_atribuicao():
    """Exclui o checklist/atribuição de um termo em um período específico (somente admin)."""
    if 'email' not in session:
        return jsonify({'error': 'Nao autenticado'}), 401

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cur.execute("SELECT tipo_usuario FROM gestao_pessoas.usuarios WHERE email = %s", (session['email'],))
        user_data = cur.fetchone()
        if not _usuario_e_admin(user_data):
            cur.close()
            return jsonify({'error': 'Acesso negado. Apenas administradores podem excluir atribuicoes.'}), 403

        data = request.get_json(silent=True) or {}
        numero_termo = (data.get('numero_termo') or '').strip()
        meses_analisados = (data.get('meses_analisados') or '').strip()

        if not numero_termo or not meses_analisados:
            cur.close()
            return jsonify({'error': 'Dados incompletos'}), 400

        cur.execute("""
            SELECT id FROM analises_pc.checklist_termo
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        if not cur.fetchone():
            cur.close()
            return jsonify({'error': 'Atribuicao nao encontrada'}), 404

        cur.execute("""
            SELECT nome_analista FROM analises_pc.checklist_analista
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        analistas_antigos = [r['nome_analista'] for r in cur.fetchall()]

        cur.execute("""
            DELETE FROM analises_pc.checklist_recursos
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        recursos_excluidos = cur.rowcount

        cur.execute("""
            DELETE FROM analises_pc.checklist_analista
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        analistas_excluidos = cur.rowcount

        cur.execute("""
            DELETE FROM analises_pc.checklist_termo
            WHERE numero_termo = %s AND meses_analisados = %s
        """, (numero_termo, meses_analisados))
        termos_excluidos = cur.rowcount

        try:
            audit_log.audit_checklist_analistas(conn, numero_termo, meses_analisados, analistas_antigos, [])
        except Exception as audit_e:
            print(f"[AVISO] Auditoria de exclusao falhou (nao critico): {audit_e}")

        conn.commit()
        cur.close()
        return jsonify({
            'success': True,
            'message': f'Atribuicao {numero_termo} ({meses_analisados}) excluida com sucesso.',
            'contadores': {
                'checklist_termo': termos_excluidos,
                'checklist_analista': analistas_excluidos,
                'checklist_recursos': recursos_excluidos
            }
        })

    except Exception as e:
        conn.rollback()
        cur.close()
        return jsonify({'error': str(e)}), 500


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
            FROM gestao_pessoas.usuarios 
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
        cur.execute("SELECT tipo_usuario FROM gestao_pessoas.usuarios WHERE email = %s", (session['email'],))
        user_data = cur.fetchone()
        
        if not _usuario_e_admin(user_data):
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
        
        # Inserir analistas em checklist_analista (OTIMIZADO: INSERT em massa)
        # 1. Buscar todos os analistas que já existem de uma vez
        if analistas:
            placeholders = ','.join(['%s'] * len(analistas))
            cur.execute(f"""
                SELECT nome_analista 
                FROM analises_pc.checklist_analista 
                WHERE numero_termo = %s 
                  AND meses_analisados = %s 
                  AND nome_analista IN ({placeholders})
            """, (numero_termo, meses_analisados, *analistas))
            
            # Conjunto dos que já existem
            existentes = {row['nome_analista'] for row in cur.fetchall()}
            
            # 2. Filtrar apenas os novos
            novos = [a for a in analistas if a not in existentes]
            
            # 3. Se há novos, fazer INSERT em massa com VALUES múltiplos
            if novos:
                values_placeholders = ','.join(['(%s, %s, %s)'] * len(novos))
                params = []
                for analista in novos:
                    params.extend([numero_termo, meses_analisados, analista])
                
                cur.execute(f"""
                    INSERT INTO analises_pc.checklist_analista 
                        (numero_termo, meses_analisados, nome_analista)
                    VALUES {values_placeholders}
                """, params)
                print(f"[DEBUG] Inseridos {len(novos)} analista(s) em massa")
        
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
        # Buscar instrução de celebração da tabela categoricas.c_geral_modelo_textos
        cur.execute("""
            SELECT titulo_texto, modelo_texto 
            FROM categoricas.c_geral_modelo_textos
            WHERE titulo_texto = 'Instrução: Avaliação do processo de celebração'
            LIMIT 1
        """)
        instrucao_row = cur.fetchone()
        instrucao = instrucao_row['modelo_texto'] if instrucao_row else None
        print(f"[DEBUG] Instrução celebração encontrada: {bool(instrucao)}")
        
        # Buscar instrução de prestação de contas
        cur.execute("""
            SELECT titulo_texto, modelo_texto 
            FROM categoricas.c_geral_modelo_textos
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
    periodo_anterior = data.get('periodo_anterior')  # presente quando usuário renomeou o período
    nome_analista = data.get('nome_analista')
    analistas = data.get('analistas', [])
    checklist_data = data.get('checklist', {})
    recursos = data.get('recursos', [])

    if not numero_termo or not meses_analisados:
        return jsonify({'error': 'Dados incompletos'}), 400

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        # 🔄 RENOMEAÇÃO DE PERÍODO: se o usuário mudou o campo período, atualizar meses_analisados
        # nas 3 tabelas antes de prosseguir com o save normal.
        if periodo_anterior and periodo_anterior != meses_analisados:
            cur.execute("""
                SELECT id FROM analises_pc.checklist_termo
                WHERE numero_termo = %s AND meses_analisados = %s
            """, (numero_termo, periodo_anterior))
            if not cur.fetchone():
                conn.rollback()
                cur.close()
                return jsonify({
                    'error': f'Periodo original {periodo_anterior} nao encontrado. Recarregue a pagina antes de salvar.'
                }), 404

            cur.execute("""
                SELECT id FROM analises_pc.checklist_termo
                WHERE numero_termo = %s AND meses_analisados = %s
            """, (numero_termo, meses_analisados))
            if cur.fetchone():
                conn.rollback()
                cur.close()
                return jsonify({
                    'error': f'Ja existe checklist para o periodo {meses_analisados}. Use o botao Editar em Meus Processos para alterar a atribuicao existente.'
                }), 409

            for tabela in ('checklist_termo', 'checklist_analista', 'checklist_recursos'):
                cur.execute(
                    f"UPDATE analises_pc.{tabela} SET meses_analisados = %s "
                    f"WHERE numero_termo = %s AND meses_analisados = %s",
                    (meses_analisados, numero_termo, periodo_anterior)
                )

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

        file_bytes = storage.download_file(f'Modelos/{filename}')
        return send_file(BytesIO(file_bytes), as_attachment=True, download_name=filename)

    except FileNotFoundError:
        return f"Arquivo não encontrado: {filename}", 404
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
        
        # Verificar se arquivo já existe no storage
        arquivos_existentes = storage.list_files('Modelos')
        if filename in arquivos_existentes:
            return jsonify({
                'error': f'Arquivo "{filename}" já existe. Renomeie ou exclua o arquivo existente primeiro.'
            }), 409
        
        # Fazer upload para storage (local ou Supabase)
        arquivo.seek(0)
        file_bytes = arquivo.read()
        content_type = 'application/pdf' if extensao == 'pdf' else \
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        storage.upload_file(f'Modelos/{filename}', file_bytes, content_type)
        
        print(f"[INFO] Upload realizado: {filename} por {session.get('email')}")
        
        return jsonify({
            'mensagem': 'Arquivo enviado com sucesso!',
            'filename': filename,
            'tamanho': len(file_bytes),
            'usuario': session.get('email')
        }), 200
    
    except Exception as e:
        print(f"[ERRO] Erro ao fazer upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Erro ao fazer upload: {str(e)}'}), 500


# ─────────────────────────────────────────────────────────────────────────────
# MANIFESTAÇÕES RECURSAIS — Upload, processamento e histórico de PDFs da OSC
# ─────────────────────────────────────────────────────────────────────────────

import threading


def _processar_pdf_manifestacao(doc_id: int, file_bytes: bytes):
    """Extrai texto de cada página do PDF e armazena em analises_pc_manifestacoes.paginas.
    Executado em thread separada; abre sua própria conexão DB via DB_CONFIG."""
    import psycopg2
    import psycopg2.extras
    import pdfplumber
    from config import DB_CONFIG
    from io import BytesIO

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        cur.execute(
            "UPDATE analises_pc_manifestacoes.documentos SET status='processando' WHERE id=%s",
            (doc_id,)
        )
        conn.commit()

        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            total = len(pdf.pages)
            cur.execute(
                "UPDATE analises_pc_manifestacoes.documentos SET total_paginas=%s WHERE id=%s",
                (total, doc_id)
            )
            conn.commit()

            for i, page in enumerate(pdf.pages, start=1):
                texto = page.extract_text() or ''
                metodo = 'pdfplumber'

                if len(texto.strip()) < 50:
                    try:
                        import pdf2image
                        import pytesseract
                        imgs = pdf2image.convert_from_bytes(
                            file_bytes, first_page=i, last_page=i, dpi=200
                        )
                        if imgs:
                            texto = pytesseract.image_to_string(imgs[0], lang='por') or ''
                            metodo = 'tesseract'
                    except Exception:
                        pass

                cur.execute("""
                    INSERT INTO analises_pc_manifestacoes.paginas
                        (documento_id, numero_pagina, texto_extraido, metodo_extracao)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (documento_id, numero_pagina) DO UPDATE
                        SET texto_extraido = EXCLUDED.texto_extraido,
                            metodo_extracao = EXCLUDED.metodo_extracao
                """, (doc_id, i, texto, metodo))

                if i % 5 == 0:
                    conn.commit()

        conn.commit()
        cur.execute(
            "UPDATE analises_pc_manifestacoes.documentos SET status='concluido' WHERE id=%s",
            (doc_id,)
        )
        conn.commit()

    except Exception as exc:
        print(f"[ERRO] Processamento PDF doc_id={doc_id}: {exc}")
        traceback.print_exc()
        try:
            conn.rollback()
            cur.execute(
                "UPDATE analises_pc_manifestacoes.documentos SET status='erro', erro_msg=%s WHERE id=%s",
                (str(exc)[:500], doc_id)
            )
            conn.commit()
        except Exception:
            pass
    finally:
        cur.close()
        conn.close()


@analises_pc_bp.route('/api/manifestacoes/upload', methods=['POST'])
@login_required
@requires_access('analises')
def upload_manifestacao():
    """Recebe PDF da OSC, salva no storage e inicia processamento em background."""
    if 'arquivo' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400

    arquivo = request.files['arquivo']
    numero_termo = request.form.get('numero_termo', '').strip()
    tipo_documento = request.form.get('tipo_documento', 'manifestacao_recursal')

    if not numero_termo:
        return jsonify({'error': 'Número do termo não informado'}), 400
    if arquivo.filename == '':
        return jsonify({'error': 'Nenhum arquivo selecionado'}), 400
    if not arquivo.filename.lower().endswith('.pdf'):
        return jsonify({'error': 'Apenas arquivos PDF são permitidos'}), 400

    tipos_validos = {'manifestacao_recursal', 'planilha', 'peticao', 'outro'}
    if tipo_documento not in tipos_validos:
        tipo_documento = 'manifestacao_recursal'

    filename = secure_filename(arquivo.filename)
    storage_path = f'Manifestacoes/{numero_termo}/{filename}'

    arquivo.seek(0)
    file_bytes = arquivo.read()

    try:
        storage.upload_file(storage_path, file_bytes, 'application/pdf')
    except Exception as e:
        return jsonify({'error': f'Erro ao salvar arquivo: {str(e)}'}), 500

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            INSERT INTO analises_pc_manifestacoes.documentos
                (numero_termo, nome_arquivo, tamanho_bytes, tipo_documento,
                 storage_path, usuario_upload, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pendente')
            RETURNING id
        """, (numero_termo, filename, len(file_bytes), tipo_documento,
              storage_path, session.get('email')))
        doc_id = cur.fetchone()['id']
        conn.commit()
        cur.close()
    except Exception as e:
        conn.rollback()
        cur.close()
        return jsonify({'error': str(e)}), 500

    threading.Thread(
        target=_processar_pdf_manifestacao,
        args=(doc_id, file_bytes),
        daemon=True
    ).start()

    return jsonify({'success': True, 'doc_id': doc_id,
                    'message': 'Upload realizado. Processamento iniciado.'})


@analises_pc_bp.route('/api/manifestacoes/status/<int:doc_id>', methods=['GET'])
@login_required
def status_manifestacao(doc_id):
    """Retorna progresso de processamento de um documento."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT d.id, d.status, d.total_paginas, d.erro_msg,
                   COUNT(p.id) AS paginas_processadas
            FROM analises_pc_manifestacoes.documentos d
            LEFT JOIN analises_pc_manifestacoes.paginas p ON p.documento_id = d.id
            WHERE d.id = %s
            GROUP BY d.id, d.status, d.total_paginas, d.erro_msg
        """, (doc_id,))
        doc = cur.fetchone()
        cur.close()
        if not doc:
            return jsonify({'error': 'Documento não encontrado'}), 404

        total = doc['total_paginas'] or 0
        processadas = doc['paginas_processadas'] or 0
        pct = round((processadas / total) * 100) if total > 0 else (
            100 if doc['status'] == 'concluido' else 0
        )
        return jsonify({
            'id': doc['id'],
            'status': doc['status'],
            'total_paginas': total,
            'paginas_processadas': processadas,
            'percentual': pct,
            'erro_msg': doc['erro_msg']
        })
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/manifestacoes/listar', methods=['GET'])
@login_required
@requires_access('analises')
def listar_manifestacoes():
    """Lista documentos de manifestação de um termo."""
    numero_termo = request.args.get('numero_termo', '').strip()
    if not numero_termo:
        return jsonify({'error': 'Número do termo não informado'}), 400

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT d.id, d.nome_arquivo, d.tamanho_bytes, d.tipo_documento,
                   d.data_upload, d.usuario_upload, d.status,
                   d.total_paginas, d.erro_msg,
                   COUNT(p.id) AS paginas_processadas
            FROM analises_pc_manifestacoes.documentos d
            LEFT JOIN analises_pc_manifestacoes.paginas p ON p.documento_id = d.id
            WHERE d.numero_termo = %s
            GROUP BY d.id
            ORDER BY d.data_upload DESC
        """, (numero_termo,))
        docs = cur.fetchall()
        cur.close()

        resultado = []
        for d in docs:
            r = dict(d)
            r['data_upload'] = r['data_upload'].strftime('%d/%m/%Y %H:%M') if r.get('data_upload') else ''
            resultado.append(r)

        return jsonify({'documentos': resultado})
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/manifestacoes/<int:doc_id>', methods=['DELETE'])
@login_required
@requires_access('analises')
def deletar_manifestacao(doc_id):
    """Remove documento e seus dados do banco (cascade) e do storage."""
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute(
            "SELECT storage_path FROM analises_pc_manifestacoes.documentos WHERE id = %s",
            (doc_id,)
        )
        doc = cur.fetchone()
        if not doc:
            cur.close()
            return jsonify({'error': 'Documento não encontrado'}), 404

        try:
            storage.delete_file(doc['storage_path'])
        except Exception:
            pass

        cur.execute(
            "DELETE FROM analises_pc_manifestacoes.documentos WHERE id = %s",
            (doc_id,)
        )
        conn.commit()
        cur.close()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        cur.close()
        return jsonify({'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# ANÁLISE IA — Deepseek cross-referência manifestação × conciliação bancária
# ─────────────────────────────────────────────────────────────────────────────

import uuid
import time as _time
import json as _json

_analises_ia: dict = {}
_analises_ia_lock = threading.Lock()
_ANALISE_TTL_S = 3600  # 1h


def _nova_analise_task() -> str:
    tid = str(uuid.uuid4())
    agora = _time.time()
    with _analises_ia_lock:
        expiradas = [k for k, v in _analises_ia.items()
                     if agora - v.get('ts', agora) > _ANALISE_TTL_S]
        for k in expiradas:
            del _analises_ia[k]
        _analises_ia[tid] = {'status': 'running', 'pct': 0,
                             'label': 'Iniciando…', 'resultado': None,
                             'erro': None, 'ts': agora}
    return tid


def _upd_analise(tid: str, **kw):
    with _analises_ia_lock:
        if tid in _analises_ia:
            _analises_ia[tid].update(kw)


def _carregar_prompt_sistema() -> str:
    """Lê prompts/analise_manifestacao_recursal.md em tempo de execução."""
    caminho = os.path.join(os.path.dirname(__file__), '..', '..', 'prompts',
                           'analise_manifestacao_recursal.md')
    caminho = os.path.normpath(caminho)
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Você é um assessor técnico da DAC/SMDHC. Analise a manifestação recursal e os dados de conciliação bancária. Responda com JSON."


def _montar_contexto_db(numero_termo: str, meses_analisados: str, doc_ids: list):
    """Consulta o banco e monta o contexto de dados para o prompt.

    Retorna (contexto_str, totais_db) onde totais_db é um dict com os valores
    reais do banco (total_glosado, total_taxas_bancarias) para serem injetados
    no resultado final sem depender da IA para esses números.

    Ordem dos blocos: DB data primeiro (nunca truncado), PDF por último.
    Isso garante que o truncamento por MAX_CHARS só corte o texto do PDF,
    nunca os dados de conciliação.

    Schema real (verificado 2026-06):
      conc_extrato : id, data, credito, debito, discriminacao, competencia,
                     origem_destino, cat_avaliacao, avaliacao_analista, numero_termo
      conc_analise : id, numero_termo, conc_extrato_id, avaliacao_guia,
                     avaliacao_comprovante, avaliacao_contratos, avaliacao_fora_municipio
      lista_inconsistencias : id, nome_item, data, debito, discriminacao,
                              competencia, origem_destino, status, numero_termo
      lista_inconsistencias_agregadas : id, nome_item, numero_termo,
                              tipo_agregacao, campo1, campo2,
                              valor_previsto, valor_executado, diferenca, status
      public.parcerias : numero_termo, osc, projeto, portaria, inicio, final,
                         total_previsto, total_pago
    """
    import psycopg2
    import psycopg2.extras
    from config import DB_CONFIG

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # blocos_db: dados do banco (sempre incluídos, vêm primeiro)
    # bloco_pdf: texto dos PDFs (vem por último — truncado se necessário)
    blocos_db = []
    bloco_pdf = None
    totais_db = {}  # valores reais do banco para injetar no resultado final

    try:
        # BLOCO 4 — Dados do Termo (public.parcerias)
        cur.execute("""
            SELECT osc, projeto, portaria, inicio, final, total_previsto, total_pago
            FROM public.parcerias
            WHERE numero_termo = %s
            LIMIT 1
        """, (numero_termo,))
        parceria = cur.fetchone()
        if parceria:
            blocos_db.append(
                f"=== BLOCO 4 — DADOS DO TERMO ===\n"
                f"Termo: {numero_termo}\n"
                f"OSC: {parceria.get('osc') or ''}\n"
                f"Projeto: {parceria.get('projeto') or ''}\n"
                f"Vigência: {parceria.get('inicio') or ''} a {parceria.get('final') or ''}\n"
                f"Total Previsto: R$ {parceria.get('total_previsto') or ''}\n"
                f"Total Pago: R$ {parceria.get('total_pago') or ''}\n"
                f"Portaria: {parceria.get('portaria') or ''}"
            )

        # BLOCO 6 — Plano de Trabalho (despesas autorizadas por categoria)
        cur.execute("""
            SELECT rubrica, categoria_despesa,
                   COUNT(DISTINCT mes) AS meses_previstos,
                   ROUND(SUM(valor)::numeric, 2) AS total_previsto
            FROM public.parcerias_despesas
            WHERE numero_termo = %s AND aditivo = 0
            GROUP BY rubrica, categoria_despesa
            ORDER BY rubrica, total_previsto DESC
        """, (numero_termo,))
        plano_despesas = cur.fetchall()

        if plano_despesas:
            linhas_pt = [
                "=== BLOCO 6 — PLANO DE TRABALHO (DESPESAS AUTORIZADAS) ===",
                "Use este bloco para verificar se uma categoria glosada estava prevista no plano aprovado.",
                "Se a categoria NÃO consta aqui → despesa não prevista no plano de trabalho (glosa procedente).",
                "Se consta → compare o total glosado com o total autorizado para dimensionar o excesso.",
                "",
                "rubrica | categoria_despesa | meses_previstos | total_previsto"
            ]
            for r in plano_despesas:
                linhas_pt.append(
                    f"  {r['rubrica']} | {r['categoria_despesa']} | "
                    f"{r['meses_previstos']} meses | R$ {r['total_previsto']}"
                )
            blocos_db.append("\n".join(linhas_pt))

        # BLOCO 7 — Repasses realizados e cronograma de desembolso
        try:
            cur.execute("""
                SELECT parcela_numero, valor_pago, data_pagamento, observacoes
                FROM gestao_financeira.ultra_liquidacoes
                WHERE numero_termo = %s
                ORDER BY data_pagamento
            """, (numero_termo,))
            repasses = cur.fetchall()

            cur.execute("""
                SELECT parcela_numero, nome_mes, valor_mes
                FROM gestao_financeira.ultra_liquidacoes_cronograma
                WHERE numero_termo = %s
                ORDER BY nome_mes
            """, (numero_termo,))
            cronograma = cur.fetchall()

            if repasses or cronograma:
                linhas_rep = [
                    "=== BLOCO 7 — REPASSES E CRONOGRAMA DE DESEMBOLSO ===",
                    "Use este bloco para avaliar o argumento de atraso nos repasses.",
                    "Compare 'data_pagamento' (repasse realizado) com o primeiro 'nome_mes' de cada parcela (início previsto).",
                    "O atraso real = diferença em dias entre data prevista e data efetivada.",
                    "",
                    "REPASSES REALIZADOS:",
                    "parcela | valor_pago | data_pagamento | observacoes"
                ]
                for r in repasses:
                    linhas_rep.append(
                        f"  {r['parcela_numero']} | R$ {r['valor_pago']} | "
                        f"{r['data_pagamento']} | {r['observacoes'] or '—'}"
                    )
                linhas_rep += ["", "CRONOGRAMA MENSAL PREVISTO:", "parcela | mes_previsto | valor_mes"]
                for r in cronograma:
                    linhas_rep.append(
                        f"  {r['parcela_numero']} | {r['nome_mes']} | R$ {r['valor_mes']}"
                    )
                blocos_db.append("\n".join(linhas_rep))
        except Exception as e_rep:
            print(f"[CONTEXTO DB] BLOCO 7 indisponível: {e_rep}")

        # BLOCO 8 — Quadro Financeiro do Projeto (saldos, contrapartida, taxas)
        try:
            def _f(v):
                if v is None:
                    return 'R$ 0,00'
                try:
                    return f'R$ {float(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
                except Exception:
                    return 'R$ 0,00'

            def _fv(v):
                try:
                    return float(v) if v is not None else 0.0
                except Exception:
                    return 0.0

            # Rendimentos — tabela dedicada (mesma fonte do conc_relatorio)
            cur.execute("""
                SELECT
                    COALESCE(SUM(rendimento_bruto), 0) AS rend_bruto,
                    COALESCE(SUM(rendimento_ir), 0)    AS rend_ir,
                    COALESCE(SUM(rendimento_iof), 0)   AS rend_iof
                FROM analises_pc.conc_rendimentos
                WHERE numero_termo = %s
            """, (numero_termo,))
            rend_row = cur.fetchone() or {}
            rend_bruto  = _fv(rend_row.get('rend_bruto'))
            rend_ir     = _fv(rend_row.get('rend_ir'))
            rend_iof    = _fv(rend_row.get('rend_iof'))
            rend_liquido = rend_bruto - rend_ir - rend_iof

            # Contrapartida — prevista total e desconto calculado
            cur.execute("""
                SELECT
                    COALESCE(SUM(valor_previsto), 0)    AS cp_previsto,
                    COALESCE(SUM(valor_executado), 0)   AS cp_executado,
                    COALESCE(SUM(valor_considerado), 0) AS cp_considerado,
                    COALESCE(SUM(GREATEST(valor_previsto - valor_executado, 0)), 0)   AS desc_prev_exec,
                    COALESCE(SUM(GREATEST(valor_executado - valor_considerado, 0)), 0) AS desc_exec_cons
                FROM analises_pc.conc_contrapartida
                WHERE numero_termo = %s
            """, (numero_termo,))
            cp_row = cur.fetchone() or {}
            cp_previsto    = _fv(cp_row.get('cp_previsto'))
            cp_executado   = _fv(cp_row.get('cp_executado'))
            cp_considerado = _fv(cp_row.get('cp_considerado'))
            cp_desconto    = _fv(cp_row.get('desc_prev_exec')) + _fv(cp_row.get('desc_exec_cons'))

            # Taxas bancárias — match exato em cat_transacao (igual ao conc_relatorio)
            cur.execute("""
                SELECT
                    COALESCE(SUM(CASE WHEN LOWER(cat_transacao) = 'taxas bancárias'
                                      THEN ABS(discriminacao) ELSE 0 END), 0) AS taxas_total,
                    COALESCE(SUM(CASE WHEN LOWER(cat_transacao) = 'devolução de taxas bancárias'
                                      THEN ABS(discriminacao) ELSE 0 END), 0) AS taxas_devolucao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s AND discriminacao IS NOT NULL
            """, (numero_termo,))
            tax_row = cur.fetchone() or {}
            taxas_total      = _fv(tax_row.get('taxas_total'))
            taxas_devolucao  = _fv(tax_row.get('taxas_devolucao'))
            taxas_nao_devolvidas = max(taxas_total - taxas_devolucao, 0.0)

            # Descontos realizados — tabela conc_banco
            cur.execute("""
                SELECT descontos_realizados
                FROM analises_pc.conc_banco
                WHERE numero_termo = %s
            """, (numero_termo,))
            desc_row = cur.fetchone()
            descontos_realizados = _fv((desc_row or {}).get('descontos_realizados'))

            # Valores já devolvidos — restituição de verba + devolução de taxas (ABS discriminacao)
            cur.execute("""
                SELECT COALESCE(SUM(ABS(discriminacao)), 0) AS valores_devolvidos
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s
                  AND LOWER(cat_transacao) IN ('restituição de verba', 'devolução de taxas bancárias')
                  AND discriminacao IS NOT NULL
            """, (numero_termo,))
            dev_row = cur.fetchone() or {}
            valores_devolvidos = _fv(dev_row.get('valores_devolvidos'))

            # Valor executado aprovado — apenas categorias do plano de trabalho (mesmo critério do conc_relatorio)
            cur.execute("""
                SELECT COALESCE(SUM(ABS(ce.discriminacao)), 0) AS valor_executado_aprovado
                FROM analises_pc.conc_extrato ce
                WHERE ce.numero_termo = %s
                  AND ce.cat_avaliacao = 'Avaliado'
                  AND ce.discriminacao IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM public.parcerias_despesas pd
                      WHERE LOWER(pd.categoria_despesa) = LOWER(ce.cat_transacao)
                        AND pd.numero_termo = ce.numero_termo
                  )
            """, (numero_termo,))
            exec_row = cur.fetchone() or {}
            valor_executado_aprovado = _fv(exec_row.get('valor_executado_aprovado'))

            # Despesas passíveis de glosa (exceto taxas bancárias)
            cur.execute("""
                SELECT COALESCE(SUM(ABS(discriminacao)), 0) AS despesas_glosa
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s
                  AND cat_avaliacao = 'Glosar'
                  AND LOWER(COALESCE(cat_transacao, '')) != 'taxas bancárias'
                  AND discriminacao IS NOT NULL
            """, (numero_termo,))
            glosa_row = cur.fetchone() or {}
            despesas_glosa = _fv(glosa_row.get('despesas_glosa'))

            # Total pago e valor total do projeto
            total_pago = _fv((parceria or {}).get('total_pago'))
            valor_total_projeto = total_pago + rend_liquido + cp_previsto

            # Saldos remanescentes
            saldos_remanescentes = max(
                valor_total_projeto - valor_executado_aprovado - despesas_glosa - taxas_nao_devolvidas,
                0.0
            )

            # Total descontos e valor a ressarcir
            total_descontos = (
                saldos_remanescentes + descontos_realizados + cp_desconto +
                despesas_glosa + taxas_nao_devolvidas
            )
            valor_ressarcir = max(total_descontos - valores_devolvidos, 0.0)

            linhas_qf = [
                "=== BLOCO 8 — QUADRO FINANCEIRO DO PROJETO ===",
                "ATENÇÃO: Estes valores foram calculados pelo sistema. NÃO recalcule — use-os diretamente nos campos indicados.",
                "",
                "[ Composição do Valor Total do Projeto ]",
                f"  Repasses realizados (total_pago):       {_f(total_pago)}",
                f"  Rendimentos líquidos (bruto - IR/IOF):  {_f(rend_liquido)}",
                f"  Contrapartida prevista:                 {_f(cp_previsto)}",
                f"  VALOR TOTAL DO PROJETO:                 {_f(valor_total_projeto)}",
                "",
                "[ Execução ]",
                f"  Despesas aprovadas (Avaliado):          {_f(valor_executado_aprovado)}",
                f"  Despesas glosadas (ex-taxas bancárias): {_f(despesas_glosa)}",
                f"  Taxas bancárias cobradas:               {_f(taxas_total)}",
                f"  Taxas bancárias devolvidas:             {_f(taxas_devolucao)}",
                "",
                "[ VALORES A USAR NOS CAMPOS JSON — NÃO RECALCULE ]",
                f"  comentario_saldos         → SALDO REMANESCENTE = {_f(saldos_remanescentes)}",
                f"    (fórmula: valor_total_projeto − aprovado − glosado − taxas_não_devolvidas)",
                f"  comentario_contrapartida  → DESCONTO CONTRAPARTIDA = {_f(cp_desconto)}",
                f"    (previsto={_f(cp_previsto)}, executado={_f(cp_executado)}, considerado={_f(cp_considerado)})",
                f"  comentario_taxas_bancarias → TAXAS NÃO DEVOLVIDAS = {_f(taxas_nao_devolvidas)}",
                f"  valor_total_ressarcir     → {_f(valor_ressarcir)}",
                f"    (total_descontos={_f(total_descontos)} − já_devolvidos={_f(valores_devolvidos)})",
                "",
                "[ Fundamentos legais ]",
                "  • Saldos remanescentes → art. 52 da Lei 13.019/2014 (devolução obrigatória ao término da parceria)",
                "  • Contrapartida não executada → desconto proporcional conforme pactuado no plano de trabalho",
                "  • Taxas bancárias não devolvidas → devem ser restituídas ao erário (art. 53, Lei 13.019/2014 e Portaria SF 210/2017)",
            ]
            blocos_db.append("\n".join(linhas_qf))

            # Salva valores financeiros em totais_db para uso no front-end se necessário
            totais_db['saldos_remanescentes'] = round(saldos_remanescentes, 2)
            totais_db['desconto_contrapartida'] = round(cp_desconto, 2)
            totais_db['taxas_nao_devolvidas'] = round(taxas_nao_devolvidas, 2)
            totais_db['valor_ressarcir'] = round(valor_ressarcir, 2)

        except Exception as e_qf:
            print(f"[CONTEXTO DB] BLOCO 8 indisponível: {e_qf}")
            import traceback; traceback.print_exc()

        # BLOCO 9 — Legislação aplicável ao período da parceria
        try:
            portaria_termo = (parceria or {}).get('portaria') or ''
            inicio_termo = (parceria or {}).get('inicio')
            final_termo = (parceria or {}).get('final')

            # Filtra legislação vigente durante a execução da parceria
            # Inclui: portaria específica do termo, leis-base e portarias SMDHC relevantes
            cur.execute("""
                SELECT lei, tipo_doc, descricao, link, status_vigencia,
                       inicio, termino
                FROM categoricas.c_geral_legislacao
                WHERE oculto IS NOT TRUE
                  AND tipo_doc IN ('Lei', 'Decreto', 'Portaria')
                  AND (
                      -- Vigente durante algum momento da execução do termo
                      (termino IS NULL OR termino >= %s)
                      AND (inicio IS NULL OR inicio <= COALESCE(%s, CURRENT_DATE))
                  )
                ORDER BY inicio
            """, (inicio_termo or '2014-01-01', final_termo))
            leis = cur.fetchall()

            if leis:
                linhas_leg = [
                    "=== BLOCO 9 — LEGISLAÇÃO APLICÁVEL ===",
                    f"Portaria do Termo: {portaria_termo or 'não informada'}",
                    f"Vigência da parceria: {inicio_termo or '?'} a {final_termo or '?'}",
                    "",
                    "Normas vigentes durante a execução (use para fundamentar análise):",
                ]
                for lei in leis:
                    lei_nome = lei.get('lei') or ''
                    lei_tipo = lei.get('tipo_doc') or ''
                    lei_desc = lei.get('descricao') or ''
                    lei_status = lei.get('status_vigencia') or 'vigente'
                    lei_link = lei.get('link') or ''
                    linha = f"  [{lei_tipo}] {lei_nome}"
                    if lei_desc:
                        linha += f": {lei_desc[:120]}"
                    if lei_status and lei_status.lower() not in ('vigente', ''):
                        linha += f" ⚠ {lei_status}"
                    if lei_link:
                        linha += f" → {lei_link}"
                    linhas_leg.append(linha)
                linhas_leg.append("")
                linhas_leg.append(
                    "NOTA: Para os textos completos das portarias e artigos específicos, "
                    "faça o upload do PDF como 'Portaria / Normativa' (BLOCO 1a) para citação direta de dispositivos."
                )
                blocos_db.append("\n".join(linhas_leg))

        except Exception as e_leg:
            print(f"[CONTEXTO DB] BLOCO 9 indisponível: {e_leg}")

        # BLOCO 2 — Conciliação: itens glosados (cat_avaliacao = 'Glosar')
        # IMPORTANTE: cat_avaliacao é o campo de classificação ('Glosar'/'Avaliado').
        #             avaliacao_analista é texto de observação do analista (razão da glosa).
        #             Estratégia: totais agregados (completos) + top-N individuais por valor.

        # 2a — Total geral e por categoria de transação
        cur.execute("""
            SELECT
                COUNT(*) as total_itens,
                SUM(ABS(discriminacao)) as total_glosado,
                SUM(CASE WHEN LOWER(cat_transacao) = 'taxas bancárias' THEN ABS(discriminacao) ELSE 0 END) as total_taxas
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s AND cat_avaliacao = 'Glosar'
        """, (numero_termo,))
        totais = cur.fetchone()

        cur.execute("""
            SELECT cat_transacao, COUNT(*) as qtd, SUM(ABS(discriminacao)) as total
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s AND cat_avaliacao = 'Glosar'
            GROUP BY cat_transacao
            ORDER BY total DESC
        """, (numero_termo,))
        por_categoria = cur.fetchall()

        # 2b — Por competência (mês)
        cur.execute("""
            SELECT competencia, COUNT(*) as qtd, SUM(ABS(discriminacao)) as total
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s AND cat_avaliacao = 'Glosar'
            GROUP BY competencia
            ORDER BY competencia
        """, (numero_termo,))
        por_mes = cur.fetchall()

        # 2c — Top 200 itens individuais por valor (para correlação com valores citados)
        cur.execute("""
            SELECT ce.data, ce.origem_destino, ce.discriminacao,
                   ce.cat_transacao, ce.competencia, ce.avaliacao_analista,
                   ca.avaliacao_guia, ca.avaliacao_comprovante,
                   ca.avaliacao_contratos, ca.avaliacao_fora_municipio
            FROM analises_pc.conc_extrato ce
            LEFT JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s AND ce.cat_avaliacao = 'Glosar'
            ORDER BY ABS(ce.discriminacao) DESC NULLS LAST
            LIMIT 200
        """, (numero_termo,))
        top_itens = cur.fetchall()

        if totais:
            # Salva totais reais do banco para injetar no resultado final
            totais_db['total_glosado'] = float(totais['total_glosado'] or 0)
            totais_db['total_taxas'] = float(totais['total_taxas'] or 0)
            totais_db['total_itens'] = int(totais['total_itens'] or 0)
            totais_db['total_sem_taxas'] = totais_db['total_glosado'] - totais_db['total_taxas']

            bloco2_linhas = [
                "=== BLOCO 2 — CONCILIAÇÃO BANCÁRIA (GLOSAS) ===",
                "NOTA: 'discriminacao' = valor individual do item (use este para cruzamento, não 'debito').",
                "      'cat_avaliacao' = classificação ('Glosar'/'Avaliado').",
                "      'avaliacao_analista' = observação textual do analista (razão da glosa).",
                "",
                "TOTAIS GLOBAIS (fonte: banco de dados — use estes valores como âncora):",
                f"  Total itens glosados : {totais['total_itens']}",
                f"  Total glosado (sum discriminacao) : R$ {totais['total_glosado']}",
                f"  Taxas bancárias incluídas nesse total : R$ {totais['total_taxas']}",
                f"  Total glosado excl. taxas bancárias  : R$ {totais_db['total_sem_taxas']:.2f}",
                "",
                "POR CATEGORIA DE TRANSAÇÃO:",
            ]
            for r in por_categoria:
                bloco2_linhas.append(f"  {r['cat_transacao'] or 'sem categoria'}: {r['qtd']} itens | R$ {r['total']}")

            bloco2_linhas += ["", "POR COMPETÊNCIA (mês de referência):"]
            for r in por_mes:
                bloco2_linhas.append(f"  {r['competencia']}: {r['qtd']} itens | R$ {r['total']}")

            bloco2_linhas += ["", f"TOP 200 ITENS POR VALOR (de {totais['total_itens']} total):",
                              "data | origem_destino | discriminacao | cat_transacao | competencia | obs_analista | guia | comprov | contrato"]
            for r in top_itens:
                bloco2_linhas.append(
                    f"{r['data']} | {r['origem_destino'] or ''} | {r['discriminacao'] or ''} | "
                    f"{r['cat_transacao'] or ''} | {r['competencia'] or ''} | "
                    f"{r['avaliacao_analista'] or '—'} | "
                    f"guia={r['avaliacao_guia'] or '—'} "
                    f"comprov={r['avaliacao_comprovante'] or '—'} "
                    f"contrato={r['avaliacao_contratos'] or '—'}"
                )
            blocos_db.append("\n".join(bloco2_linhas))

        # BLOCO 5 — Catálogo de glosas (categoricas) cruzado com tipos presentes no processo
        # Identifica quais tipos de glosa ocorrem neste processo via avaliacao_analista,
        # depois puxa só esses tipos com texto explicativo e fundamentos legais.
        cur.execute("""
            SELECT DISTINCT LOWER(avaliacao_analista) as obs
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s AND cat_avaliacao = 'Glosar'
              AND avaliacao_analista IS NOT NULL
        """, (numero_termo,))
        obs_set = {r['obs'] for r in cur.fetchall() if r['obs']}

        cur.execute("""
            SELECT g.id, g.glosa_nome, g.glosa_texto, g.glosa_inconsistencia,
                   array_agg(f.glosa_lei || ' — ' || f.glosa_artigo
                             ORDER BY f.id) FILTER (WHERE f.glosa_lei IS NOT NULL) AS fundamentos
            FROM categoricas.c_dac_glosas g
            LEFT JOIN categoricas.c_dac_glosas_fundamento f ON f.glosa_id = g.id
            GROUP BY g.id, g.glosa_nome, g.glosa_texto, g.glosa_inconsistencia
            ORDER BY g.id
        """)
        todos_tipos = cur.fetchall()

        # Filtra tipos relevantes: nome ou inconsistência mencionada nas observações do processo
        import re as _re2
        tipos_relevantes = []
        for t in todos_tipos:
            nome_l = (t['glosa_nome'] or '').lower()
            incons_l = (t['glosa_inconsistencia'] or '').lower()
            # Cruza palavras-chave do catálogo com as observações reais
            palavras_tipo = set(_re2.findall(r'\b\w{4,}\b', nome_l + ' ' + incons_l))
            if any(any(p in obs for p in palavras_tipo) for obs in obs_set):
                tipos_relevantes.append(t)

        # Se cruzamento não achou nada (obs muito genéricas), inclui catálogo completo
        if not tipos_relevantes:
            tipos_relevantes = todos_tipos

        if tipos_relevantes:
            linhas_cat = ["=== BLOCO 5 — CATÁLOGO DE TIPOS DE GLOSA (com fundamento legal) ===",
                          "Use estes textos e fundamentos ao redigir a resposta técnica de cada ponto.",
                          f"({len(tipos_relevantes)} tipos identificados como relevantes para este processo)"]
            for t in tipos_relevantes:
                linhas_cat.append(
                    f"\n[GLOSA: {t['glosa_nome']}]"
                    f"\nTexto relatório: {t['glosa_texto'] or '—'}"
                    f"\nInconsistência: {t['glosa_inconsistencia'] or '—'}"
                )
                if t['fundamentos']:
                    for fund in t['fundamentos']:
                        linhas_cat.append(f"  Base legal: {fund}")
            blocos_db.append("\n".join(linhas_cat))

        # BLOCO 3 — Inconsistências agregadas
        cur.execute("""
            SELECT nome_item, tipo_agregacao, campo1, campo2,
                   valor_previsto, valor_executado, diferenca, status
            FROM analises_pc.lista_inconsistencias_agregadas
            WHERE numero_termo = %s
            LIMIT 100
        """, (numero_termo,))
        incons_agr = cur.fetchall()

        # BLOCO 3b — Inconsistências simples (usa discriminacao como valor)
        cur.execute("""
            SELECT nome_item, data, discriminacao, competencia,
                   origem_destino, status
            FROM analises_pc.lista_inconsistencias
            WHERE numero_termo = %s
            LIMIT 100
        """, (numero_termo,))
        incons_simples = cur.fetchall()

        if incons_agr or incons_simples:
            linhas_i = []
            for r in incons_agr:
                linhas_i.append(
                    f"• [AGREGADA] {r['nome_item']} | tipo={r.get('tipo_agregacao','')} "
                    f"previsto={r.get('valor_previsto','')} executado={r.get('valor_executado','')} "
                    f"dif={r.get('diferenca','')} status={r.get('status','')}"
                )
            for r in incons_simples:
                linhas_i.append(
                    f"• [ITEM] {r['nome_item']} | data={r.get('data','')} "
                    f"discriminacao={r.get('discriminacao','')} "
                    f"competencia={r.get('competencia','')} "
                    f"favorecido={r.get('origem_destino','')} status={r.get('status','')}"
                )
            blocos_db.append(f"=== BLOCO 3 — INCONSISTÊNCIAS REGISTRADAS ===\n" + "\n".join(linhas_i))

        # BLOCOs 1a e 1b — Documentos PDF
        # 1a: docs de referência do poder público (edital, parecer, normativa) — sempre completos
        # 1b: manifestação da OSC — seleção semântica via FTS, só o que couber no orçamento
        MAX_REF_CHARS = 25_000   # orçamento para docs de referência (sempre incluídos)
        MAX_PDF_CHARS = 70_000   # orçamento para manifestação OSC (FTS-selecionada)
        DOC_TIPOS_REF = {'edital', 'parecer_juridico', 'normativa', 'documento_referencia'}

        bloco_ref = None   # BLOCO 1a
        bloco_pdf = None   # BLOCO 1b

        if doc_ids:
            from collections import defaultdict
            import re as _re

            # ── Descobre tipo de cada documento ──────────────────────────────────
            cur.execute("""
                SELECT id, tipo_documento FROM analises_pc_manifestacoes.documentos
                WHERE id = ANY(%s)
            """, (doc_ids,))
            tipos_docs = {r['id']: (r['tipo_documento'] or '') for r in cur.fetchall()}

            doc_ids_ref = [did for did in doc_ids if tipos_docs.get(did) in DOC_TIPOS_REF]
            doc_ids_osc = [did for did in doc_ids if tipos_docs.get(did) not in DOC_TIPOS_REF]

            # ── BLOCO 1a — Documentos de referência (sempre completos) ───────────
            if doc_ids_ref:
                cur.execute("""
                    SELECT p.documento_id, d.nome_arquivo, d.tipo_documento,
                           p.numero_pagina, p.texto_extraido
                    FROM analises_pc_manifestacoes.paginas p
                    JOIN analises_pc_manifestacoes.documentos d ON d.id = p.documento_id
                    WHERE p.documento_id = ANY(%s)
                      AND p.texto_extraido IS NOT NULL
                      AND length(trim(p.texto_extraido)) > 20
                    ORDER BY p.documento_id, p.numero_pagina
                """, (doc_ids_ref,))
                pags_ref = cur.fetchall()

                por_doc_ref = defaultdict(list)
                for pg in pags_ref:
                    por_doc_ref[(pg['documento_id'], pg['nome_arquivo'], pg['tipo_documento'])].append(pg)

                ref_linhas = [
                    "=== BLOCO 1a — DOCUMENTOS DE REFERÊNCIA (PODER PÚBLICO) ===",
                    "Use estes documentos para fundamentar a resposta técnica — cite dispositivos específicos ao refutar argumentos da OSC.",
                ]
                chars_ref = 0
                for (did, nome, tipo), pgs in por_doc_ref.items():
                    ref_linhas.append(f"\n[DOCUMENTO: {nome} | {tipo}]")
                    for pg in sorted(pgs, key=lambda x: x['numero_pagina']):
                        texto = pg['texto_extraido'] or ''
                        if chars_ref + len(texto) <= MAX_REF_CHARS:
                            ref_linhas.append(f"[Pág. {pg['numero_pagina']}] {texto}")
                            chars_ref += len(texto)
                        else:
                            resto = MAX_REF_CHARS - chars_ref
                            if resto > 200:
                                ref_linhas.append(f"[Pág. {pg['numero_pagina']}~] {texto[:resto]}…")
                            ref_linhas.append("[... demais páginas omitidas por limite de contexto]")
                            chars_ref = MAX_REF_CHARS
                            break
                bloco_ref = "\n".join(ref_linhas)
                totais_db['chars_ref'] = chars_ref

            # ── BLOCO 1b — Manifestação OSC (FTS semântico) ──────────────────────
            if doc_ids_osc:
                # Extrai termos das glosas do processo
                cur.execute("""
                    SELECT DISTINCT origem_destino, avaliacao_analista
                    FROM analises_pc.conc_extrato
                    WHERE numero_termo = %s AND cat_avaliacao = 'Glosar'
                      AND origem_destino IS NOT NULL
                    ORDER BY origem_destino
                    LIMIT 100
                """, (numero_termo,))
                glosas_termos = cur.fetchall()

                stop_pt = {'de','da','do','das','dos','em','no','na','nos','nas','para',
                           'com','por','que','se','não','e','a','o','um','uma','ao','às',
                           'os','as','sua','seu','como','mais','foi','ser','tem','também',
                           'muito','pela','pelo','entre','sobre','após','antes','quando'}
                termos = []
                for g in glosas_termos:
                    if g['origem_destino']:
                        termos.append(g['origem_destino'].strip())
                    if g['avaliacao_analista']:
                        palavras = _re.findall(r'\b\w{5,}\b', g['avaliacao_analista'])
                        termos.extend(w for w in palavras if w.lower() not in stop_pt)

                vistos = set()
                termos_unicos = []
                for t in termos:
                    tl = t.lower()
                    if tl not in vistos and len(tl) >= 3:
                        vistos.add(tl)
                        termos_unicos.append(t)
                    if len(termos_unicos) >= 60:
                        break

                texto_busca = ' '.join(termos_unicos)

                paginas_relevantes = []
                if texto_busca:
                    try:
                        cur.execute("""
                            SELECT p.documento_id, d.nome_arquivo, d.tipo_documento,
                                   p.numero_pagina, p.texto_extraido,
                                   ts_rank(p.ts_busca,
                                           websearch_to_tsquery('portuguese', %s)) AS rank
                            FROM analises_pc_manifestacoes.paginas p
                            JOIN analises_pc_manifestacoes.documentos d ON d.id = p.documento_id
                            WHERE p.documento_id = ANY(%s)
                              AND p.ts_busca @@ websearch_to_tsquery('portuguese', %s)
                              AND p.texto_extraido IS NOT NULL
                              AND length(trim(p.texto_extraido)) > 20
                            ORDER BY rank DESC
                            LIMIT 80
                        """, (texto_busca, doc_ids_osc, texto_busca))
                        paginas_relevantes = cur.fetchall()
                    except Exception:
                        paginas_relevantes = []

                cur.execute("""
                    SELECT p.documento_id, d.nome_arquivo, d.tipo_documento,
                           p.numero_pagina, p.texto_extraido, 0 AS rank
                    FROM analises_pc_manifestacoes.paginas p
                    JOIN analises_pc_manifestacoes.documentos d ON d.id = p.documento_id
                    WHERE p.documento_id = ANY(%s)
                      AND p.numero_pagina <= 5
                      AND p.texto_extraido IS NOT NULL
                      AND length(trim(p.texto_extraido)) > 20
                    ORDER BY p.documento_id, p.numero_pagina
                """, (doc_ids_osc,))
                primeiras = cur.fetchall()

                if not paginas_relevantes:
                    cur.execute("""
                        SELECT p.documento_id, d.nome_arquivo, d.tipo_documento,
                               p.numero_pagina, p.texto_extraido, 0 AS rank
                        FROM analises_pc_manifestacoes.paginas p
                        JOIN analises_pc_manifestacoes.documentos d ON d.id = p.documento_id
                        WHERE p.documento_id = ANY(%s)
                          AND p.texto_extraido IS NOT NULL
                          AND length(trim(p.texto_extraido)) > 20
                        ORDER BY p.documento_id, p.numero_pagina
                        LIMIT 60
                    """, (doc_ids_osc,))
                    paginas_relevantes = cur.fetchall()

                vistas = set()
                todas_pags = []
                for pg in primeiras:
                    key = (pg['documento_id'], pg['numero_pagina'])
                    if key not in vistas:
                        vistas.add(key)
                        todas_pags.append(dict(pg, is_intro=True))
                for pg in paginas_relevantes:
                    key = (pg['documento_id'], pg['numero_pagina'])
                    if key not in vistas:
                        vistas.add(key)
                        todas_pags.append(dict(pg, is_intro=False))

                total_chars_real = sum(len(pg['texto_extraido'] or '') for pg in todas_pags)
                totais_db['total_chars_pdf'] = total_chars_real
                totais_db['docs_selecionados'] = len(set(pg['documento_id'] for pg in todas_pags))
                totais_db['paginas_selecionadas'] = len(todas_pags)
                totais_db['termos_busca'] = len(termos_unicos)

                por_doc = defaultdict(list)
                for pg in todas_pags:
                    por_doc[(pg['documento_id'], pg['nome_arquivo'], pg['tipo_documento'])].append(pg)

                pdf_linhas = [
                    "=== BLOCO 1b — MANIFESTAÇÃO DA OSC (seleção semântica) ===",
                    f"Termos de busca extraídos das glosas do processo: {len(termos_unicos)} termos",
                    f"Páginas selecionadas: {len(todas_pags)} (★ = alta relevância, ○ = introdução/contexto)",
                ]

                chars_usados = 0
                for (did, nome, tipo), pgs in por_doc.items():
                    pgs_sorted = sorted(pgs, key=lambda x: x['numero_pagina'])
                    grupo = [f"\n[DOCUMENTO: {nome} | {tipo}]"]
                    for pg in pgs_sorted:
                        texto = pg['texto_extraido'] or ''
                        if chars_usados >= MAX_PDF_CHARS:
                            grupo.append("[... limite de contexto atingido — demais páginas omitidas]")
                            break
                        if chars_usados + len(texto) <= MAX_PDF_CHARS:
                            marca = '○' if pg.get('is_intro') else '★'
                            grupo.append(f"[Pág. {pg['numero_pagina']}{marca}] {texto}")
                            chars_usados += len(texto)
                        else:
                            resto = MAX_PDF_CHARS - chars_usados
                            if resto > 200:
                                grupo.append(f"[Pág. {pg['numero_pagina']}~] {texto[:resto]}…")
                                chars_usados = MAX_PDF_CHARS
                            break
                    pdf_linhas.append("\n".join(grupo))

                bloco_pdf = "\n".join(pdf_linhas)

            # totais para casos onde só há docs de referência (sem OSC)
            if 'total_chars_pdf' not in totais_db:
                totais_db.setdefault('total_chars_pdf', 0)
                totais_db.setdefault('termos_busca', 0)

    finally:
        cur.close()
        conn.close()

    # Ordem final: DB data primeiro, docs referência (1a), manifestação OSC (1b) por último.
    # O truncamento em _executar_analise_ia só cortará o bloco_pdf (OSC).
    partes_contexto = blocos_db[:]
    if bloco_ref:
        partes_contexto.append(bloco_ref)
    if bloco_pdf:
        partes_contexto.append(bloco_pdf)

    return "\n\n".join(partes_contexto), totais_db


def _executar_analise_ia(tid: str, numero_termo: str, meses_analisados: str,
                          doc_ids: list, foco_personalizado: str):
    """Thread de background: monta contexto, chama Deepseek, armazena resultado."""
    DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'
    DEEPSEEK_MODEL = 'deepseek-chat'

    try:
        _upd_analise(tid, pct=10, label='Consultando dados do banco…')
        contexto, totais_db = _montar_contexto_db(numero_termo, meses_analisados, doc_ids)

        _upd_analise(tid, pct=35, label='Preparando prompt para Deepseek…')
        sistema = _carregar_prompt_sistema()

        instrucao_foco = (
            f"\n\n## Foco Específico Solicitado pelo Analista\n{foco_personalizado.strip()}"
            if foco_personalizado and foco_personalizado.strip()
            else ""
        )

        prompt_usuario = (
            f"Termo de Parceria: {numero_termo}\n"
            f"Período Analisado: {meses_analisados}\n"
            f"{instrucao_foco}\n\n"
            f"{contexto}"
        )

        # Trunca apenas o excedente — como DB data vem primeiro e PDF por último,
        # o corte afeta somente o texto do PDF, nunca os dados de conciliação.
        MAX_CHARS = 120_000
        if len(prompt_usuario) > MAX_CHARS:
            prompt_usuario = prompt_usuario[:MAX_CHARS] + "\n\n[TEXTO DO PDF TRUNCADO — DADOS DE CONCILIAÇÃO COMPLETOS ACIMA]"

        _upd_analise(tid, pct=40, label=f'Chamando Deepseek ({len(prompt_usuario):,} chars)…')

        api_key = os.environ.get('DEEPSEEK_API_KEY', '')
        if not api_key:
            raise ValueError('DEEPSEEK_API_KEY não configurada no .env')

        resp = requests.post(
            DEEPSEEK_URL,
            headers={'Authorization': f'Bearer {api_key}',
                     'Content-Type': 'application/json'},
            json={
                'model': DEEPSEEK_MODEL,
                'messages': [
                    {'role': 'system', 'content': sistema},
                    {'role': 'user',   'content': prompt_usuario},
                ],
                'response_format': {'type': 'json_object'},
                'temperature': 0.2,
                'max_tokens': 8192,
            },
            timeout=240,
        )

        _upd_analise(tid, pct=85, label='Processando resposta…')
        resp.raise_for_status()

        conteudo = resp.json()['choices'][0]['message']['content']
        uso = resp.json().get('usage', {})
        print(f"[ANALISE IA] tokens prompt={uso.get('prompt_tokens','?')} "
              f"completion={uso.get('completion_tokens','?')}")

        # Parse robusto
        try:
            resultado = _json.loads(conteudo)
        except _json.JSONDecodeError:
            import re
            m = re.search(r'\{.*\}', conteudo, re.DOTALL)
            resultado = _json.loads(m.group(0)) if m else {'erro_parse': conteudo[:500]}

        # Injeta totais reais do banco — não depende da IA para esses números.
        # valor_total_glosado = total real do banco (cat_avaliacao='Glosar')
        # valor_total_aceito_recurso = o que a IA recomenda aceitar (calculado pela IA)
        # valor_total_mantido_glosa = glosado - aceito (recalculado aqui com consistência)
        if totais_db.get('total_glosado') is not None:
            total_real = totais_db['total_glosado']
            resultado['valor_total_glosado'] = f"R$ {total_real:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            resultado['_fonte_total_glosado'] = 'banco_de_dados'
            resultado['_total_taxas_bancarias'] = f"R$ {totais_db.get('total_taxas', 0):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

            # Recalcula mantido se a IA forneceu valor aceito
            aceito_str = resultado.get('valor_total_aceito_recurso', '')
            if aceito_str:
                import re as _re
                nums = _re.findall(r'[\d]+[.,][\d]+', aceito_str.replace('.', '').replace(',', '.'))
                if nums:
                    try:
                        aceito_val = float(nums[0])
                        mantido_val = max(0.0, total_real - aceito_val)
                        resultado['valor_total_mantido_glosa'] = f"R$ {mantido_val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    except (ValueError, IndexError):
                        pass

        # Salva resultado no banco de dados
        try:
            import psycopg2 as _pg2
            import json as _json2
            import re as _re3
            from config import DB_CONFIG

            def _parse_valor_num(s):
                if not s:
                    return None
                nums = _re3.findall(r'\d+[\d.,]*', str(s).replace('.', '').replace(',', '.'))
                try:
                    return float(nums[0]) if nums else None
                except (ValueError, IndexError):
                    return None

            conn_save = _pg2.connect(**DB_CONFIG)
            cur_save = conn_save.cursor()
            cur_save.execute("""
                INSERT INTO analises_pc_manifestacoes.analises_ia
                    (numero_termo, meses_analisados, doc_ids, foco_personalizado,
                     recomendacao_geral, valor_total_glosado, valor_total_aceito,
                     valor_total_mantido, resultado, modelo_ia,
                     prompt_tokens, completion_tokens)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                numero_termo,
                meses_analisados,
                doc_ids,
                foco_personalizado,
                resultado.get('recomendacao_geral'),
                _parse_valor_num(resultado.get('valor_total_glosado')),
                _parse_valor_num(resultado.get('valor_total_aceito_recurso')),
                _parse_valor_num(resultado.get('valor_total_mantido_glosa')),
                _json2.dumps(resultado, ensure_ascii=False),
                DEEPSEEK_MODEL,
                uso.get('prompt_tokens'),
                uso.get('completion_tokens'),
            ))
            conn_save.commit()
            cur_save.close()
            conn_save.close()
            print(f"[ANALISE IA] Resultado salvo no banco para termo={numero_termo}")
        except Exception as e_save:
            print(f"[ANALISE IA] Erro ao salvar no banco: {e_save}")

        _upd_analise(tid, status='done', pct=100, label='Concluído',
                     resultado=resultado)

    except Exception as exc:
        print(f"[ANALISE IA ERRO] tid={tid}: {exc}")
        traceback.print_exc()
        _upd_analise(tid, status='erro', pct=100,
                     label='Erro', erro=str(exc))


@analises_pc_bp.route('/api/manifestacoes/estimativa', methods=['POST'])
@login_required
@requires_access('analises')
def estimativa_contexto():
    """Retorna estimativa de tamanho do contexto antes de iniciar a análise."""
    data = request.get_json(silent=True) or {}
    numero_termo = (data.get('numero_termo') or '').strip()
    doc_ids = [int(i) for i in (data.get('doc_ids') or []) if str(i).isdigit()]

    if not numero_termo:
        return jsonify({'error': 'Número do termo não informado'}), 400

    import psycopg2, psycopg2.extras
    from config import DB_CONFIG
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT d.id, d.nome_arquivo, d.tipo_documento, d.total_paginas,
                   COALESCE(SUM(length(COALESCE(p.texto_extraido,''))), 0) as chars_texto
            FROM analises_pc_manifestacoes.documentos d
            LEFT JOIN analises_pc_manifestacoes.paginas p ON p.documento_id = d.id
            WHERE d.numero_termo = %s AND d.id = ANY(%s)
            GROUP BY d.id, d.nome_arquivo, d.tipo_documento, d.total_paginas
        """, (numero_termo, doc_ids))
        docs = cur.fetchall()

        cur.execute("""
            SELECT COUNT(*) as qtd_glosas, SUM(ABS(discriminacao)) as total_glosas
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s AND cat_avaliacao = 'Glosar'
        """, (numero_termo,))
        glosas = cur.fetchone()
    finally:
        cur.close()
        conn.close()

    total_pdf = sum(d['chars_texto'] for d in docs)
    MAX_PDF = 70_000
    MAX_TOTAL = 120_000
    db_estimado = 45_000  # estimativa conservadora dos blocos do banco

    return jsonify({
        'docs': [{'id': d['id'], 'nome': d['nome_arquivo'], 'tipo': d['tipo_documento'],
                  'paginas': d['total_paginas'], 'chars': d['chars_texto']} for d in docs],
        'total_chars_pdf': total_pdf,
        'budget_pdf': MAX_PDF,
        'budget_total': MAX_TOTAL,
        'db_estimado': db_estimado,
        'pdf_truncado': total_pdf > MAX_PDF,
        'pct_pdf_lido': min(100, round(MAX_PDF / total_pdf * 100)) if total_pdf else 100,
        'qtd_glosas': glosas['qtd_glosas'] if glosas else 0,
        'total_glosas': float(glosas['total_glosas'] or 0) if glosas else 0,
    })


@analises_pc_bp.route('/api/manifestacoes/analisar', methods=['POST'])
@login_required
@requires_access('analises')
def analisar_manifestacao():
    """Inicia análise Deepseek em background. Retorna task_id para polling."""
    data = request.get_json(silent=True) or {}
    numero_termo = (data.get('numero_termo') or '').strip()
    meses_analisados = (data.get('meses_analisados') or '').strip()
    doc_ids = [int(i) for i in (data.get('doc_ids') or []) if str(i).isdigit()]
    foco = data.get('foco_personalizado', '')

    if not numero_termo:
        return jsonify({'error': 'Número do termo não informado'}), 400

    tid = _nova_analise_task()
    threading.Thread(
        target=_executar_analise_ia,
        args=(tid, numero_termo, meses_analisados, doc_ids, foco),
        daemon=True
    ).start()

    return jsonify({'task_id': tid})


@analises_pc_bp.route('/api/manifestacoes/historico_ia', methods=['GET'])
@login_required
@requires_access('analises')
def historico_analises_ia():
    """Lista análises IA salvas para um termo."""
    numero_termo = request.args.get('numero_termo', '').strip()
    if not numero_termo:
        return jsonify({'error': 'numero_termo obrigatório'}), 400

    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            SELECT id, numero_termo, recomendacao_geral,
                   valor_total_glosado, valor_total_aceito, valor_total_mantido,
                   modelo_ia, prompt_tokens, completion_tokens, criado_em, resultado
            FROM analises_pc_manifestacoes.analises_ia
            WHERE numero_termo = %s
            ORDER BY criado_em DESC
            LIMIT 10
        """, (numero_termo,))
        rows = cur.fetchall()
        cur.close()
        resultado = []
        for r in rows:
            d = dict(r)
            d['criado_em'] = d['criado_em'].strftime('%d/%m/%Y %H:%M') if d.get('criado_em') else ''
            resultado.append(d)
        return jsonify({'analises': resultado})
    except Exception as e:
        cur.close()
        return jsonify({'error': str(e)}), 500


@analises_pc_bp.route('/api/manifestacoes/historico_ia/<int:analise_id>', methods=['DELETE'])
@login_required
@requires_access('analises')
def excluir_analise_ia(analise_id):
    """Exclui uma análise IA pelo id."""
    import psycopg2 as _pg2
    from config import DB_CONFIG
    try:
        conn = _pg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM analises_pc_manifestacoes.analises_ia WHERE id = %s RETURNING id",
            (analise_id,)
        )
        deleted = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        if not deleted:
            return jsonify({'erro': 'Análise não encontrada'}), 404
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'erro': str(e)}), 500


@analises_pc_bp.route('/api/manifestacoes/tarefa/<task_id>', methods=['GET'])
@login_required
def status_analise_ia(task_id):
    """Retorna estado atual de uma tarefa de análise IA."""
    with _analises_ia_lock:
        tarefa = dict(_analises_ia.get(task_id, {}))
    if not tarefa:
        return jsonify({'error': 'Tarefa não encontrada ou expirada'}), 404
    return jsonify(tarefa)


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
            FROM categoricas.c_geral_modelo_textos
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
    """Lista arquivos disponíveis na pasta modelos/ (ou Supabase)"""
    if session.get('tipo_usuario') != 'Agente Público':
        return jsonify({'error': 'Acesso negado'}), 403
    
    try:
        arquivos = storage.list_files('Modelos')
        arquivos_filtrados = [f for f in arquivos if f.endswith(('.pdf', '.xlsx', '.xls', '.docx', '.doc'))]
        return jsonify({'arquivos': sorted(arquivos_filtrados)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def verificar_ratificacao(cursor, numero_termo, nome_item):
    """
    Verifica se uma inconsistência já foi ratificada em qualquer das 3 tabelas.
    Retorna um dicionário com: {'ratificada': bool, 'status': str}
    OTIMIZADO: Uma única query com UNION ALL em vez de 3 queries sequenciais.
    """
    cursor.execute("""
        SELECT status FROM analises_pc.lista_inconsistencias
        WHERE numero_termo = %s AND nome_item = %s
        
        UNION ALL
        
        SELECT status FROM analises_pc.lista_inconsistencias_agregadas
        WHERE numero_termo = %s AND nome_item = %s
        
        UNION ALL
        
        SELECT status FROM analises_pc.lista_inconsistencias_globais
        WHERE numero_termo = %s AND nome_item = %s
        
        LIMIT 1
    """, (numero_termo, nome_item, numero_termo, nome_item, numero_termo, nome_item))
    
    resultado = cursor.fetchone()
    if resultado:
        return {'ratificada': True, 'status': resultado['status']}
    
    # Não encontrado em nenhuma tabela
    return {'ratificada': False, 'status': None}


def agrupar_cards_compostos(inconsistencias):
    """
    DESABILITADO: Retorna lista de inconsistências sem agrupamento.
    Cada inconsistência é mantida individualmente.
    """
    # Retornar lista sem modificações
    return inconsistencias


@analises_pc_bp.route('/conc_inconsistencias')
def conc_inconsistencias():
    """Página de Relatório de Inconsistências da Conciliação Bancária"""
    print("[DEBUG] ========================================")
    print("[DEBUG] Iniciando rota /conc_inconsistencias")
    print("[DEBUG] ========================================")
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        print("[DEBUG] Buscando modelo de texto...")
        # Buscar modelo de texto
        cur.execute("""
            SELECT titulo_texto, modelo_texto
            FROM categoricas.c_geral_modelo_textos
            WHERE titulo_texto = 'Análise de Contas: Relatório de Inconsistências'
            LIMIT 1
        """)
        
        modelo = cur.fetchone()
        print(f"[DEBUG] Modelo encontrado: {modelo is not None}")
        cur.close()
        
        if not modelo:
            print("[DEBUG] Modelo não encontrado, usando placeholder")
            # Se não encontrar, criar placeholder
            modelo = {
                'titulo_texto': 'Análise de Contas: Relatório de Inconsistências',
                'modelo_texto': '<p>Modelo de texto ainda não cadastrado. Acesse Modelos de Texto para criar.</p>'
            }
        
        print("[DEBUG] Renderizando template...")
        result = render_template('analises_pc/conc_inconsistencias.html', modelo=modelo)
        print("[DEBUG] ✅ Template renderizado com sucesso")
        return result
    
    except Exception as e:
        cur.close()
        print(f"[ERRO] conc_inconsistencias: {str(e)}")
        return render_template('analises_pc/conc_inconsistencias.html', 
                             modelo={'titulo_texto': 'Erro', 'modelo_texto': f'<p>Erro ao carregar modelo: {str(e)}</p>'})


@analises_pc_bp.route('/api/identificar-inconsistencias/<path:numero_termo>')
def identificar_inconsistencias(numero_termo):
    """
    Identifica inconsistências automaticamente para um termo específico.
    Retorna lista de inconsistências com transações identificadas.
    
    Nota: Usa <path:numero_termo> para aceitar barras (/) no número do termo.
    """
    print(f"[DEBUG] ===== INÍCIO identificar_inconsistencias =====")
    print(f"[DEBUG] Termo recebido: '{numero_termo}'")
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        inconsistencias_identificadas = []
        
        # ========================================
        # OTIMIZAÇÃO: Buscar TODOS os modelos de texto de uma vez (1 query em vez de 26)
        # ========================================
        print("[DEBUG] Buscando modelos de texto (otimizado)...")
        cur.execute("""
            SELECT id, nome_item, modelo_texto, solucao, ordem
            FROM categoricas.c_dac_modelo_textos_inconsistencias
            WHERE id IN (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 25, 26)
            ORDER BY ordem
        """)
        modelos_cache = {row['id']: row for row in cur.fetchall()}
        print(f"[DEBUG] {len(modelos_cache)} modelos carregados em cache")
        
        # ========================================
        # 1. APRESENTAÇÃO DE TODAS AS GUIAS
        # ========================================
        print("[DEBUG] Card 1: Iniciando verificação - Apresentação de todas as guias")
        # Verifica se TODOS os registros PREENCHIDOS (desconsiderando vazios/null) têm avaliacao_guia = 'Não apresentada'
        cur.execute("""
            SELECT 
                COUNT(*) as total_preenchidos,
                COALESCE(SUM(CASE WHEN avaliacao_guia = 'Não apresentada' THEN 1 ELSE 0 END), 0) as nao_apresentadas
            FROM analises_pc.conc_analise ca
            INNER JOIN analises_pc.conc_extrato ce ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND ca.avaliacao_guia IS NOT NULL
              AND ca.avaliacao_guia != ''
        """, (numero_termo,))
        
        resultado_guias = cur.fetchone()
        
        # Só identifica inconsistência se:
        # 1. Há registros preenchidos (total_preenchidos > 0)
        # 2. TODOS os preenchidos são "Não apresentada"
        if resultado_guias and resultado_guias['total_preenchidos'] > 0:
            if resultado_guias['total_preenchidos'] == resultado_guias['nao_apresentadas']:
                # TODOS os registros preenchidos são "Não apresentada" - inconsistência identificada!
                
                # Buscar modelo de texto do cache (otimizado)
                modelo = modelos_cache.get(8)
                
                if modelo:
                    # Buscar transações relacionadas
                    cur.execute("""
                        SELECT 
                            ce.id,
                            ce.indice,
                            ce.data,
                            ce.credito,
                            ce.debito,
                            ce.discriminacao,
                            ce.cat_transacao,
                            ce.competencia,
                            ce.origem_destino
                        FROM analises_pc.conc_extrato ce
                        INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                        WHERE ce.numero_termo = %s
                          AND ca.avaliacao_guia = 'Não apresentada'
                        ORDER BY ce.data, ce.indice
                    """, (numero_termo,))
                    
                    transacoes = cur.fetchall()
                    
                    inconsistencias_identificadas.append({
                        'id': modelo['id'],
                        'nome_item': modelo['nome_item'],
                        'modelo_texto': modelo['modelo_texto'],
                        'solucao': modelo['solucao'],
                        'transacoes': transacoes,
                        'ordem': modelo.get('ordem', 999)
                    })
        
        # ========================================
        # 2. TAXAS BANCÁRIAS
        # ========================================
        print("[DEBUG] Card 2: Iniciando verificação - Taxas Bancárias")
        # Verifica se (Soma de Taxas Bancárias) - (Soma de Devoluções) > 0
        cur.execute("""
            SELECT 
                ce.id,
                ce.indice,
                ce.data,
                ce.credito,
                ce.debito,
                ce.discriminacao,
                ce.cat_transacao,
                ce.competencia,
                ce.origem_destino
            FROM analises_pc.conc_extrato ce
            WHERE ce.numero_termo = %s
              AND ce.cat_transacao IN ('Taxas Bancárias', 'Devolução de Taxas Bancárias')
            ORDER BY ce.data, ce.indice
        """, (numero_termo,))
        
        transacoes_taxas = cur.fetchall()
        
        if transacoes_taxas:
            # Calcular saldo líquido: Taxas - Devoluções
            total_taxas = sum(
                float(t['discriminacao'] or 0) 
                for t in transacoes_taxas 
                if t['cat_transacao'] == 'Taxas Bancárias'
            )
            total_devolucoes = sum(
                float(t['discriminacao'] or 0) 
                for t in transacoes_taxas 
                if t['cat_transacao'] == 'Devolução de Taxas Bancárias'
            )
            
            saldo_taxas = total_taxas - total_devolucoes
            
            # Se saldo > 0, há inconsistência
            if saldo_taxas > 0:
                # Buscar modelo de texto do cache (otimizado)
                modelo_taxas = modelos_cache.get(1)
                
                if modelo_taxas:
                    # Formatar valor para moeda brasileira
                    valor_formatado = f"R$ {saldo_taxas:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    
                    # Substituir valor_taxa_usuario no modelo
                    texto_formatado = modelo_taxas['modelo_texto'].replace('valor_taxa_usuario', valor_formatado)
                    
                    inconsistencias_identificadas.append({
                        'id': modelo_taxas['id'],
                        'nome_item': modelo_taxas['nome_item'],
                        'modelo_texto': texto_formatado,
                        'solucao': modelo_taxas['solucao'],
                        'transacoes': [],  # Taxas Bancárias não mostra tabela de transações
                        'valor_calculado': saldo_taxas,
                        'ordem': modelo_taxas.get('ordem', 999),
                        'mostrar_tabela': False  # Flag para ocultar tabela no frontend
                    })
        
        # ========================================
        # 3. JUROS E MULTAS
        # ========================================
        print("[DEBUG] Card 3: Iniciando verificação - Juros e Multas")
        # Verifica se (Soma de Juros e/ou Multas) - (Soma de Devoluções) > 0
        cur.execute("""
            SELECT 
                ce.id,
                ce.indice,
                ce.data,
                ce.credito,
                ce.debito,
                ce.discriminacao,
                ce.cat_transacao,
                ce.competencia,
                ce.origem_destino
            FROM analises_pc.conc_extrato ce
            WHERE ce.numero_termo = %s
              AND ce.cat_transacao IN ('Juros e/ou Multas', 'Devolução de Juros e/ou Multas')
            ORDER BY ce.data, ce.indice
        """, (numero_termo,))
        
        transacoes_juros = cur.fetchall()
        
        if transacoes_juros:
            # Calcular saldo líquido: Juros - Devoluções
            total_juros = sum(
                float(t['discriminacao'] or 0) 
                for t in transacoes_juros 
                if t['cat_transacao'] == 'Juros e/ou Multas'
            )
            total_devolucoes_juros = sum(
                float(t['discriminacao'] or 0) 
                for t in transacoes_juros 
                if t['cat_transacao'] == 'Devolução de Juros e/ou Multas'
            )
            
            saldo_juros = total_juros - total_devolucoes_juros
            
            # Se saldo > 0, há inconsistência
            if saldo_juros > 0:
                # Buscar modelo de texto do cache (otimizado)
                modelo_juros = modelos_cache.get(2)
                
                if modelo_juros:
                    # Formatar valor para moeda brasileira
                    valor_formatado = f"R$ {saldo_juros:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    
                    # Substituir valor_juros_usuario no modelo
                    texto_formatado = modelo_juros['modelo_texto'].replace('valor_juros_usuario', valor_formatado)
                    
                    inconsistencias_identificadas.append({
                        'id': modelo_juros['id'],
                        'nome_item': modelo_juros['nome_item'],
                        'modelo_texto': texto_formatado,
                        'solucao': modelo_juros['solucao'],
                        'transacoes': transacoes_juros,
                        'valor_calculado': saldo_juros,
                        'ordem': modelo_juros.get('ordem', 999)
                    })
        
        # ========================================
        # 4. NÃO USO DA CONTA ESPECÍFICA
        # ========================================
        print("[DEBUG] Card 4: Iniciando verificação - Não uso da conta específica")
        # Verifica se a conta de execução difere da conta prevista no termo
        # Buscar conta prevista em public.parcerias
        cur.execute("""
            SELECT conta
            FROM public.parcerias
            WHERE numero_termo = %s
            LIMIT 1
        """, (numero_termo,))
        
        parceria = cur.fetchone()
        
        if parceria and parceria['conta']:
            conta_prevista = parceria['conta'].strip()
            
            # Buscar conta de execução em analises_pc.conc_banco
            cur.execute("""
                SELECT conta_execucao
                FROM analises_pc.conc_banco
                WHERE numero_termo = %s
                LIMIT 1
            """, (numero_termo,))
            
            conc_banco = cur.fetchone()
            
            if conc_banco and conc_banco['conta_execucao']:
                conta_executada = conc_banco['conta_execucao'].strip()
                
                # Se as contas forem divergentes, há inconsistência
                if conta_prevista != conta_executada:
                    # Buscar modelo de texto do cache (otimizado)
                    modelo_conta = modelos_cache.get(3)
                    
                    if modelo_conta:
                        # Substituir placeholders
                        texto_formatado = modelo_conta['modelo_texto']
                        texto_formatado = texto_formatado.replace('conta_prevista', conta_prevista)
                        texto_formatado = texto_formatado.replace('conta_executada', conta_executada)
                        
                        # Não buscar transações - apenas descrição
                        inconsistencias_identificadas.append({
                            'id': modelo_conta['id'],
                            'nome_item': modelo_conta['nome_item'],
                            'modelo_texto': texto_formatado,
                            'solucao': modelo_conta['solucao'],
                            'transacoes': [],  # Vazio - não mostrar tabela
                            'conta_prevista': conta_prevista,
                            'conta_executada': conta_executada,
                            'ordem': modelo_conta.get('ordem', 999)
                        })
        
        # ========================================
        # 5. RESTITUIÇÃO FINAL
        # ========================================
        print("[DEBUG] Card 5: Iniciando verificação - Restituição Final")
        # Calcular valor residual (Saldos não Utilizados Remanescentes)
        # Fórmula: Valor Total Projeto - Executado Aprovado - Despesas Glosa
        
        # Buscar dados necessários para o cálculo
        cur.execute("""
            SELECT total_pago, contrapartida
            FROM public.parcerias
            WHERE numero_termo = %s
            LIMIT 1
        """, (numero_termo,))
        parceria_rest = cur.fetchone()
        
        if parceria_rest:
            # Calcular rendimentos (bruto por padrão)
            cur.execute("""
                SELECT SUM(discriminacao) as total
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s
                  AND cat_transacao = 'Rendimentos'
            """, (numero_termo,))
            rendimentos_rest = cur.fetchone()
            total_rendimentos = float(rendimentos_rest['total'] or 0) if rendimentos_rest else 0
            
            # Valor executado e aprovado - MESMA LÓGICA DO CONC_RELATORIO
            # Usar ABS() e verificar se categoria existe em parcerias_despesas
            cur.execute("""
                SELECT COALESCE(SUM(ABS(ce.discriminacao)), 0) as total
                FROM analises_pc.conc_extrato ce
                WHERE ce.numero_termo = %s 
                    AND ce.cat_avaliacao = 'Avaliado'
                    AND ce.discriminacao IS NOT NULL
                    AND EXISTS (
                        SELECT 1 
                        FROM public.parcerias_despesas pd
                        WHERE LOWER(pd.categoria_despesa) = LOWER(ce.cat_transacao)
                            AND pd.numero_termo = ce.numero_termo
                    )
            """, (numero_termo,))
            exec_aprovado = cur.fetchone()
            valor_exec_aprovado = float(exec_aprovado['total'] or 0) if exec_aprovado else 0
            
            # Despesas passíveis de glosa - USAR ABS() para consistência
            cur.execute("""
                SELECT COALESCE(SUM(ABS(discriminacao)), 0) as total
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s 
                    AND cat_avaliacao = 'Glosar'
                    AND LOWER(cat_transacao) != 'taxas bancárias'
                    AND discriminacao IS NOT NULL
            """, (numero_termo,))
            glosas_rest = cur.fetchone()
            despesas_glosa = float(glosas_rest['total'] or 0) if glosas_rest else 0
            
            # Taxas Bancárias não Devolvidas
            cur.execute("""
                SELECT 
                    COALESCE(SUM(CASE WHEN LOWER(cat_transacao) = 'taxas bancárias' THEN ABS(discriminacao) ELSE 0 END), 0) as total_taxas,
                    COALESCE(SUM(CASE WHEN LOWER(cat_transacao) = 'devolução de taxas bancárias' THEN ABS(discriminacao) ELSE 0 END), 0) as total_devolucao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s AND discriminacao IS NOT NULL
            """, (numero_termo,))
            taxas_data_rest = cur.fetchone()
            taxas_bancarias_rest = float(taxas_data_rest['total_taxas'] or 0) if taxas_data_rest else 0
            devolucao_taxas_rest = float(taxas_data_rest['total_devolucao'] or 0) if taxas_data_rest else 0
            taxas_nao_devolvidas_rest = taxas_bancarias_rest - devolucao_taxas_rest
            
            # Calcular Valor Total do Projeto
            contrapartida_rest = float(parceria_rest['contrapartida'] or 0)
            valor_total_projeto_rest = float(parceria_rest['total_pago']) + total_rendimentos + contrapartida_rest
            
            # Saldos não Utilizados Remanescentes = Valor Total - Executado - Glosas - Taxas não Devolvidas
            saldos_remanescentes = valor_total_projeto_rest - valor_exec_aprovado - despesas_glosa - taxas_nao_devolvidas_rest
            
            # Se houver saldo positivo, identificar inconsistência
            if saldos_remanescentes > 0:
                # Buscar modelo de texto do cache (otimizado)
                modelo_rest = modelos_cache.get(4)
                
                if modelo_rest:
                    # Formatar valor para moeda brasileira
                    valor_formatado = f"R$ {saldos_remanescentes:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    
                    # Substituir placeholder
                    texto_formatado = modelo_rest['modelo_texto'].replace('valor_residual_usuario', valor_formatado)
                    
                    inconsistencias_identificadas.append({
                        'id': modelo_rest['id'],
                        'nome_item': modelo_rest['nome_item'],
                        'modelo_texto': texto_formatado,
                        'solucao': modelo_rest['solucao'],
                        'transacoes': [],  # Sem tabela de transações
                        'valor_calculado': saldos_remanescentes,
                        'ordem': modelo_rest.get('ordem', 999)
                    })
        
        # ========================================
        # 6. APRESENTAR TODOS OS CONTRATOS
        # ========================================
        print("[DEBUG] Card 6: Iniciando verificação - Apresentar todos os Contratos")
        # Verifica se há transações com contratos não apresentados
        # Condição: avaliacao_contratos = 'Não apresentado'
        
        cur.execute("""
            SELECT 
                COUNT(*) as total_preenchidos,
                COALESCE(SUM(CASE WHEN ca.avaliacao_contratos = 'Não apresentado' THEN 1 ELSE 0 END), 0) as nao_apresentados
            FROM analises_pc.conc_analise ca
            INNER JOIN analises_pc.conc_extrato ce ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND ca.avaliacao_contratos IS NOT NULL
              AND ca.avaliacao_contratos != ''
        """, (numero_termo,))
        
        resultado_contratos = cur.fetchone()
        
        # Só identifica inconsistência se há registros com "Não apresentado"
        if resultado_contratos and resultado_contratos['nao_apresentados'] > 0:
            # Buscar modelo de texto do cache (otimizado)
            modelo_contratos = modelos_cache.get(5)
            
            if modelo_contratos:
                # Buscar transações relacionadas
                cur.execute("""
                    SELECT 
                        ce.id,
                        ce.indice,
                        ce.data,
                        ce.credito,
                        ce.debito,
                        ce.discriminacao,
                        ce.cat_transacao,
                        ce.competencia,
                        ce.origem_destino
                    FROM analises_pc.conc_extrato ce
                    INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                    WHERE ce.numero_termo = %s
                      AND ca.avaliacao_contratos = 'Não apresentado'
                    ORDER BY ce.data, ce.indice
                """, (numero_termo,))
                
                transacoes_contratos = cur.fetchall()
                
                inconsistencias_identificadas.append({
                    'id': modelo_contratos['id'],
                    'nome_item': modelo_contratos['nome_item'],
                    'modelo_texto': modelo_contratos['modelo_texto'],
                    'solucao': modelo_contratos['solucao'],
                    'transacoes': transacoes_contratos,
                    'ordem': modelo_contratos.get('ordem', 999)
                })
        
        # ========================================
        # 7. CRÉDITOS NÃO JUSTIFICADOS
        # ========================================
        print("[DEBUG] Card 7: Iniciando verificação - Créditos não justificados")
        # Verifica transações com crédito > 0 e cat_avaliacao != 'Avaliado'
        cur.execute("""
            SELECT 
                ce.id,
                ce.indice,
                ce.data,
                ce.credito,
                ce.debito,
                ce.discriminacao,
                ce.cat_transacao,
                ce.competencia,
                ce.origem_destino
            FROM analises_pc.conc_extrato ce
            WHERE ce.numero_termo = %s
              AND ce.credito > 0
              AND (ce.cat_avaliacao IS NULL OR ce.cat_avaliacao != 'Avaliado')
            ORDER BY ce.data, ce.indice
        """, (numero_termo,))
        
        transacoes_creditos = cur.fetchall()
        
        if transacoes_creditos:
            # Buscar modelo de texto do cache (otimizado)
            modelo_creditos = modelos_cache.get(6)
            
            if modelo_creditos:
                inconsistencias_identificadas.append({
                    'id': modelo_creditos['id'],
                    'nome_item': modelo_creditos['nome_item'],
                    'modelo_texto': modelo_creditos['modelo_texto'],
                    'solucao': modelo_creditos['solucao'],
                    'transacoes': transacoes_creditos,
                    'ordem': modelo_creditos.get('ordem', 999)
                })
        
        # ========================================
        # 8. DESPESAS NÃO PREVISTAS
        # ========================================
        print("[DEBUG] Card 8: Iniciando verificação - Despesas não previstas")
        # Verifica transações categorizadas como "Débitos Indevidos"
        cur.execute("""
            SELECT 
                ce.id,
                ce.indice,
                ce.data,
                ce.credito,
                ce.debito,
                ce.discriminacao,
                ce.cat_transacao,
                ce.competencia,
                ce.origem_destino
            FROM analises_pc.conc_extrato ce
            WHERE ce.numero_termo = %s
              AND ce.cat_transacao = 'Débitos Indevidos'
            ORDER BY ce.data, ce.indice
        """, (numero_termo,))
        
        transacoes_debitos_indevidos = cur.fetchall()
        
        if transacoes_debitos_indevidos:
            # Buscar modelo de texto do cache (otimizado)
            modelo_debitos = modelos_cache.get(7)
            
            if modelo_debitos:
                inconsistencias_identificadas.append({
                    'id': modelo_debitos['id'],
                    'nome_item': modelo_debitos['nome_item'],
                    'modelo_texto': modelo_debitos['modelo_texto'],
                    'solucao': modelo_debitos['solucao'],
                    'transacoes': transacoes_debitos_indevidos,
                    'ordem': modelo_debitos.get('ordem', 999)
                })
        
        # ========================================
        # 9. DESPESA SEM GUIA (ALGUMAS, NÃO TODAS)
        # ========================================
        print("[DEBUG] Card 9: Iniciando verificação - Despesa sem guia")
        # Verifica se ALGUMAS (mas não todas) guias não foram apresentadas
        # Este card é excludente com Card 1 (que verifica se TODAS não foram apresentadas)
        
        # Verificar se há registros com "Não apresentada" mas não é o caso de TODOS
        cur.execute("""
            SELECT 
                COUNT(*) as total_preenchidos,
                COALESCE(SUM(CASE WHEN avaliacao_guia = 'Não apresentada' THEN 1 ELSE 0 END), 0) as nao_apresentadas
            FROM analises_pc.conc_analise ca
            INNER JOIN analises_pc.conc_extrato ce ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND ca.avaliacao_guia IS NOT NULL
              AND ca.avaliacao_guia != ''
        """, (numero_termo,))
        
        resultado_guias_parcial = cur.fetchone()
        
        # Só identifica se:
        # 1. Há registros com "Não apresentada" (nao_apresentadas > 0)
        # 2. MAS não são TODOS (nao_apresentadas < total_preenchidos)
        if resultado_guias_parcial and resultado_guias_parcial['nao_apresentadas'] > 0:
            if resultado_guias_parcial['nao_apresentadas'] < resultado_guias_parcial['total_preenchidos']:
                # ALGUMAS guias não foram apresentadas (mas não todas)
                
                # Buscar modelo de texto do cache (otimizado)
                modelo_guias_parcial = modelos_cache.get(9)
                
                if modelo_guias_parcial:
                    # Buscar transações relacionadas (apenas as não apresentadas)
                    cur.execute("""
                        SELECT 
                            ce.id,
                            ce.indice,
                            ce.data,
                            ce.credito,
                            ce.debito,
                            ce.discriminacao,
                            ce.cat_transacao,
                            ce.competencia,
                            ce.origem_destino
                        FROM analises_pc.conc_extrato ce
                        INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                        WHERE ce.numero_termo = %s
                          AND ca.avaliacao_guia = 'Não apresentada'
                        ORDER BY ce.data, ce.indice
                    """, (numero_termo,))
                    
                    transacoes_guias_parcial = cur.fetchall()
                    
                    inconsistencias_identificadas.append({
                        'id': modelo_guias_parcial['id'],
                        'nome_item': modelo_guias_parcial['nome_item'],
                        'modelo_texto': modelo_guias_parcial['modelo_texto'],
                        'solucao': modelo_guias_parcial['solucao'],
                        'transacoes': transacoes_guias_parcial,
                        'ordem': modelo_guias_parcial.get('ordem', 999)
                    })
        
        # ========================================
        # 10. PAGO EM ESPÉCIE
        # ========================================
        print("[DEBUG] Card 10: Iniciando verificação - Pago em espécie")
        # Verifica transações com comprovante "Pago em Espécie"
        cur.execute("""
            SELECT 
                ce.id,
                ce.indice,
                ce.data,
                ce.credito,
                ce.debito,
                ce.discriminacao,
                ce.cat_transacao,
                ce.competencia,
                ce.origem_destino
            FROM analises_pc.conc_extrato ce
            INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND ca.avaliacao_comprovante = 'Pago em Espécie'
            ORDER BY ce.data, ce.indice
        """, (numero_termo,))
        
        transacoes_especie = cur.fetchall()
        
        if transacoes_especie:
            # Buscar modelo de texto do cache (otimizado)
            modelo_especie = modelos_cache.get(10)
            
            if modelo_especie:
                inconsistencias_identificadas.append({
                    'id': modelo_especie['id'],
                    'nome_item': modelo_especie['nome_item'],
                    'modelo_texto': modelo_especie['modelo_texto'],
                    'solucao': modelo_especie['solucao'],
                    'transacoes': transacoes_especie,
                    'ordem': modelo_especie.get('ordem', 999)
                })
        
        # ========================================
        # 11. PAGO EM CARTÃO DE CRÉDITO
        # ========================================
        print("[DEBUG] Card 11: Iniciando verificação - Pago em cartão de crédito")
        # Verifica transações com comprovante "Cartão de Crédito"
        cur.execute("""
            SELECT 
                ce.id,
                ce.indice,
                ce.data,
                ce.credito,
                ce.debito,
                ce.discriminacao,
                ce.cat_transacao,
                ce.competencia,
                ce.origem_destino
            FROM analises_pc.conc_extrato ce
            INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND ca.avaliacao_comprovante = 'Cartão de Crédito'
            ORDER BY ce.data, ce.indice
        """, (numero_termo,))
        
        transacoes_cartao = cur.fetchall()
        
        if transacoes_cartao:
            # Buscar modelo de texto do cache (otimizado)
            modelo_cartao = modelos_cache.get(11)
            
            if modelo_cartao:
                inconsistencias_identificadas.append({
                    'id': modelo_cartao['id'],
                    'nome_item': modelo_cartao['nome_item'],
                    'modelo_texto': modelo_cartao['modelo_texto'],
                    'solucao': modelo_cartao['solucao'],
                    'transacoes': transacoes_cartao,
                    'ordem': modelo_cartao.get('ordem', 999)
                })
        
        # ========================================
        # 12. PAGO EM CHEQUE
        # ========================================
        print("[DEBUG] Card 12: Iniciando verificação - Pago em cheque")
        # Verifica transações com comprovante "Pago em Cheque"
        cur.execute("""
            SELECT 
                ce.id,
                ce.indice,
                ce.data,
                ce.credito,
                ce.debito,
                ce.discriminacao,
                ce.cat_transacao,
                ce.competencia,
                ce.origem_destino
            FROM analises_pc.conc_extrato ce
            INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND ca.avaliacao_comprovante = 'Pago em Cheque'
            ORDER BY ce.data, ce.indice
        """, (numero_termo,))
        
        transacoes_cheque = cur.fetchall()
        
        if transacoes_cheque:
            # Buscar modelo de texto do cache (otimizado)
            modelo_cheque = modelos_cache.get(12)
            
            if modelo_cheque:
                inconsistencias_identificadas.append({
                    'id': modelo_cheque['id'],
                    'nome_item': modelo_cheque['nome_item'],
                    'modelo_texto': modelo_cheque['modelo_texto'],
                    'solucao': modelo_cheque['solucao'],
                    'transacoes': transacoes_cheque,
                    'ordem': modelo_cheque.get('ordem', 999)
                })
        
        # ========================================
        # CARD 13: Reembolsos sem comprovação
        # ========================================
        print(f"[DEBUG] Verificando Card 13: Reembolsos sem comprovação...")
        cur.execute("""
            SELECT ce.id, ce.indice, ce.data, ce.credito, ce.debito,
                   ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino,
                   ce.avaliacao_analista, ca.avaliacao_comprovante
            FROM analises_pc.conc_extrato ce
            INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND (ce.origem_destino ILIKE %s OR ce.avaliacao_analista ILIKE %s)
              AND ca.avaliacao_comprovante != 'Apresentado corretamente'
            ORDER BY ce.data, ce.indice
        """, (numero_termo, '%Reembolso%', '%Reembolso%'))
        
        transacoes_reembolso_sem_comp = cur.fetchall()
        
        if transacoes_reembolso_sem_comp:
            # Buscar modelo de texto do cache (otimizado)
            modelo_reembolso = modelos_cache.get(13)
            
            if modelo_reembolso:
                inconsistencias_identificadas.append({
                    'id': modelo_reembolso['id'],
                    'nome_item': modelo_reembolso['nome_item'],
                    'modelo_texto': modelo_reembolso['modelo_texto'],
                    'solucao': modelo_reembolso['solucao'],
                    'transacoes': transacoes_reembolso_sem_comp,
                    'ordem': modelo_reembolso.get('ordem', 999)
                })
        
        # ========================================
        # CARD 14: Pagamento em duplicidade
        # ========================================
        print(f"[DEBUG] Verificando Card 14: Pagamento em duplicidade...")
        cur.execute("""
            SELECT ce.id, ce.indice, ce.data, ce.credito, ce.debito,
                   ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino,
                   ce.avaliacao_analista
            FROM analises_pc.conc_extrato ce
            INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND (ce.origem_destino ILIKE %s OR ce.avaliacao_analista ILIKE %s)
            ORDER BY ce.data, ce.indice
        """, (numero_termo, '%Duplicidade%', '%Duplicidade%'))
        
        transacoes_duplicidade = cur.fetchall()
        
        if transacoes_duplicidade:
            # Buscar modelo de texto do cache (otimizado)
            modelo_duplicidade = modelos_cache.get(14)
            
            if modelo_duplicidade:
                inconsistencias_identificadas.append({
                    'id': modelo_duplicidade['id'],
                    'nome_item': modelo_duplicidade['nome_item'],
                    'modelo_texto': modelo_duplicidade['modelo_texto'],
                    'solucao': modelo_duplicidade['solucao'],
                    'transacoes': transacoes_duplicidade,
                    'ordem': modelo_duplicidade.get('ordem', 999)
                })
        
        # ========================================
        # CARD 15: Pagamento para outro Favorecido
        # ========================================
        print(f"[DEBUG] Verificando Card 15: Pagamento para outro Favorecido...")
        cur.execute("""
            SELECT ce.id, ce.indice, ce.data, ce.credito, ce.debito,
                   ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino,
                   ce.avaliacao_analista
            FROM analises_pc.conc_extrato ce
            INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND (ce.origem_destino ILIKE %s OR ce.avaliacao_analista ILIKE %s)
            ORDER BY ce.data, ce.indice
        """, (numero_termo, '%Outro favorecido%', '%Outro favorecido%'))
        
        transacoes_outro_favorecido = cur.fetchall()
        
        if transacoes_outro_favorecido:
            # Buscar modelo de texto do cache (otimizado)
            modelo_outro_favorecido = modelos_cache.get(15)
            
            if modelo_outro_favorecido:
                inconsistencias_identificadas.append({
                    'id': modelo_outro_favorecido['id'],
                    'nome_item': modelo_outro_favorecido['nome_item'],
                    'modelo_texto': modelo_outro_favorecido['modelo_texto'],
                    'solucao': modelo_outro_favorecido['solucao'],
                    'transacoes': transacoes_outro_favorecido,
                    'ordem': modelo_outro_favorecido.get('ordem', 999)
                })
        
        # ========================================
        # CARD 16: Alteração do vínculo de contratado
        # ========================================
        print(f"[DEBUG] Verificando Card 16: Alteração do vínculo de contratado...")
        cur.execute("""
            SELECT ce.id, ce.indice, ce.data, ce.credito, ce.debito,
                   ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino,
                   ce.avaliacao_analista
            FROM analises_pc.conc_extrato ce
            INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
            WHERE ce.numero_termo = %s
              AND (ce.origem_destino ILIKE %s 
                   OR ce.origem_destino ILIKE %s
                   OR ce.avaliacao_analista ILIKE %s
                   OR ce.avaliacao_analista ILIKE %s)
            ORDER BY ce.data, ce.indice
        """, (numero_termo, '%Alteração do vínculo%', '%Alteração de vínculo%', '%Alteração do vínculo%', '%Alteração de vínculo%'))
        
        transacoes_alteracao_vinculo = cur.fetchall()
        
        if transacoes_alteracao_vinculo:
            # Buscar modelo de texto do cache (otimizado)
            modelo_alteracao_vinculo = modelos_cache.get(16)
            
            if modelo_alteracao_vinculo:
                inconsistencias_identificadas.append({
                    'id': modelo_alteracao_vinculo['id'],
                    'nome_item': modelo_alteracao_vinculo['nome_item'],
                    'modelo_texto': modelo_alteracao_vinculo['modelo_texto'],
                    'solucao': modelo_alteracao_vinculo['solucao'],
                    'transacoes': transacoes_alteracao_vinculo,
                    'ordem': modelo_alteracao_vinculo.get('ordem', 999)
                })
        
        # ========================================
        # CARD 17: Execução de rubrica superior ao previsto
        # ========================================
        print(f"[DEBUG] Verificando Card 17: Execução de rubrica superior ao previsto...")
        cur.execute("""
            WITH previsto AS (
                SELECT 
                    pd.rubrica,
                    CEIL(pd.mes / 3.0) as trimestre,
                    SUM(pd.valor) as valor_previsto
                FROM public.parcerias_despesas pd
                WHERE pd.numero_termo = %s
                GROUP BY pd.rubrica, trimestre
            ),
            executado AS (
                SELECT 
                    pd.rubrica,
                    CEIL(
                        ((EXTRACT(YEAR FROM ce.competencia) - EXTRACT(YEAR FROM p.inicio)) * 12 +
                         (EXTRACT(MONTH FROM ce.competencia) - EXTRACT(MONTH FROM p.inicio)) + 1) / 3.0
                    ) as trimestre,
                    SUM(ce.discriminacao) as valor_executado
                FROM analises_pc.conc_extrato ce
                INNER JOIN public.parcerias p ON p.numero_termo = ce.numero_termo
                INNER JOIN (
                    SELECT DISTINCT ON (categoria_despesa, numero_termo) 
                        rubrica, categoria_despesa, numero_termo
                    FROM public.parcerias_despesas
                ) pd ON pd.numero_termo = ce.numero_termo 
                    AND pd.categoria_despesa = ce.cat_transacao
                WHERE ce.numero_termo = %s
                GROUP BY pd.rubrica, trimestre
            )
            SELECT 
                p.rubrica,
                p.trimestre,
                p.valor_previsto,
                COALESCE(e.valor_executado, 0) as valor_executado,
                p.valor_previsto - COALESCE(e.valor_executado, 0) as diferenca
            FROM previsto p
            LEFT JOIN executado e ON p.rubrica = e.rubrica AND p.trimestre = e.trimestre
            WHERE p.valor_previsto - COALESCE(e.valor_executado, 0) < 0
            ORDER BY p.rubrica, p.trimestre
        """, (numero_termo, numero_termo))
        
        divergencias_rubrica = cur.fetchall()
        
        if divergencias_rubrica:
            # Buscar modelo de texto do cache (otimizado)
            modelo_rubrica = modelos_cache.get(17)
            
            if modelo_rubrica:
                inconsistencias_identificadas.append({
                    'id': modelo_rubrica['id'],
                    'nome_item': modelo_rubrica['nome_item'],
                    'modelo_texto': modelo_rubrica['modelo_texto'],
                    'solucao': modelo_rubrica['solucao'],
                    'transacoes': divergencias_rubrica,
                    'ordem': modelo_rubrica.get('ordem', 999),
                    'mostrar_tabela': True,
                    'tipo_tabela': 'rubrica_trimestral'  # Indicador para renderização customizada
                })
        
        # ========================================
        # CARD 18: Despesa sem previsão no período
        # ========================================
        print(f"[DEBUG] Verificando Card 18: Despesa sem previsão no período...")
        cur.execute("""
            SELECT 
                ce.cat_transacao as categoria_despesa,
                ((EXTRACT(YEAR FROM ce.competencia) - EXTRACT(YEAR FROM p.inicio)) * 12 +
                 (EXTRACT(MONTH FROM ce.competencia) - EXTRACT(MONTH FROM p.inicio)) + 1) as mes,
                SUM(ce.discriminacao) as valor_executado
            FROM analises_pc.conc_extrato ce
            INNER JOIN public.parcerias p ON p.numero_termo = ce.numero_termo
            INNER JOIN (
                SELECT DISTINCT categoria_despesa, numero_termo
                FROM public.parcerias_despesas
            ) categorias_validas ON categorias_validas.numero_termo = ce.numero_termo 
                AND categorias_validas.categoria_despesa = ce.cat_transacao
            LEFT JOIN public.parcerias_despesas pd 
                ON pd.numero_termo = ce.numero_termo
                AND pd.categoria_despesa = ce.cat_transacao
                AND pd.mes = ((EXTRACT(YEAR FROM ce.competencia) - EXTRACT(YEAR FROM p.inicio)) * 12 +
                             (EXTRACT(MONTH FROM ce.competencia) - EXTRACT(MONTH FROM p.inicio)) + 1)
            WHERE ce.numero_termo = %s
              AND ce.cat_transacao IS NOT NULL
              AND (pd.mes IS NULL OR pd.valor = 0 OR pd.valor IS NULL)
            GROUP BY ce.cat_transacao, p.inicio, ce.competencia
            ORDER BY ce.cat_transacao, mes
        """, (numero_termo,))
        
        despesas_sem_previsao = cur.fetchall()
        
        if despesas_sem_previsao:
            # Buscar modelo de texto do cache (otimizado)
            modelo_despesa_sem_previsao = modelos_cache.get(18)
            
            if modelo_despesa_sem_previsao:
                inconsistencias_identificadas.append({
                    'id': modelo_despesa_sem_previsao['id'],
                    'nome_item': modelo_despesa_sem_previsao['nome_item'],
                    'modelo_texto': modelo_despesa_sem_previsao['modelo_texto'],
                    'solucao': modelo_despesa_sem_previsao['solucao'],
                    'transacoes': despesas_sem_previsao,
                    'ordem': modelo_despesa_sem_previsao.get('ordem', 999),
                    'mostrar_tabela': True,
                    'tipo_tabela': 'despesa_sem_previsao'  # Indicador para renderização customizada
                })
        
        # ========================================
        # CARD 19: Vigência extemporânea
        # ========================================
        print(f"[DEBUG] Verificando Card 19: Vigência extemporânea...")
        cur.execute("""
            SELECT 
                ce.id, ce.indice, ce.data, ce.credito, ce.debito,
                ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino,
                ce.avaliacao_analista
            FROM analises_pc.conc_extrato ce
            INNER JOIN public.parcerias p ON p.numero_termo = ce.numero_termo
            WHERE ce.numero_termo = %s
              AND (
                  -- Competência fora do período de vigência
                  (ce.competencia < p.inicio OR ce.competencia > p.final)
                  -- Ou marcado pelo analista
                  OR ce.avaliacao_analista ILIKE %s
                  OR ce.avaliacao_analista ILIKE %s
              )
            ORDER BY ce.data, ce.indice
        """, (numero_termo, '%Vigência extemporânea%', '%Vigencia extemporanea%'))
        
        transacoes_vigencia_extemporanea = cur.fetchall()
        
        if transacoes_vigencia_extemporanea:
            # Buscar modelo de texto do cache (otimizado)
            modelo_vigencia = modelos_cache.get(19)
            
            if modelo_vigencia:
                inconsistencias_identificadas.append({
                    'id': modelo_vigencia['id'],
                    'nome_item': modelo_vigencia['nome_item'],
                    'modelo_texto': modelo_vigencia['modelo_texto'],
                    'solucao': modelo_vigencia['solucao'],
                    'transacoes': transacoes_vigencia_extemporanea,
                    'ordem': modelo_vigencia.get('ordem', 999)
                })
        
        # ========================================
        # CARD 20: Ausência de aplicação total
        # ========================================
        print(f"[DEBUG] Verificando Card 20: Ausência de aplicação total...")
        try:
            cur.execute("""
                SELECT COUNT(*) as total_aplicacoes
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s
                  AND cat_transacao ILIKE %s
            """, (numero_termo, '%Aplica%'))
            
            resultado_aplicacao = cur.fetchone()
            total_aplicacoes = resultado_aplicacao['total_aplicacoes'] if resultado_aplicacao else 0
            print(f"[DEBUG] Card 20 - Total de aplicações encontradas: {total_aplicacoes}")
            
            # Se não há nenhuma aplicação no termo, adicionar inconsistência SEM tabela
            if total_aplicacoes == 0:
                # Buscar modelo de texto do cache (otimizado)
                modelo_ausencia_aplicacao = modelos_cache.get(20)
                
                if modelo_ausencia_aplicacao:
                    inconsistencias_identificadas.append({
                        'id': modelo_ausencia_aplicacao['id'],
                        'nome_item': modelo_ausencia_aplicacao['nome_item'],
                        'modelo_texto': modelo_ausencia_aplicacao['modelo_texto'],
                        'solucao': modelo_ausencia_aplicacao['solucao'],
                        'transacoes': [],  # SEM transações
                        'mostrar_tabela': False,  # Flag para não mostrar tabela
                        'ordem': modelo_ausencia_aplicacao.get('ordem', 999)
                    })
                    print(f"[DEBUG] Card 20 - Inconsistência adicionada")
        except Exception as e:
            conn.rollback()  # Resetar transação após erro
            print(f"[ERRO] Card 20 falhou: {e}")
            import traceback
            traceback.print_exc()
        
        # ========================================
        # CARD 21: Ausência de aplicação em 48h
        # ========================================
        print(f"[DEBUG] Verificando Card 21: Ausência de aplicação em 48h...")
        try:
            # Buscar todas as transações com "Parcela" em cat_transacao
            print(f"[DEBUG] Card 21 - Buscando parcelas para termo: {numero_termo}")
            cur.execute("""
                SELECT id, indice, data, discriminacao, cat_transacao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s
                  AND cat_transacao ILIKE %s
                ORDER BY data
            """, (numero_termo, '%Parcela%'))
            
            transacoes_parcelas = cur.fetchall()
            print(f"[DEBUG] Card 21 - Total de parcelas encontradas: {len(transacoes_parcelas)}")
            parcelas_sem_aplicacao = []
            
            # Para cada parcela, verificar se há aplicação nos próximos 2 dias
            for idx, parcela in enumerate(transacoes_parcelas):
                data_parcela = parcela['data']
                data_limite = data_parcela + timedelta(days=2)  # 48 horas = 2 dias
                print(f"[DEBUG] Card 21 - Verificando parcela {idx+1}/{len(transacoes_parcelas)}: data={data_parcela}, limite={data_limite}")
                
                # Buscar se existe aplicação entre data_parcela e data_limite
                cur.execute("""
                    SELECT COUNT(*) as total_aplicacoes
                    FROM analises_pc.conc_extrato
                    WHERE numero_termo = %s
                      AND cat_transacao ILIKE %s
                      AND data > %s
                      AND data <= %s
                """, (numero_termo, '%Aplica%', data_parcela, data_limite))
                
                resultado = cur.fetchone()
                total_aplicacoes_periodo = resultado['total_aplicacoes'] if resultado else 0
                print(f"[DEBUG] Card 21 - Aplicações encontradas no período: {total_aplicacoes_periodo}")
                
                # Se não há aplicação nos próximos 2 dias, adicionar à lista
                if total_aplicacoes_periodo == 0:
                    parcelas_sem_aplicacao.append(parcela)
            
            print(f"[DEBUG] Card 21 - Total de parcelas sem aplicação em 48h: {len(parcelas_sem_aplicacao)}")
            
            if parcelas_sem_aplicacao:
                # Buscar modelo de texto do cache (otimizado)
                modelo_aplicacao_48h = modelos_cache.get(21)
                
                if modelo_aplicacao_48h:
                    inconsistencias_identificadas.append({
                        'id': modelo_aplicacao_48h['id'],
                        'nome_item': modelo_aplicacao_48h['nome_item'],
                        'modelo_texto': modelo_aplicacao_48h['modelo_texto'],
                        'solucao': modelo_aplicacao_48h['solucao'],
                        'transacoes': parcelas_sem_aplicacao,
                        'tipo_tabela': 'aplicacao_48h',  # Tipo especial para tabela reduzida
                        'ordem': modelo_aplicacao_48h.get('ordem', 999)
                    })
                    print(f"[DEBUG] Card 21 - Inconsistência adicionada")
        except Exception as e:
            conn.rollback()  # Resetar transação após erro
            print(f"[ERRO] Card 21 falhou: {e}")
            import traceback
            traceback.print_exc()
        
        # ========================================
        # CARD 22: Aplicação Divergente
        # ========================================
        print(f"[DEBUG] Verificando Card 22: Aplicação Divergente...")
        try:
            # Buscar aplicações que NÃO sejam Poupança
            cur.execute("""
                SELECT id, indice, data, discriminacao, cat_transacao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s
                  AND cat_transacao ILIKE %s
                  AND cat_transacao NOT ILIKE %s
                ORDER BY data
            """, (numero_termo, '%Aplica%', '%Poupan%'))
            
            transacoes_aplicacao_divergente = cur.fetchall()
            print(f"[DEBUG] Card 22 - Aplicações divergentes encontradas: {len(transacoes_aplicacao_divergente)}")
            
            if transacoes_aplicacao_divergente:
                # Buscar modelo de texto do cache (otimizado)
                modelo_aplicacao_divergente = modelos_cache.get(22)
                
                if modelo_aplicacao_divergente:
                    inconsistencias_identificadas.append({
                        'id': modelo_aplicacao_divergente['id'],
                        'nome_item': modelo_aplicacao_divergente['nome_item'],
                        'modelo_texto': modelo_aplicacao_divergente['modelo_texto'],
                        'solucao': modelo_aplicacao_divergente['solucao'],
                        'transacoes': transacoes_aplicacao_divergente,
                        'tipo_tabela': 'aplicacao_divergente',  # Tipo especial para tabela reduzida
                        'ordem': modelo_aplicacao_divergente.get('ordem', 999)
                    })
                    print(f"[DEBUG] Card 22 - Inconsistência adicionada")
        except Exception as e:
            conn.rollback()  # Resetar transação após erro
            print(f"[ERRO] Card 22 falhou: {e}")
            import traceback
            traceback.print_exc()
        
        # ========================================
        # CARD 25: Fora do Município
        # ========================================
        print(f"[DEBUG] Verificando Card 25: Fora do Município...")
        try:
            # Buscar transações marcadas como "Fora do município"
            cur.execute("""
                SELECT 
                    ce.id, ce.indice, ce.data, ce.credito, ce.debito,
                    ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND ca.avaliacao_fora_municipio ILIKE %s
                ORDER BY ce.data, ce.indice
            """, (numero_termo, '%Fora do município%'))
            
            transacoes_fora_municipio = cur.fetchall()
            print(f"[DEBUG] Card 25 - Transações fora do município: {len(transacoes_fora_municipio)}")
            
            if transacoes_fora_municipio:
                # Buscar modelo de texto do cache (otimizado)
                modelo_fora_municipio = modelos_cache.get(25)
                
                if modelo_fora_municipio:
                    inconsistencias_identificadas.append({
                        'id': modelo_fora_municipio['id'],
                        'nome_item': modelo_fora_municipio['nome_item'],
                        'modelo_texto': modelo_fora_municipio['modelo_texto'],
                        'solucao': modelo_fora_municipio['solucao'],
                        'transacoes': transacoes_fora_municipio,
                        'ordem': modelo_fora_municipio.get('ordem', 999)
                    })
                    print(f"[DEBUG] Card 25 - Inconsistência adicionada")
        except Exception as e:
            conn.rollback()  # Resetar transação após erro
            print(f"[ERRO] Card 25 falhou: {e}")
            import traceback
            traceback.print_exc()
        
        # ========================================
        # CARD 26: Especificar categoria de despesa
        # ========================================
        print(f"[DEBUG] Verificando Card 26: Especificar categoria de despesa...")
        try:
            # Buscar transações onde avaliacao_analista contém "especificar"
            # Busca em ce.avaliacao_analista (coluna do extrato)
            cur.execute("""
                SELECT 
                    ce.id AS id_conc_extrato, ce.indice, ce.data, ce.credito, ce.debito,
                    ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino,
                    ce.avaliacao_analista
                FROM analises_pc.conc_extrato ce
                WHERE ce.numero_termo = %s
                  AND ce.avaliacao_analista ILIKE %s
                ORDER BY ce.data, ce.indice
            """, (numero_termo, '%especificar%'))
            
            transacoes_especificar = cur.fetchall()
            print(f"[DEBUG] Card 26 - Transações para especificar categoria: {len(transacoes_especificar)}")
            
            if transacoes_especificar:
                # Buscar modelo de texto do cache (otimizado)
                modelo_especificar = modelos_cache.get(26)
                
                if modelo_especificar:
                    inconsistencias_identificadas.append({
                        'id': modelo_especificar['id'],
                        'nome_item': modelo_especificar['nome_item'],
                        'modelo_texto': modelo_especificar['modelo_texto'],
                        'solucao': modelo_especificar['solucao'],
                        'transacoes': transacoes_especificar,
                        'ordem': modelo_especificar.get('ordem', 999)
                    })
                    print(f"[DEBUG] Card 26 - Inconsistência adicionada")
        except Exception as e:
            conn.rollback()  # Resetar transação após erro
            print(f"[ERRO] Card 26 falhou: {e}")
            import traceback
            traceback.print_exc()
        
        # ========================================
        # ADICIONAR MAIS INCONSISTÊNCIAS AQUI NO FUTURO
        # ========================================
        
        # ========================================
        # AGRUPAR INCONSISTÊNCIAS EM CARDS COMPOSTOS
        # ========================================
        print(f"[DEBUG] Total de inconsistências identificadas: {len(inconsistencias_identificadas)}")
        # Identificar transações que aparecem em múltiplas inconsistências
        inconsistencias_agrupadas = agrupar_cards_compostos(inconsistencias_identificadas)
        print(f"[DEBUG] Total após agrupamento: {len(inconsistencias_agrupadas)}")
        
        # Verificar quais inconsistências já foram ratificadas e buscar status
        for inc in inconsistencias_agrupadas:
            resultado = verificar_ratificacao(cur, numero_termo, inc['nome_item'])
            inc['ratificada'] = resultado['ratificada']
            inc['status'] = resultado['status']  # Adicionar status ao retorno
        
        # ========================================
        # ATUALIZAÇÃO AUTOMÁTICA DE STATUS
        # ========================================
        # Comparar inconsistências identificadas vs ratificadas
        # Se uma inconsistência foi ratificada mas não aparece mais na lista atual,
        # significa que foi corrigida → atualizar status para 'Atendida'
        
        nomes_identificados = {inc['nome_item'] for inc in inconsistencias_agrupadas}
        print(f"[DEBUG] Inconsistências identificadas atualmente: {len(nomes_identificados)}")
        
        # Buscar TODAS as inconsistências ratificadas para este termo em todas as tabelas
        # Tabela 1: lista_inconsistencias (transações individuais)
        cur.execute("""
            SELECT DISTINCT nome_item
            FROM analises_pc.lista_inconsistencias
            WHERE numero_termo = %s AND status != 'Atendida'
        """, (numero_termo,))
        ratificadas_transacoes = {row['nome_item'] for row in cur.fetchall()}
        
        # Tabela 2: lista_inconsistencias_agregadas
        cur.execute("""
            SELECT DISTINCT nome_item
            FROM analises_pc.lista_inconsistencias_agregadas
            WHERE numero_termo = %s AND status != 'Atendida'
        """, (numero_termo,))
        ratificadas_agregadas = {row['nome_item'] for row in cur.fetchall()}
        
        # Tabela 3: lista_inconsistencias_globais
        cur.execute("""
            SELECT DISTINCT nome_item
            FROM analises_pc.lista_inconsistencias_globais
            WHERE numero_termo = %s AND status != 'Atendida'
        """, (numero_termo,))
        ratificadas_globais = {row['nome_item'] for row in cur.fetchall()}
        
        # Combinar todas as ratificações
        todas_ratificadas = ratificadas_transacoes | ratificadas_agregadas | ratificadas_globais
        print(f"[DEBUG] Inconsistências ratificadas (não atendidas): {len(todas_ratificadas)}")
        
        # Identificar quais foram corrigidas (ratificadas mas não mais identificadas)
        corrigidas = todas_ratificadas - nomes_identificados
        
        if corrigidas:
            print(f"[DEBUG] Inconsistências corrigidas detectadas: {corrigidas}")
            
            # Atualizar status para 'Atendida' em todas as tabelas
            for nome_item in corrigidas:
                # Determinar em qual tabela está
                if nome_item in ratificadas_transacoes:
                    cur.execute("""
                        UPDATE analises_pc.lista_inconsistencias
                        SET status = 'Atendida'
                        WHERE numero_termo = %s AND nome_item = %s AND status != 'Atendida'
                    """, (numero_termo, nome_item))
                    print(f"[DEBUG] ✅ Atualizado em lista_inconsistencias: {nome_item}")
                
                if nome_item in ratificadas_agregadas:
                    cur.execute("""
                        UPDATE analises_pc.lista_inconsistencias_agregadas
                        SET status = 'Atendida'
                        WHERE numero_termo = %s AND nome_item = %s AND status != 'Atendida'
                    """, (numero_termo, nome_item))
                    print(f"[DEBUG] ✅ Atualizado em lista_inconsistencias_agregadas: {nome_item}")
                
                if nome_item in ratificadas_globais:
                    cur.execute("""
                        UPDATE analises_pc.lista_inconsistencias_globais
                        SET status = 'Atendida'
                        WHERE numero_termo = %s AND nome_item = %s AND status != 'Atendida'
                    """, (numero_termo, nome_item))
                    print(f"[DEBUG] ✅ Atualizado em lista_inconsistencias_globais: {nome_item}")
            
            conn.commit()
            print(f"[DEBUG] Status automático atualizado para {len(corrigidas)} inconsistência(s)")
        else:
            print("[DEBUG] Nenhuma inconsistência corrigida detectada")
        
        cur.close()
        
        # Ordenar inconsistências pela coluna 'ordem'
        inconsistencias_agrupadas.sort(key=lambda x: x.get('ordem', 999))
        
        print(f"[DEBUG] ===== FIM identificar_inconsistencias - SUCESSO =====")
        print(f"[DEBUG] Retornando {len(inconsistencias_agrupadas)} inconsistências")
        
        return jsonify({
            'sucesso': True,
            'numero_termo': numero_termo,
            'inconsistencias': inconsistencias_agrupadas
        })
    
    except Exception as e:
        cur.close()
        print(f"[ERRO] identificar_inconsistencias: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@analises_pc_bp.route('/api/ratificar-inconsistencia', methods=['POST'])
def ratificar_inconsistencia():
    """
    Ratifica uma inconsistência e registra na tabela lista_inconsistencias.
    Recebe: 
    - nome_item (string ou array): nome único ou lista de nomes para cards compostos
    - numero_termo (string)
    - e_card_composto (boolean, opcional): indica se é card composto
    """
    conn = get_db()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        dados = request.json
        nome_item = dados.get('nome_item')
        numero_termo = dados.get('numero_termo')
        
        if not nome_item or not numero_termo:
            return jsonify({'erro': 'Parâmetros nome_item e numero_termo são obrigatórios'}), 400
        
        print(f"[DEBUG] Ratificando inconsistência: {nome_item}")
        
        # Buscar ID e modelo_texto da inconsistência
        cur.execute("""
            SELECT id, modelo_texto
            FROM categoricas.c_dac_modelo_textos_inconsistencias
            WHERE nome_item = %s
            LIMIT 1
        """, (nome_item,))
        modelo = cur.fetchone()
        
        if not modelo:
            return jsonify({'erro': f'Inconsistência "{nome_item}" não encontrada'}), 404
        
        id_inconsistencia = modelo['id']
        modelo_texto_original = modelo['modelo_texto']
        
        # Buscar transações para ratificar baseado no ID
        transacoes_para_ratificar = []
        
        # Cards globais (sem transações) - não buscar transações, lista vazia
        if id_inconsistencia in [1, 2, 3, 4, 20]:
            # Card 1: Taxas bancárias não justificadas
            # Card 2: Juros e Multas
            # Card 3: Não uso de conta específica  
            # Card 4: Restituição final não executada
            # Card 20: Ausência de aplicação total
            transacoes_para_ratificar = []  # Sem transações
            print(f"[DEBUG] Card {id_inconsistencia} é global/flag - sem transações para ratificar")
        
        elif id_inconsistencia == 8:  # Apresentação de todas as guias
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND ca.avaliacao_guia = 'Não apresentada'
            """, (numero_termo,))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 5:  # Apresentar todos os Contratos
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND ca.avaliacao_contratos = 'Não apresentado'
            """, (numero_termo,))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 6:  # Créditos não justificados
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                WHERE ce.numero_termo = %s
                  AND ce.credito > 0
                  AND (ce.cat_avaliacao IS NULL OR ce.cat_avaliacao != 'Avaliado')
            """, (numero_termo,))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 7:  # Despesas não previstas
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                WHERE ce.numero_termo = %s
                  AND ce.cat_transacao = 'Débitos Indevidos'
            """, (numero_termo,))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 9:  # Despesa sem guia (algumas, não todas)
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND ca.avaliacao_guia = 'Não apresentada'
            """, (numero_termo,))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 10:  # Pago em espécie
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND ca.avaliacao_comprovante = 'Pago em Espécie'
            """, (numero_termo,))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 11:  # Pago em cartão de crédito
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND ca.avaliacao_comprovante = 'Cartão de Crédito'
            """, (numero_termo,))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 12:  # Pago em cheque
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND ca.avaliacao_comprovante = 'Pago em Cheque'
            """, (numero_termo,))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 13:  # Reembolsos sem comprovação
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND (ce.origem_destino ILIKE %s OR ce.avaliacao_analista ILIKE %s)
                  AND ca.avaliacao_comprovante != 'Apresentado corretamente'
            """, (numero_termo, '%Reembolso%', '%Reembolso%'))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 14:  # Pagamento em duplicidade
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND (ce.origem_destino ILIKE %s OR ce.avaliacao_analista ILIKE %s)
            """, (numero_termo, '%Duplicidade%', '%Duplicidade%'))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 15:  # Pagamento para outro Favorecido
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND (ce.origem_destino ILIKE %s OR ce.avaliacao_analista ILIKE %s)
            """, (numero_termo, '%Outro favorecido%', '%Outro favorecido%'))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 16:  # Alteração do vínculo de contratado
            cur.execute("""
                SELECT 
                    ce.id as id_conc_extrato,
                    ce.data,
                    ce.credito,
                    ce.debito,
                    ce.discriminacao,
                    ce.cat_transacao,
                    ce.competencia,
                    ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND (ce.origem_destino ILIKE %s 
                       OR ce.origem_destino ILIKE %s
                       OR ce.avaliacao_analista ILIKE %s
                       OR ce.avaliacao_analista ILIKE %s)
            """, (numero_termo, '%Alteração do vínculo%', '%Alteração de vínculo%', '%Alteração do vínculo%', '%Alteração de vínculo%'))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 17:  # Execução de rubrica superior ao previsto
            # Para este card, ratificamos as divergências encontradas (não há transações específicas)
            # A query retorna as rubricas/trimestres com execução superior
            cur.execute("""
                WITH previsto AS (
                    SELECT 
                        pd.rubrica,
                        CEIL(pd.mes / 3.0) as trimestre,
                        SUM(pd.valor) as valor_previsto
                    FROM public.parcerias_despesas pd
                    WHERE pd.numero_termo = %s
                    GROUP BY pd.rubrica, trimestre
                ),
                executado AS (
                    SELECT 
                        pd.rubrica,
                        CEIL(
                            ((EXTRACT(YEAR FROM ce.competencia) - EXTRACT(YEAR FROM p.inicio)) * 12 +
                             (EXTRACT(MONTH FROM ce.competencia) - EXTRACT(MONTH FROM p.inicio)) + 1) / 3.0
                        ) as trimestre,
                        SUM(ce.discriminacao) as valor_executado
                    FROM analises_pc.conc_extrato ce
                    INNER JOIN public.parcerias p ON p.numero_termo = ce.numero_termo
                    INNER JOIN (
                        SELECT DISTINCT ON (categoria_despesa, numero_termo) 
                            rubrica, categoria_despesa, numero_termo
                        FROM public.parcerias_despesas
                    ) pd ON pd.numero_termo = ce.numero_termo 
                        AND pd.categoria_despesa = ce.cat_transacao
                    WHERE ce.numero_termo = %s
                    GROUP BY pd.rubrica, trimestre
                )
                SELECT 
                    p.rubrica,
                    p.trimestre,
                    p.valor_previsto,
                    COALESCE(e.valor_executado, 0) as valor_executado,
                    p.valor_previsto - COALESCE(e.valor_executado, 0) as diferenca
                FROM previsto p
                LEFT JOIN executado e ON p.rubrica = e.rubrica AND p.trimestre = e.trimestre
                WHERE p.valor_previsto - COALESCE(e.valor_executado, 0) < 0
                ORDER BY p.rubrica, p.trimestre
            """, (numero_termo, numero_termo))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 18:  # Despesa sem previsão no período
            # Para este card, ratificamos as despesas executadas sem previsão mensal
            cur.execute("""
                SELECT 
                    ce.cat_transacao as categoria_despesa,
                    ((EXTRACT(YEAR FROM ce.competencia) - EXTRACT(YEAR FROM p.inicio)) * 12 +
                     (EXTRACT(MONTH FROM ce.competencia) - EXTRACT(MONTH FROM p.inicio)) + 1) as mes,
                    SUM(ce.discriminacao) as valor_executado
                FROM analises_pc.conc_extrato ce
                INNER JOIN public.parcerias p ON p.numero_termo = ce.numero_termo
                INNER JOIN (
                    SELECT DISTINCT categoria_despesa, numero_termo
                    FROM public.parcerias_despesas
                ) categorias_validas ON categorias_validas.numero_termo = ce.numero_termo 
                    AND categorias_validas.categoria_despesa = ce.cat_transacao
                LEFT JOIN public.parcerias_despesas pd 
                    ON pd.numero_termo = ce.numero_termo
                    AND pd.categoria_despesa = ce.cat_transacao
                    AND pd.mes = ((EXTRACT(YEAR FROM ce.competencia) - EXTRACT(YEAR FROM p.inicio)) * 12 +
                                 (EXTRACT(MONTH FROM ce.competencia) - EXTRACT(MONTH FROM p.inicio)) + 1)
                WHERE ce.numero_termo = %s
                  AND ce.cat_transacao IS NOT NULL
                  AND (pd.mes IS NULL OR pd.valor = 0 OR pd.valor IS NULL)
                GROUP BY ce.cat_transacao, p.inicio, ce.competencia
                ORDER BY ce.cat_transacao, mes
            """, (numero_termo,))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 19:  # Vigência extemporânea
            # Transações com competência fora do período de vigência
            cur.execute("""
                SELECT 
                    ce.id, ce.indice, ce.data, ce.credito, ce.debito,
                    ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino,
                    ce.avaliacao_analista
                FROM analises_pc.conc_extrato ce
                INNER JOIN public.parcerias p ON p.numero_termo = ce.numero_termo
                WHERE ce.numero_termo = %s
                  AND (
                      (ce.competencia < p.inicio OR ce.competencia > p.final)
                      OR ce.avaliacao_analista ILIKE %s
                      OR ce.avaliacao_analista ILIKE %s
                  )
                ORDER BY ce.data, ce.indice
            """, (numero_termo, '%Vigência extemporânea%', '%Vigencia extemporanea%'))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 20:  # Ausência de aplicação total
            # Este card não tem transações específicas (é uma ausência global)
            # Não inserir registros, apenas marcar como ratificado
            transacoes_para_ratificar = []
        
        elif id_inconsistencia == 21:  # Ausência de aplicação em 48h
            # Buscar parcelas sem aplicação em 48h
            print(f"[DEBUG] Card 21 Ratificação - Buscando parcelas para termo: {numero_termo}")
            cur.execute("""
                SELECT id, indice, data, discriminacao, cat_transacao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s
                  AND cat_transacao ILIKE %s
                ORDER BY data
            """, (numero_termo, '%Parcela%'))
            
            transacoes_parcelas = cur.fetchall()
            print(f"[DEBUG] Card 21 Ratificação - Parcelas encontradas: {len(transacoes_parcelas)}")
            transacoes_para_ratificar = []
            
            # Para cada parcela, verificar se há aplicação nos próximos 2 dias
            for idx, parcela in enumerate(transacoes_parcelas):
                data_parcela = parcela['data']
                data_limite = data_parcela + timedelta(days=2)
                print(f"[DEBUG] Card 21 Ratificação - Verificando parcela {idx+1}/{len(transacoes_parcelas)}: data={data_parcela}")
                
                cur.execute("""
                    SELECT COUNT(*) as total_aplicacoes
                    FROM analises_pc.conc_extrato
                    WHERE numero_termo = %s
                      AND cat_transacao ILIKE %s
                      AND data > %s
                      AND data <= %s
                """, (numero_termo, '%Aplica%', data_parcela, data_limite))
                
                resultado = cur.fetchone()
                total_aplicacoes_periodo = resultado['total_aplicacoes'] if resultado else 0
                print(f"[DEBUG] Card 21 Ratificação - Aplicações no período: {total_aplicacoes_periodo}")
                
                if total_aplicacoes_periodo == 0:
                    transacoes_para_ratificar.append(parcela)
            
            print(f"[DEBUG] Card 21 Ratificação - Total de parcelas sem aplicação: {len(transacoes_para_ratificar)}")
        
        elif id_inconsistencia == 22:  # Aplicação Divergente
            # Buscar aplicações que NÃO sejam Poupança
            print(f"[DEBUG] Card 22 Ratificação - Buscando aplicações divergentes para termo: {numero_termo}")
            cur.execute("""
                SELECT id, indice, data, discriminacao, cat_transacao
                FROM analises_pc.conc_extrato
                WHERE numero_termo = %s
                  AND cat_transacao ILIKE %s
                  AND cat_transacao NOT ILIKE %s
                ORDER BY data
            """, (numero_termo, '%Aplica%', '%Poupan%'))
            
            transacoes_para_ratificar = cur.fetchall()
            print(f"[DEBUG] Card 22 Ratificação - Aplicações divergentes encontradas: {len(transacoes_para_ratificar)}")
        
        elif id_inconsistencia == 25:  # Fora do Município
            # Buscar transações marcadas como "Fora do município"
            cur.execute("""
                SELECT 
                    ce.id, ce.indice, ce.data, ce.credito, ce.debito,
                    ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino
                FROM analises_pc.conc_extrato ce
                INNER JOIN analises_pc.conc_analise ca ON ca.conc_extrato_id = ce.id
                WHERE ce.numero_termo = %s
                  AND ca.avaliacao_fora_municipio ILIKE %s
                ORDER BY ce.data, ce.indice
            """, (numero_termo, '%Fora do município%'))
            
            transacoes_para_ratificar = cur.fetchall()
        
        elif id_inconsistencia == 26:  # Especificar categoria de despesa
            # Buscar transações onde avaliacao_analista contém "especificar"
            # Busca em ce.avaliacao_analista (coluna do extrato)
            cur.execute("""
                SELECT 
                    ce.id AS id_conc_extrato, ce.indice, ce.data, ce.credito, ce.debito,
                    ce.discriminacao, ce.cat_transacao, ce.competencia, ce.origem_destino,
                    ce.avaliacao_analista
                FROM analises_pc.conc_extrato ce
                WHERE ce.numero_termo = %s
                  AND ce.avaliacao_analista ILIKE %s
                ORDER BY ce.data, ce.indice
            """, (numero_termo, '%especificar%'))
            
            transacoes_para_ratificar = cur.fetchall()
        
        print(f"[DEBUG] Total de transações para ratificar: {len(transacoes_para_ratificar)}")
        print(f"[DEBUG] id_inconsistencia: {id_inconsistencia}")
        
        # Determinar tipo de tabela baseado no id_inconsistencia
        # Cards 17, 18: lista_inconsistencias_agregadas (dados agregados por rubrica/trimestre)
        # Cards 1, 4, 20, 21, 22: lista_inconsistencias_globais (flags globais sem transações)
        # Demais cards: lista_inconsistencias (transações individuais)
        
        registros_inseridos = 0
        usuario = session.get('usuario', 'Sistema')
        
        if id_inconsistencia in [17, 18]:  # Cards agregados
            # ====================================================
            # TABELA: lista_inconsistencias_agregadas
            # ====================================================
            print(f"[DEBUG] Usando lista_inconsistencias_agregadas para card {id_inconsistencia}")
            
            if len(transacoes_para_ratificar) > 0:
                # Preparar dados para batch INSERT
                values_list = []
                for row in transacoes_para_ratificar:
                    # Determinar campos baseado no tipo de agregação
                    if id_inconsistencia == 17:  # Rubrica vs Trimestre
                        values_list.append((
                            nome_item,
                            numero_termo,
                            'rubrica_trimestre',
                            row.get('rubrica'),
                            row.get('trimestre'),
                            row.get('valor_previsto'),
                            row.get('valor_executado'),
                            row.get('diferenca'),
                            'Não atendida',
                            usuario
                        ))
                    elif id_inconsistencia == 18:  # Despesa sem previsão
                        values_list.append((
                            nome_item,
                            numero_termo,
                            'despesa_sem_previsao',
                            row.get('categoria_despesa'),
                            row.get('mes'),
                            None,  # valor_previsto (não aplicável)
                            row.get('valor_executado'),
                            row.get('valor_executado'),  # diferenca = valor_executado
                            'Não atendida',
                            usuario
                        ))
                
                # Batch INSERT com ON CONFLICT
                execute_values(
                    cur,
                    """
                    INSERT INTO analises_pc.lista_inconsistencias_agregadas (
                        nome_item, numero_termo, tipo_agregacao,
                        campo1, campo2, valor_previsto, valor_executado, diferenca,
                        status, usuario
                    ) VALUES %s
                    ON CONFLICT (numero_termo, nome_item, campo1, campo2)
                    DO UPDATE SET
                        data_registro = NOW(),
                        status = 'Não atendida',
                        valor_previsto = EXCLUDED.valor_previsto,
                        valor_executado = EXCLUDED.valor_executado,
                        diferenca = EXCLUDED.diferenca
                    """,
                    values_list
                )
                registros_inseridos = len(values_list)
        
        elif id_inconsistencia in [1, 2, 3, 4, 20]:  # Cards globais (sem transações ou flags gerais)
            # ====================================================
            # TABELA: lista_inconsistencias_globais
            # ====================================================
            # Card 1: Taxas bancárias não justificadas
            # Card 2: Juros e Multas
            # Card 3: Não uso de conta específica
            # Card 4: Restituição final não executada
            # Card 20: Ausência de aplicação total
            print(f"[DEBUG] Usando lista_inconsistencias_globais para card {id_inconsistencia}")
            
            # Processar texto do modelo substituindo placeholders
            texto_processado = modelo_texto_original
            
            if id_inconsistencia == 1:  # Taxas bancárias
                # Buscar total de taxas bancárias
                cur.execute("""
                    SELECT SUM(ABS(discriminacao)) as total_taxas
                    FROM analises_pc.conc_extrato
                    WHERE numero_termo = %s AND LOWER(cat_transacao) = 'taxas bancárias'
                """, (numero_termo,))
                taxas_data = cur.fetchone()
                total_taxas = taxas_data['total_taxas'] if taxas_data and taxas_data['total_taxas'] else 0
                valor_formatado = f"R$ {total_taxas:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                texto_processado = texto_processado.replace('valor_taxa_usuario', valor_formatado)
            
            elif id_inconsistencia == 3:  # Não uso da conta específica
                # Buscar conta prevista de public.parcerias
                cur.execute("""
                    SELECT conta
                    FROM public.parcerias
                    WHERE numero_termo = %s
                    LIMIT 1
                """, (numero_termo,))
                parceria = cur.fetchone()
                conta_prevista = parceria['conta'] if parceria and parceria['conta'] else 'N/A'
                
                # Buscar conta executada de analises_pc.conc_banco
                cur.execute("""
                    SELECT DISTINCT banco_extrato, conta_execucao
                    FROM analises_pc.conc_banco
                    WHERE numero_termo = %s AND conta_execucao IS NOT NULL
                    LIMIT 1
                """, (numero_termo,))
                conta_exec = cur.fetchone()
                
                if conta_exec and conta_exec['conta_execucao']:
                    banco = conta_exec['banco_extrato'] if conta_exec['banco_extrato'] else ''
                    conta_executada = f"{banco} - {conta_exec['conta_execucao']}" if banco else conta_exec['conta_execucao']
                else:
                    conta_executada = 'N/A'
                
                texto_processado = texto_processado.replace('conta_prevista', conta_prevista)
                texto_processado = texto_processado.replace('conta_executada', conta_executada)
            
            elif id_inconsistencia == 4:  # Restituição final
                # Calcular valor residual
                cur.execute("""
                    SELECT total_pago, contrapartida
                    FROM public.parcerias
                    WHERE numero_termo = %s
                    LIMIT 1
                """, (numero_termo,))
                parceria = cur.fetchone()
                
                if parceria:
                    # Rendimentos
                    cur.execute("""
                        SELECT SUM(discriminacao) as total
                        FROM analises_pc.conc_extrato
                        WHERE numero_termo = %s AND cat_transacao = 'Rendimentos'
                    """, (numero_termo,))
                    rendimentos = cur.fetchone()
                    total_rendimentos = float(rendimentos['total'] or 0) if rendimentos else 0
                    
                    # Executado aprovado
                    cur.execute("""
                        SELECT COALESCE(SUM(ABS(ce.discriminacao)), 0) as total
                        FROM analises_pc.conc_extrato ce
                        WHERE ce.numero_termo = %s 
                            AND ce.cat_avaliacao = 'Avaliado'
                            AND ce.discriminacao IS NOT NULL
                            AND EXISTS (
                                SELECT 1 
                                FROM public.parcerias_despesas pd
                                WHERE LOWER(pd.categoria_despesa) = LOWER(ce.cat_transacao)
                                    AND pd.numero_termo = ce.numero_termo
                            )
                    """, (numero_termo,))
                    exec_aprovado = cur.fetchone()
                    valor_exec_aprovado = float(exec_aprovado['total'] or 0) if exec_aprovado else 0
                    
                    # Glosas
                    cur.execute("""
                        SELECT COALESCE(SUM(ABS(discriminacao)), 0) as total
                        FROM analises_pc.conc_extrato
                        WHERE numero_termo = %s 
                            AND cat_avaliacao = 'Glosar'
                            AND LOWER(cat_transacao) != 'taxas bancárias'
                            AND discriminacao IS NOT NULL
                    """, (numero_termo,))
                    glosas = cur.fetchone()
                    despesas_glosa = float(glosas['total'] or 0) if glosas else 0
                    
                    # Taxas não devolvidas
                    cur.execute("""
                        SELECT 
                            COALESCE(SUM(CASE WHEN LOWER(cat_transacao) = 'taxas bancárias' THEN ABS(discriminacao) ELSE 0 END), 0) as total_taxas,
                            COALESCE(SUM(CASE WHEN LOWER(cat_transacao) = 'devolução de taxas bancárias' THEN ABS(discriminacao) ELSE 0 END), 0) as total_devolucao
                        FROM analises_pc.conc_extrato
                        WHERE numero_termo = %s AND discriminacao IS NOT NULL
                    """, (numero_termo,))
                    taxas_data = cur.fetchone()
                    taxas_bancarias = float(taxas_data['total_taxas'] or 0) if taxas_data else 0
                    devolucao_taxas = float(taxas_data['total_devolucao'] or 0) if taxas_data else 0
                    taxas_nao_devolvidas = taxas_bancarias - devolucao_taxas
                    
                    # Calcular valor residual
                    contrapartida = float(parceria['contrapartida'] or 0)
                    valor_total_projeto = float(parceria['total_pago']) + total_rendimentos + contrapartida
                    saldos_remanescentes = valor_total_projeto - valor_exec_aprovado - despesas_glosa - taxas_nao_devolvidas
                    
                    valor_formatado = f"R$ {saldos_remanescentes:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
                    texto_processado = texto_processado.replace('valor_residual_usuario', valor_formatado)
            
            # INSERT único com ON CONFLICT incluindo texto processado
            cur.execute("""
                INSERT INTO analises_pc.lista_inconsistencias_globais (
                    nome_item,
                    numero_termo,
                    status,
                    usuario,
                    data_ratificacao,
                    texto
                ) VALUES (%s, %s, %s, %s, NOW(), %s)
                ON CONFLICT (numero_termo, nome_item)
                DO UPDATE SET
                    data_ratificacao = NOW(),
                    status = 'Não atendida',
                    texto = EXCLUDED.texto
            """, (nome_item, numero_termo, 'Não atendida', usuario, texto_processado))
            registros_inseridos = 1
            
            print(f"[DEBUG] Texto processado salvo: {texto_processado[:100]}...")
        
        elif id_inconsistencia in [21, 22]:  # Cards agregados com tabelas customizadas
            # ====================================================
            # TABELA: lista_inconsistencias_agregadas
            # ====================================================
            # Card 21: Ausência de aplicação em 48h (parcelas sem aplicação)
            # Card 22: Aplicação divergente (aplicações não-poupança)
            print(f"[DEBUG] Usando lista_inconsistencias_agregadas para card {id_inconsistencia}")
            print(f"[DEBUG] Total de transações para processar: {len(transacoes_para_ratificar)}")
            
            if len(transacoes_para_ratificar) > 0:
                # Preparar dados para batch INSERT
                values_list = []
                for idx, row in enumerate(transacoes_para_ratificar):
                    try:
                        # Log da estrutura da row
                        print(f"[DEBUG] Processando row {idx+1}: keys={list(row.keys())}")
                        
                        # Para Card 21 e 22: usar data como campo1, valor como campo2
                        data_obj = row.get('data')
                        if not data_obj:
                            print(f"[ERRO] Row {idx+1} não tem campo 'data': {row}")
                            continue
                        
                        data_str = data_obj.strftime('%Y-%m-%d') if hasattr(data_obj, 'strftime') else str(data_obj)
                        discriminacao_val = row.get('discriminacao', 0)
                        valor_str = str(discriminacao_val)
                        
                        print(f"[DEBUG] Row {idx+1} processada: data={data_str}, valor={valor_str}")
                        
                        values_list.append((
                            nome_item,
                            numero_termo,
                            'parcela_sem_aplicacao' if id_inconsistencia == 21 else 'aplicacao_divergente',
                            data_str,  # campo1: data
                            valor_str,  # campo2: valor
                            None,  # valor_previsto
                            discriminacao_val,  # valor_executado
                            discriminacao_val,  # diferenca
                            'Não atendida',
                            usuario
                        ))
                    except Exception as e:
                        print(f"[ERRO] Falha ao processar row {idx+1}: {e}")
                        print(f"[ERRO] Row data: {row}")
                        continue
                
                print(f"[DEBUG] Total de values preparados para INSERT: {len(values_list)}")
                
                if len(values_list) > 0:
                    # Batch INSERT com ON CONFLICT
                    execute_values(
                        cur,
                        """
                        INSERT INTO analises_pc.lista_inconsistencias_agregadas (
                            nome_item, numero_termo, tipo_agregacao,
                            campo1, campo2, valor_previsto, valor_executado, diferenca,
                            status, usuario
                        ) VALUES %s
                        ON CONFLICT (numero_termo, nome_item, campo1, campo2)
                        DO UPDATE SET
                            data_registro = NOW(),
                            status = 'Não atendida',
                            valor_executado = EXCLUDED.valor_executado,
                            diferenca = EXCLUDED.diferenca
                        """,
                        values_list
                    )
                    registros_inseridos = len(values_list)
                else:
                    print(f"[WARN] Nenhum valor válido para inserir no card {id_inconsistencia}")
                    registros_inseridos = 0
            else:
                print(f"[WARN] Nenhuma transação para ratificar no card {id_inconsistencia}")
                registros_inseridos = 0
        
        else:  # Cards com transações individuais
            # ====================================================
            # TABELA: lista_inconsistencias (padrão)
            # ====================================================
            print(f"[DEBUG] Usando lista_inconsistencias para card {id_inconsistencia}")
            
            if len(transacoes_para_ratificar) > 0:
                # Preparar dados para batch INSERT com verificação de campos obrigatórios
                values_list = []
                for t in transacoes_para_ratificar:
                    # Verificar se tem id_conc_extrato (obrigatório)
                    if 'id_conc_extrato' not in t or t['id_conc_extrato'] is None:
                        print(f"[WARN] Transação sem id_conc_extrato ignorada: {t}")
                        continue
                    
                    values_list.append((
                        nome_item,
                        t['id_conc_extrato'],
                        t.get('data'),
                        t.get('credito', 0),
                        t.get('debito', 0),
                        t.get('discriminacao'),
                        t.get('cat_transacao'),
                        t.get('competencia'),
                        t.get('origem_destino'),
                        'Não atendida',
                        numero_termo,
                        usuario
                    ))
                
                if values_list:
                    # Batch INSERT com ON CONFLICT
                    execute_values(
                        cur,
                        """
                        INSERT INTO analises_pc.lista_inconsistencias (
                            nome_item, id_conc_extrato, data, credito, debito,
                            discriminacao, cat_transacao, competencia, origem_destino,
                            status, numero_termo, usuario_registro
                        ) VALUES %s
                        ON CONFLICT (numero_termo, nome_item, id_conc_extrato)
                        DO UPDATE SET
                            data = EXCLUDED.data,
                            credito = EXCLUDED.credito,
                            debito = EXCLUDED.debito,
                            discriminacao = EXCLUDED.discriminacao,
                            status = 'Não atendida'
                        """,
                        values_list
                    )
                    registros_inseridos = len(values_list)
                else:
                    print(f"[WARN] Nenhuma transação válida para inserir (todas sem id_conc_extrato)")
        
        conn.commit()
        cur.close()
        
        print(f"[DEBUG] Ratificação concluída - {registros_inseridos} registro(s) com nome_item: {nome_item}")
        
        return jsonify({
            'sucesso': True,
            'registros_inseridos': registros_inseridos,
            'mensagem': f'{registros_inseridos} registro(s) adicionado(s) à lista de inconsistências'
        })
    
    except Exception as e:
        conn.rollback()
        cur.close()
        print(f"[ERRO] ratificar_inconsistencia: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@analises_pc_bp.route('/api/atualizar-status-inconsistencia', methods=['POST'])
def atualizar_status_inconsistencia():
    """
    Atualizar status de inconsistências ratificadas (manual ou automático).
    
    Suporta dois escopos:
    - 'card': Atualiza todas as transações do card
    - 'transaction': Atualiza apenas uma transação específica
    """
    try:
        data = request.get_json()
        nome_item = data.get('nome_item')
        numero_termo = data.get('numero_termo')
        novo_status = data.get('status')
        scope = data.get('scope', 'card')  # 'card' ou 'transaction'
        id_conc_extrato = data.get('id_conc_extrato')  # Apenas para scope='transaction'
        
        if not nome_item or not numero_termo or not novo_status:
            return jsonify({'erro': 'Parâmetros obrigatórios: nome_item, numero_termo, status'}), 400
        
        if novo_status not in ['Não atendida', 'Para análise', 'Atendida']:
            return jsonify({'erro': 'Status inválido. Use: Não atendida, Para análise ou Atendida'}), 400
        
        conn = get_db()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Determinar qual tabela usar baseado no nome_item
        # Buscar id_inconsistencia para determinar tipo de card
        cur.execute("""
            SELECT id FROM categoricas.c_dac_modelo_textos_inconsistencias
            WHERE nome_item = %s
        """, (nome_item,))
        result = cur.fetchone()
        
        if not result:
            cur.close()
            return jsonify({'erro': f'Inconsistência "{nome_item}" não encontrada no catálogo'}), 404
        
        id_inconsistencia = result['id']
        registros_atualizados = 0
        
        if id_inconsistencia in [17, 18]:  # Cards agregados
            # Atualizar em lista_inconsistencias_agregadas
            if scope == 'card':
                cur.execute("""
                    UPDATE analises_pc.lista_inconsistencias_agregadas
                    SET status = %s, data_registro = NOW()
                    WHERE numero_termo = %s AND nome_item = %s
                """, (novo_status, numero_termo, nome_item))
            else:
                # Para cards agregados não há scope transaction (não aplicável)
                cur.close()
                return jsonify({'erro': 'Escopo "transaction" não aplicável para cards agregados'}), 400
        
        elif id_inconsistencia in [1, 4, 20]:  # Cards globais
            # Atualizar em lista_inconsistencias_globais
            cur.execute("""
                UPDATE analises_pc.lista_inconsistencias_globais
                SET status = %s, data_ratificacao = NOW()
                WHERE numero_termo = %s AND nome_item = %s
            """, (novo_status, numero_termo, nome_item))
        
        else:  # Cards com transações individuais
            if scope == 'card':
                # Atualizar todas as transações do card
                cur.execute("""
                    UPDATE analises_pc.lista_inconsistencias
                    SET status = %s
                    WHERE numero_termo = %s AND nome_item = %s
                """, (novo_status, numero_termo, nome_item))
            elif scope == 'transaction':
                # Atualizar apenas uma transação específica
                if not id_conc_extrato:
                    cur.close()
                    return jsonify({'erro': 'id_conc_extrato obrigatório para scope "transaction"'}), 400
                
                cur.execute("""
                    UPDATE analises_pc.lista_inconsistencias
                    SET status = %s
                    WHERE numero_termo = %s AND nome_item = %s AND id_conc_extrato = %s
                """, (novo_status, numero_termo, nome_item, id_conc_extrato))
        
        registros_atualizados = cur.rowcount
        conn.commit()
        cur.close()
        
        print(f"[DEBUG] Status atualizado: {nome_item} → {novo_status} ({registros_atualizados} registro(s))")
        
        return jsonify({
            'sucesso': True,
            'registros_atualizados': registros_atualizados,
            'mensagem': f'Status atualizado para "{novo_status}" em {registros_atualizados} registro(s)'
        })
    
    except Exception as e:
        conn.rollback()
        cur.close()
        print(f"[ERRO] atualizar_status_inconsistencia: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500
