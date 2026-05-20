"""
Blueprint principal (tela inicial, dashboard)
"""

from datetime import date, timedelta
from flask import Blueprint, render_template, session, request, redirect, url_for, flash, jsonify
from db import get_cursor, get_db
from utils import login_required
from decorators import requires_access

main_bp = Blueprint('main', __name__)


@main_bp.route("/", methods=["GET"])
@login_required
def index():
    """
    Tela inicial / Dashboard
    """
    # Buscar dados do usuário para exibir nome / tipo
    cur = get_cursor()
    cur.execute("SELECT id, email, tipo_usuario, data_criacao, acessos FROM gestao_pessoas.usuarios WHERE id = %s", (session["user_id"],))
    user = cur.fetchone()
    cur.close()

    # Sessão referencia usuário inexistente (deletado ou corrompido) — encerrar
    if user is None:
        session.clear()
        return redirect(url_for('auth.login'))

    # Preparar variáveis de controle de acesso
    is_admin = user['tipo_usuario'] == 'Agente Público'
    user_acessos = (user['acessos'] or '').split(';') if user['acessos'] else []

    # Lembretes: eventos de hoje e amanhã
    lembretes_hoje = []
    lembretes_amanha = []
    try:
        hoje = date.today()
        amanha = hoje + timedelta(days=1)
        tipo_usuario_logado = user['tipo_usuario']
        eh_gerente = tipo_usuario_logado in ['Agente Público', 'admin']

        # Also check visualizar_todos_eventos flag in DB
        if not eh_gerente:
            cur_chk = get_cursor()
            cur_chk.execute(
                "SELECT visualizar_todos_eventos FROM gestao_pessoas.usuarios_infos WHERE usuario_email = %s",
                (session.get('email'),)
            )
            row_chk = cur_chk.fetchone()
            cur_chk.close()
            if row_chk and row_chk['visualizar_todos_eventos']:
                eh_gerente = True

        cur2 = get_cursor()
        # Datas importantes (pessoais)
        if eh_gerente:
            cur2.execute("""
                SELECT 'pessoal' AS tipo, di.nome_data AS titulo, di.data_inicio,
                       di.horario_inicio AS horario, ui.usuario_nome
                FROM calendario.datas_importantes di
                LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = di.usuario_email
                WHERE di.data_inicio IN (%s, %s)
                ORDER BY di.data_inicio, di.horario_inicio NULLS LAST
            """, (hoje, amanha))
        else:
            cur2.execute("""
                SELECT 'pessoal' AS tipo, di.nome_data AS titulo, di.data_inicio,
                       di.horario_inicio AS horario, ui.usuario_nome
                FROM calendario.datas_importantes di
                LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = di.usuario_email
                WHERE di.tipo_usuario = %s AND di.data_inicio IN (%s, %s)
                ORDER BY di.data_inicio, di.horario_inicio NULLS LAST
            """, (tipo_usuario_logado, hoje, amanha))
        datas_imp = list(cur2.fetchall())

        # Eventos institucionais
        if eh_gerente:
            cur2.execute("""
                SELECT 'evento' AS tipo, de.nome_atividade AS titulo, de.data_inicio,
                       NULL AS horario, ui.usuario_nome
                FROM calendario.datas_eventos de
                LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = de.usuario_email
                WHERE de.data_inicio IN (%s, %s)
                ORDER BY de.data_inicio
            """, (hoje, amanha))
        else:
            cur2.execute("""
                SELECT 'evento' AS tipo, de.nome_atividade AS titulo, de.data_inicio,
                       NULL AS horario, ui.usuario_nome
                FROM calendario.datas_eventos de
                LEFT JOIN gestao_pessoas.usuarios_infos ui ON ui.usuario_email = de.usuario_email
                WHERE de.tipo_usuario = %s AND de.data_inicio IN (%s, %s)
                ORDER BY de.data_inicio
            """, (tipo_usuario_logado, hoje, amanha))
        datas_ev = list(cur2.fetchall())
        cur2.close()

        todos = datas_imp + datas_ev
        lembretes_hoje = [r for r in todos if r['data_inicio'] == hoje]
        lembretes_amanha = [r for r in todos if r['data_inicio'] == amanha]
    except Exception:
        pass

    # Lembrete de sexta-feira: escala de teletrabalho pendente para próxima semana
    alerta_escala_tt = False
    next_monday_iso = ''
    try:
        if hoje.weekday() == 4:  # Sexta-feira = 4
            _email = session.get('email', '')
            _tipo = user['tipo_usuario']
            _pode_tt = _tipo in ('Agente Público', 'admin')
            if not _pode_tt:
                cur_p = get_cursor()
                cur_p.execute(
                    "SELECT usuario_escala_permissao FROM gestao_pessoas.usuarios_infos WHERE usuario_email = %s",
                    (_email,)
                )
                row_p = cur_p.fetchone()
                cur_p.close()
                _pode_tt = bool(row_p and row_p['usuario_escala_permissao'])
            if _pode_tt:
                _next_monday = hoje + timedelta(days=3)
                cur_tt = get_cursor()
                cur_tt.execute(
                    "SELECT COUNT(*) AS cnt FROM calendario.escala_teletrabalho WHERE semana_inicio = %s",
                    (_next_monday,)
                )
                row_tt = cur_tt.fetchone()
                cur_tt.close()
                if not (row_tt and row_tt['cnt'] > 0):
                    alerta_escala_tt = True
                    next_monday_iso = _next_monday.isoformat()
    except Exception:
        pass

    return render_template("tela_inicial.html", user=user, is_admin=is_admin, user_acessos=user_acessos,
                           lembretes_hoje=lembretes_hoje, lembretes_amanha=lembretes_amanha,
                           alerta_escala_tt=alerta_escala_tt, next_monday_iso=next_monday_iso)



