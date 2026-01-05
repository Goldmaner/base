"""
Blueprint de parcerias (listagem e formulário)
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify
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
    cur.execute("SELECT informacao FROM categoricas.c_tipo_contrato ORDER BY informacao")
    tipos_contrato_raw = cur.fetchall()
    tipos_contrato = [row['informacao'] for row in tipos_contrato_raw]
    
    # Buscar pessoas gestoras para o dropdown de filtro (todas, incluindo inativas)
    cur.execute("SELECT DISTINCT nome_pg FROM categoricas.c_pessoa_gestora ORDER BY nome_pg")
    pessoas_gestoras_filtro = [row['nome_pg'] for row in cur.fetchall()]
    
    # DEBUG: Verificar duplicação
    print(f"[DEBUG] Total de tipos_contrato retornados: {len(tipos_contrato)}")
    print(f"[DEBUG] Tipos únicos: {len(set(tipos_contrato))}")
    if len(tipos_contrato) != len(set(tipos_contrato)):
        print(f"[ALERTA] DUPLICAÇÃO DETECTADA em c_tipo_contrato!")
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
             LEFT JOIN categoricas.c_pessoa_gestora cpg ON cpg.nome_pg = pg.nome_pg
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
                LEFT JOIN categoricas.c_pessoa_gestora cpg ON cpg.nome_pg = pg.nome_pg
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
                
                # Registrar na tabela de auditoria parcerias_pg
                numero_termo = request.form.get('numero_termo')
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
    cur.execute("SELECT informacao FROM categoricas.c_tipo_contrato ORDER BY informacao")
    tipos_contrato = [row['informacao'] for row in cur.fetchall()]
    cur.execute("SELECT lei FROM categoricas.c_legislacao ORDER BY lei")
    legislacoes = [row['lei'] for row in cur.fetchall()]
    
    # Buscar pessoas gestoras (todas, incluindo inativas)
    cur.execute("SELECT nome_pg, numero_rf, status_pg FROM categoricas.c_pessoa_gestora ORDER BY nome_pg")
    pessoas_gestoras = cur.fetchall()
    
    cur.close()
    
    # Verificar se há um número de termo na query string (vindo da conferência)
    numero_termo_param = request.args.get('numero_termo', '')
    
    # Criar objeto parceria com dados pré-preenchidos se existir
    parceria_preenchida = None
    if numero_termo_param:
        # Buscar dados do CSV para este termo
        import pandas as pd
        import os
        
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'saida.csv')
        
        if os.path.exists(csv_path):
            try:
                df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig')
                # Buscar a linha correspondente ao termo
                termo_data = df[df['numero_termo'] == numero_termo_param]
                
                if not termo_data.empty:
                    # Converter para dicionário
                    parceria_preenchida = termo_data.iloc[0].to_dict()
                    
                    # Converter valores NaN para None/vazios
                    for key, value in parceria_preenchida.items():
                        if pd.isna(value):
                            parceria_preenchida[key] = None
                    
                    # Tratar datas do pandas (Timestamp) para string no formato YYYY-MM-DD
                    if parceria_preenchida.get('inicio') and isinstance(parceria_preenchida['inicio'], pd.Timestamp):
                        parceria_preenchida['inicio'] = parceria_preenchida['inicio'].strftime('%Y-%m-%d')
                    if parceria_preenchida.get('final') and isinstance(parceria_preenchida['final'], pd.Timestamp):
                        parceria_preenchida['final'] = parceria_preenchida['final'].strftime('%Y-%m-%d')
                else:
                    # Se não encontrou no CSV, criar apenas com numero_termo
                    parceria_preenchida = {'numero_termo': numero_termo_param}
            except Exception as e:
                print(f"[ERRO] Ao ler CSV: {e}")
                parceria_preenchida = {'numero_termo': numero_termo_param}
        else:
            parceria_preenchida = {'numero_termo': numero_termo_param}
    
    return render_template("parcerias_form.html", 
                         parceria=parceria_preenchida,
                         tipos_contrato=tipos_contrato,
                         legislacoes=legislacoes,
                         pessoas_gestoras=pessoas_gestoras,
                         rf_pessoa_gestora=None,
                         modo_importacao=True if parceria_preenchida else False)


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
    cur.execute("SELECT informacao FROM categoricas.c_tipo_contrato ORDER BY informacao")
    tipos_contrato = [row['informacao'] for row in cur.fetchall()]
    cur.execute("SELECT lei FROM categoricas.c_legislacao ORDER BY lei")
    legislacoes = [row['lei'] for row in cur.fetchall()]
    
    # Buscar pessoas gestoras (todas, incluindo inativas)
    cur.execute("SELECT nome_pg, numero_rf, status_pg FROM categoricas.c_pessoa_gestora ORDER BY nome_pg")
    pessoas_gestoras = cur.fetchall()
    
    # Buscar RF da pessoa gestora atual se existir
    rf_pessoa_gestora = None
    if pg_result:
        cur.execute("SELECT numero_rf FROM categoricas.c_pessoa_gestora WHERE nome_pg = %s", (pg_result['nome_pg'],))
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
    
    cur.close()
    
    return render_template("parcerias_form.html", 
                         parceria=parceria,
                         tipos_contrato=tipos_contrato,
                         legislacoes=legislacoes,
                         pessoas_gestoras=pessoas_gestoras,
                         rf_pessoa_gestora=rf_pessoa_gestora,
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
    cur.execute("SELECT id, informacao, sigla FROM categoricas.c_tipo_contrato ORDER BY sigla")
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
                    LEFT JOIN categoricas.c_pessoa_gestora cpg ON cpg.nome_pg = pg.nome_pg
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
    Compara as parcerias do CSV com as do banco
    e mostra as parcerias não inseridas no sistema com todos os dados
    """
    print("[DEBUG CONFERENCIA] Função conferencia() foi chamada!")
    
    import pandas as pd
    import os
    
    try:
        # Caminho do CSV gerado pelo script import_conferencia.py
        csv_path = os.path.join(os.path.dirname(__file__), '..', 'scripts', 'saida.csv')
        csv_path_abs = os.path.abspath(csv_path)
        
        print(f"[DEBUG CONFERENCIA] Procurando CSV em: {csv_path_abs}")
        print(f"[DEBUG CONFERENCIA] Arquivo existe: {os.path.exists(csv_path_abs)}")
        
        # Verifica se o arquivo existe
        if not os.path.exists(csv_path):
            flash("Arquivo de conferência não encontrado. Clique em 'Atualizar' para gerar.", "warning")
            print(f"[DEBUG CONFERENCIA] Redirecionando para listar - arquivo não existe")
            return redirect(url_for('parcerias.listar'))
        
        # Lê o CSV com todos os campos
        df = pd.read_csv(csv_path, sep=';', encoding='utf-8-sig')
        
        print(f"[DEBUG CONFERENCIA] CSV lido com sucesso - {len(df)} linhas")
        print(f"[DEBUG CONFERENCIA] Colunas: {list(df.columns)}")
        
        # O CSV já contém apenas os termos não inseridos
        termos_nao_inseridos = df['numero_termo'].tolist()
        
        # Busca total de termos no banco para estatísticas
        cur = get_cursor()
        cur.execute("SELECT COUNT(DISTINCT numero_termo) as total FROM Parcerias")
        total_database = cur.fetchone()['total']
        cur.close()
        
        print(f"[DEBUG CONFERENCIA] Total no banco: {total_database}")
        print(f"[DEBUG CONFERENCIA] Termos não inseridos: {len(termos_nao_inseridos)}")
        
        # Estatísticas
        total_nao_inseridos = len(termos_nao_inseridos)
        total_planilha = total_database + total_nao_inseridos
        total_inseridos = total_database
        
        return render_template(
            'temp_conferencia.html',
            termos_nao_inseridos=termos_nao_inseridos,
            total_planilha=total_planilha,
            total_database=total_database,
            total_nao_inseridos=total_nao_inseridos,
            total_inseridos=total_inseridos
        )
        
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
        FROM categoricas.c_analistas_dgp
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
        FROM categoricas.c_analistas_dgp
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
