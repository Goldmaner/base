"""
Blueprint de gestão de férias
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify, session
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access
import csv
from io import StringIO
from datetime import datetime, timedelta

ferias_bp = Blueprint('ferias', __name__, url_prefix='/ferias')


@ferias_bp.route("/", methods=["GET"])
@login_required
@requires_access('ferias')
def listar():
    """
    Listagem de férias com filtros
    """
    cur = get_cursor()
    
    try:
        # Obter filtros
        filtro_nome = request.args.get('filtro_nome', '').strip()
        filtro_d_usuario = request.args.get('filtro_d_usuario', '').strip()
        filtro_ano = request.args.get('filtro_ano', '').strip()
        filtro_tipo_agente = request.args.get('filtro_tipo_agente', '').strip()
        
        # Buscar anos disponíveis para o filtro
        cur.execute("""
            SELECT DISTINCT EXTRACT(YEAR FROM ferias_inicio) as ano
            FROM gestao_pessoas.datas_ferias
            ORDER BY ano DESC
        """)
        anos_disponiveis = [int(row['ano']) for row in cur.fetchall()]
        
        # Query base
        query = """
            SELECT 
                df.id,
                df.d_usuario,
                df.nome_completo,
                df.ferias_inicio,
                df.ferias_fim,
                df.aquisitivo_inicio,
                df.aquisitivo_fim,
                (df.ferias_fim - df.ferias_inicio + 1) as dias_ferias,
                u.tipo_usuario
            FROM gestao_pessoas.datas_ferias df
            LEFT JOIN gestao_pessoas.usuarios u ON df.d_usuario = u.d_usuario
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if filtro_nome:
            query += " AND LOWER(df.nome_completo) LIKE LOWER(%s)"
            params.append(f"%{filtro_nome}%")
        
        if filtro_d_usuario:
            query += " AND LOWER(df.d_usuario) LIKE LOWER(%s)"
            params.append(f"%{filtro_d_usuario}%")
        
        if filtro_ano and filtro_ano.isdigit():
            query += " AND EXTRACT(YEAR FROM df.ferias_inicio) = %s"
            params.append(int(filtro_ano))
        
        if filtro_tipo_agente:
            query += " AND u.tipo_usuario = %s"
            params.append(filtro_tipo_agente)
        
        # Ordenação - do menor para o maior (ASC)
        query += " ORDER BY df.ferias_inicio ASC"
        
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
        ferias = cur.fetchall()
        
        # Buscar nomes únicos para o filtro
        cur.execute("""
            SELECT DISTINCT nome_completo
            FROM gestao_pessoas.datas_ferias
            ORDER BY nome_completo
        """)
        nomes_disponiveis = [row['nome_completo'] for row in cur.fetchall()]
        
        # Buscar d_usuarios da tabela de usuários
        cur.execute("""
            SELECT DISTINCT d_usuario, email
            FROM gestao_pessoas.usuarios
            WHERE d_usuario IS NOT NULL AND d_usuario != ''
            ORDER BY d_usuario
        """)
        usuarios_disponiveis = cur.fetchall()
        
        # Buscar tipos de agente disponíveis
        cur.execute("""
            SELECT DISTINCT u.tipo_usuario
            FROM gestao_pessoas.usuarios u
            INNER JOIN gestao_pessoas.datas_ferias df ON u.d_usuario = df.d_usuario
            WHERE u.tipo_usuario IS NOT NULL AND u.tipo_usuario != ''
            ORDER BY u.tipo_usuario
        """)
        tipos_agente_disponiveis = [row['tipo_usuario'] for row in cur.fetchall()]
        
        cur.close()
        
        # Verificar se usuário é admin ou Agente Público
        tipo_usuario_logado = session.get('tipo_usuario', '')
        mostrar_tipo_agente = tipo_usuario_logado in ['Agente Público', 'admin']
        
        return render_template(
            'ferias.html',
            ferias=ferias,
            anos_disponiveis=anos_disponiveis,
            nomes_disponiveis=nomes_disponiveis,
            usuarios_disponiveis=usuarios_disponiveis,
            tipos_agente_disponiveis=tipos_agente_disponiveis,
            mostrar_tipo_agente=mostrar_tipo_agente,
            page=page,
            total_pages=total_pages,
            total_count=total_count
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERRO] Erro ao carregar férias: {str(e)}")
        flash(f'Erro ao carregar dados: {str(e)}', 'danger')
        cur.close()
        return redirect(url_for('main.index'))


