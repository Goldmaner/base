"""
Blueprint principal (tela inicial, dashboard)
"""

from flask import Blueprint, render_template, session, request, redirect, url_for, flash, jsonify
from db import get_cursor, get_db
from utils import login_required

main_bp = Blueprint('main', __name__)


@main_bp.route("/", methods=["GET"])
@login_required
def index():
    """
    Tela inicial / Dashboard
    """
    # Buscar dados do usuário para exibir nome / tipo
    cur = get_cursor()
    cur.execute("SELECT id, email, tipo_usuario, data_criacao FROM usuarios WHERE id = %s", (session["user_id"],))
    user = cur.fetchone()
    cur.close()
    return render_template("tela_inicial.html", user=user)


@main_bp.route("/admin/portarias", methods=["GET", "POST"])
@login_required
def gerenciar_portarias():
    """
    Gerenciar portarias/legislações
    """
    conn = get_db()
    cur = conn.cursor()
    
    if request.method == "POST":
        try:
            lei = request.form.get('lei')
            inicio = request.form.get('inicio') or None
            termino = request.form.get('termino') or None
            
            # Verificar se já existe
            cur.execute("SELECT lei FROM categoricas.c_legislacao WHERE lei = %s", (lei,))
            existe = cur.fetchone()
            
            if existe:
                # Atualizar
                cur.execute("""
                    UPDATE categoricas.c_legislacao 
                    SET inicio = %s, termino = %s
                    WHERE lei = %s
                """, (inicio, termino, lei))
                flash(f"Legislação '{lei}' atualizada com sucesso!", "success")
            else:
                # Inserir
                cur.execute("""
                    INSERT INTO categoricas.c_legislacao (lei, inicio, termino)
                    VALUES (%s, %s, %s)
                """, (lei, inicio, termino))
                flash(f"Legislação '{lei}' criada com sucesso!", "success")
            
            conn.commit()
            return redirect(url_for('main.gerenciar_portarias'))
            
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao salvar legislação: {str(e)}", "danger")
    
    # GET - Buscar todas as legislações
    cur.execute("""
        SELECT lei, inicio, termino
        FROM categoricas.c_legislacao 
        ORDER BY inicio DESC NULLS LAST, lei
    """)
    legislacoes = cur.fetchall()
    cur.close()
    
    return render_template("portarias_analise.html", legislacoes=legislacoes)


@main_bp.route("/api/portaria-automatica", methods=["POST"])
@login_required
def portaria_automatica():
    """
    API para determinar automaticamente a portaria baseada na data de início e tipo de termo
    """
    try:
        data = request.get_json()
        data_inicio = data.get('data_inicio')
        numero_termo = data.get('numero_termo', '')
        
        if not data_inicio:
            return jsonify({"portaria": None, "transicao": False})
        
        # Extrair informações do termo
        numero_termo_upper = numero_termo.upper()
        tem_tfm_tcl = 'TFM' in numero_termo_upper or 'TCL' in numero_termo_upper
        tem_fumcad = 'FUMCAD' in numero_termo_upper
        tem_fmid = 'FMID' in numero_termo_upper
        tem_tcv = 'TCV' in numero_termo_upper
        
        # Regras hardcoded baseadas na tabela fornecida
        regras = [
            {
                'lei': 'Decreto nº 6.170',
                'inicio': '2007-07-25',
                'termino': '2008-08-11',
                'regra_termo': ['TCV'],
                'regra_coordenacao': []
            },
            {
                'lei': 'Portaria nº 006/2008/SF-SEMPLA',
                'inicio': '2008-08-12',
                'termino': '2012-09-30',
                'regra_termo': ['TCV'],
                'regra_coordenacao': []
            },
            {
                'lei': 'Portaria nº 072/SMPP/2012',
                'inicio': '2012-03-22',
                'termino': '2014-05-21',
                'regra_termo': ['TCV'],
                'regra_coordenacao': ['FUMCAD']
            },
            {
                'lei': 'Portaria nº 009/SMDHC/2014',
                'inicio': '2014-05-22',
                'termino': '2017-09-30',
                'regra_termo': ['TCV'],
                'regra_coordenacao': ['FUMCAD']
            },
            {
                'lei': 'Portaria nº 121/SMDHC/2019',
                'inicio': '2017-10-01',
                'termino': '2023-02-28',
                'regra_termo': ['TFM', 'TCL'],
                'regra_coordenacao': []
            },
            {
                'lei': 'Portaria nº 140/SMDHC/2019',
                'inicio': '2017-10-01',
                'termino': '2023-12-31',
                'regra_termo': ['TFM', 'TCL'],
                'regra_coordenacao': ['FUMCAD', 'FMID']
            },
            {
                'lei': 'Portaria nº 021/SMDHC/2023',
                'inicio': '2023-03-01',
                'termino': '2030-12-31',
                'regra_termo': ['TFM', 'TCL'],
                'regra_coordenacao': []
            },
            {
                'lei': 'Portaria nº 090/SMDHC/2023',
                'inicio': '2024-01-01',
                'termino': '2030-12-31',
                'regra_termo': ['TFM', 'TCL'],
                'regra_coordenacao': ['FUMCAD', 'FMID']
            }
        ]
        
        portaria_selecionada = None
        
        for regra in regras:
            # Verificar se a data de início está no período da legislação
            if data_inicio < regra['inicio'] or data_inicio > regra['termino']:
                continue
            
            # Verificar regra de termo
            if tem_tfm_tcl and not any(t in regra['regra_termo'] for t in ['TFM', 'TCL']):
                continue
            if tem_tcv and 'TCV' not in regra['regra_termo']:
                continue
            
            # Verificar regra de coordenação
            if tem_fumcad or tem_fmid:
                if tem_fumcad and 'FUMCAD' not in regra['regra_coordenacao']:
                    continue
                if tem_fmid and 'FMID' not in regra['regra_coordenacao']:
                    continue
            else:
                # Se não tem FUMCAD nem FMID, preferir legislação sem essas coordenações
                if regra['regra_coordenacao']:
                    # Verificar se há outra opção sem coordenação
                    outras_opcoes = [
                        r for r in regras 
                        if data_inicio >= r['inicio'] and data_inicio <= r['termino']
                        and not r['regra_coordenacao']
                    ]
                    if outras_opcoes:
                        continue
            
            portaria_selecionada = regra['lei']
            break
        
        return jsonify({
            "portaria": portaria_selecionada,
            "transicao": False  # Será calculado separadamente com data de término
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