@main_bp.route("/admin/portarias", methods=["GET", "POST"])
@login_required
@requires_access('portarias')
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
            cur.execute("SELECT lei FROM categoricas.c_geral_legislacao WHERE lei = %s", (lei,))
            existe = cur.fetchone()
            
            if existe:
                # Atualizar
                cur.execute("""
                    UPDATE categoricas.c_geral_legislacao 
                    SET inicio = %s, termino = %s
                    WHERE lei = %s
                """, (inicio, termino, lei))
                flash(f"Legislação '{lei}' atualizada com sucesso!", "success")
            else:
                # Inserir
                cur.execute("""
                    INSERT INTO categoricas.c_geral_legislacao (lei, inicio, termino)
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
        FROM categoricas.c_geral_legislacao 
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


# ============================================================================
# ROTAS PARA MODELOS DE TEXTO
# ============================================================================

@main_bp.route('/modelos-textos', methods=['GET'])
@login_required
@requires_access('modelos_textos')
def modelos_textos_index():
    """
    Página para gerenciar modelos de texto (lista, criar, editar, ocultar)
    """
    is_admin = False
    try:
        if session.get('tipo_usuario') == 'Agente Público':
            is_admin = True
    except Exception:
        pass

    return render_template('o_modelo_textos.html', is_admin=is_admin)


@main_bp.route('/modelos-textos/api', methods=['GET'])
@login_required
@requires_access('modelos_textos')
def modelos_textos_list():
    """Retorna lista de modelos de texto. Se o usuário for admin e passar mostrar_ocultos=1, traz ocultos."""
    try:
        mostrar_ocultos = request.args.get('mostrar_ocultos', '0') == '1'
        print(f"DEBUG: mostrar_ocultos = {request.args.get('mostrar_ocultos', '0')}, parsed = {mostrar_ocultos}, tipo_usuario = {session.get('tipo_usuario')}")

        # Garantir que a coluna 'oculto' exista (adiciona se necessário)
        cur = get_cursor()
        try:
            cur.execute("ALTER TABLE categoricas.c_geral_legislacao ADD COLUMN IF NOT EXISTS oculto boolean DEFAULT FALSE")
            get_db().commit()
        except Exception:
            try:
                get_db().rollback()
            except:
                pass

        # Montar query
        if mostrar_ocultos and session.get('tipo_usuario') == 'Agente Público':
            query = "SELECT id, titulo_texto, modelo_texto, categoria_texto, COALESCE(oculto, false) as oculto FROM categoricas.c_geral_modelo_textos ORDER BY titulo_texto"
            print(f"DEBUG: Usando query TODOS (admin)")
            cur.execute(query)
        else:
            query = "SELECT id, titulo_texto, modelo_texto, categoria_texto, COALESCE(oculto, false) as oculto FROM categoricas.c_geral_modelo_textos WHERE COALESCE(oculto, false) = false ORDER BY titulo_texto"
            print(f"DEBUG: Usando query NÃO OCULTOS")
            cur.execute(query)

        dados = cur.fetchall()
        print(f"DEBUG: Encontrados {len(dados)} registros")
        cur.close()

        # Converter para lista simples
        resultado = []
        for row in dados:
            resultado.append({
                'id': row['id'],
                'titulo_texto': row['titulo_texto'],
                'modelo_texto': row['modelo_texto'],
                'categoria_texto': row.get('categoria_texto'),
                'oculto': bool(row.get('oculto'))
            })

        return jsonify({'dados': resultado})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500


@main_bp.route('/modelos-textos/api', methods=['POST'])
@login_required
@requires_access('modelos_textos')
def modelos_textos_create():
    """Cria um novo modelo de texto"""
    try:
        dados = request.json
        titulo = dados.get('titulo_texto')
        modelo = dados.get('modelo_texto')
        categoria = dados.get('categoria_texto')
        if not titulo:
            return jsonify({'erro': 'titulo_texto é obrigatório'}), 400

        cur = get_cursor()
        cur.execute("INSERT INTO categoricas.c_geral_modelo_textos (titulo_texto, modelo_texto, categoria_texto, oculto) VALUES (%s, %s, %s, false) RETURNING id",
                    (titulo, modelo, categoria))
        novo = cur.fetchone()
        get_db().commit()
        cur.close()
        return jsonify({'sucesso': True, 'id': novo['id']})
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            get_db().rollback()
        except:
            pass
        return jsonify({'erro': str(e)}), 500


@main_bp.route('/modelos-textos/api/<int:id>', methods=['PUT'])
@login_required
@requires_access('modelos_textos')
def modelos_textos_update(id):
    """Atualiza título e/ou conteúdo do modelo"""
    try:
        dados = request.json
        titulo = dados.get('titulo_texto')
        modelo = dados.get('modelo_texto')
        categoria = dados.get('categoria_texto')
        if titulo is None and modelo is None and categoria is None:
            return jsonify({'erro': 'Nenhum campo para atualizar'}), 400

        cur = get_cursor()
        # Montar SET dinâmico
        sets = []
        params = []
        if titulo is not None:
            sets.append('titulo_texto = %s')
            params.append(titulo)
        if modelo is not None:
            sets.append('modelo_texto = %s')
            params.append(modelo)
        if categoria is not None:
            sets.append('categoria_texto = %s')
            params.append(categoria)
        params.append(id)

        query = f"UPDATE categoricas.c_geral_modelo_textos SET {', '.join(sets)} WHERE id = %s"
        cur.execute(query, tuple(params))
        get_db().commit()
        cur.close()
        return jsonify({'sucesso': True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            get_db().rollback()
        except:
            pass
        return jsonify({'erro': str(e)}), 500


@main_bp.route('/modelos-textos/api/<int:id>/toggle_oculto', methods=['POST'])
@login_required
@requires_access('modelos_textos')
def modelos_textos_toggle_oculto(id):
    """Alterna sinalizador oculto (true/false)."""
    try:
        dados = request.json or {}
        novo = dados.get('oculto')
        if novo is None:
            return jsonify({'erro': 'Campo oculto obrigatório (true/false)'}), 400

        cur = get_cursor()
        cur.execute("UPDATE categoricas.c_geral_modelo_textos SET oculto = %s WHERE id = %s", (bool(novo), id))
        get_db().commit()
        cur.close()
        return jsonify({'sucesso': True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            get_db().rollback()
        except:
            pass
        return jsonify({'erro': str(e)}), 500


@main_bp.route('/modelos-textos/api/<int:id>', methods=['DELETE'])
@login_required
@requires_access('modelos_textos')
def modelos_textos_delete(id):
    """Apaga um modelo de texto (apenas para Agente Público)"""
    try:
        # Verificar se é admin
        if session.get('tipo_usuario') != 'Agente Público':
            return jsonify({'erro': 'Acesso negado. Apenas Agente Público pode apagar modelos.'}), 403

        cur = get_cursor()
        cur.execute("DELETE FROM categoricas.c_geral_modelo_textos WHERE id = %s", (id,))
        get_db().commit()
        cur.close()
        return jsonify({'sucesso': True})
    except Exception as e:
        import traceback
        traceback.print_exc()
        try:
            get_db().rollback()
        except:
            pass
        return jsonify({'erro': str(e)}), 500



@main_bp.route('/api/termos-com-analise-dp')
@login_required
def listar_termos_com_analise_dp():
    """
    Retorna lista de termos que possuem análise do DP ou Mista
    (responsabilidade_analise = 1 ou 2)
    """
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT DISTINCT p.numero_termo
            FROM public.parcerias p
            INNER JOIN public.parcerias_analises pa 
                ON p.numero_termo = pa.numero_termo
            WHERE pa.responsabilidade_analise IN (1, 2)
            ORDER BY p.numero_termo DESC
        """)
        
        termos = [{'numero_termo': row['numero_termo']} for row in cur.fetchall()]
        cur.close()
        
        return jsonify({'termos': termos})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'erro': str(e)}), 500
