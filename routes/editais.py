"""
Blueprint de gestão de editais
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, session
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access
import csv
from io import StringIO
from datetime import datetime

editais_bp = Blueprint('editais', __name__, url_prefix='/editais')


@editais_bp.route("/", methods=["GET"])
@login_required
@requires_access('editais')
def listar():
    """
    Listagem de editais com filtros
    """
    cur = get_cursor()
    
    try:
        # Obter filtros
        filtro_tipo = request.args.get('filtro_tipo', '').strip()
        filtro_nome = request.args.get('filtro_nome', '').strip()
        filtro_ano = request.args.get('filtro_ano', '').strip()
        filtro_unidade = request.args.get('filtro_unidade', '').strip()
        filtro_responsavel = request.args.get('filtro_responsavel', '').strip()
        filtro_status = request.args.get('filtro_status', '').strip()
        
        # Buscar anos disponíveis para o filtro
        cur.execute("""
            SELECT DISTINCT edital_ano
            FROM public.parcerias_edital
            WHERE edital_ano IS NOT NULL
            ORDER BY edital_ano DESC
        """)
        anos_disponiveis = [row['edital_ano'] for row in cur.fetchall()]
        
        # Buscar tipos disponíveis
        cur.execute("""
            SELECT DISTINCT edital_tipo
            FROM public.parcerias_edital
            WHERE edital_tipo IS NOT NULL AND edital_tipo != ''
            ORDER BY edital_tipo
        """)
        tipos_disponiveis = [row['edital_tipo'] for row in cur.fetchall()]
        
        # Buscar unidades gestoras disponíveis
        cur.execute("""
            SELECT DISTINCT edital_unidade_gestora
            FROM public.parcerias_edital
            WHERE edital_unidade_gestora IS NOT NULL AND edital_unidade_gestora != ''
            ORDER BY edital_unidade_gestora
        """)
        unidades_disponiveis = [row['edital_unidade_gestora'] for row in cur.fetchall()]
        
        # Buscar status disponíveis de categoricas.c_dp_status_edital
        cur.execute("""
            SELECT status
            FROM categoricas.c_dp_status_edital
            ORDER BY status
        """)
        status_disponiveis = [row['status'] for row in cur.fetchall()]
        
        # Query base
        query = """
            SELECT 
                id,
                edital_tipo,
                edital_nome,
                edital_ano,
                edital_unidade_gestora,
                edital_responsavel,
                edital_processo_sei,
                edital_objeto,
                edital_data_publicacao,
                edital_data_homologacao,
                status,
                criado_em
            FROM public.parcerias_edital
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if filtro_tipo:
            query += " AND edital_tipo = %s"
            params.append(filtro_tipo)
        
        if filtro_nome:
            query += " AND LOWER(edital_nome) LIKE LOWER(%s)"
            params.append(f"%{filtro_nome}%")
        
        if filtro_ano and filtro_ano.isdigit():
            query += " AND edital_ano = %s"
            params.append(int(filtro_ano))
        
        if filtro_unidade:
            query += " AND edital_unidade_gestora = %s"
            params.append(filtro_unidade)
        
        if filtro_responsavel:
            query += " AND LOWER(edital_responsavel) LIKE LOWER(%s)"
            params.append(f"%{filtro_responsavel}%")
        
        if filtro_status:
            query += " AND status = %s"
            params.append(filtro_status)
        
        # Ordenação - do mais recente para o mais antigo
        query += " ORDER BY edital_ano DESC, edital_data_publicacao DESC NULLS LAST, edital_nome"
        
        # Paginação
        page = request.args.get('page', 1, type=int)
        per_page = 50
        offset = (page - 1) * per_page
        
        # Contar total
        count_query = f"SELECT COUNT(*) as total FROM ({query}) as subquery"
        cur.execute(count_query, params)
        total_count = cur.fetchone()['total']
        total_pages = (total_count + per_page - 1) // per_page
        
        # Buscar dados com paginação
        query += f" LIMIT {per_page} OFFSET {offset}"
        cur.execute(query, params)
        editais = cur.fetchall()
        
        cur.close()
        
        return render_template(
            'editais.html',
            editais=editais,
            anos_disponiveis=anos_disponiveis,
            tipos_disponiveis=tipos_disponiveis,
            unidades_disponiveis=unidades_disponiveis,
            status_disponiveis=status_disponiveis,
            page=page,
            total_pages=total_pages,
            total_count=total_count
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERRO] Erro ao carregar editais: {str(e)}")
        flash(f'Erro ao carregar dados: {str(e)}', 'danger')
        cur.close()
        return redirect(url_for('main.index'))


