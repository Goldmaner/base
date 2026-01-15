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
