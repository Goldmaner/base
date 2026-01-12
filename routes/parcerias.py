"""
Blueprint de parcerias (listagem e formulário)
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, session
from db import get_cursor, get_db, execute_query
from utils import login_required
from decorators import requires_access
import csv
from io import StringIO, BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

parcerias_bp = Blueprint('parcerias', __name__, url_prefix='/parcerias')


@parcerias_bp.route("/", methods=["GET"])
@login_required
@requires_access('parcerias')
def listar():
    """
    Listagem de todas as parcerias/termos com filtros e busca
    """
    # Obter parâmetros de filtro e busca
    filtro_termo = request.args.get('filtro_termo', '').strip()
    filtro_osc = request.args.get('filtro_osc', '').strip()
    filtro_projeto = request.args.get('filtro_projeto', '').strip()
    filtro_tipo_termo = request.args.get('filtro_tipo_termo', '').strip()
    filtro_status = request.args.get('filtro_status', '').strip()
    filtro_pessoa_gestora = request.args.get('filtro_pessoa_gestora', '').strip()
    busca_sei_celeb = request.args.get('busca_sei_celeb', '').strip()
    busca_sei_pc = request.args.get('busca_sei_pc', '').strip()
    
    # Obter parâmetro de paginação (padrão: 100)
    limite = request.args.get('limite', '100')
    if limite == 'todas':
        limite_sql = None
    else:
        try:
            limite_sql = int(limite)
        except ValueError:
            limite_sql = 100
    
    cur = get_cursor()
    
    # Buscar tipos de contrato para o dropdown de filtro
    cur.execute("SELECT informacao FROM categoricas.c_geral_tipo_contrato ORDER BY informacao")
    tipos_contrato_raw = cur.fetchall()
    tipos_contrato = [row['informacao'] for row in tipos_contrato_raw]
    
    # Buscar pessoas gestoras para o dropdown de filtro (todas, incluindo inativas)
    cur.execute("SELECT DISTINCT nome_pg FROM categoricas.c_geral_pessoa_gestora ORDER BY nome_pg")
    pessoas_gestoras_filtro = [row['nome_pg'] for row in cur.fetchall()]
    
    # DEBUG: Verificar duplicação
    print(f"[DEBUG] Total de tipos_contrato retornados: {len(tipos_contrato)}")
    print(f"[DEBUG] Tipos únicos: {len(set(tipos_contrato))}")
    if len(tipos_contrato) != len(set(tipos_contrato)):
        print(f"[ALERTA] DUPLICAÇÃO DETECTADA em c_geral_tipo_contrato!")
        print(f"[DEBUG] Tipos com duplicação: {[t for t in tipos_contrato if tipos_contrato.count(t) > 1]}")
    
    # Query principal - buscar parcerias com datas como texto para evitar erro de conversão
    query = """
        SELECT
            p.numero_termo,
            p.osc,
            p.projeto,
            p.tipo_termo,
            p.inicio::text as inicio_str,
            p.final::text as final_str,
            p.meses,
            p.total_previsto,
            p.total_pago,
            p.sei_celeb,
            p.sei_pc,
            (SELECT pg.nome_pg 
             FROM parcerias_pg pg 
             WHERE pg.numero_termo = p.numero_termo 
             ORDER BY pg.data_de_criacao DESC 
             LIMIT 1) as pessoa_gestora,
            (SELECT cpg.status_pg 
             FROM parcerias_pg pg 
             LEFT JOIN categoricas.c_geral_pessoa_gestora cpg ON cpg.nome_pg = pg.nome_pg
             WHERE pg.numero_termo = p.numero_termo 
             ORDER BY pg.data_de_criacao DESC 
             LIMIT 1) as status_pg,
            (SELECT pg.solicitacao 
             FROM parcerias_pg pg 
             WHERE pg.numero_termo = p.numero_termo 
             ORDER BY pg.data_de_criacao DESC 
             LIMIT 1) as solicitacao
        FROM Parcerias p
        WHERE 1=1
    """
    
    params = []
    
    # Adicionar filtros se fornecidos
    if filtro_termo:
        query += " AND numero_termo ILIKE %s"
        params.append(f"%{filtro_termo}%")
    
    if filtro_osc:
        query += " AND osc ILIKE %s"
        params.append(f"%{filtro_osc}%")
    
    if filtro_projeto:
        query += " AND projeto ILIKE %s"
        params.append(f"%{filtro_projeto}%")
    
    if filtro_tipo_termo:
        query += " AND p.tipo_termo ILIKE %s"
        params.append(f"%{filtro_tipo_termo}%")
    
    if filtro_pessoa_gestora:
        if filtro_pessoa_gestora.lower() == 'nenhuma':
            # Filtrar parcerias que NÃO têm pessoa gestora
            query += """ AND NOT EXISTS (
                SELECT 1 FROM parcerias_pg pg 
                WHERE pg.numero_termo = p.numero_termo
            )"""
        elif filtro_pessoa_gestora.lower() == 'inativos':
            # Filtrar parcerias com pessoas gestoras inativas
            query += """ AND EXISTS (
                SELECT 1 FROM parcerias_pg pg 
                LEFT JOIN categoricas.c_geral_pessoa_gestora cpg ON cpg.nome_pg = pg.nome_pg
                WHERE pg.numero_termo = p.numero_termo 
                AND cpg.status_pg != 'Ativo'
                AND pg.data_de_criacao = (
                    SELECT MAX(data_de_criacao) 
                    FROM parcerias_pg 
                    WHERE numero_termo = p.numero_termo
                )
            )"""
        else:
            # Filtrar parcerias com pessoa gestora específica
            query += """ AND EXISTS (
                SELECT 1 FROM parcerias_pg pg 
                WHERE pg.numero_termo = p.numero_termo 
                AND pg.nome_pg ILIKE %s
                AND pg.data_de_criacao = (
                    SELECT MAX(data_de_criacao) 
                    FROM parcerias_pg 
                    WHERE numero_termo = p.numero_termo
                )
            )"""
            params.append(f"%{filtro_pessoa_gestora}%")
    
    if busca_sei_celeb:
        query += " AND sei_celeb ILIKE %s"
        params.append(f"%{busca_sei_celeb}%")
    
    if busca_sei_pc:
        query += " AND sei_pc ILIKE %s"
        params.append(f"%{busca_sei_pc}%")
    
    # Filtro de status baseado em datas
    # Vigente: inicio <= HOJE <= final
    # Encerrado: final < HOJE
    # Não iniciado: inicio > HOJE
    # Rescindido e Suspenso: deixar para depois (não filtrar por enquanto)
    if filtro_status:
        if filtro_status == 'vigente':
            query += " AND inicio <= CURRENT_DATE AND final >= CURRENT_DATE"
        elif filtro_status == 'encerrado':
            query += " AND final < CURRENT_DATE"
        elif filtro_status == 'nao_iniciado':
            query += " AND inicio > CURRENT_DATE"
        elif filtro_status in ['rescindido', 'suspenso']:
            # Por enquanto, não implementado - não retorna nada
            # No futuro, adicionar coluna de status na tabela
            query += " AND 1=0"  # Condição falsa para não retornar resultados
    
    query += " ORDER BY numero_termo"
    
    # Adicionar LIMIT se não for "todas"
    if limite_sql is not None:
        query += f" LIMIT {limite_sql}"
    
    print(f"[DEBUG] Executando query com filtro_termo: {filtro_termo}")
    cur.execute(query, params)
    
    try:
        parcerias = cur.fetchall()
        print(f"[DEBUG] {len(parcerias)} parcerias retornadas com sucesso")
        
        # Converter datas de string para date object
        from datetime import datetime
        for parceria in parcerias:
            try:
                if parceria['inicio_str']:
                    parceria['inicio'] = datetime.strptime(parceria['inicio_str'], '%Y-%m-%d').date()
                else:
                    parceria['inicio'] = None
            except (ValueError, TypeError) as e:
                print(f"[ERRO] Data inicio inválida para termo {parceria['numero_termo']}: {parceria['inicio_str']} - {e}")
                parceria['inicio'] = None
            
            try:
                if parceria['final_str']:
                    parceria['final'] = datetime.strptime(parceria['final_str'], '%Y-%m-%d').date()
                else:
                    parceria['final'] = None
            except (ValueError, TypeError) as e:
                print(f"[ERRO] Data final inválida para termo {parceria['numero_termo']}: {parceria['final_str']} - {e}")
                parceria['final'] = None
        
    except ValueError as e:
        print(f"[ERRO] Erro ao processar datas das parcerias: {e}")
        print(f"[DEBUG] Tentando identificar registro problemático...")
        
        # Re-executar query para buscar dados como texto
        query_debug = query.replace("p.inicio", "p.inicio::text as inicio_str, p.inicio")
        query_debug = query_debug.replace("p.final", "p.final::text as final_str, p.final")
        
        cur.execute(query_debug, params)
        try:
            for row in cur:
                print(f"[DEBUG] Termo: {row.get('numero_termo')} - Inicio: {row.get('inicio_str')} - Final: {row.get('final_str')}")
        except:
            pass
        
        # Retornar erro ao usuário
        cur.close()
        return render_template("parcerias.html", 
                             parcerias=[],
                             tipos_contrato=tipos_contrato,
                             pessoas_gestoras_filtro=pessoas_gestoras_filtro,
                             contagem_status={},
                             total_geral=0,
                             limite_atual=limite,
                             erro=f"Erro ao carregar parcerias: {str(e)}. Há uma data inválida no banco de dados.")
    
    # Calcular status para cada parceria
    from datetime import date
    hoje = date.today()
    contagem_status = {}
    
    for parceria in parcerias:
        status = '-'
        try:
            if parceria['inicio'] and parceria['final']:
                # Validar se as datas são objetos date válidos
                inicio = parceria['inicio']
                final = parceria['final']
                
                # Se forem strings, tentar converter
                if isinstance(inicio, str):
                    print(f"[AVISO] inicio como string: {inicio} para termo {parceria.get('numero_termo', 'N/A')}")
                if isinstance(final, str):
                    print(f"[AVISO] final como string: {final} para termo {parceria.get('numero_termo', 'N/A')}")
                
                if inicio <= hoje <= final:
                    status = 'Vigente'
                elif final < hoje:
                    status = 'Encerrado'
                elif inicio > hoje:
                    status = 'Não iniciado'
        except (TypeError, ValueError) as e:
            print(f"[ERRO] Erro ao calcular status para termo {parceria.get('numero_termo', 'N/A')}: {e}")
            print(f"[DEBUG] inicio={parceria.get('inicio')}, final={parceria.get('final')}")
            status = 'Erro'
        
        parceria['status_calculado'] = status
        
        # Contagem por status
        if status in contagem_status:
            contagem_status[status] += 1
        else:
            contagem_status[status] = 1
    
    # Obter total geral (sem filtros) para referência
    cur.execute("SELECT COUNT(*) as total FROM Parcerias")
    total_geral = cur.fetchone()['total']
    
    cur.close()
    
    # DEBUG: Verificar duplicação de parcerias
    print(f"[DEBUG] Total de parcerias retornadas: {len(parcerias)}")
    termos = [p['numero_termo'] for p in parcerias]
    print(f"[DEBUG] Termos únicos: {len(set(termos))}")
    if len(termos) != len(set(termos)):
        print(f"[ALERTA] DUPLICAÇÃO DETECTADA em Parcerias!")
        duplicados = [t for t in termos if termos.count(t) > 1]
        print(f"[DEBUG] Termos duplicados: {set(duplicados)}")
    
    return render_template("parcerias.html", 
                         parcerias=parcerias,
                         tipos_contrato=tipos_contrato,
                         pessoas_gestoras_filtro=pessoas_gestoras_filtro,
                         filtro_termo=filtro_termo,
                         filtro_osc=filtro_osc,
                         filtro_projeto=filtro_projeto,
                         filtro_tipo_termo=filtro_tipo_termo,
                         filtro_status=filtro_status,
                         filtro_pessoa_gestora=filtro_pessoa_gestora,
                         busca_sei_celeb=busca_sei_celeb,
                         busca_sei_pc=busca_sei_pc,
                         limite=limite,
                         contagem_status=contagem_status,
                         total_geral=total_geral)


@parcerias_bp.route("/nova", methods=["GET", "POST"])
@login_required
@requires_access('parcerias')
def nova():
    """
    Criar nova parceria
    """
    if request.method == "POST":
        print("[DEBUG NOVA] Recebendo POST para criar nova parceria")
        print(f"[DEBUG NOVA] Número do termo: {request.form.get('numero_termo')}")
        
        # Validar datas antes de processar
        data_inicio = request.form.get('inicio', '').strip()
        data_final = request.form.get('final', '').strip()
        
        if data_inicio:
            try:
                from datetime import datetime
                dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
                if dt_inicio.year > 9999:
                    flash('❌ Data de início inválida! O ano não pode ultrapassar 9999. Por favor, corrija a data.', 'danger')
                    return redirect(url_for('parcerias.nova'))
            except ValueError:
                flash('❌ Data de início em formato inválido! Use o formato AAAA-MM-DD.', 'danger')
                return redirect(url_for('parcerias.nova'))
        
        if data_final:
            try:
                from datetime import datetime
                dt_final = datetime.strptime(data_final, '%Y-%m-%d')
                if dt_final.year > 9999:
                    flash('❌ Data de término inválida! O ano não pode ultrapassar 9999. Por favor, corrija a data.', 'danger')
                    return redirect(url_for('parcerias.nova'))
            except ValueError:
                flash('❌ Data de término em formato inválido! Use o formato AAAA-MM-DD.', 'danger')
                return redirect(url_for('parcerias.nova'))
        
        try:
            query = """
                INSERT INTO Parcerias (
                    numero_termo, osc, projeto, tipo_termo, portaria, cnpj,
                    inicio, final, meses, total_previsto, total_pago, conta,
                    transicao, sei_celeb, sei_pc, endereco, sei_plano, 
                    sei_orcamento, contrapartida
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            params = (
                request.form.get('numero_termo'),
                request.form.get('osc'),
                request.form.get('projeto'),
                request.form.get('tipo_termo'),
                request.form.get('portaria'),
                request.form.get('cnpj'),
                request.form.get('inicio') or None,
                request.form.get('final') or None,
                request.form.get('meses') or None,
                request.form.get('total_previsto_hidden') or request.form.get('total_previsto') or None,
                request.form.get('total_pago_hidden') or request.form.get('total_pago') or 0,
                request.form.get('conta'),
                1 if request.form.get('transicao') == 'on' else 0,
                request.form.get('sei_celeb'),
                request.form.get('sei_pc'),
                request.form.get('endereco'),
                request.form.get('sei_plano'),
                request.form.get('sei_orcamento'),
                1 if request.form.get('contrapartida') == 'on' else 0
            )
            
            print(f"[DEBUG NOVA] Parâmetros do INSERT: {params[:5]}...")  # Primeiros 5 para não lotar o log
            
            resultado_insert = execute_query(query, params)
            print(f"[DEBUG NOVA] Resultado do INSERT na Parcerias: {resultado_insert}")
            
            if resultado_insert:
                print("[DEBUG NOVA] INSERT bem-sucedido! Processando auditoria...")
                numero_termo = request.form.get('numero_termo')
                
                # === SALVAR INFORMAÇÕES ADICIONAIS ===
                try:
                    # Verificar se já existe registro
                    cur_check = get_cursor()
                    cur_check.execute(
                        "SELECT id FROM public.parcerias_infos_adicionais WHERE numero_termo = %s",
                        (numero_termo,)
                    )
                    exists = cur_check.fetchone()
                    cur_check.close()
                    
                    if exists:
                        # Atualizar registro existente
                        infos_query = """
                            UPDATE public.parcerias_infos_adicionais SET
                                parceria_responsavel_legal = %s,
                                parceria_objeto = %s,
                                parceria_beneficiarios_diretos = %s,
                                parceria_beneficiarios_indiretos = %s,
                                parceria_justificativa_projeto = %s,
                                parceria_abrangencia_projeto = %s,
                                parceria_data_suspensao = %s,
                                parceria_data_retomada = %s
                            WHERE numero_termo = %s
                        """
                        infos_params = (
                            request.form.get('parceria_responsavel_legal') or None,
                            request.form.get('parceria_objeto') or None,
                            request.form.get('parceria_beneficiarios_diretos') or None,
                            request.form.get('parceria_beneficiarios_indiretos') or None,
                            request.form.get('parceria_justificativa_projeto') or None,
                            request.form.get('parceria_abrangencia_projeto') or None,
                            request.form.get('parceria_data_suspensao') or None,
                            request.form.get('parceria_data_retomada') or None,
                            numero_termo
                        )
                    else:
                        # Inserir novo registro
                        infos_query = """
                            INSERT INTO public.parcerias_infos_adicionais (
                                numero_termo, parceria_responsavel_legal, parceria_objeto,
                                parceria_beneficiarios_diretos, parceria_beneficiarios_indiretos,
                                parceria_justificativa_projeto, parceria_abrangencia_projeto,
                                parceria_data_suspensao, parceria_data_retomada
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        infos_params = (
                            numero_termo,
                            request.form.get('parceria_responsavel_legal') or None,
                            request.form.get('parceria_objeto') or None,
                            request.form.get('parceria_beneficiarios_diretos') or None,
                            request.form.get('parceria_beneficiarios_indiretos') or None,
                            request.form.get('parceria_justificativa_projeto') or None,
                            request.form.get('parceria_abrangencia_projeto') or None,
                            request.form.get('parceria_data_suspensao') or None,
                            request.form.get('parceria_data_retomada') or None
                        )
                    
                    execute_query(infos_query, infos_params)
                    print(f"[DEBUG NOVA] Informações adicionais salvas para {numero_termo}")
                except Exception as e:
                    print(f"[ERRO] Falha ao salvar informações adicionais: {e}")
                
                # === SALVAR ENDEREÇOS ===
                try:
                    # Deletar endereços existentes (caso seja uma atualização)
                    delete_enderecos = "DELETE FROM public.parcerias_enderecos WHERE numero_termo = %s"
                    execute_query(delete_enderecos, (numero_termo,))
                    
                    # Verificar se projeto é online
                    projeto_online = request.form.get('projeto_online') == 'on'
                    
                    if not projeto_online:
                        # Pegar todos os endereços (arrays do formulário)
                        logradouros = request.form.getlist('parceria_logradouro[]')
                        numeros = request.form.getlist('parceria_numero[]')
                        complementos = request.form.getlist('parceria_complemento[]')
                        ceps = request.form.getlist('parceria_cep[]')
                        distritos = request.form.getlist('parceria_distrito[]')
                        observacoes = request.form.getlist('observacao[]')
                        
                        # Inserir cada endereço
                        for idx, logradouro in enumerate(logradouros):
                            if logradouro:  # Só insere se logradouro foi preenchido
                                endereco_query = """
                                    INSERT INTO public.parcerias_enderecos (
                                        numero_termo, parceria_logradouro, parceria_complemento, parceria_numero,
                                        parceria_cep, parceria_distrito, observacao
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """
                                endereco_params = (
                                    numero_termo,
                                    logradouro,
                                    complementos[idx] if idx < len(complementos) else None,
                                    numeros[idx] if idx < len(numeros) else None,
                                    ceps[idx] if idx < len(ceps) else None,
                                    distritos[idx] if idx < len(distritos) else None,
                                    observacoes[idx] if idx < len(observacoes) else None
                                )
                                execute_query(endereco_query, endereco_params)
                        
                        print(f"[DEBUG NOVA] {len(logradouros)} endereço(s) salvo(s) para {numero_termo}")
                except Exception as e:
                    print(f"[ERRO] Falha ao salvar endereços: {e}")
                
                # Salvar/atualizar termo_sei_doc em parcerias_sei se fornecido
                termo_sei_doc = request.form.get('termo_sei_doc', '').strip()
                
                if termo_sei_doc:
                    try:
                        # Verificar se já existe registro para este termo
                        check_query = """
                            SELECT id FROM public.parcerias_sei 
                            WHERE numero_termo = %s AND aditamento = '-' AND apostilamento = '-'
                        """
                        cur_check = get_cursor()
                        cur_check.execute(check_query, (numero_termo,))
                        exists = cur_check.fetchone()
                        cur_check.close()
                        
                        if exists:
                            # Atualizar termo_sei_doc existente
                            update_sei_query = """
                                UPDATE public.parcerias_sei 
                                SET termo_sei_doc = %s
                                WHERE numero_termo = %s AND aditamento = '-' AND apostilamento = '-'
                            """
                            execute_query(update_sei_query, (termo_sei_doc, numero_termo))
                            print(f"[DEBUG NOVA] termo_sei_doc atualizado em parcerias_sei: {termo_sei_doc}")
                        else:
                            # Inserir novo registro
                            insert_sei_query = """
                                INSERT INTO public.parcerias_sei (numero_termo, termo_sei_doc, aditamento, apostilamento)
                                VALUES (%s, %s, '-', '-')
                            """
                            execute_query(insert_sei_query, (numero_termo, termo_sei_doc))
                            print(f"[DEBUG NOVA] Novo registro criado em parcerias_sei com termo_sei_doc: {termo_sei_doc}")
                    except Exception as e:
                        print(f"[ERRO] Falha ao salvar termo_sei_doc: {e}")
                
                # Registrar na tabela de auditoria parcerias_pg
                pessoa_gestora = request.form.get('pessoa_gestora')
                solicitacao_checkbox = request.form.get('solicitacao_alteracao')
                solicitacao = True if solicitacao_checkbox == 'on' else False
                
                # DEBUG
                print(f"[DEBUG NOVA] Checkbox solicitacao_alteracao: {solicitacao_checkbox}")
                print(f"[DEBUG NOVA] Valor solicitacao: {solicitacao}")
                print(f"[DEBUG NOVA] Pessoa gestora: {pessoa_gestora}")
                
                if pessoa_gestora:  # Só registrar se foi selecionada uma pessoa gestora
                    from flask import session
                    usuario_id = session.get('user_id')  # ID do usuário logado
                    
                    audit_query = """
                        INSERT INTO parcerias_pg (numero_termo, nome_pg, usuario_id, dado_anterior, solicitacao)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    print(f"[DEBUG NOVA] Executando INSERT com solicitacao={solicitacao}")
                    resultado = execute_query(audit_query, (numero_termo, pessoa_gestora, usuario_id, None, solicitacao))
                    print(f"[DEBUG NOVA] Resultado INSERT parcerias_pg: {resultado}")
                
                print("[DEBUG NOVA] Enviando flash de sucesso e redirecionando...")
                flash("Parceria criada com sucesso!", "success")
                
                # Verificar se veio da página de conferência
                origem = request.form.get('origem_conferencia')
                if origem == 'conferencia':
                    # Redirecionar para conferência e atualizar
                    return redirect(url_for('parcerias.conferencia_pos_insercao'))
                else:
                    return redirect(url_for('parcerias.nova'))
            else:
                print("[DEBUG NOVA] FALHA no INSERT! execute_query retornou False")
                flash("Erro ao criar parceria no banco de dados!", "danger")
            
        except Exception as e:
            print(f"[DEBUG NOVA] EXCEÇÃO capturada: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
            flash(f"Erro ao criar parceria: {str(e)}", "danger")
    
    # GET - retornar formulário vazio (ou com dados pré-preenchidos da conferência)
    # Buscar dados dos dropdowns
    cur = get_cursor()
    cur.execute("SELECT informacao FROM categoricas.c_geral_tipo_contrato ORDER BY informacao")
    tipos_contrato = [row['informacao'] for row in cur.fetchall()]
    cur.execute("SELECT lei FROM categoricas.c_geral_legislacao ORDER BY lei")
    legislacoes = [row['lei'] for row in cur.fetchall()]
    
    # Buscar pessoas gestoras (todas, incluindo inativas)
    cur.execute("SELECT nome_pg, numero_rf, status_pg FROM categoricas.c_geral_pessoa_gestora ORDER BY nome_pg")
    pessoas_gestoras = cur.fetchall()
    
    cur.close()
    
    # Verificar se há parâmetros na query string (vindo da conferência)
    numero_termo_param = request.args.get('numero_termo', '')
    osc_param = request.args.get('osc', '')
    
    # Buscar termo_sei_doc se houver numero_termo
    termo_sei_doc = None
    if numero_termo_param:
        try:
            cur_sei = get_cursor()
            cur_sei.execute("""
                SELECT termo_sei_doc 
                FROM public.parcerias_sei 
                WHERE numero_termo = %s AND aditamento = '-' AND apostilamento = '-'
            """, (numero_termo_param,))
            result_sei = cur_sei.fetchone()
            cur_sei.close()
            if result_sei:
                termo_sei_doc = result_sei['termo_sei_doc']
        except Exception as e:
            print(f"[ERRO] Falha ao buscar termo_sei_doc: {e}")
    
    # Criar objeto parceria com dados pré-preenchidos
    parceria_preenchida = {
        'numero_termo': numero_termo_param,
        'osc': osc_param,
        'cnpj': ''  # Será preenchido via JavaScript no frontend
    }
    
    # Buscar informações adicionais e endereços (vazios para nova)
    infos_adicionais = {}
    enderecos = []
    projeto_online = False
    
    return render_template("parcerias_form.html", 
                         parceria=parceria_preenchida,
                         tipos_contrato=tipos_contrato,
                         legislacoes=legislacoes,
                         pessoas_gestoras=pessoas_gestoras,
                         rf_pessoa_gestora=None,
                         termo_sei_doc=termo_sei_doc,
                         infos_adicionais=infos_adicionais,
                         enderecos=enderecos,
                         projeto_online=projeto_online,
                         modo_importacao=True if numero_termo_param else False)


@parcerias_bp.route("/editar/<path:numero_termo>", methods=["GET", "POST"])
@login_required
@requires_access('parcerias')
def editar(numero_termo):
    """
    Formulário completo de edição de parceria
    """
    if request.method == "POST":
        # Validar datas antes de processar
        data_inicio = request.form.get('inicio', '').strip()
        data_final = request.form.get('final', '').strip()
        
        if data_inicio:
            try:
                from datetime import datetime
                dt_inicio = datetime.strptime(data_inicio, '%Y-%m-%d')
                if dt_inicio.year > 9999:
                    flash('❌ Data de início inválida! O ano não pode ultrapassar 9999. Por favor, corrija a data.', 'danger')
                    return redirect(url_for('parcerias.editar', numero_termo=numero_termo))
            except ValueError:
                flash('❌ Data de início em formato inválido! Use o formato AAAA-MM-DD.', 'danger')
                return redirect(url_for('parcerias.editar', numero_termo=numero_termo))
        
        if data_final:
            try:
                from datetime import datetime
                dt_final = datetime.strptime(data_final, '%Y-%m-%d')
                if dt_final.year > 9999:
                    flash('❌ Data de término inválida! O ano não pode ultrapassar 9999. Por favor, corrija a data.', 'danger')
                    return redirect(url_for('parcerias.editar', numero_termo=numero_termo))
            except ValueError:
                flash('❌ Data de término em formato inválido! Use o formato AAAA-MM-DD.', 'danger')
                return redirect(url_for('parcerias.editar', numero_termo=numero_termo))
        
        # Buscar valor anterior da pessoa_gestora para auditoria
        cur = get_cursor()
        cur.execute("""
            SELECT nome_pg FROM parcerias_pg 
            WHERE numero_termo = %s 
            ORDER BY data_de_criacao DESC 
            LIMIT 1
        """, (numero_termo,))
        resultado = cur.fetchone()
        pessoa_gestora_anterior = resultado['nome_pg'] if resultado else None
        cur.close()
        
        # Atualizar os dados da parceria
        try:
            query = """
                UPDATE Parcerias SET
                    osc = %s,
                    projeto = %s,
                    tipo_termo = %s,
                    portaria = %s,
                    cnpj = %s,
                    inicio = %s,
                    final = %s,
                    meses = %s,
                    total_previsto = %s,
                    total_pago = %s,
                    conta = %s,
                    transicao = %s,
                    sei_celeb = %s,
                    sei_pc = %s,
                    endereco = %s,
                    sei_plano = %s,
                    sei_orcamento = %s,
                    contrapartida = %s
                WHERE numero_termo = %s
            """
            
            pessoa_gestora_nova = request.form.get('pessoa_gestora') or None
            
            params = (
                request.form.get('osc'),
                request.form.get('projeto'),
                request.form.get('tipo_termo'),
                request.form.get('portaria'),
                request.form.get('cnpj'),
                request.form.get('inicio') or None,
                request.form.get('final') or None,
                request.form.get('meses') or None,
                request.form.get('total_previsto_hidden') or request.form.get('total_previsto') or None,
                request.form.get('total_pago_hidden') or request.form.get('total_pago') or 0,
                request.form.get('conta'),
                1 if request.form.get('transicao') == 'on' else 0,
                request.form.get('sei_celeb'),
                request.form.get('sei_pc'),
                request.form.get('endereco'),
                request.form.get('sei_plano'),
                request.form.get('sei_orcamento'),
                1 if request.form.get('contrapartida') == 'on' else 0,
                numero_termo
            )
            
            if execute_query(query, params):
                # === SALVAR INFORMAÇÕES ADICIONAIS ===
                try:
                    # Verificar se já existe registro
                    cur_check = get_cursor()
                    cur_check.execute(
                        "SELECT id FROM public.parcerias_infos_adicionais WHERE numero_termo = %s",
                        (numero_termo,)
                    )
                    exists = cur_check.fetchone()
                    cur_check.close()
                    
                    if exists:
                        # Atualizar registro existente
                        infos_query = """
                            UPDATE public.parcerias_infos_adicionais SET
                                parceria_responsavel_legal = %s,
                                parceria_objeto = %s,
                                parceria_beneficiarios_diretos = %s,
                                parceria_beneficiarios_indiretos = %s,
                                parceria_justificativa_projeto = %s,
                                parceria_abrangencia_projeto = %s,
                                parceria_data_suspensao = %s,
                                parceria_data_retomada = %s
                            WHERE numero_termo = %s
                        """
                        infos_params = (
                            request.form.get('parceria_responsavel_legal') or None,
                            request.form.get('parceria_objeto') or None,
                            request.form.get('parceria_beneficiarios_diretos') or None,
                            request.form.get('parceria_beneficiarios_indiretos') or None,
                            request.form.get('parceria_justificativa_projeto') or None,
                            request.form.get('parceria_abrangencia_projeto') or None,
                            request.form.get('parceria_data_suspensao') or None,
                            request.form.get('parceria_data_retomada') or None,
                            numero_termo
                        )
                    else:
                        # Inserir novo registro
                        infos_query = """
                            INSERT INTO public.parcerias_infos_adicionais (
                                numero_termo, parceria_responsavel_legal, parceria_objeto,
                                parceria_beneficiarios_diretos, parceria_beneficiarios_indiretos,
                                parceria_justificativa_projeto, parceria_abrangencia_projeto,
                                parceria_data_suspensao, parceria_data_retomada
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        infos_params = (
                            numero_termo,
                            request.form.get('parceria_responsavel_legal') or None,
                            request.form.get('parceria_objeto') or None,
                            request.form.get('parceria_beneficiarios_diretos') or None,
                            request.form.get('parceria_beneficiarios_indiretos') or None,
                            request.form.get('parceria_justificativa_projeto') or None,
                            request.form.get('parceria_abrangencia_projeto') or None,
                            request.form.get('parceria_data_suspensao') or None,
                            request.form.get('parceria_data_retomada') or None
                        )
                    
                    execute_query(infos_query, infos_params)
                    print(f"[DEBUG EDITAR] Informações adicionais salvas para {numero_termo}")
                except Exception as e:
                    print(f"[ERRO] Falha ao salvar informações adicionais: {e}")
                
                # === SALVAR ENDEREÇOS ===
                try:
                    # Deletar endereços existentes
                    delete_enderecos = "DELETE FROM public.parcerias_enderecos WHERE numero_termo = %s"
                    execute_query(delete_enderecos, (numero_termo,))
                    
                    # Verificar se projeto é online
                    projeto_online = request.form.get('projeto_online') == 'on'
                    
                    if not projeto_online:
                        # Pegar todos os endereços (arrays do formulário)
                        logradouros = request.form.getlist('parceria_logradouro[]')
                        numeros = request.form.getlist('parceria_numero[]')
                        complementos = request.form.getlist('parceria_complemento[]')
                        ceps = request.form.getlist('parceria_cep[]')
                        distritos = request.form.getlist('parceria_distrito[]')
                        observacoes = request.form.getlist('observacao[]')
                        
                        # Inserir cada endereço
                        for idx, logradouro in enumerate(logradouros):
                            if logradouro:  # Só insere se logradouro foi preenchido
                                endereco_query = """
                                    INSERT INTO public.parcerias_enderecos (
                                        numero_termo, parceria_logradouro, parceria_complemento, parceria_numero,
                                        parceria_cep, parceria_distrito, observacao
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """
                                endereco_params = (
                                    numero_termo,
                                    logradouro,
                                    complementos[idx] if idx < len(complementos) else None,
                                    numeros[idx] if idx < len(numeros) else None,
                                    ceps[idx] if idx < len(ceps) else None,
                                    distritos[idx] if idx < len(distritos) else None,
                                    observacoes[idx] if idx < len(observacoes) else None
                                )
                                execute_query(endereco_query, endereco_params)
                        
                        print(f"[DEBUG EDITAR] {len(logradouros)} endereço(s) salvo(s) para {numero_termo}")
                except Exception as e:
                    print(f"[ERRO] Falha ao salvar endereços: {e}")
                
                # Salvar/atualizar termo_sei_doc em parcerias_sei se fornecido
                termo_sei_doc = request.form.get('termo_sei_doc', '').strip()
                
                if termo_sei_doc:
                    try:
                        # Verificar se já existe registro para este termo
                        cur_check = get_cursor()
                        cur_check.execute("""
                            SELECT id FROM public.parcerias_sei 
                            WHERE numero_termo = %s AND aditamento = '-' AND apostilamento = '-'
                        """, (numero_termo,))
                        exists = cur_check.fetchone()
                        cur_check.close()
                        
                        if exists:
                            # Atualizar termo_sei_doc existente
                            update_sei_query = """
                                UPDATE public.parcerias_sei 
                                SET termo_sei_doc = %s
                                WHERE numero_termo = %s AND aditamento = '-' AND apostilamento = '-'
                            """
                            execute_query(update_sei_query, (termo_sei_doc, numero_termo))
                            print(f"[DEBUG EDITAR] termo_sei_doc atualizado em parcerias_sei: {termo_sei_doc}")
                        else:
                            # Inserir novo registro
                            insert_sei_query = """
                                INSERT INTO public.parcerias_sei (numero_termo, termo_sei_doc, aditamento, apostilamento)
                                VALUES (%s, %s, '-', '-')
                            """
                            execute_query(insert_sei_query, (numero_termo, termo_sei_doc))
                            print(f"[DEBUG EDITAR] Novo registro criado em parcerias_sei com termo_sei_doc: {termo_sei_doc}")
                    except Exception as e:
                        print(f"[ERRO] Falha ao salvar termo_sei_doc em editar: {e}")
                
                # Registrar na tabela de auditoria parcerias_pg se houve mudança
                solicitacao_checkbox = request.form.get('solicitacao_alteracao')
                solicitacao = True if solicitacao_checkbox == 'on' else False
                
                # DEBUG
                print(f"[DEBUG EDITAR] Checkbox solicitacao_alteracao: {solicitacao_checkbox}")
                print(f"[DEBUG EDITAR] Valor solicitacao: {solicitacao}")
                print(f"[DEBUG EDITAR] Pessoa gestora nova: {pessoa_gestora_nova}")
                print(f"[DEBUG EDITAR] Pessoa gestora anterior: {pessoa_gestora_anterior}")
                
                if pessoa_gestora_nova != pessoa_gestora_anterior:
                    from flask import session
                    usuario_id = session.get('user_id')
                    
                    print(f"[DEBUG EDITAR] Pessoa gestora MUDOU - criando novo registro")
                    audit_query = """
                        INSERT INTO parcerias_pg (numero_termo, nome_pg, usuario_id, dado_anterior, solicitacao)
                        VALUES (%s, %s, %s, %s, %s)
                    """
                    resultado = execute_query(audit_query, (numero_termo, pessoa_gestora_nova, usuario_id, pessoa_gestora_anterior, solicitacao))
                    print(f"[DEBUG EDITAR] Resultado INSERT (mudou PG): {resultado}")
                elif pessoa_gestora_nova:
                    # Se a pessoa gestora não mudou mas a checkbox mudou, atualizar apenas o flag
                    from flask import session
                    usuario_id = session.get('user_id')
                    
                    print(f"[DEBUG EDITAR] Pessoa gestora NÃO mudou - verificando solicitacao")
                    # Verificar o estado atual de solicitacao
                    cur = get_cursor()
                    cur.execute("""
                        SELECT solicitacao FROM parcerias_pg 
                        WHERE numero_termo = %s 
                        ORDER BY data_de_criacao DESC 
                        LIMIT 1
                    """, (numero_termo,))
                    resultado = cur.fetchone()
                    solicitacao_anterior = resultado['solicitacao'] if resultado else False
                    cur.close()
                    
                    print(f"[DEBUG EDITAR] Solicitacao anterior: {solicitacao_anterior}")
                    print(f"[DEBUG EDITAR] Solicitacao nova: {solicitacao}")
                    
                    # Se mudou, criar novo registro
                    if solicitacao != solicitacao_anterior:
                        print(f"[DEBUG EDITAR] Solicitacao MUDOU - criando novo registro")
                        audit_query = """
                            INSERT INTO parcerias_pg (numero_termo, nome_pg, usuario_id, dado_anterior, solicitacao)
                            VALUES (%s, %s, %s, %s, %s)
                        """
                        resultado_insert = execute_query(audit_query, (numero_termo, pessoa_gestora_nova, usuario_id, pessoa_gestora_anterior, solicitacao))
                        print(f"[DEBUG EDITAR] Resultado INSERT (mudou solicitacao): {resultado_insert}")
                    else:
                        print(f"[DEBUG EDITAR] Solicitacao NÃO mudou - nenhum registro criado")
                
                flash("Parceria atualizada com sucesso!", "success")
                return redirect(url_for('parcerias.listar'))
            else:
                flash("Erro ao atualizar parceria no banco de dados!", "danger")
            
        except Exception as e:
            flash(f"Erro ao atualizar parceria: {str(e)}", "danger")
    
    # GET - buscar dados da parceria
    cur = get_cursor()
    cur.execute("""
        SELECT 
            numero_termo,
            osc,
            projeto,
            tipo_termo,
            portaria,
            cnpj,
            inicio,
            final,
            meses,
            total_previsto,
            total_pago,
            conta,
            transicao,
            sei_celeb,
            sei_pc,
            endereco,
            sei_plano,
            sei_orcamento,
            contrapartida
        FROM Parcerias
        WHERE numero_termo = %s
    """, (numero_termo,))
    
    parceria = cur.fetchone()
    
    if not parceria:
        cur.close()
        flash("Parceria não encontrada!", "danger")
        return redirect(url_for('parcerias.listar'))
    
    # Buscar pessoa gestora atual de parcerias_pg
    cur.execute("""
        SELECT nome_pg, solicitacao FROM parcerias_pg 
        WHERE numero_termo = %s 
        ORDER BY data_de_criacao DESC 
        LIMIT 1
    """, (numero_termo,))
    pg_result = cur.fetchone()
    
    # Adicionar pessoa_gestora e solicitacao ao dicionário parceria
    if pg_result:
        parceria = dict(parceria)
        parceria['pessoa_gestora'] = pg_result['nome_pg']
        parceria['solicitacao'] = pg_result['solicitacao']
    
    # Buscar dados dos dropdowns
    cur.execute("SELECT informacao FROM categoricas.c_geral_tipo_contrato ORDER BY informacao")
    tipos_contrato = [row['informacao'] for row in cur.fetchall()]
    cur.execute("SELECT lei FROM categoricas.c_geral_legislacao ORDER BY lei")
    legislacoes = [row['lei'] for row in cur.fetchall()]
    
    # Buscar pessoas gestoras (todas, incluindo inativas)
    cur.execute("SELECT nome_pg, numero_rf, status_pg FROM categoricas.c_geral_pessoa_gestora ORDER BY nome_pg")
    pessoas_gestoras = cur.fetchall()
    
    # Buscar RF da pessoa gestora atual se existir
    rf_pessoa_gestora = None
    if pg_result:
        cur.execute("SELECT numero_rf FROM categoricas.c_geral_pessoa_gestora WHERE nome_pg = %s", (pg_result['nome_pg'],))
        rf_result = cur.fetchone()
        if rf_result:
            rf_pessoa_gestora = rf_result['numero_rf']
    
    # Buscar informações de rescisão
    cur.execute("""
        SELECT data_rescisao 
        FROM public.termos_rescisao 
        WHERE TRIM(numero_termo) = TRIM(%s)
    """, (numero_termo,))
    rescisao_result = cur.fetchone()
    
    data_rescisao = None
    termo_rescindido = False
    if rescisao_result and rescisao_result['data_rescisao']:
        termo_rescindido = True
        data_rescisao = rescisao_result['data_rescisao']
    
    # Buscar termo_sei_doc de parcerias_sei
    termo_sei_doc = None
    try:
        cur_sei = get_cursor()
        cur_sei.execute("""
            SELECT termo_sei_doc 
            FROM public.parcerias_sei 
            WHERE numero_termo = %s AND aditamento = '-' AND apostilamento = '-'
        """, (numero_termo,))
        result_sei = cur_sei.fetchone()
        cur_sei.close()
        if result_sei:
            termo_sei_doc = result_sei['termo_sei_doc']
    except Exception as e:
        print(f"[ERRO] Falha ao buscar termo_sei_doc em editar: {e}")
    
    # Buscar informações adicionais
    cur.execute("""
        SELECT parceria_responsavel_legal, parceria_objeto, parceria_beneficiarios_diretos, 
               parceria_beneficiarios_indiretos, parceria_justificativa_projeto, 
               parceria_abrangencia_projeto, parceria_data_suspensao, parceria_data_retomada
        FROM public.parcerias_infos_adicionais
        WHERE numero_termo = %s
    """, (numero_termo,))
    infos_result = cur.fetchone()
    infos_adicionais = dict(infos_result) if infos_result else {}
    
    # Buscar endereços
    cur.execute("""
        SELECT e.id, e.parceria_logradouro, e.parceria_numero, e.parceria_complemento, 
               e.parceria_cep, e.parceria_distrito, e.observacao,
               r.distrito as distrito_nome, r.subprefeitura, r.regiao
        FROM public.parcerias_enderecos e
        LEFT JOIN categoricas.c_geral_regionalizacao r ON e.parceria_distrito = r.codigo_distrital
        WHERE e.numero_termo = %s
        ORDER BY e.id
    """, (numero_termo,))
    enderecos = cur.fetchall()
    
    # Verificar se é projeto online
    projeto_online = False
    if enderecos and len(enderecos) == 1 and enderecos[0].get('observacao') == 'Projeto Online':
        projeto_online = True
    
    cur.close()
    
    return render_template("parcerias_form.html", 
                         parceria=parceria,
                         tipos_contrato=tipos_contrato,
                         legislacoes=legislacoes,
                         pessoas_gestoras=pessoas_gestoras,
                         rf_pessoa_gestora=rf_pessoa_gestora,
                         termo_sei_doc=termo_sei_doc,
                         infos_adicionais=infos_adicionais,
                         enderecos=enderecos,
                         projeto_online=projeto_online,
                         termo_rescindido=termo_rescindido,
                         data_rescisao=data_rescisao)


@parcerias_bp.route("/api/oscs", methods=["GET"])
@login_required
@requires_access('parcerias')
def api_oscs():
    """
    API para buscar lista de OSCs únicas para autocomplete
    """
    from flask import jsonify
    
    cur = get_cursor()
    cur.execute("""
        SELECT DISTINCT osc, cnpj 
        FROM Parcerias 
        WHERE osc IS NOT NULL AND osc != ''
        ORDER BY osc
    """)
    oscs = cur.fetchall()
    cur.close()
    
    # Criar dicionário com OSC e CNPJ
    result = {}
    for row in oscs:
        if row['osc']:
            result[row['osc']] = row['cnpj'] or ''
    
    return jsonify(result)


@parcerias_bp.route("/api/sigla-tipo-termo", methods=["GET"])
@login_required
@requires_access('parcerias')
def api_sigla_tipo_termo():
    """
    API para buscar mapeamento de siglas para tipos de termo
    """
    from flask import jsonify
    
    cur = get_cursor()
    cur.execute("SELECT id, informacao, sigla FROM categoricas.c_geral_tipo_contrato ORDER BY sigla")
    tipos = cur.fetchall()
    cur.close()
    
    # Criar mapeamento sigla -> tipo
    mapeamento = {}
    for row in tipos:
        if row['sigla']:
            mapeamento[row['sigla'].upper()] = row['informacao']
    
    return jsonify(mapeamento)


@parcerias_bp.route("/exportar-csv", methods=["GET"])
@login_required
@requires_access('parcerias')
def exportar_csv():
    """
    Exporta parcerias para CSV respeitando os filtros aplicados
    """
    try:
        # Obter os mesmos parâmetros de filtro da listagem
        filtro_termo = request.args.get('filtro_termo', '').strip()
        filtro_osc = request.args.get('filtro_osc', '').strip()
        filtro_projeto = request.args.get('filtro_projeto', '').strip()
        filtro_tipo_termo = request.args.get('filtro_tipo_termo', '').strip()
        filtro_status = request.args.get('filtro_status', '').strip()
        filtro_pessoa_gestora = request.args.get('filtro_pessoa_gestora', '').strip()
        busca_sei_celeb = request.args.get('busca_sei_celeb', '').strip()
        busca_sei_pc = request.args.get('busca_sei_pc', '').strip()
        
        cur = get_cursor()
        
        # Construir query com filtros (mesma lógica da listagem)
        query = """
            SELECT 
                p.numero_termo,
                p.tipo_termo,
                p.osc,
                p.cnpj,
                p.projeto,
                p.portaria,
                p.inicio,
                p.final,
                p.meses,
                p.total_previsto,
                p.sei_celeb,
                p.sei_pc,
                p.sei_plano,
                p.sei_orcamento,
                p.transicao,
                (SELECT pg.nome_pg 
                 FROM parcerias_pg pg 
                 WHERE pg.numero_termo = p.numero_termo 
                 ORDER BY pg.data_de_criacao DESC 
                 LIMIT 1) as pessoa_gestora,
                (SELECT pg.solicitacao 
                 FROM parcerias_pg pg 
                 WHERE pg.numero_termo = p.numero_termo 
                 ORDER BY pg.data_de_criacao DESC 
                 LIMIT 1) as solicitacao
            FROM Parcerias p
            WHERE 1=1
        """
        
        params = []
        
        # Adicionar filtros se fornecidos
        if filtro_termo:
            query += " AND p.numero_termo ILIKE %s"
            params.append(f"%{filtro_termo}%")
        
        if filtro_osc:
            query += " AND p.osc ILIKE %s"
            params.append(f"%{filtro_osc}%")
        
        if filtro_projeto:
            query += " AND p.projeto ILIKE %s"
            params.append(f"%{filtro_projeto}%")
        
        if filtro_tipo_termo:
            query += " AND p.tipo_termo ILIKE %s"
            params.append(f"%{filtro_tipo_termo}%")
        
        if filtro_pessoa_gestora:
            if filtro_pessoa_gestora.lower() == 'nenhuma':
                query += """ AND NOT EXISTS (
                    SELECT 1 FROM parcerias_pg pg 
                    WHERE pg.numero_termo = p.numero_termo
                )"""
            elif filtro_pessoa_gestora.lower() == 'inativos':
                query += """ AND EXISTS (
                    SELECT 1 FROM parcerias_pg pg 
                    LEFT JOIN categoricas.c_geral_pessoa_gestora cpg ON cpg.nome_pg = pg.nome_pg
                    WHERE pg.numero_termo = p.numero_termo 
                    AND cpg.status_pg != 'Ativo'
                    AND pg.data_de_criacao = (
                        SELECT MAX(data_de_criacao) 
                        FROM parcerias_pg 
                        WHERE numero_termo = p.numero_termo
                    )
                )"""
            else:
                query += """ AND EXISTS (
                    SELECT 1 FROM parcerias_pg pg 
                    WHERE pg.numero_termo = p.numero_termo 
                    AND pg.nome_pg ILIKE %s
                    AND pg.data_de_criacao = (
                        SELECT MAX(data_de_criacao) 
                        FROM parcerias_pg 
                        WHERE numero_termo = p.numero_termo
                    )
                )"""
                params.append(f"%{filtro_pessoa_gestora}%")
        
        if busca_sei_celeb:
            query += " AND p.sei_celeb ILIKE %s"
            params.append(f"%{busca_sei_celeb}%")
        
        if busca_sei_pc:
            query += " AND p.sei_pc ILIKE %s"
            params.append(f"%{busca_sei_pc}%")
        
        # Filtro de status baseado em datas
        if filtro_status:
            if filtro_status == 'vigente':
                query += " AND p.inicio <= CURRENT_DATE AND p.final >= CURRENT_DATE"
            elif filtro_status == 'encerrado':
                query += " AND p.final < CURRENT_DATE"
            elif filtro_status == 'nao_iniciado':
                query += " AND p.inicio > CURRENT_DATE"
            elif filtro_status in ['rescindido', 'suspenso']:
                query += " AND 1=0"  # Condição falsa para não retornar resultados
        
        query += " ORDER BY p.numero_termo"
        
        cur.execute(query, params)
        parcerias = cur.fetchall()
        cur.close()
        
        # Criar arquivo CSV em memória com BOM UTF-8 para corrigir encoding
        output = StringIO()
        output.write('\ufeff')  # BOM UTF-8
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Cabeçalho do CSV
        writer.writerow([
            'Número do Termo',
            'Tipo de Termo',
            'OSC',
            'CNPJ',
            'Projeto',
            'Portaria',
            'Pessoa Gestora',
            'Solicitação',
            'Data Início',
            'Data Término',
            'Meses',
            'Total Previsto',
            'SEI Celebração',
            'SEI P&C',
            'SEI Plano',
            'SEI Orçamento',
            'Transição'
        ])
        
        # Escrever dados
        for parceria in parcerias:
            total_previsto = float(parceria['total_previsto'] or 0)
            
            writer.writerow([
                parceria['numero_termo'],
                parceria['tipo_termo'] or '-',
                parceria['osc'] or '-',
                parceria['cnpj'] or '-',
                parceria['projeto'] or '-',
                parceria['portaria'] or '-',
                parceria['pessoa_gestora'] or '-',
                'Sim' if parceria.get('solicitacao') else 'Não',
                parceria['inicio'].strftime('%d/%m/%Y') if parceria['inicio'] else '-',
                parceria['final'].strftime('%d/%m/%Y') if parceria['final'] else '-',
                parceria['meses'] if parceria['meses'] is not None else '-',
                f"R$ {total_previsto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'),
                parceria['sei_celeb'] or '-',
                parceria['sei_pc'] or '-',
                parceria['sei_plano'] or '-',
                parceria['sei_orcamento'] or '-',
                'Sim' if parceria['transicao'] else 'Não'
            ])
        
        # Preparar resposta
        output.seek(0)
        data_atual = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Verificar se há filtros aplicados para incluir no nome do arquivo
        tem_filtros = any([filtro_termo, filtro_osc, filtro_projeto, filtro_tipo_termo, 
                          filtro_status, filtro_pessoa_gestora, busca_sei_celeb, busca_sei_pc])
        
        if tem_filtros:
            filename = f'parcerias_filtradas_{data_atual}.csv'
        else:
            filename = f'parcerias_completo_{data_atual}.csv'
        
        # Log para debug
        print(f"[EXPORTAR CSV] Total de registros exportados: {len(parcerias)}")
        print(f"[EXPORTAR CSV] Filtros aplicados: {tem_filtros}")
        
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        return f"Erro ao exportar CSV: {str(e)}", 500


@parcerias_bp.route("/exportar-pdf", methods=["GET"])
@login_required
@requires_access('parcerias')
def exportar_pdf():
    """
    Exporta uma parceria específica para PDF
    """
    try:
        # Obter número do termo da query string
        numero_termo = request.args.get('numero_termo', '').strip()
        
        if not numero_termo:
            return "Número do termo não informado", 400
        
        cur = get_cursor()
        
        # Query para buscar a parceria
        query = """
            SELECT 
                numero_termo,
                tipo_termo,
                osc,
                cnpj,
                projeto,
                portaria,
                inicio,
                final,
                meses,
                total_previsto,
                sei_celeb,
                sei_pc,
                sei_plano,
                sei_orcamento,
                transicao
            FROM Parcerias
            WHERE numero_termo = %s
        """
        
        cur.execute(query, (numero_termo,))
        parceria = cur.fetchone()
        cur.close()
        
        if not parceria:
            return "Parceria não encontrada", 404
        
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
            textColor=colors.HexColor('#1a73e8'),
            spaceAfter=30,
            alignment=1  # Centralizado
        )
        
        # Estilo para labels
        label_style = ParagraphStyle(
            'Label',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#666666'),
            spaceAfter=2
        )
        
        # Estilo para valores
        value_style = ParagraphStyle(
            'Value',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=12
        )
        
        # Título
        titulo = Paragraph(f"Parceria - {parceria['numero_termo']}", title_style)
        elements.append(titulo)
        elements.append(Spacer(1, 0.5*cm))
        
        # Preparar dados
        total_previsto = float(parceria['total_previsto'] or 0)
        data_inicio_fmt = parceria['inicio'].strftime('%d/%m/%Y') if parceria['inicio'] else '-'
        data_termino_fmt = parceria['final'].strftime('%d/%m/%Y') if parceria['final'] else '-'
        total_previsto_fmt = f"R$ {total_previsto:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        
        # Dados da parceria em formato de tabela
        dados = [
            ['Número do Termo:', parceria['numero_termo']],
            ['Tipo de Termo:', parceria['tipo_termo'] or '-'],
            ['OSC:', parceria['osc'] or '-'],
            ['CNPJ:', parceria['cnpj'] or '-'],
            ['Projeto:', parceria['projeto'] or '-'],
            ['Portaria:', parceria['portaria'] or '-'],
            ['Data de Início:', data_inicio_fmt],
            ['Data de Término:', data_termino_fmt],
            ['Meses:', str(parceria['meses']) if parceria['meses'] is not None else '-'],
            ['Total Previsto:', total_previsto_fmt],
            ['SEI Celebração:', parceria['sei_celeb'] or '-'],
            ['SEI P&C:', parceria['sei_pc'] or '-'],
            ['SEI Plano:', parceria['sei_plano'] or '-'],
            ['SEI Orçamento:', parceria['sei_orcamento'] or '-'],
            ['Transição:', 'Sim' if parceria['transicao'] else 'Não']
        ]
        
        # Criar tabela
        tabela = Table(dados, colWidths=[5*cm, 12*cm])
        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0f0f0')),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('TOPPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        
        elements.append(tabela)
        elements.append(Spacer(1, 1*cm))
        
        # Rodapé
        data_geracao = datetime.now().strftime('%d/%m/%Y às %H:%M')
        rodape = Paragraph(f"<i>Documento gerado em {data_geracao}</i>", 
                          ParagraphStyle('Footer', parent=styles['Normal'], 
                                       fontSize=8, textColor=colors.grey))
        elements.append(rodape)
        
        # Gerar PDF
        doc.build(elements)
        
        # Preparar resposta
        buffer.seek(0)
        filename = f'parceria_{numero_termo.replace("/", "-")}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.pdf'
        
        return Response(
            buffer.getvalue(),
            mimetype='application/pdf',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/pdf'
            }
        )
        
    except Exception as e:
        return f"Erro ao gerar PDF: {str(e)}", 500


@parcerias_bp.route("/conferencia", methods=["GET"])
@login_required
@requires_access('parcerias')
def conferencia():
    """
    Rota de conferência de parcerias - agora com input manual de CSV
    """
    return render_template('temp_conferencia.html')


@parcerias_bp.route("/conferencia/processar", methods=["POST"])
@login_required
@requires_access('parcerias')
def conferencia_processar():
    """
    Processa o CSV colado pelo usuário e compara com o banco de dados
    Extrai: Número do Termo (col 1) e Nome da OSC (col 2)
    """
    try:
        data = request.get_json()
        csv_data = data.get('csv_data', '').strip()
        
        if not csv_data:
            return jsonify({'erro': 'Nenhum dado CSV fornecido'}), 400
        
        # Processa o CSV (pega número do termo E nome da OSC)
        linhas = csv_data.split('\n')
        termos_csv = {}  # {numero_termo: nome_osc}
        
        for i, linha in enumerate(linhas):
            linha = linha.strip()
            if not linha:
                continue
            
            # Pula o cabeçalho (primeira linha)
            if i == 0:
                continue
            
            # Pega os campos
            partes = linha.split(';')
            if len(partes) >= 1:
                numero_termo = partes[0].strip()
                nome_osc = partes[1].strip() if len(partes) >= 2 else ''
                
                if numero_termo and numero_termo != '0' and numero_termo.lower() != 'null':
                    termos_csv[numero_termo] = nome_osc
        
        print(f"[DEBUG CSV] Total de termos extraídos do CSV: {len(termos_csv)}")
        
        # Busca termos no banco
        cur = get_cursor()
        cur.execute("SELECT numero_termo FROM Parcerias ORDER BY numero_termo")
        termos_db = [row['numero_termo'] for row in cur.fetchall()]
        cur.close()
        
        termos_db_unicos = set(termos_db)
        
        print(f"[DEBUG CSV] Total de termos no banco: {len(termos_db_unicos)}")
        
        # Compara
        set_csv = set(termos_csv.keys())
        
        # Termos faltantes com suas OSCs
        faltantes = []
        for termo in sorted(set_csv - termos_db_unicos):
            faltantes.append({
                'numero_termo': termo,
                'osc': termos_csv[termo]
            })
        
        # Termos existentes (só os números)
        existentes = sorted(list(set_csv & termos_db_unicos))
        
        print(f"[DEBUG CSV] Faltantes: {len(faltantes)}, Existentes: {len(existentes)}")
        
        return jsonify({
            'faltantes': faltantes,
            'existentes': existentes,
            'stats': {
                'total_csv': len(termos_csv),
                'total_banco': len(termos_db_unicos),
                'total_faltantes': len(faltantes),
                'total_existentes': len(existentes)
            }
        })
        
    except Exception as e:
        import traceback
        print(f"[ERRO CSV] {str(e)}")
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500
        
    except Exception as e:
        import traceback
        print(f"[ERRO CONFERENCIA] Exceção capturada: {str(e)}")
        print(f"[ERRO CONFERENCIA] Traceback completo:")
        traceback.print_exc()
        flash(f"Erro ao processar conferência: {str(e)}", "danger")
        return redirect(url_for('parcerias.listar'))


@parcerias_bp.route("/conferencia/atualizar", methods=["POST"])
@login_required
@requires_access('parcerias')
def atualizar_conferencia():
    """
    Executa o script import_conferencia.py para atualizar os dados
    e redireciona de volta para a página de conferência
    """
    import subprocess
    import os
    
    try:
        # Caminho do script
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'import_conferencia.py')
        
        if not os.path.exists(script_path):
            flash("Script import_conferencia.py não encontrado.", "danger")
            return redirect(url_for('parcerias.conferencia'))
        
        # Executa o script
        result = subprocess.run(
            ['python', script_path],
            capture_output=True,
            text=True,
            timeout=30  # Timeout de 30 segundos
        )
        
        if result.returncode == 0:
            flash("Conferência atualizada com sucesso! ✓", "success")
        else:
            flash(f"Erro ao executar o script: {result.stderr}", "danger")
        
        return redirect(url_for('parcerias.conferencia'))
        
    except subprocess.TimeoutExpired:
        flash("Timeout: O script demorou muito para executar.", "danger")
        return redirect(url_for('parcerias.conferencia'))
    except Exception as e:
        flash(f"Erro ao atualizar conferência: {str(e)}", "danger")
        return redirect(url_for('parcerias.conferencia'))


@parcerias_bp.route("/conferencia/pos-insercao", methods=["GET"])
@login_required
@requires_access('parcerias')
def conferencia_pos_insercao():
    """
    Rota intermediária após inserção de parceria vinda da conferência.
    Executa atualização automática e redireciona para a conferência.
    """
    import subprocess
    import os
    
    try:
        # Caminho do script
        script_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'import_conferencia.py')
        
        if os.path.exists(script_path):
            # Executa o script para atualizar a conferência
            result = subprocess.run(
                ['python', script_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                flash("Parceria importada com sucesso! Conferência atualizada automaticamente. ✓", "success")
            else:
                flash("Parceria importada, mas houve erro ao atualizar a conferência.", "warning")
        else:
            flash("Parceria importada com sucesso!", "success")
        
    except subprocess.TimeoutExpired:
        flash("Parceria importada, mas a atualização da conferência excedeu o tempo limite.", "warning")
    except Exception as e:
        flash(f"Parceria importada, mas houve erro ao atualizar conferência: {str(e)}", "warning")
    
    return redirect(url_for('parcerias.conferencia'))


@parcerias_bp.route("/dicionario-oscs", methods=["GET"])
@login_required
@requires_access('parcerias')
def dicionario_oscs():
    """
    Dicionário de OSCs - permite padronizar e corrigir nomes de OSCs
    Mostra todas as OSCs únicas com contagem de termos associados
    """
    try:
        # Parâmetro de paginação
        pagina = request.args.get('pagina', 1, type=int)
        por_pagina = 50
        offset = (pagina - 1) * por_pagina
        
        cur = get_cursor()
        
        # Buscar total de OSCs únicas
        cur.execute("""
            SELECT COUNT(DISTINCT osc) as total
            FROM Parcerias
            WHERE osc IS NOT NULL AND osc != ''
        """)
        total_oscs = cur.fetchone()['total']
        total_paginas = (total_oscs + por_pagina - 1) // por_pagina
        
        # Buscar OSCs com contagem de termos (paginado)
        query = """
            SELECT 
                osc,
                COUNT(numero_termo) as total_termos,
                MIN(cnpj) as cnpj_exemplo
            FROM Parcerias
            WHERE osc IS NOT NULL AND osc != ''
            GROUP BY osc
            ORDER BY osc
            LIMIT %s OFFSET %s
        """
        
        cur.execute(query, (por_pagina, offset))
        oscs = cur.fetchall()
        cur.close()
        
        return render_template('parcerias_osc_dict.html',
                             oscs=oscs,
                             total_oscs=total_oscs,
                             pagina_atual=pagina,
                             total_paginas=total_paginas)
        
    except Exception as e:
        print(f"[ERRO] Erro ao carregar dicionário de OSCs: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Erro ao carregar dicionário de OSCs: {str(e)}", "danger")
        return redirect(url_for('parcerias.listar'))


@parcerias_bp.route("/buscar-oscs", methods=["GET"])
@login_required
@requires_access('parcerias')
def buscar_oscs():
    """
    API para buscar OSCs no banco de dados (busca global)
    """
    try:
        termo_busca = request.args.get('q', '').strip()
        
        if not termo_busca:
            return jsonify({'error': 'Termo de busca vazio'}), 400
        
        cur = get_cursor()
        
        # Buscar OSCs que contenham o termo (ILIKE para case-insensitive)
        query = """
            SELECT 
                osc,
                COUNT(numero_termo) as total_termos,
                MIN(cnpj) as cnpj_exemplo
            FROM Parcerias
            WHERE osc ILIKE %s
            GROUP BY osc
            ORDER BY osc
            LIMIT 100
        """
        
        cur.execute(query, (f'%{termo_busca}%',))
        oscs = cur.fetchall()
        cur.close()
        
        return jsonify({
            'oscs': [dict(osc) for osc in oscs],
            'total': len(oscs),
            'termo_busca': termo_busca
        }), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar OSCs: {str(e)}")
        return jsonify({'error': str(e)}), 500


@parcerias_bp.route("/termos-por-osc/<path:osc>", methods=["GET"])
@login_required
@requires_access('parcerias')
def termos_por_osc(osc):
    """
    API para buscar todos os termos de uma OSC específica
    """
    try:
        cur = get_cursor()
        
        query = """
            SELECT 
                numero_termo,
                tipo_termo,
                projeto,
                inicio,
                final,
                total_previsto
            FROM Parcerias
            WHERE osc = %s
            ORDER BY numero_termo
        """
        
        cur.execute(query, (osc,))
        termos = cur.fetchall()
        cur.close()
        
        # Converter datas para string e formatar valores
        termos_formatados = []
        for termo in termos:
            termo_dict = dict(termo)
            termo_dict['inicio'] = termo['inicio'].strftime('%d/%m/%Y') if termo['inicio'] else '-'
            termo_dict['final'] = termo['final'].strftime('%d/%m/%Y') if termo['final'] else '-'
            termo_dict['total_previsto'] = float(termo['total_previsto']) if termo['total_previsto'] else 0
            termos_formatados.append(termo_dict)
        
        return jsonify({'termos': termos_formatados}), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar termos da OSC: {str(e)}")
        return jsonify({'error': str(e)}), 500


@parcerias_bp.route("/atualizar-osc", methods=["POST"])
@login_required
@requires_access('parcerias')
def atualizar_osc():
    """
    API para atualizar nome de uma OSC em todos os registros
    """
    try:
        data = request.get_json()
        osc_antiga = data.get('osc_antiga', '').strip()
        osc_nova = data.get('osc_nova', '').strip()
        
        if not osc_antiga or not osc_nova:
            return jsonify({'error': 'OSC antiga e nova são obrigatórias'}), 400
        
        if osc_antiga == osc_nova:
            return jsonify({'error': 'OSC antiga e nova são iguais'}), 400
        
        cur = get_cursor()
        
        # Verificar se já existe outra OSC com o nome novo (para evitar duplicação não intencional)
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM Parcerias 
            WHERE osc = %s AND osc != %s
        """, (osc_nova, osc_antiga))
        
        if cur.fetchone()['count'] > 0:
            # Se já existe, avisar mas permitir (pode ser fusão intencional)
            print(f"[AVISO] Já existe OSC com nome '{osc_nova}' no banco")
        
        # Atualizar todos os registros
        query = """
            UPDATE Parcerias
            SET osc = %s
            WHERE osc = %s
        """
        
        cur.execute(query, (osc_nova, osc_antiga))
        linhas_afetadas = cur.rowcount
        
        # Commit da transação
        get_db().commit()
        cur.close()
        
        print(f"[SUCESSO] OSC atualizada: '{osc_antiga}' → '{osc_nova}' ({linhas_afetadas} registros)")
        
        return jsonify({
            'message': f'✅ OSC atualizada com sucesso! {linhas_afetadas} registro(s) afetado(s).',
            'linhas_afetadas': linhas_afetadas
        }), 200
        
    except Exception as e:
        print(f"[ERRO] Erro ao atualizar OSC: {str(e)}")
        import traceback
        traceback.print_exc()
        get_db().rollback()
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ROTAS DE TERMOS RESCINDIDOS
# ============================================================================

@parcerias_bp.route("/rescisoes", methods=["GET"])
@login_required
@requires_access('parcerias')
def termos_rescindidos():
    """
    Página de cadastro e listagem de termos rescindidos
    """
    cur = get_cursor()
    
    # Buscar termos já rescindidos com responsável
    cur.execute("""
        SELECT tr.id, tr.numero_termo, tr.data_rescisao, tr.sei_rescisao, 
               tr.responsavel_rescisao, p.osc as osc_nome
        FROM public.termos_rescisao tr
        LEFT JOIN public.parcerias p ON tr.numero_termo = p.numero_termo
        ORDER BY tr.data_rescisao DESC NULLS LAST, tr.id DESC
    """)
    rescisoes = cur.fetchall()
    
    # Buscar lista de analistas DGP (ativos e inativos)
    cur.execute("""
        SELECT nome_analista
        FROM categoricas.c_dgp_analistas
        ORDER BY nome_analista
    """)
    analistas_dgp = [row['nome_analista'] for row in cur.fetchall()]
    
    cur.close()
    
    # NÃO carregar todos os termos aqui - usar API de autocomplete
    return render_template('termos_rescindidos.html',
                         rescisoes=rescisoes,
                         analistas_dgp=analistas_dgp,
                         rescisao_editando=None)


@parcerias_bp.route("/api/termos-disponiveis", methods=["GET"])
@login_required
@requires_access('parcerias')
def api_termos_disponiveis():
    """
    API para autocomplete de termos disponíveis (não rescindidos)
    Busca termos que começam com o texto digitado
    """
    try:
        # Obter termo de busca (texto digitado pelo usuário)
        query = request.args.get('q', '').strip().upper()
        
        # Limitar a 50 resultados para performance
        limite = 50
        
        cur = get_cursor()
        
        if query:
            # Buscar termos que começam com o texto digitado
            cur.execute("""
                SELECT DISTINCT p.numero_termo
                FROM public.parcerias p
                WHERE p.numero_termo NOT IN (
                    SELECT numero_termo FROM public.termos_rescisao
                )
                AND UPPER(p.numero_termo) LIKE %s
                ORDER BY p.numero_termo
                LIMIT %s
            """, (f"{query}%", limite))
        else:
            # Se não há busca, retornar vazio (não carregar todos)
            cur.close()
            return jsonify([])
        
        termos = [row['numero_termo'] for row in cur.fetchall()]
        cur.close()
        
        return jsonify(termos)
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar termos disponíveis: {str(e)}")
        return jsonify({'erro': str(e)}), 500


@parcerias_bp.route("/rescisao/salvar", methods=["POST"])
@login_required
@requires_access('parcerias')
def salvar_rescisao():
    """
    Salvar novo termo rescindido
    """
    numero_termo = request.form.get('numero_termo', '').strip()
    data_rescisao = request.form.get('data_rescisao', '').strip()
    sei_rescisao = request.form.get('sei_rescisao', '').strip()
    responsavel_rescisao = request.form.get('responsavel_rescisao', '').strip()
    
    # Validações
    if not numero_termo:
        flash('Número do termo é obrigatório!', 'danger')
        return redirect(url_for('parcerias.termos_rescindidos'))
    
    if not data_rescisao:
        flash('Data de rescisão é obrigatória!', 'danger')
        return redirect(url_for('parcerias.termos_rescindidos'))
    
    if not sei_rescisao:
        flash('SEI da rescisão é obrigatório!', 'danger')
        return redirect(url_for('parcerias.termos_rescindidos'))
    
    if not responsavel_rescisao:
        flash('Responsável pela rescisão é obrigatório!', 'danger')
        return redirect(url_for('parcerias.termos_rescindidos'))
    
    cur = get_cursor()
    
    try:
        # Verificar se o termo existe em parcerias
        cur.execute("SELECT COUNT(*) as total FROM public.parcerias WHERE numero_termo = %s", (numero_termo,))
        termo_existe = cur.fetchone()['total'] > 0
        
        if not termo_existe:
            flash(f'Termo "{numero_termo}" não existe na base de parcerias!', 'danger')
            return redirect(url_for('parcerias.termos_rescindidos'))
        
        # Verificar se já foi rescindido
        cur.execute("SELECT COUNT(*) as total FROM public.termos_rescisao WHERE numero_termo = %s", (numero_termo,))
        ja_rescindido = cur.fetchone()['total'] > 0
        
        if ja_rescindido:
            flash(f'Termo "{numero_termo}" já está cadastrado como rescindido!', 'warning')
            return redirect(url_for('parcerias.termos_rescindidos'))
        
        # Inserir rescisão
        cur.execute("""
            INSERT INTO public.termos_rescisao (numero_termo, data_rescisao, sei_rescisao, responsavel_rescisao)
            VALUES (%s, %s, %s, %s)
        """, (numero_termo, data_rescisao, sei_rescisao, responsavel_rescisao))
        
        get_db().commit()
        cur.close()
        
        flash(f'Termo "{numero_termo}" cadastrado como rescindido com sucesso!', 'success')
        return redirect(url_for('parcerias.termos_rescindidos'))
        
    except Exception as e:
        print(f"[ERRO] Erro ao salvar rescisão: {str(e)}")
        import traceback
        traceback.print_exc()
        get_db().rollback()
        flash(f'Erro ao salvar rescisão: {str(e)}', 'danger')
        return redirect(url_for('parcerias.termos_rescindidos'))


@parcerias_bp.route("/rescisao/editar/<int:id>", methods=["GET", "POST"])
@login_required
@requires_access('parcerias')
def editar_rescisao(id):
    """
    Editar termo rescindido existente
    """
    cur = get_cursor()
    
    if request.method == 'POST':
        # Processar atualização
        data_rescisao = request.form.get('data_rescisao', '').strip()
        sei_rescisao = request.form.get('sei_rescisao', '').strip()
        responsavel_rescisao = request.form.get('responsavel_rescisao', '').strip()
        numero_termo = request.form.get('numero_termo', '').strip()  # Hidden field
        
        if not data_rescisao or not sei_rescisao or not responsavel_rescisao:
            flash('Todos os campos são obrigatórios!', 'danger')
            return redirect(url_for('parcerias.editar_rescisao', id=id))
        
        try:
            cur.execute("""
                UPDATE public.termos_rescisao
                SET data_rescisao = %s, sei_rescisao = %s, responsavel_rescisao = %s
                WHERE id = %s
            """, (data_rescisao, sei_rescisao, responsavel_rescisao, id))
            
            get_db().commit()
            cur.close()
            
            flash(f'Rescisão do termo "{numero_termo}" atualizada com sucesso!', 'success')
            return redirect(url_for('parcerias.termos_rescindidos'))
            
        except Exception as e:
            print(f"[ERRO] Erro ao atualizar rescisão: {str(e)}")
            get_db().rollback()
            flash(f'Erro ao atualizar rescisão: {str(e)}', 'danger')
            return redirect(url_for('parcerias.editar_rescisao', id=id))
    
    # GET: Carregar dados para edição
    cur.execute("""
        SELECT tr.*, p.osc as osc_nome
        FROM public.termos_rescisao tr
        LEFT JOIN public.parcerias p ON tr.numero_termo = p.numero_termo
        WHERE tr.id = %s
    """, (id,))
    rescisao_editando = cur.fetchone()
    
    if not rescisao_editando:
        flash('Rescisão não encontrada!', 'danger')
        return redirect(url_for('parcerias.termos_rescindidos'))
    
    # Buscar todas as rescisões para a tabela
    cur.execute("""
        SELECT tr.id, tr.numero_termo, tr.data_rescisao, tr.sei_rescisao, 
               tr.responsavel_rescisao, p.osc as osc_nome
        FROM public.termos_rescisao tr
        LEFT JOIN public.parcerias p ON tr.numero_termo = p.numero_termo
        ORDER BY tr.data_rescisao DESC NULLS LAST, tr.id DESC
    """)
    rescisoes = cur.fetchall()
    
    # Buscar lista de analistas DGP (ativos e inativos)
    cur.execute("""
        SELECT nome_analista
        FROM categoricas.c_dgp_analistas
        ORDER BY nome_analista
    """)
    analistas_dgp = [row['nome_analista'] for row in cur.fetchall()]
    
    # Termos disponíveis (vazio pois está editando)
    termos_disponiveis = [rescisao_editando['numero_termo']]
    
    cur.close()
    
    return render_template('termos_rescindidos.html',
                         rescisoes=rescisoes,
                         analistas_dgp=analistas_dgp,
                         termos_disponiveis=termos_disponiveis,
                         rescisao_editando=rescisao_editando)


@parcerias_bp.route("/rescisao/deletar/<int:id>", methods=["POST"])
@login_required
@requires_access('parcerias')
def deletar_rescisao(id):
    """
    Deletar termo rescindido
    """
    cur = get_cursor()
    
    try:
        # Buscar número do termo antes de deletar (para mensagem)
        cur.execute("SELECT numero_termo FROM public.termos_rescisao WHERE id = %s", (id,))
        rescisao = cur.fetchone()
        
        if not rescisao:
            flash('Rescisão não encontrada!', 'danger')
            return redirect(url_for('parcerias.termos_rescindidos'))
        
        numero_termo = rescisao['numero_termo']
        
        # Deletar
        cur.execute("DELETE FROM public.termos_rescisao WHERE id = %s", (id,))
        get_db().commit()
        cur.close()
        
        flash(f'Rescisão do termo "{numero_termo}" excluída com sucesso!', 'success')
        return redirect(url_for('parcerias.termos_rescindidos'))
        
    except Exception as e:
        print(f"[ERRO] Erro ao deletar rescisão: {str(e)}")
        get_db().rollback()
        flash(f'Erro ao deletar rescisão: {str(e)}', 'danger')
        return redirect(url_for('parcerias.termos_rescindidos'))


# ============================================================================
# ROTAS DE ALTERAÇÕES DGP
# ============================================================================

@parcerias_bp.route("/dgp_alteracoes", methods=["GET"])
@login_required
@requires_access('parcerias')
def dgp_alteracoes():
    """
    Página de gerenciamento de alterações em termos de parceria
    """
    cur = get_cursor()
    
    try:
        # Buscar tipos de alteração com seus instrumentos e configurações de campo
        cur.execute("""
            SELECT 
                alt_tipo, 
                alt_instrumento,
                alt_campo_tipo,
                alt_campo_placeholder,
                alt_campo_maxlength,
                alt_campo_min
            FROM categoricas.c_alt_tipo 
            ORDER BY alt_tipo
        """)
        tipos_alteracao = cur.fetchall()
        
        # Buscar instrumentos disponíveis
        cur.execute("""
            SELECT DISTINCT instrumento_alteracao 
            FROM categoricas.c_alt_instrumento 
            ORDER BY instrumento_alteracao
        """)
        instrumentos = [row['instrumento_alteracao'] for row in cur.fetchall()]
        
        # Buscar analistas DGP da tabela categoricas.c_dgp_analistas
        analistas_dgp = []
        try:
            cur.execute("""
                SELECT nome_analista
                FROM categoricas.c_dgp_analistas
                WHERE nome_analista IS NOT NULL
                ORDER BY nome_analista
            """)
            analistas_dgp = [row['nome_analista'] for row in cur.fetchall()]
        except Exception as e:
            print(f"[WARN] Erro ao buscar analistas DGP: {str(e)}")
            # Fallback para lista estática se tabela não existir
            analistas_dgp = ['Administrador', 'Sistema']
        
        # Buscar alterações cadastradas com filtros
        filtro_termo = request.args.get('filtro_termo', '').strip()
        filtro_instrumento = request.args.get('filtro_instrumento', '').strip()
        filtro_tipos = request.args.getlist('filtro_tipos[]')
        filtro_responsavel = request.args.get('filtro_responsavel', '').strip()
        
        # Construir query base
        query_base = """
            SELECT 
                numero_termo,
                instrumento_alteracao,
                alt_numero,
                string_agg(DISTINCT alt_tipo, ', ' ORDER BY alt_tipo) as tipos_alteracao,
                MAX(alt_responsavel) as responsavel
            FROM public.termos_alteracoes
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if filtro_termo:
            query_base += " AND numero_termo ILIKE %s"
            params.append(f"%{filtro_termo}%")
        
        if filtro_instrumento:
            query_base += " AND instrumento_alteracao = %s"
            params.append(filtro_instrumento)
        
        if filtro_tipos:
            placeholders = ','.join(['%s'] * len(filtro_tipos))
            query_base += f" AND alt_tipo IN ({placeholders})"
            params.extend(filtro_tipos)
        
        if filtro_responsavel:
            query_base += " AND alt_responsavel LIKE %s"
            params.append(f"%{filtro_responsavel}%")
        
        query_base += """
            GROUP BY numero_termo, instrumento_alteracao, alt_numero
            ORDER BY numero_termo
        """
        
        cur.execute(query_base, params)
        alteracoes = cur.fetchall()
        
        cur.close()
        
        return render_template(
            'dgp_alteracoes.html',
            tipos_alteracao=tipos_alteracao,
            instrumentos=instrumentos,
            alteracoes=alteracoes,
            analistas_dgp=analistas_dgp
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao carregar página de alterações: {str(e)}")
        flash(f'Erro ao carregar dados: {str(e)}', 'danger')
        return redirect(url_for('parcerias.listar'))


@parcerias_bp.route("/api/termos_parcerias", methods=["GET"])
@login_required
def api_termos_parcerias():
    """
    API para buscar termos de parcerias (para Select2)
    Retorna todos os termos que não estão rescindidos
    """
    termo_busca = request.args.get('q', '').strip()
    
    cur = get_cursor()
    
    try:
        # Buscar termos que NÃO estão na tabela de rescisão
        query = """
            SELECT DISTINCT p.numero_termo 
            FROM public.parcerias p
            WHERE p.numero_termo NOT IN (
                SELECT numero_termo FROM public.termos_rescisao
            )
        """
        
        params = []
        
        if termo_busca:
            query += " AND p.numero_termo ILIKE %s"
            params.append(f'%{termo_busca}%')
        
        query += " ORDER BY p.numero_termo LIMIT 100"
        
        cur.execute(query, params)
        # Retornar no formato esperado pelo Select2: lista de objetos {id, text}
        termos = [{'id': row['numero_termo'], 'text': row['numero_termo']} for row in cur.fetchall()]
        cur.close()
        
        return jsonify(termos)
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar termos: {str(e)}")
        return jsonify([]), 500


@parcerias_bp.route("/api/lista_oscs", methods=["GET"])
@login_required
def api_lista_oscs():
    """
    API para listar todas as OSCs únicas
    """
    cur = get_cursor()
    
    try:
        cur.execute("""
            SELECT DISTINCT osc 
            FROM public.parcerias 
            WHERE osc IS NOT NULL AND osc != ''
            ORDER BY osc
        """)
        oscs = [row['osc'] for row in cur.fetchall()]
        cur.close()
        
        return jsonify(oscs)
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar OSCs: {str(e)}")
        return jsonify([]), 500


@parcerias_bp.route("/api/lista_pgs", methods=["GET"])
@login_required
def api_lista_pgs():
    """
    API para listar todas as pessoas gestoras únicas
    """
    cur = get_cursor()
    
    try:
        cur.execute("""
            SELECT DISTINCT nome_pg 
            FROM public.parcerias_pg 
            WHERE nome_pg IS NOT NULL AND nome_pg != ''
            ORDER BY nome_pg
        """)
        pgs = [row['nome_pg'] for row in cur.fetchall()]
        cur.close()
        
        return jsonify(pgs)
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar PGs: {str(e)}")
        return jsonify([]), 500


@parcerias_bp.route("/alteracao/salvar", methods=["POST"])
@login_required
@requires_access('parcerias')
def salvar_alteracao():
    """
    Salvar alteração(ões) de termo
    Cada tipo de alteração selecionado será salvo como um registro separado
    Se status = "Concluído", atualiza as tabelas originais
    """
    cur = get_cursor()
    
    try:
        # Dados gerais
        numero_termo = request.form.get('numero_termo', '').strip()
        instrumento_alteracao = request.form.get('instrumento_alteracao', '').strip()
        alt_numero = int(request.form.get('alt_numero', 0))
        alt_status = request.form.get('alt_status', '').strip()
        # Múltiplos responsáveis concatenados com ;
        alt_responsaveis = request.form.getlist('alt_responsavel[]')
        alt_responsavel = ';'.join([r.strip() for r in alt_responsaveis if r.strip()])
        alt_observacao = request.form.get('alt_observacao', '').strip()
        
        # Validar campos obrigatórios
        if not numero_termo or not instrumento_alteracao or not alt_status or not alt_responsavel:
            flash('Todos os campos obrigatórios devem ser preenchidos!', 'danger')
            return redirect(url_for('parcerias.dgp_alteracoes'))
        
        # Tipos de alteração e informações (arrays)
        tipos_alteracao = request.form.getlist('alt_tipo[]')
        alt_infos = request.form.getlist('alt_info[]')
        alt_info_inicios = request.form.getlist('alt_info_inicio[]')
        alt_info_fins = request.form.getlist('alt_info_fim[]')
        
        if not tipos_alteracao or not any(tipos_alteracao):
            flash('Selecione pelo menos um tipo de alteração!', 'danger')
            return redirect(url_for('parcerias.dgp_alteracoes'))
        
        # Processar cada tipo de alteração
        registros_inseridos = 0
        idx_info = 0
        idx_date_range = 0
        
        for i, alt_tipo in enumerate(tipos_alteracao):
            if not alt_tipo.strip():
                continue
            
            # Determinar o valor de alt_info baseado no tipo
            alt_info = None
            if alt_tipo == 'Adequação de vigência':
                # Usar date range
                if idx_date_range < len(alt_info_inicios) and idx_date_range < len(alt_info_fins):
                    alt_info = f"{alt_info_inicios[idx_date_range]}|{alt_info_fins[idx_date_range]}"
                    idx_date_range += 1
            else:
                # Usar info normal
                if idx_info < len(alt_infos):
                    alt_info = alt_infos[idx_info]
                    idx_info += 1
            
            # Capturar valor antigo se status = "Concluído"
            alt_old_info = None
            if alt_status == 'Concluído' and alt_info:
                alt_old_info = _capturar_valor_antigo(cur, numero_termo, alt_tipo)
            
            # Inserir registro
            data_fim = 'NOW()' if alt_status == 'Concluído' else 'NULL'
            
            cur.execute(f"""
                INSERT INTO public.termos_alteracoes 
                (numero_termo, instrumento_alteracao, alt_numero, alt_tipo, alt_status,
                 alt_info, alt_old_info, alt_responsavel, alt_observacao,
                 alt_data_cadastro_inicio, alt_data_cadastro_fim, criado_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), {data_fim}, %s)
            """, (
                numero_termo,
                instrumento_alteracao,
                alt_numero,
                alt_tipo.strip(),
                alt_status,
                alt_info,
                alt_old_info,
                alt_responsavel,
                alt_observacao if alt_observacao else None,
                session.get('username', 'Sistema')
            ))
            
            # Se concluído, atualizar tabelas originais
            if alt_status == 'Concluído' and alt_info:
                _atualizar_tabela_original(cur, numero_termo, alt_tipo, alt_info)
            
            registros_inseridos += 1
        
        get_db().commit()
        cur.close()
        
        flash(f'{registros_inseridos} alteração(ões) cadastrada(s) com sucesso para o termo {numero_termo}!', 'success')
        return redirect(url_for('parcerias.dgp_alteracoes'))
        
    except Exception as e:
        print(f"[ERRO] Erro ao salvar alteração: {str(e)}")
        import traceback
        traceback.print_exc()
        get_db().rollback()
        flash(f'Erro ao salvar alteração: {str(e)}', 'danger')
        return redirect(url_for('parcerias.dgp_alteracoes'))


def _capturar_valor_antigo(cur, numero_termo, alt_tipo):
    """
    Captura o valor antigo da tabela original antes de atualizar
    """
    import json
    
    try:
        mapa = {
            'Nome do projeto': ('public.parcerias', 'projeto'),
            'Nome da organização': ('public.parcerias', 'osc'),
            'CNPJ da organização': ('public.parcerias', 'cnpj'),
            'Nome do responsável legal': ('public.parcerias_infos_adicionais', 'parceria_responsavel_legal'),
            'Pessoa gestora indicada pela administração pública': ('public.parcerias_pg', 'nome_pg'),
            'Objeto da parceria': ('public.parcerias_infos_adicionais', 'parceria_objeto'),
            'Quantidade de beneficiários diretos': ('public.parcerias_infos_adicionais', 'parceria_beneficiarios_diretos'),
            'Aumento de valor total da parceria': ('public.parcerias', 'total_previsto'),
            'Redução de valor de valor total da parceria': ('public.parcerias', 'total_previsto'),
            'Remanejamentos sem alteração de valor mensal': ('public.parcerias', 'sei_orcamento'),
            'FACC': ('public.parcerias', 'conta'),
            'Prorrogação de vigência': ('public.parcerias', 'final'),
            'Adequação de vigência': ('public.parcerias', 'inicio|final'),
            'Redução de vigência da parceria': ('public.parcerias', 'final'),
            'Suspensão de vigência da parceria': ('public.parcerias_infos_adicionais', 'parceria_data_suspensao'),
            'Retomada de vigência da parceria': ('public.parcerias_infos_adicionais', 'parceria_data_retomada'),
            'Justificativa do Projeto': ('public.parcerias_infos_adicionais', 'parceria_justificativa_projeto'),
            'Abragência geográfica': ('public.parcerias_infos_adicionais', 'parceria_abrangencia_projeto'),
            'Quantidade de beneficiários indiretos': ('public.parcerias_infos_adicionais', 'parceria_beneficiarios_indiretos'),
        }
        
        # Caso especial para Localização do projeto - capturar todos os endereços
        if alt_tipo == 'Localização do projeto':
            cur.execute("""
                SELECT 
                    id,
                    parceria_logradouro,
                    parceria_numero,
                    parceria_complemento,
                    parceria_cep,
                    parceria_distrito,
                    observacao
                FROM public.parcerias_enderecos
                WHERE numero_termo = %s
                ORDER BY id
            """, (numero_termo,))
            
            enderecos = cur.fetchall()
            if enderecos:
                # Serializar como JSON
                dados_enderecos = []
                for end in enderecos:
                    dados_enderecos.append({
                        'id': end['id'],
                        'parceria_logradouro': end['parceria_logradouro'],
                        'parceria_numero': end['parceria_numero'],
                        'parceria_complemento': end['parceria_complemento'],
                        'parceria_cep': end['parceria_cep'],
                        'parceria_distrito': end['parceria_distrito'],
                        'observacao': end['observacao']
                    })
                return json.dumps(dados_enderecos, ensure_ascii=False)
            return None
        
        if alt_tipo not in mapa:
            return None
        
        tabela, coluna = mapa[alt_tipo]
        
        # Adequação de vigência tem duas colunas
        if '|' in coluna:
            col1, col2 = coluna.split('|')
            cur.execute(f"SELECT {col1}, {col2} FROM {tabela} WHERE numero_termo = %s", (numero_termo,))
            row = cur.fetchone()
            if row:
                return f"{row[col1]}|{row[col2]}" if row[col1] and row[col2] else None
        else:
            # Caso especial para pessoa gestora - pegar a mais recente
            if tabela == 'public.parcerias_pg':
                cur.execute(f"SELECT {coluna} FROM {tabela} WHERE numero_termo = %s ORDER BY data_de_criacao DESC LIMIT 1", (numero_termo,))
            else:
                cur.execute(f"SELECT {coluna} FROM {tabela} WHERE numero_termo = %s", (numero_termo,))
            
            row = cur.fetchone()
            if row and row[coluna] is not None:
                return str(row[coluna])
        
        return None
        
    except Exception as e:
        print(f"[WARN] Erro ao capturar valor antigo: {str(e)}")
        return None


def _atualizar_tabela_original(cur, numero_termo, alt_tipo, alt_info):
    """
    Atualiza a tabela original com o novo valor quando status = "Concluído"
    """
    from datetime import datetime
    from dateutil.relativedelta import relativedelta
    
    try:
        # Mapear tipo de alteração para tabela e coluna
        if alt_tipo == 'Nome do projeto':
            cur.execute("UPDATE public.parcerias SET projeto = %s WHERE numero_termo = %s", (alt_info, numero_termo))
        
        elif alt_tipo == 'Nome da organização':
            cur.execute("UPDATE public.parcerias SET osc = %s WHERE numero_termo = %s", (alt_info, numero_termo))
        
        elif alt_tipo == 'CNPJ da organização':
            cur.execute("UPDATE public.parcerias SET cnpj = %s WHERE numero_termo = %s", (alt_info, numero_termo))
        
        elif alt_tipo == 'Nome do responsável legal':
            cur.execute("""
                UPDATE public.parcerias_infos_adicionais 
                SET parceria_responsavel_legal = %s 
                WHERE numero_termo = %s
            """, (alt_info, numero_termo))
        
        elif alt_tipo == 'Pessoa gestora indicada pela administração pública':
            # Inserir nova pessoa gestora (histórico mantido por data_de_criacao)
            cur.execute("""
                INSERT INTO public.parcerias_pg (numero_termo, nome_pg)
                VALUES (%s, %s)
            """, (numero_termo, alt_info))
        
        elif alt_tipo == 'Objeto da parceria':
            cur.execute("""
                UPDATE public.parcerias_infos_adicionais 
                SET parceria_objeto = %s 
                WHERE numero_termo = %s
            """, (alt_info, numero_termo))
        
        elif alt_tipo == 'Quantidade de beneficiários diretos':
            cur.execute("""
                UPDATE public.parcerias_infos_adicionais 
                SET parceria_beneficiarios_diretos = %s 
                WHERE numero_termo = %s
            """, (int(alt_info), numero_termo))
        
        elif alt_tipo in ['Aumento de valor total da parceria', 'Redução de valor de valor total da parceria']:
            # Limpar formatação de moeda
            valor = alt_info.replace('R$', '').replace('.', '').replace(',', '.').strip()
            cur.execute("UPDATE public.parcerias SET total_previsto = %s WHERE numero_termo = %s", (float(valor), numero_termo))
        
        elif alt_tipo == 'Remanejamentos sem alteração de valor mensal':
            cur.execute("UPDATE public.parcerias SET sei_orcamento = %s WHERE numero_termo = %s", (alt_info, numero_termo))
        
        elif alt_tipo == 'FACC':
            cur.execute("UPDATE public.parcerias SET conta = %s WHERE numero_termo = %s", (alt_info, numero_termo))
        
        elif alt_tipo in ['Prorrogação de vigência', 'Redução de vigência da parceria']:
            # Atualizar data final e recalcular meses
            cur.execute("UPDATE public.parcerias SET final = %s WHERE numero_termo = %s", (alt_info, numero_termo))
            _recalcular_meses(cur, numero_termo)
        
        elif alt_tipo == 'Adequação de vigência':
            # Atualizar data de início e fim
            datas = alt_info.split('|')
            if len(datas) == 2:
                cur.execute("""
                    UPDATE public.parcerias 
                    SET inicio = %s, final = %s 
                    WHERE numero_termo = %s
                """, (datas[0], datas[1], numero_termo))
                _recalcular_meses(cur, numero_termo)
        
        elif alt_tipo == 'Suspensão de vigência da parceria':
            cur.execute("""
                UPDATE public.parcerias_infos_adicionais 
                SET parceria_data_suspensao = %s 
                WHERE numero_termo = %s
            """, (alt_info, numero_termo))
        
        elif alt_tipo == 'Retomada de vigência da parceria':
            cur.execute("""
                UPDATE public.parcerias_infos_adicionais 
                SET parceria_data_retomada = %s 
                WHERE numero_termo = %s
            """, (alt_info, numero_termo))
        
        elif alt_tipo == 'Justificativa do Projeto':
            cur.execute("""
                UPDATE public.parcerias_infos_adicionais 
                SET parceria_justificativa_projeto = %s 
                WHERE numero_termo = %s
            """, (alt_info, numero_termo))
        
        elif alt_tipo == 'Abragência geográfica':
            cur.execute("""
                UPDATE public.parcerias_infos_adicionais 
                SET parceria_abrangencia_projeto = %s 
                WHERE numero_termo = %s
            """, (alt_info, numero_termo))
        
        elif alt_tipo == 'Quantidade de beneficiários indiretos':
            cur.execute("""
                UPDATE public.parcerias_infos_adicionais 
                SET parceria_beneficiarios_indiretos = %s 
                WHERE numero_termo = %s
            """, (int(alt_info), numero_termo))
        
        elif alt_tipo == 'Localização do projeto':
            # Atualizar endereços - alt_info contém JSON com array de endereços
            import json
            
            try:
                enderecos_novos = json.loads(alt_info)
                
                # IDs dos endereços que devem permanecer
                ids_manter = [end['id'] for end in enderecos_novos if end.get('id') and isinstance(end['id'], int)]
                
                # Deletar endereços que não estão na nova lista (foram removidos)
                if ids_manter:
                    placeholders = ','.join(['%s'] * len(ids_manter))
                    cur.execute(f"""
                        DELETE FROM public.parcerias_enderecos 
                        WHERE numero_termo = %s AND id NOT IN ({placeholders})
                    """, (numero_termo, *ids_manter))
                else:
                    # Se não há IDs para manter, deletar todos
                    cur.execute("DELETE FROM public.parcerias_enderecos WHERE numero_termo = %s", (numero_termo,))
                
                # Processar cada endereço
                for endereco in enderecos_novos:
                    endereco_id = endereco.get('id')
                    
                    if endereco_id and isinstance(endereco_id, int):
                        # UPDATE endereço existente
                        cur.execute("""
                            UPDATE public.parcerias_enderecos SET
                                parceria_logradouro = %s,
                                parceria_numero = %s,
                                parceria_complemento = %s,
                                parceria_cep = %s,
                                parceria_distrito = %s,
                                observacao = %s
                            WHERE id = %s AND numero_termo = %s
                        """, (
                            endereco.get('parceria_logradouro'),
                            endereco.get('parceria_numero'),
                            endereco.get('parceria_complemento'),
                            endereco.get('parceria_cep'),
                            endereco.get('parceria_distrito'),
                            endereco.get('observacao'),
                            endereco_id,
                            numero_termo
                        ))
                    else:
                        # INSERT novo endereço
                        cur.execute("""
                            INSERT INTO public.parcerias_enderecos (
                                numero_termo, parceria_logradouro, parceria_numero,
                                parceria_complemento, parceria_cep, parceria_distrito, observacao
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            numero_termo,
                            endereco.get('parceria_logradouro'),
                            endereco.get('parceria_numero'),
                            endereco.get('parceria_complemento'),
                            endereco.get('parceria_cep'),
                            endereco.get('parceria_distrito'),
                            endereco.get('observacao')
                        ))
                
                print(f"[INFO] {len(enderecos_novos)} endereço(s) atualizado(s) para {numero_termo}")
                
            except json.JSONDecodeError as je:
                print(f"[ERRO] Erro ao decodificar JSON de endereços: {str(je)}")
                raise
        
        print(f"[INFO] Tabela original atualizada para {alt_tipo}: {alt_info}")
        
    except Exception as e:
        print(f"[ERRO] Erro ao atualizar tabela original: {str(e)}")
        raise


def _recalcular_meses(cur, numero_termo):
    """
    Recalcula o número de meses entre data de início e fim
    """
    from dateutil.relativedelta import relativedelta
    
    try:
        cur.execute("SELECT inicio, final FROM public.parcerias WHERE numero_termo = %s", (numero_termo,))
        row = cur.fetchone()
        
        if row and row['inicio'] and row['final']:
            inicio = row['inicio']
            final = row['final']
            
            # Calcular diferença em meses
            diff = relativedelta(final, inicio)
            meses = diff.years * 12 + diff.months
            
            # Atualizar
            cur.execute("UPDATE public.parcerias SET meses = %s WHERE numero_termo = %s", (meses, numero_termo))
            print(f"[INFO] Meses recalculados para {numero_termo}: {meses}")
    
    except Exception as e:
        print(f"[ERRO] Erro ao recalcular meses: {str(e)}")


@parcerias_bp.route("/alteracao/editar", methods=["GET"])
@login_required
@requires_access('parcerias')
def editar_alteracao():
    """
    Buscar dados de uma alteração para edição
    """
    numero_termo = request.args.get('numero_termo', '').strip()
    instrumento = request.args.get('instrumento', '').strip()
    alt_numero = int(request.args.get('alt_numero', 0))
    
    cur = get_cursor()
    
    try:
        # Buscar todos os registros para esse termo/instrumento/número
        cur.execute("""
            SELECT alt_tipo, alt_status, alt_info, alt_old_info, 
                   alt_responsavel, alt_observacao
            FROM public.termos_alteracoes
            WHERE numero_termo = %s 
              AND instrumento_alteracao = %s 
              AND alt_numero = %s
            ORDER BY id
        """, (numero_termo, instrumento, alt_numero))
        
        rows = cur.fetchall()
        cur.close()
        
        if not rows:
            return jsonify({'error': 'Alteração não encontrada'}), 404
        
        # Preparar dados para retornar
        tipos = []
        infos = []
        status = rows[0]['alt_status']  # Todos têm o mesmo status
        responsavel = rows[0]['alt_responsavel']  # Todos têm o mesmo responsável
        observacao = rows[0]['alt_observacao']  # Todos têm a mesma observação
        
        for row in rows:
            tipos.append(row['alt_tipo'])
            infos.append(row['alt_info'] or '')
        
        return jsonify({
            'tipos': tipos,
            'infos': infos,
            'status': status,
            'responsavel': responsavel,
            'observacao': observacao or ''
        })
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar alteração: {str(e)}")
        return jsonify({'error': str(e)}), 500


@parcerias_bp.route("/alteracao/atualizar", methods=["POST"])
@login_required
@requires_access('parcerias')
def atualizar_alteracao():
    """
    Atualizar alteração existente
    Deleta os registros antigos e cria novos com os dados atualizados
    """
    cur = get_cursor()
    
    try:
        # Parâmetros originais (para identificar registros a deletar)
        numero_termo_original = request.args.get('numero_termo', '').strip()
        instrumento_original = request.args.get('instrumento', '').strip()
        alt_numero_original = int(request.args.get('alt_numero', 0))
        
        # Novos dados gerais
        numero_termo = request.form.get('numero_termo', '').strip()
        instrumento_alteracao = request.form.get('instrumento_alteracao', '').strip()
        alt_numero = int(request.form.get('alt_numero', 0))
        alt_status = request.form.get('alt_status', '').strip()
        # Múltiplos responsáveis concatenados com ;
        alt_responsaveis = request.form.getlist('alt_responsavel[]')
        alt_responsavel = ';'.join([r.strip() for r in alt_responsaveis if r.strip()])
        alt_observacao = request.form.get('alt_observacao', '').strip()
        
        # Validar campos obrigatórios
        if not numero_termo or not instrumento_alteracao or not alt_status or not alt_responsavel:
            flash('Todos os campos obrigatórios devem ser preenchidos!', 'danger')
            return redirect(url_for('parcerias.dgp_alteracoes'))
        
        # Tipos de alteração e informações (arrays)
        tipos_alteracao = request.form.getlist('alt_tipo[]')
        alt_infos = request.form.getlist('alt_info[]')
        alt_info_inicios = request.form.getlist('alt_info_inicio[]')
        alt_info_fins = request.form.getlist('alt_info_fim[]')
        
        if not tipos_alteracao or not any(tipos_alteracao):
            flash('Selecione pelo menos um tipo de alteração!', 'danger')
            return redirect(url_for('parcerias.dgp_alteracoes'))
        
        # Deletar registros antigos
        cur.execute("""
            DELETE FROM public.termos_alteracoes
            WHERE numero_termo = %s 
              AND instrumento_alteracao = %s 
              AND alt_numero = %s
        """, (numero_termo_original, instrumento_original, alt_numero_original))
        
        # Inserir novos registros
        registros_inseridos = 0
        idx_info = 0
        idx_date_range = 0
        
        for i, alt_tipo in enumerate(tipos_alteracao):
            if not alt_tipo.strip():
                continue
            
            # Determinar o valor de alt_info baseado no tipo
            alt_info = None
            if alt_tipo == 'Adequação de vigência':
                # Usar date range
                if idx_date_range < len(alt_info_inicios) and idx_date_range < len(alt_info_fins):
                    alt_info = f"{alt_info_inicios[idx_date_range]}|{alt_info_fins[idx_date_range]}"
                    idx_date_range += 1
            else:
                # Usar info normal
                if idx_info < len(alt_infos):
                    alt_info = alt_infos[idx_info]
                    idx_info += 1
            
            # Capturar valor antigo se status = "Concluído"
            alt_old_info = None
            if alt_status == 'Concluído' and alt_info:
                alt_old_info = _capturar_valor_antigo(cur, numero_termo, alt_tipo)
            
            # Inserir registro
            data_fim = 'NOW()' if alt_status == 'Concluído' else 'NULL'
            
            cur.execute(f"""
                INSERT INTO public.termos_alteracoes 
                (numero_termo, instrumento_alteracao, alt_numero, alt_tipo, alt_status,
                 alt_info, alt_old_info, alt_responsavel, alt_observacao,
                 alt_data_cadastro_inicio, alt_data_cadastro_fim,
                 criado_por, atualizado_por, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), {data_fim}, %s, %s, NOW())
            """, (
                numero_termo,
                instrumento_alteracao,
                alt_numero,
                alt_tipo.strip(),
                alt_status,
                alt_info,
                alt_old_info,
                alt_responsavel,
                alt_observacao if alt_observacao else None,
                session.get('username', 'Sistema'),
                session.get('username', 'Sistema')
            ))
            
            # Se concluído, atualizar tabelas originais
            if alt_status == 'Concluído' and alt_info:
                _atualizar_tabela_original(cur, numero_termo, alt_tipo, alt_info)
            
            registros_inseridos += 1
        
        get_db().commit()
        cur.close()
        
        flash(f'Alteração atualizada com sucesso! {registros_inseridos} tipo(s) de alteração.', 'success')
        return redirect(url_for('parcerias.dgp_alteracoes'))
        
    except Exception as e:
        print(f"[ERRO] Erro ao atualizar alteração: {str(e)}")
        get_db().rollback()
        flash(f'Erro ao atualizar alteração: {str(e)}', 'danger')
        return redirect(url_for('parcerias.dgp_alteracoes'))


@parcerias_bp.route("/alteracao/deletar", methods=["POST"])
@login_required
@requires_access('parcerias')
def deletar_alteracao():
    """
    Deletar alteração(ões) de termo
    Deleta todos os registros com a mesma combinação de termo/instrumento/número
    """
    numero_termo = request.args.get('numero_termo', '').strip()
    instrumento = request.args.get('instrumento', '').strip()
    alt_numero = int(request.args.get('alt_numero', 0))
    
    cur = get_cursor()
    
    try:
        # Deletar todos os registros com essa combinação
        cur.execute("""
            DELETE FROM public.termos_alteracoes
            WHERE numero_termo = %s 
              AND instrumento_alteracao = %s 
              AND alt_numero = %s
        """, (numero_termo, instrumento, alt_numero))
        
        registros_deletados = cur.rowcount
        
        get_db().commit()
        cur.close()
        
        flash(f'Alteração(ões) do termo "{numero_termo}" excluída(s) com sucesso! ({registros_deletados} registro(s))', 'success')
        return redirect(url_for('parcerias.dgp_alteracoes'))
        
    except Exception as e:
        print(f"[ERRO] Erro ao deletar alteração: {str(e)}")
        get_db().rollback()
        flash(f'Erro ao deletar alteração: {str(e)}', 'danger')
        return redirect(url_for('parcerias.dgp_alteracoes'))


# ========== APIs para Informações Adicionais e Endereços ==========

@parcerias_bp.route("/api/distritos", methods=["GET"])
@login_required
@requires_access('parcerias')
def api_distritos():
    """
    API para buscar distritos de c_geral_regionalizacao
    Retorna lista para Select2
    """
    q = request.args.get('q', '').strip()
    
    cur = get_cursor()
    
    try:
        if q:
            cur.execute("""
                SELECT DISTINCT codigo_distrital, distrito, subprefeitura, regiao
                FROM categoricas.c_geral_regionalizacao
                WHERE distrito ILIKE %s
                ORDER BY distrito
                LIMIT 50
            """, (f'%{q}%',))
        else:
            cur.execute("""
                SELECT DISTINCT codigo_distrital, distrito, subprefeitura, regiao
                FROM categoricas.c_geral_regionalizacao
                ORDER BY distrito
                LIMIT 50
            """)
        
        distritos = cur.fetchall()
        
        # Formatar para Select2
        resultado = []
        for row in distritos:
            resultado.append({
                'id': row['codigo_distrital'],
                'text': row['distrito'],
                'subprefeitura': row['subprefeitura'],
                'regiao': row['regiao']
            })
        
        cur.close()
        return jsonify(resultado)
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar distritos: {str(e)}")
        return jsonify([]), 500


@parcerias_bp.route("/api/distrito-info/<codigo>", methods=["GET"])
@login_required
@requires_access('parcerias')
def api_distrito_info(codigo):
    """
    API para buscar informações de um distrito específico
    Retorna subprefeitura e região
    """
    cur = get_cursor()
    
    try:
        cur.execute("""
            SELECT DISTINCT distrito, subprefeitura, regiao
            FROM categoricas.c_geral_regionalizacao
            WHERE codigo_distrital = %s
            LIMIT 1
        """, (codigo,))
        
        info = cur.fetchone()
        cur.close()
        
        if info:
            return jsonify({
                'success': True,
                'distrito': info['distrito'],
                'subprefeitura': info['subprefeitura'],
                'regiao': info['regiao']
            })
        else:
            return jsonify({'success': False}), 404
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar info do distrito: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@parcerias_bp.route("/api/enderecos/<numero_termo>", methods=["GET"])
@login_required
@requires_access('parcerias')
def api_enderecos_termo(numero_termo):
    """
    API para buscar todos os endereços de um termo
    Usado na alteração "Localização do projeto"
    """
    cur = get_cursor()
    
    try:
        cur.execute("""
            SELECT 
                id,
                parceria_logradouro,
                parceria_numero,
                parceria_complemento,
                parceria_cep,
                parceria_distrito,
                observacao
            FROM public.parcerias_enderecos
            WHERE numero_termo = %s
            ORDER BY id
        """, (numero_termo,))
        
        enderecos = cur.fetchall()
        cur.close()
        
        # Converter para lista de dicionários
        resultado = []
        for end in enderecos:
            resultado.append({
                'id': end['id'],
                'parceria_logradouro': end['parceria_logradouro'] or '',
                'parceria_numero': end['parceria_numero'] or '',
                'parceria_complemento': end['parceria_complemento'] or '',
                'parceria_cep': end['parceria_cep'] or '',
                'parceria_distrito': end['parceria_distrito'] or '',
                'observacao': end['observacao'] or ''
            })
        
        return jsonify({
            'success': True,
            'enderecos': resultado
        })
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar endereços: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