@editais_bp.route("/exportar_csv", methods=["GET"])
@login_required
@requires_access('editais')
def exportar_csv():
    """
    Exportar editais para CSV (respeitando filtros ativos)
    """
    cur = get_cursor()
    
    try:
        # Obter filtros (mesmos da página principal)
        filtro_tipo = request.args.get('filtro_tipo', '').strip()
        filtro_nome = request.args.get('filtro_nome', '').strip()
        filtro_ano = request.args.get('filtro_ano', '').strip()
        filtro_unidade = request.args.get('filtro_unidade', '').strip()
        filtro_responsavel = request.args.get('filtro_responsavel', '').strip()
        filtro_status = request.args.get('filtro_status', '').strip()
        
        # Query base
        query = """
            SELECT 
                edital_tipo,
                edital_nome,
                edital_ano,
                edital_unidade_gestora,
                edital_responsavel,
                edital_processo_sei,
                edital_objeto,
                edital_data_publicacao,
                edital_data_homologacao,
                status
            FROM public.parcerias_edital
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if filtro_tipo:
            query += " AND edital_tipo = %s"
            params.append(filtro_tipo)
        
        if filtro_nome:
            query += " AND LOWER(edital_nome) LIKE LOWER(%s)"
            params.append(f"%{filtro_nome}%")
        
        if filtro_ano and filtro_ano.isdigit():
            query += " AND edital_ano = %s"
            params.append(int(filtro_ano))
        
        if filtro_unidade:
            query += " AND edital_unidade_gestora = %s"
            params.append(filtro_unidade)
        
        if filtro_responsavel:
            query += " AND LOWER(edital_responsavel) LIKE LOWER(%s)"
            params.append(f"%{filtro_responsavel}%")
        
        if filtro_status:
            query += " AND status = %s"
            params.append(filtro_status)
        
        query += " ORDER BY edital_ano DESC, edital_data_publicacao DESC NULLS LAST"
        
        cur.execute(query, params)
        editais = cur.fetchall()
        
        cur.close()
        
        # Gerar CSV com encoding UTF-8-BOM e separador ponto e vírgula
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Cabeçalho
        writer.writerow([
            'Tipo',
            'Nome',
            'Ano',
            'Unidade Gestora',
            'Responsável',
            'Processo SEI',
            'Objeto',
            'Data Publicação',
            'Data Homologação',
            'Status'
        ])
        
        # Dados
        for e in editais:
            writer.writerow([
                e['edital_tipo'] or '',
                e['edital_nome'] or '',
                e['edital_ano'] or '',
                e['edital_unidade_gestora'] or '',
                e['edital_responsavel'] or '',
                e['edital_processo_sei'] or '',
                e['edital_objeto'] or '',
                e['edital_data_publicacao'].strftime('%d/%m/%Y') if e['edital_data_publicacao'] else '',
                e['edital_data_homologacao'].strftime('%d/%m/%Y') if e['edital_data_homologacao'] else '',
                e['status'] or ''
            ])
        
        # Preparar resposta com BOM UTF-8
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'editais_{timestamp}.csv'
        
        # Adicionar BOM UTF-8 no início
        csv_content = '\ufeff' + output.getvalue()
        
        return Response(
            csv_content.encode('utf-8'),
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8'
            }
        )
        
    except Exception as e:
        print(f"[ERRO] Erro ao exportar CSV: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f"Erro ao exportar CSV: {str(e)}", "danger")
        return redirect(url_for('editais.listar'))


@editais_bp.route("/criar", methods=["POST"])
@login_required
@requires_access('editais')
def criar():
    """
    Criar novo edital
    """
    try:
        edital_tipo = request.form.get('edital_tipo', '').strip()
        edital_nome = request.form.get('edital_nome', '').strip()
        edital_ano = request.form.get('edital_ano', '').strip()
        edital_unidade_gestora = request.form.get('edital_unidade_gestora', '').strip()
        edital_responsavel = request.form.get('edital_responsavel', '').strip()
        edital_processo_sei = request.form.get('edital_processo_sei', '').strip()
        edital_objeto = request.form.get('edital_objeto', '').strip()
        edital_data_publicacao = request.form.get('edital_data_publicacao', '').strip()
        edital_data_homologacao = request.form.get('edital_data_homologacao', '').strip()
        status = request.form.get('status', '').strip()
        
        # Validações
        if not all([edital_tipo, edital_nome, edital_ano]):
            flash('Campos obrigatórios: Tipo, Nome e Ano!', 'danger')
            return redirect(url_for('editais.listar'))
        
        cur = get_cursor()
        cur.execute("""
            INSERT INTO public.parcerias_edital 
            (edital_tipo, edital_nome, edital_ano, edital_unidade_gestora, edital_responsavel, 
             edital_processo_sei, edital_objeto, edital_data_publicacao, edital_data_homologacao, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (edital_tipo, edital_nome, int(edital_ano), edital_unidade_gestora, edital_responsavel,
              edital_processo_sei, edital_objeto, 
              edital_data_publicacao if edital_data_publicacao else None,
              edital_data_homologacao if edital_data_homologacao else None,
              status))
        
        get_db().commit()
        cur.close()
        
        flash(f'Edital "{edital_nome}" cadastrado com sucesso!', 'success')
        return redirect(url_for('editais.listar'))
        
    except Exception as e:
        get_db().rollback()
        print(f"[ERRO] Erro ao criar edital: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao criar edital: {str(e)}', 'danger')
        return redirect(url_for('editais.listar'))


@editais_bp.route("/editar/<int:id>", methods=["POST"])
@login_required
@requires_access('editais')
def editar(id):
    """
    Editar edital existente
    """
    try:
        edital_tipo = request.form.get('edital_tipo', '').strip()
        edital_nome = request.form.get('edital_nome', '').strip()
        edital_ano = request.form.get('edital_ano', '').strip()
        edital_unidade_gestora = request.form.get('edital_unidade_gestora', '').strip()
        edital_responsavel = request.form.get('edital_responsavel', '').strip()
        edital_processo_sei = request.form.get('edital_processo_sei', '').strip()
        edital_objeto = request.form.get('edital_objeto', '').strip()
        edital_data_publicacao = request.form.get('edital_data_publicacao', '').strip()
        edital_data_homologacao = request.form.get('edital_data_homologacao', '').strip()
        status = request.form.get('status', '').strip()
        
        # Validações
        if not all([edital_tipo, edital_nome, edital_ano]):
            flash('Campos obrigatórios: Tipo, Nome e Ano!', 'danger')
            return redirect(url_for('editais.listar'))
        
        cur = get_cursor()
        cur.execute("""
            UPDATE public.parcerias_edital
            SET edital_tipo = %s,
                edital_nome = %s,
                edital_ano = %s,
                edital_unidade_gestora = %s,
                edital_responsavel = %s,
                edital_processo_sei = %s,
                edital_objeto = %s,
                edital_data_publicacao = %s,
                edital_data_homologacao = %s,
                status = %s
            WHERE id = %s
        """, (edital_tipo, edital_nome, int(edital_ano), edital_unidade_gestora, edital_responsavel,
              edital_processo_sei, edital_objeto,
              edital_data_publicacao if edital_data_publicacao else None,
              edital_data_homologacao if edital_data_homologacao else None,
              status, id))
        
        if cur.rowcount == 0:
            flash('Edital não encontrado!', 'danger')
        else:
            get_db().commit()
            flash(f'Edital "{edital_nome}" atualizado com sucesso!', 'success')
        
        cur.close()
        return redirect(url_for('editais.listar'))
        
    except Exception as e:
        get_db().rollback()
        print(f"[ERRO] Erro ao editar edital: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao editar edital: {str(e)}', 'danger')
        return redirect(url_for('editais.listar'))


@editais_bp.route("/deletar/<int:id>", methods=["POST"])
@login_required
@requires_access('editais')
def deletar(id):
    """
    Deletar edital
    """
    try:
        cur = get_cursor()
        
        # Buscar dados antes de deletar para mensagem
        cur.execute("SELECT edital_nome FROM public.parcerias_edital WHERE id = %s", (id,))
        edital = cur.fetchone()
        
        if not edital:
            flash('Edital não encontrado!', 'danger')
            cur.close()
            return redirect(url_for('editais.listar'))
        
        nome = edital['edital_nome']
        
        # Deletar
        cur.execute("DELETE FROM public.parcerias_edital WHERE id = %s", (id,))
        get_db().commit()
        cur.close()
        
        flash(f'Edital "{nome}" excluído com sucesso!', 'success')
        return redirect(url_for('editais.listar'))
        
    except Exception as e:
        get_db().rollback()
        print(f"[ERRO] Erro ao deletar edital: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao deletar edital: {str(e)}', 'danger')
        return redirect(url_for('editais.listar'))


# ==================== ORÇAMENTO DE EDITAIS ====================

@editais_bp.route("/orcamento", methods=["GET"])
@login_required
@requires_access('editais')
def orcamento_listar():
    """Listagem de orçamentos de editais (consolidado)"""
    from flask import jsonify
    cur = get_cursor()
    
    try:
        # Buscar editais agrupados
        cur.execute("""
            SELECT 
                edital_nome,
                edital_tipo,
                edital_unidade,
                dotacao_formatada,
                projeto_atividade,
                etapa,
                observacoes,
                MIN(nome_mes) as vigencia_inicio,
                MAX(nome_mes) as vigencia_fim,
                SUM(valor_mes) as valor_total,
                COUNT(*) as qtd_meses,
                created_por,
                MAX(created_em) as ultima_atualizacao
            FROM gestao_financeira.orcamento_edital_nova
            GROUP BY edital_nome, edital_tipo, edital_unidade, dotacao_formatada, projeto_atividade, etapa, observacoes, created_por
            ORDER BY ultima_atualizacao DESC
        """)
        
        editais = []
        for row in cur.fetchall():
            vigencia_str = ''
            if row['vigencia_inicio'] and row['vigencia_fim']:
                inicio = row['vigencia_inicio']
                fim = row['vigencia_fim']
                
                # Mapear meses em português
                meses_pt = {
                    'Jan': 'jan', 'Feb': 'fev', 'Mar': 'mar', 'Apr': 'abr',
                    'May': 'mai', 'Jun': 'jun', 'Jul': 'jul', 'Aug': 'ago',
                    'Sep': 'set', 'Oct': 'out', 'Nov': 'nov', 'Dec': 'dez'
                }
                
                inicio_mes = meses_pt.get(inicio.strftime('%b'), inicio.strftime('%b').lower())
                fim_mes = meses_pt.get(fim.strftime('%b'), fim.strftime('%b').lower())
                vigencia_str = f"{inicio_mes}/{inicio.strftime('%y')}-{fim_mes}/{fim.strftime('%y')} ({row['qtd_meses']} meses)"
            
            editais.append({
                'edital_nome': row['edital_nome'],
                'edital_tipo': row['edital_tipo'] or '-',
                'edital_unidade': row['edital_unidade'] or '-',
                'dotacao_formatada': row['dotacao_formatada'] or '-',
                'projeto_atividade': row['projeto_atividade'] or '-',
                'valor_total': float(row['valor_total'] or 0),
                'vigencia': vigencia_str,
                'etapa': row['etapa'] or '-',
                'observacoes': row['observacoes'] or '-',
                'created_por': row['created_por'] or '-'
            })
        
        # Buscar unidades disponíveis (coordenacao)
        cur.execute("""
            SELECT DISTINCT coordenacao
            FROM categoricas.c_geral_dotacoes
            WHERE coordenacao IS NOT NULL AND coordenacao != ''
            ORDER BY coordenacao
        """)
        unidades_disponiveis = [row['coordenacao'] for row in cur.fetchall()]
        
        cur.close()
        
        return render_template('editais_orcamento.html', 
                             editais=editais,
                             unidades_disponiveis=unidades_disponiveis,
                             total_count=len(editais))
        
    except Exception as e:
        print(f"[ERRO] Erro ao listar orçamentos de editais: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao carregar orçamentos: {str(e)}', 'danger')
        return render_template('editais_orcamento.html', editais=[], unidades_disponiveis=[], total_count=0)


@editais_bp.route("/orcamento/api/dotacoes", methods=["GET"])
@login_required
@requires_access('editais')
def api_dotacoes():
    """API para buscar dotações por unidade"""
    from flask import jsonify
    cur = get_cursor()
    
    try:
        unidade = request.args.get('unidade', '').strip()
        
        if not unidade:
            return jsonify({'success': False, 'error': 'Unidade não fornecida'})
        
        print(f"\n[DEBUG API DOTAÇÕES] Buscando dotações para unidade: '{unidade}'")
        
        # Query com TRIM e comparação case-insensitive
        cur.execute("""
            SELECT DISTINCT dotacao_numero
            FROM categoricas.c_geral_dotacoes
            WHERE TRIM(coordenacao) ILIKE TRIM(%s)
              AND dotacao_numero IS NOT NULL
              AND dotacao_numero != ''
            ORDER BY dotacao_numero
        """, (unidade,))
        
        dotacoes = [row['dotacao_numero'] for row in cur.fetchall()]
        
        print(f"[DEBUG API DOTAÇÕES] Encontradas {len(dotacoes)} dotações")
        if len(dotacoes) > 0:
            print(f"[DEBUG API DOTAÇÕES] Primeiras 3 dotações: {dotacoes[:3]}")
        
        cur.close()
        
        return jsonify({'success': True, 'dotacoes': dotacoes})
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar dotações: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})


@editais_bp.route("/orcamento/api/edital/<edital_nome>", methods=["GET"])
@login_required
@requires_access('editais')
def api_edital_detalhes(edital_nome):
    """API para buscar detalhes completos de um edital (todos os meses)"""
    from flask import jsonify
    cur = get_cursor()
    
    try:
        cur.execute("""
            SELECT 
                id,
                edital_nome,
                edital_tipo,
                edital_unidade,
                dotacao_formatada,
                projeto_atividade,
                valor_mes,
                nome_mes,
                etapa,
                observacoes,
                created_por
            FROM gestao_financeira.orcamento_edital_nova
            WHERE edital_nome = %s
            ORDER BY nome_mes
        """, (edital_nome,))
        
        meses = []
        edital_info = None
        
        for row in cur.fetchall():
            if not edital_info:
                edital_info = {
                    'edital_nome': row['edital_nome'],
                    'edital_tipo': row['edital_tipo'],
                    'edital_unidade': row['edital_unidade'],
                    'dotacao_formatada': row['dotacao_formatada'],
                    'projeto_atividade': row['projeto_atividade'],
                    'etapa': row['etapa'],
                    'observacoes': row['observacoes']
                }
            
            meses.append({
                'id': row['id'],
                'valor_mes': float(row['valor_mes'] or 0),
                'nome_mes': row['nome_mes'].strftime('%Y-%m-%d') if row['nome_mes'] else None
            })
        
        cur.close()
        
        return jsonify({'success': True, 'edital': edital_info, 'meses': meses})
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar detalhes do edital: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@editais_bp.route("/orcamento/criar", methods=["POST"])
@login_required
@requires_access('editais')
def orcamento_criar():
    """Criar novo orçamento de edital com cronograma mensal"""
    from flask import jsonify
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Dados do formulário
        edital_nome = request.form.get('edital_nome', '').strip()
        edital_tipo = request.form.get('edital_tipo', '-').strip()
        edital_unidade = request.form.get('edital_unidade', '').strip()
        dotacao_formatada = request.form.get('dotacao_formatada', '').strip()
        projeto_atividade = request.form.get('projeto_atividade', '').strip()
        etapa = request.form.get('etapa', 'Em estudo preliminar').strip()
        observacoes = request.form.get('observacoes', '').strip()
        
        # Cronograma mensal (JSON ou form data)
        import json
        meses_data = request.form.get('meses_data', '[]')
        meses = json.loads(meses_data)
        
        if not edital_nome:
            flash('Nome do edital é obrigatório!', 'danger')
            return redirect(url_for('editais.orcamento_listar'))
        
        if not meses:
            flash('Adicione pelo menos um mês no cronograma!', 'danger')
            return redirect(url_for('editais.orcamento_listar'))
        
        # Verificar se já existe edital com esse nome
        cur.execute("""
            SELECT COUNT(*) as qtd
            FROM gestao_financeira.orcamento_edital_nova
            WHERE edital_nome = %s
        """, (edital_nome,))
        
        if cur.fetchone()['qtd'] > 0:
            flash(f'Já existe um edital com o nome "{edital_nome}"!', 'danger')
            return redirect(url_for('editais.orcamento_listar'))
        
        # Obter usuário logado
        username = session.get('username', 'Sistema')
        
        # Inserir cada mês como uma linha
        for mes in meses:
            cur.execute("""
                INSERT INTO gestao_financeira.orcamento_edital_nova
                (edital_nome, edital_tipo, edital_unidade, dotacao_formatada, projeto_atividade, 
                 valor_mes, nome_mes, etapa, observacoes, created_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                edital_nome,
                edital_tipo,
                edital_unidade,
                dotacao_formatada,
                projeto_atividade,
                mes['valor'],
                mes['mes'],
                etapa,
                observacoes,
                username
            ))
        
        conn.commit()
        cur.close()
        
        flash(f'Orçamento do edital "{edital_nome}" cadastrado com sucesso! ({len(meses)} meses)', 'success')
        return redirect(url_for('editais.orcamento_listar'))
        
    except Exception as e:
        conn.rollback()
        print(f"[ERRO] Erro ao criar orçamento: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao cadastrar orçamento: {str(e)}', 'danger')
        return redirect(url_for('editais.orcamento_listar'))


@editais_bp.route("/orcamento/deletar/<edital_nome>", methods=["POST"])
@login_required
@requires_access('editais')
def orcamento_deletar(edital_nome):
    """Deletar orçamento de edital (todas as linhas)"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Deletar todas as linhas do edital
        cur.execute("""
            DELETE FROM gestao_financeira.orcamento_edital_nova
            WHERE edital_nome = %s
        """, (edital_nome,))
        
        conn.commit()
        cur.close()
        
        flash(f'Orçamento do edital "{edital_nome}" excluído com sucesso!', 'success')
        return redirect(url_for('editais.orcamento_listar'))
        
    except Exception as e:
        conn.rollback()
        print(f"[ERRO] Erro ao deletar orçamento: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao deletar orçamento: {str(e)}', 'danger')
        return redirect(url_for('editais.orcamento_listar'))


@editais_bp.route("/orcamento/editar/<edital_nome>", methods=["POST"])
@login_required
@requires_access('editais')
def orcamento_editar(edital_nome):
    """Editar orçamento de edital (deletar tudo e reinserir)"""
    conn = get_db()
    cur = get_cursor()
    
    try:
        # Dados do formulário
        edital_nome_novo = request.form.get('edital_nome', '').strip()
        edital_tipo = request.form.get('edital_tipo', '-').strip()
        edital_unidade = request.form.get('edital_unidade', '').strip()
        dotacao_formatada = request.form.get('dotacao_formatada', '').strip()
        projeto_atividade = request.form.get('projeto_atividade', '').strip()
        etapa = request.form.get('etapa', 'Em estudo preliminar').strip()
        observacoes = request.form.get('observacoes', '').strip()
        
        # Cronograma mensal
        import json
        meses_data = request.form.get('meses_data', '[]')
        meses = json.loads(meses_data)
        
        if not edital_nome_novo:
            flash('Nome do edital é obrigatório!', 'danger')
            return redirect(url_for('editais.orcamento_listar'))
        
        if not meses:
            flash('Adicione pelo menos um mês no cronograma!', 'danger')
            return redirect(url_for('editais.orcamento_listar'))
        
        # Obter usuário logado
        username = session.get('username', 'Sistema')
        
        # Deletar todas as linhas antigas
        cur.execute("""
            DELETE FROM gestao_financeira.orcamento_edital_nova
            WHERE edital_nome = %s
        """, (edital_nome,))
        
        # Inserir novamente com dados atualizados
        for mes in meses:
            cur.execute("""
                INSERT INTO gestao_financeira.orcamento_edital_nova
                (edital_nome, edital_tipo, edital_unidade, dotacao_formatada, projeto_atividade, 
                 valor_mes, nome_mes, etapa, observacoes, created_por)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                edital_nome_novo,
                edital_tipo,
                edital_unidade,
                dotacao_formatada,
                projeto_atividade,
                mes['valor'],
                mes['mes'],
                etapa,
                observacoes,
                username
            ))
        
        conn.commit()
        cur.close()
        
        flash(f'Orçamento do edital "{edital_nome_novo}" atualizado com sucesso! ({len(meses)} meses)', 'success')
        return redirect(url_for('editais.orcamento_listar'))
        
    except Exception as e:
        conn.rollback()
        print(f"[ERRO] Erro ao editar orçamento: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao editar orçamento: {str(e)}', 'danger')
        return redirect(url_for('editais.orcamento_listar'))