@ferias_bp.route("/exportar_csv", methods=["GET"])
@login_required
@requires_access('ferias')
def exportar_csv():
    """
    Exportar férias para CSV (respeitando filtros ativos)
    """
    cur = get_cursor()
    
    try:
        # Obter filtros (mesmos da página principal)
        filtro_nome = request.args.get('filtro_nome', '').strip()
        filtro_d_usuario = request.args.get('filtro_d_usuario', '').strip()
        filtro_ano = request.args.get('filtro_ano', '').strip()
        filtro_tipo_agente = request.args.get('filtro_tipo_agente', '').strip()
        
        # Query base
        query = """
            SELECT 
                df.d_usuario,
                df.nome_completo,
                df.ferias_inicio,
                df.ferias_fim,
                df.aquisitivo_inicio,
                df.aquisitivo_fim,
                (df.ferias_fim - df.ferias_inicio + 1) as dias_ferias,
                u.tipo_usuario
            FROM gestao_pessoas.datas_ferias df
            LEFT JOIN gestao_pessoas.usuarios u ON df.d_usuario = u.d_usuario
            WHERE 1=1
        """
        
        params = []
        
        # Aplicar filtros
        if filtro_nome:
            query += " AND LOWER(df.nome_completo) LIKE LOWER(%s)"
            params.append(f"%{filtro_nome}%")
        
        if filtro_d_usuario:
            query += " AND LOWER(df.d_usuario) LIKE LOWER(%s)"
            params.append(f"%{filtro_d_usuario}%")
        
        if filtro_ano and filtro_ano.isdigit():
            query += " AND EXTRACT(YEAR FROM df.ferias_inicio) = %s"
            params.append(int(filtro_ano))
        
        if filtro_tipo_agente:
            query += " AND u.tipo_usuario = %s"
            params.append(filtro_tipo_agente)
        
        query += " ORDER BY df.ferias_inicio ASC"
        
        cur.execute(query, params)
        ferias = cur.fetchall()
        
        cur.close()
        
        # Gerar CSV com encoding UTF-8-BOM e separador ponto e vírgula
        output = StringIO()
        writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
        
        # Cabeçalho
        writer.writerow([
            'Registro',
            'Nome Completo',
            'Tipo de Agente',
            'Início Férias',
            'Fim Férias',
            'Dias',
            'Período Aquisitivo Início',
            'Período Aquisitivo Fim'
        ])
        
        # Dados
        for f in ferias:
            writer.writerow([
                f['d_usuario'],
                f['nome_completo'],
                f['tipo_usuario'] or '-',
                f['ferias_inicio'].strftime('%d/%m/%Y') if f['ferias_inicio'] else '',
                f['ferias_fim'].strftime('%d/%m/%Y') if f['ferias_fim'] else '',
                f['dias_ferias'],
                f['aquisitivo_inicio'].strftime('%d/%m/%Y') if f['aquisitivo_inicio'] else '',
                f['aquisitivo_fim'].strftime('%d/%m/%Y') if f['aquisitivo_fim'] else ''
            ])
        
        # Preparar resposta com BOM UTF-8
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'ferias_{timestamp}.csv'
        
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
        return redirect(url_for('ferias.listar'))


