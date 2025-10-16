"""
Blueprint de parcerias (listagem e formulário)
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash
from db import get_cursor, get_db
from utils import login_required

parcerias_bp = Blueprint('parcerias', __name__, url_prefix='/parcerias')


@parcerias_bp.route("/", methods=["GET"])
@login_required
def listar():
    """
    Listagem de todas as parcerias/termos com filtros e busca
    """
    # Obter parâmetros de filtro e busca
    filtro_termo = request.args.get('filtro_termo', '').strip()
    filtro_osc = request.args.get('filtro_osc', '').strip()
    filtro_projeto = request.args.get('filtro_projeto', '').strip()
    filtro_tipo_termo = request.args.get('filtro_tipo_termo', '').strip()
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
    cur.execute("SELECT informacao FROM c_tipo_contrato ORDER BY informacao")
    tipos_contrato = [row['informacao'] for row in cur.fetchall()]
    
    # Construir query dinamicamente com filtros
    query = """
        SELECT 
            numero_termo,
            osc,
            projeto,
            tipo_termo,
            inicio,
            final,
            meses,
            total_previsto,
            total_pago,
            sei_celeb,
            sei_pc
        FROM Parcerias
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
        query += " AND tipo_termo ILIKE %s"
        params.append(f"%{filtro_tipo_termo}%")
    
    if busca_sei_celeb:
        query += " AND sei_celeb ILIKE %s"
        params.append(f"%{busca_sei_celeb}%")
    
    if busca_sei_pc:
        query += " AND sei_pc ILIKE %s"
        params.append(f"%{busca_sei_pc}%")
    
    query += " ORDER BY numero_termo"
    
    # Adicionar LIMIT se não for "todas"
    if limite_sql is not None:
        query += f" LIMIT {limite_sql}"
    
    cur.execute(query, params)
    parcerias = cur.fetchall()
    cur.close()
    
    return render_template("parcerias.html", 
                         parcerias=parcerias,
                         tipos_contrato=tipos_contrato,
                         filtro_termo=filtro_termo,
                         filtro_osc=filtro_osc,
                         filtro_projeto=filtro_projeto,
                         filtro_tipo_termo=filtro_tipo_termo,
                         busca_sei_celeb=busca_sei_celeb,
                         busca_sei_pc=busca_sei_pc,
                         limite=limite)


@parcerias_bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova():
    """
    Criar nova parceria
    """
    if request.method == "POST":
        conn = None
        cur = None
        try:
            conn = get_db()
            # Garantir que não há transação pendente com erro
            try:
                conn.rollback()
            except:
                pass
            
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO Parcerias (
                    numero_termo, osc, projeto, tipo_termo, portaria, cnpj,
                    inicio, final, meses, total_previsto, total_pago, conta,
                    transicao, sei_celeb, sei_pc, endereco, sei_plano, 
                    sei_orcamento, contrapartida
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
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
            ))
            
            conn.commit()
            flash("Parceria criada com sucesso!", "success")
            return redirect(url_for('parcerias.nova'))  # Redireciona para nova parceria em vez da listagem
            
        except Exception as e:
            if conn:
                conn.rollback()
            flash(f"Erro ao criar parceria: {str(e)}", "danger")
            
        finally:
            if cur:
                cur.close()
    
    # GET - retornar formulário vazio
    # Buscar dados dos dropdowns
    cur = get_cursor()
    cur.execute("SELECT informacao FROM c_tipo_contrato ORDER BY informacao")
    tipos_contrato = [row['informacao'] for row in cur.fetchall()]
    cur.execute("SELECT lei FROM c_legislacao ORDER BY lei")
    legislacoes = [row['lei'] for row in cur.fetchall()]
    cur.close()
    
    return render_template("parcerias_form.html", 
                         parceria=None,
                         tipos_contrato=tipos_contrato,
                         legislacoes=legislacoes)


@parcerias_bp.route("/editar/<path:numero_termo>", methods=["GET", "POST"])
@login_required
def editar(numero_termo):
    """
    Formulário completo de edição de parceria
    """
    if request.method == "POST":
        # Atualizar os dados da parceria
        conn = None
        cur = None
        try:
            conn = get_db()
            # Garantir que não há transação pendente com erro
            try:
                conn.rollback()
            except:
                pass
            
            cur = conn.cursor()
            
            cur.execute("""
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
            """, (
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
                1 if request.form.get('transicao') == 'on' else 0,  # checkbox como integer
                request.form.get('sei_celeb'),
                request.form.get('sei_pc'),
                request.form.get('endereco'),
                request.form.get('sei_plano'),
                request.form.get('sei_orcamento'),
                1 if request.form.get('contrapartida') == 'on' else 0,  # checkbox como integer
                numero_termo
            ))
            
            conn.commit()
            flash("Parceria atualizada com sucesso!", "success")
            return redirect(url_for('parcerias.listar'))
            
        except Exception as e:
            if conn:
                conn.rollback()  # Desfazer transação em caso de erro
            flash(f"Erro ao atualizar parceria: {str(e)}", "danger")
            
        finally:
            if cur:
                cur.close()
    
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
    
    # Buscar dados dos dropdowns
    cur.execute("SELECT informacao FROM c_tipo_contrato ORDER BY informacao")
    tipos_contrato = [row['informacao'] for row in cur.fetchall()]
    cur.execute("SELECT lei FROM c_legislacao ORDER BY lei")
    legislacoes = [row['lei'] for row in cur.fetchall()]
    cur.close()
    
    if not parceria:
        flash("Parceria não encontrada!", "danger")
        return redirect(url_for('parcerias.listar'))
    
    return render_template("parcerias_form.html", 
                         parceria=parceria,
                         tipos_contrato=tipos_contrato,
                         legislacoes=legislacoes)


@parcerias_bp.route("/api/oscs", methods=["GET"])
@login_required
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
def api_sigla_tipo_termo():
    """
    API para buscar mapeamento de siglas para tipos de termo
    """
    from flask import jsonify
    
    cur = get_cursor()
    cur.execute("SELECT id, informacao, sigla FROM c_tipo_contrato ORDER BY sigla")
    tipos = cur.fetchall()
    cur.close()
    
    # Criar mapeamento sigla -> tipo
    mapeamento = {}
    for row in tipos:
        if row['sigla']:
            mapeamento[row['sigla'].upper()] = row['informacao']
    
    return jsonify(mapeamento)