@ferias_bp.route("/criar", methods=["POST"])
@login_required
@requires_access('ferias')
def criar():
    """
    Criar novo período de férias
    """
    try:
        d_usuario = request.form.get('d_usuario', '').strip()
        nome_completo = request.form.get('nome_completo', '').strip()
        ferias_inicio = request.form.get('ferias_inicio', '').strip()
        ferias_fim = request.form.get('ferias_fim', '').strip()
        aquisitivo_inicio = request.form.get('aquisitivo_inicio', '').strip()
        aquisitivo_fim = request.form.get('aquisitivo_fim', '').strip()
        
        # Validações
        if not all([d_usuario, nome_completo, ferias_inicio, ferias_fim, aquisitivo_inicio, aquisitivo_fim]):
            flash('Todos os campos são obrigatórios!', 'danger')
            return redirect(url_for('ferias.listar'))
        
        cur = get_cursor()
        cur.execute("""
            INSERT INTO gestao_pessoas.datas_ferias 
            (d_usuario, nome_completo, ferias_inicio, ferias_fim, aquisitivo_inicio, aquisitivo_fim)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (d_usuario, nome_completo, ferias_inicio, ferias_fim, aquisitivo_inicio, aquisitivo_fim))
        
        get_db().commit()
        cur.close()
        
        flash(f'Férias de {nome_completo} cadastradas com sucesso!', 'success')
        return redirect(url_for('ferias.listar'))
        
    except Exception as e:
        get_db().rollback()
        print(f"[ERRO] Erro ao criar férias: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao criar férias: {str(e)}', 'danger')
        return redirect(url_for('ferias.listar'))


@ferias_bp.route("/editar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def editar(id):
    """
    Editar período de férias existente
    """
    try:
        d_usuario = request.form.get('d_usuario', '').strip()
        nome_completo = request.form.get('nome_completo', '').strip()
        ferias_inicio = request.form.get('ferias_inicio', '').strip()
        ferias_fim = request.form.get('ferias_fim', '').strip()
        aquisitivo_inicio = request.form.get('aquisitivo_inicio', '').strip()
        aquisitivo_fim = request.form.get('aquisitivo_fim', '').strip()
        
        # Validações
        if not all([d_usuario, nome_completo, ferias_inicio, ferias_fim, aquisitivo_inicio, aquisitivo_fim]):
            flash('Todos os campos são obrigatórios!', 'danger')
            return redirect(url_for('ferias.listar'))
        
        cur = get_cursor()
        cur.execute("""
            UPDATE gestao_pessoas.datas_ferias
            SET d_usuario = %s,
                nome_completo = %s,
                ferias_inicio = %s,
                ferias_fim = %s,
                aquisitivo_inicio = %s,
                aquisitivo_fim = %s
            WHERE id = %s
        """, (d_usuario, nome_completo, ferias_inicio, ferias_fim, aquisitivo_inicio, aquisitivo_fim, id))
        
        if cur.rowcount == 0:
            flash('Férias não encontradas!', 'danger')
        else:
            get_db().commit()
            flash(f'Férias de {nome_completo} atualizadas com sucesso!', 'success')
        
        cur.close()
        return redirect(url_for('ferias.listar'))
        
    except Exception as e:
        get_db().rollback()
        print(f"[ERRO] Erro ao editar férias: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao editar férias: {str(e)}', 'danger')
        return redirect(url_for('ferias.listar'))


@ferias_bp.route("/deletar/<int:id>", methods=["POST"])
@login_required
@requires_access('ferias')
def deletar(id):
    """
    Deletar período de férias
    """
    try:
        cur = get_cursor()
        
        # Buscar dados antes de deletar para mensagem
        cur.execute("SELECT nome_completo FROM gestao_pessoas.datas_ferias WHERE id = %s", (id,))
        ferias = cur.fetchone()
        
        if not ferias:
            flash('Férias não encontradas!', 'danger')
            cur.close()
            return redirect(url_for('ferias.listar'))
        
        nome = ferias['nome_completo']
        
        # Deletar
        cur.execute("DELETE FROM gestao_pessoas.datas_ferias WHERE id = %s", (id,))
        get_db().commit()
        cur.close()
        
        flash(f'Férias de {nome} excluídas com sucesso!', 'success')
        return redirect(url_for('ferias.listar'))
        
    except Exception as e:
        get_db().rollback()
        print(f"[ERRO] Erro ao deletar férias: {str(e)}")
        import traceback
        traceback.print_exc()
        flash(f'Erro ao deletar férias: {str(e)}', 'danger')
        return redirect(url_for('ferias.listar'))


@ferias_bp.route("/calendario", methods=["GET"])
@login_required
@requires_access('ferias')
def calendario():
    """
    Visualização de calendário de férias
    """
    cur = get_cursor()
    
    try:
        # Buscar todas as férias para o calendário
        ano_filtro = request.args.get('ano', datetime.now().year, type=int)
        
        cur.execute("""
            SELECT 
                id,
                d_usuario,
                nome_completo,
                ferias_inicio,
                ferias_fim,
                (ferias_fim - ferias_inicio + 1) as dias_ferias
            FROM gestao_pessoas.datas_ferias
            WHERE EXTRACT(YEAR FROM ferias_inicio) = %s
               OR EXTRACT(YEAR FROM ferias_fim) = %s
            ORDER BY ferias_inicio
        """, (ano_filtro, ano_filtro))
        
        ferias = cur.fetchall()
        
        # Buscar anos disponíveis
        cur.execute("""
            SELECT DISTINCT EXTRACT(YEAR FROM ferias_inicio) as ano
            FROM gestao_pessoas.datas_ferias
            ORDER BY ano DESC
        """)
        anos_disponiveis = [int(row['ano']) for row in cur.fetchall()]
        
        cur.close()
        
        # Converter para formato JSON para o calendário
        eventos = []
        for f in ferias:
            eventos.append({
                'title': f['nome_completo'],
                'start': f['ferias_inicio'].isoformat() if f['ferias_inicio'] else None,
                'end': (f['ferias_fim'] + timedelta(days=1)).isoformat() if f['ferias_fim'] else None,  # FullCalendar end é exclusivo
                'extendedProps': {
                    'd_usuario': f['d_usuario'],
                    'dias': f['dias_ferias']
                }
            })
        
        return render_template(
            'ferias_calendario.html',
            eventos=eventos,
            ano_atual=ano_filtro,
            anos_disponiveis=anos_disponiveis
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[ERRO] Erro ao carregar calendário: {str(e)}")
        flash(f'Erro ao carregar calendário: {str(e)}', 'danger')
        cur.close()
        return redirect(url_for('ferias.listar'))
