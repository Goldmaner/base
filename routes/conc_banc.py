"""
Rotas para Conciliação Bancária - Análise de Prestação de Contas
(versão otimizada: datalists globais, bulk delete, lazy dropdowns)
"""

from flask import Blueprint, render_template, request, jsonify, session
from db import get_cursor, get_db, DatabaseUnavailable
from functools import wraps
from datetime import datetime, date
from decorators import requires_access, requires_write_access
from routes.conc_termo_permissions import ensure_can_edit_termo, get_termo_permission
import os
import uuid
import boto3
from botocore.client import Config
from werkzeug.utils import secure_filename

bp = Blueprint('conc_banc', __name__, url_prefix='/conc_banc')


def _rollback_quietly(db):
    if db is None:
        return
    try:
        db.rollback()
    except Exception:
        pass


def _try_lock_termo(cur, numero_termo):
    cur.execute("SELECT pg_try_advisory_xact_lock(hashtext(%s)) AS locked", (numero_termo,))
    row = cur.fetchone()
    return bool(row and row.get('locked'))


def _resposta_termo_em_save():
    return jsonify({
        'erro': 'Outro salvamento deste termo esta em andamento. Tente novamente em alguns segundos.',
        'codigo': 'termo_em_salvamento'
    }), 409


def _ids_extrato_validos(cur, numero_termo, ids):
    ids = [int(i) for i in ids if i]
    if not ids:
        return set()
    cur.execute("""
        SELECT id
        FROM analises_pc.conc_extrato
        WHERE numero_termo = %s AND id = ANY(%s)
    """, (numero_termo, ids))
    return {row['id'] for row in cur.fetchall()}


def _request_numero_termo():
    data = request.get_json(silent=True) or {}
    return (
        data.get('numero_termo')
        or request.args.get('numero_termo')
        or request.form.get('numero_termo')
        or ''
    ).strip()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'erro': 'Sessão expirada'}), 401
        return f(*args, **kwargs)
    return decorated_function


@bp.route('/')
@login_required
@requires_access('conc_bancaria')
def index():
    """Página principal de conciliação bancária"""
    return render_template('analises_pc/conc_banc.html')


@bp.route('/api/extrato', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_listar_extrato():
    """
    API para listar movimentações do extrato
    Query params: numero_termo, limite
    """
    try:
        import time
        inicio = time.time()

        cur = get_cursor()

        numero_termo = request.args.get('numero_termo', '').strip()
        limite = request.args.get('limite', '100').strip()

        query = """
            SELECT
                id,
                indice,
                data,
                credito,
                debito,
                discriminacao,
                cat_transacao,
                competencia,
                origem_destino,
                cat_avaliacao,
                avaliacao_analista,
                mesclado_com,
                numero_termo
            FROM analises_pc.conc_extrato
            WHERE 1=1
        """

        params = []

        if numero_termo:
            query += " AND numero_termo = %s"
            params.append(numero_termo)

        # Ordenar por índice
        query += " ORDER BY indice ASC, id ASC"

        # Adicionar limite
        if limite.lower() != 'todas':
            try:
                limite_num = int(limite)
                query += f" LIMIT {limite_num}"
            except ValueError:
                query += " LIMIT 100"

        tempo_query = time.time()
        cur.execute(query, params)
        tempo_execute = (time.time() - tempo_query) * 1000

        tempo_fetch = time.time()
        extrato = cur.fetchall()
        tempo_fetchall = (time.time() - tempo_fetch) * 1000

        # Processar dados
        tempo_process = time.time()
        resultado = []
        for item in extrato:
            row = dict(item)

            # Converter datas para string ISO
            if row.get('data'):
                row['data'] = row['data'].isoformat()
            if row.get('competencia'):
                row['competencia'] = row['competencia'].isoformat()

            # Converter valores numéricos para float
            if row.get('credito'):
                row['credito'] = float(row['credito'])
            if row.get('debito'):
                row['debito'] = float(row['debito'])
            if row.get('discriminacao'):
                row['discriminacao'] = float(row['discriminacao'])

            # Converter mesclado_com (array PostgreSQL para lista Python)
            if row.get('mesclado_com'):
                row['mesclado_com'] = list(row['mesclado_com'])
            else:
                row['mesclado_com'] = []

            resultado.append(row)

        tempo_processing = (time.time() - tempo_process) * 1000
        tempo_total = (time.time() - inicio) * 1000
        print(f"[GET EXTRATO] Total: {tempo_total:.2f}ms | Execute: {tempo_execute:.2f}ms | Fetch: {tempo_fetchall:.2f}ms | Process: {tempo_processing:.2f}ms | Linhas: {len(resultado)}")

        return jsonify(resultado), 200

    except Exception as e:
        print(f"[ERRO] ao listar extrato: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/permissao-termo', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_permissao_termo():
    """Informa se o usuario logado pode editar o termo selecionado."""
    numero_termo = request.args.get('numero_termo', '').strip()
    if not numero_termo:
        return jsonify({'erro': 'numero_termo e obrigatorio'}), 400

    try:
        cur = get_cursor()
        return jsonify(get_termo_permission(cur, numero_termo)), 200
    except Exception as e:
        print(f"[ERRO] ao verificar permissao do termo: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/extrato', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_salvar_extrato():
    """API para salvar múltiplas linhas do extrato de uma vez"""
    db = None
    try:
        import time
        inicio = time.time()
        timings = {}

        dados = request.get_json()
        linhas = dados.get('linhas', [])
        numero_termo = dados.get('numero_termo')
        modo_completo = dados.get('modo_completo', False)  # Flag para indicar se está salvando tudo

        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400

        cur = get_cursor()
        db = get_db()

        t_perm = time.time()
        ok, resposta = ensure_can_edit_termo(cur, numero_termo)
        timings['permissao_ms'] = (time.time() - t_perm) * 1000
        if not ok:
            return resposta

        t_lock = time.time()
        if not _try_lock_termo(cur, numero_termo):
            return _resposta_termo_em_save()
        timings['lock_wait_ms'] = (time.time() - t_lock) * 1000

        # Coletar IDs das linhas enviadas
        ids_enviados = [linha.get('id') for linha in linhas if linha.get('id')]

        # DELETAR apenas se modo_completo = True (garantia de que temos todas as linhas)
        t_delete = time.time()
        if modo_completo:
            if ids_enviados:
                placeholders = ','.join(['%s'] * len(ids_enviados))
                cur.execute(f"""
                    DELETE FROM analises_pc.conc_extrato
                    WHERE numero_termo = %s AND id NOT IN ({placeholders})
                """, [numero_termo] + ids_enviados)
            else:
                # Se não há IDs (todas linhas novas), deletar tudo do termo
                cur.execute("DELETE FROM analises_pc.conc_extrato WHERE numero_termo = %s", (numero_termo,))
        timings['delete_ausentes_ms'] = (time.time() - t_delete) * 1000

        # UPSERT com savepoints: cada linha é isolada — erro em 1 não cancela as demais
        t_upsert = time.time()
        ids_processados = []
        ids_inseridos = []   # apenas INSERTs
        ids_inseridos_map = []
        erros_linhas = []    # linhas que falharam: [{indice, id, mensagem}]

        for i, linha in enumerate(linhas):
            if not linha.get('indice'):
                continue

            credito = linha.get('credito')
            debito  = linha.get('debito')
            linha_id = linha.get('id')
            sp = f'sp_{i}'

            cur.execute(f'SAVEPOINT {sp}')
            try:
                # Validação semântica (antes de ir ao banco)
                if credito and debito:
                    raise ValueError('Linha com crédito e débito ao mesmo tempo')

                if linha_id:
                    cur.execute("""
                        UPDATE analises_pc.conc_extrato SET
                            indice = %s, data = %s, credito = %s, debito = %s,
                            discriminacao = %s, cat_transacao = %s, competencia = %s,
                            origem_destino = %s, cat_avaliacao = %s,
                            avaliacao_analista = %s, mesclado_com = %s
                        WHERE id = %s AND numero_termo = %s
                        RETURNING id
                    """, (
                        linha.get('indice'), linha.get('data') or None,
                        credito or None, debito or None,
                        linha.get('discriminacao') or None, linha.get('cat_transacao') or None,
                        linha.get('competencia') or None, linha.get('origem_destino') or None,
                        linha.get('cat_avaliacao') or None, linha.get('avaliacao_analista') or None,
                        linha.get('mesclado_com') or None, linha_id, numero_termo
                    ))
                    result = cur.fetchone()
                    if result:
                        ids_processados.append(result['id'])
                else:
                    cur.execute("""
                        INSERT INTO analises_pc.conc_extrato (
                            indice, data, credito, debito, discriminacao,
                            cat_transacao, competencia, origem_destino,
                            cat_avaliacao, avaliacao_analista, mesclado_com, numero_termo
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        linha.get('indice'), linha.get('data') or None,
                        credito or None, debito or None,
                        linha.get('discriminacao') or None, linha.get('cat_transacao') or None,
                        linha.get('competencia') or None, linha.get('origem_destino') or None,
                        linha.get('cat_avaliacao') or None, linha.get('avaliacao_analista') or None,
                        linha.get('mesclado_com') or None, numero_termo
                    ))
                    novo_id = cur.fetchone()['id']
                    ids_processados.append(novo_id)
                    ids_inseridos.append(novo_id)
                    ids_inseridos_map.append({
                        'indice': linha.get('indice'),
                        'id': novo_id
                    })

                cur.execute(f'RELEASE SAVEPOINT {sp}')

            except DatabaseUnavailable:
                raise
            except Exception as linha_err:
                cur.execute(f'ROLLBACK TO SAVEPOINT {sp}')
                erros_linhas.append({
                    'indice': linha.get('indice'),
                    'id': linha_id,
                    'mensagem': str(linha_err)
                })
                print(f'[SAVE] Linha {linha.get("indice")} falhou (savepoint revertido): {linha_err}')

        timings['upsert_linhas_ms'] = (time.time() - t_upsert) * 1000
        t_auto = time.time()

        # ============================================================
        # AUTOMAÇÃO: Destinatário Identificado/Não Identificado
        # ============================================================
        # Buscar portaria e transição do termo
        cur.execute("""
            SELECT portaria, transicao
            FROM public.parcerias
            WHERE numero_termo = %s
        """, (numero_termo,))
        termo_info = cur.fetchone()

        if termo_info:
            portaria = termo_info['portaria'] or ''
            transicao = termo_info['transicao'] or 0

            print(f"[AUTOMAÇÃO] Termo: {numero_termo}, Portaria: {portaria}, Transição: {transicao}")

            # Determinar data de corte baseada na portaria
            data_corte = None

            # Portarias 021 (2019 ou 2023)
            if 'Portaria nº 021/SMDHC/2019' in portaria or 'Portaria n° 021/SMDHC/2019' in portaria or \
               'Portaria nº 021/SMDHC/2023' in portaria or 'Portaria n° 021/SMDHC/2023' in portaria:
                data_corte = date(2023, 3, 1)  # mar/23
                print(f"[AUTOMAÇÃO] Portaria 021 detectada, corte: mar/23")
            # Portarias 090 (2019 ou 2023)
            elif 'Portaria nº 090/SMDHC/2019' in portaria or 'Portaria n° 090/SMDHC/2019' in portaria or \
                 'Portaria nº 090/SMDHC/2023' in portaria or 'Portaria n° 090/SMDHC/2023' in portaria:
                data_corte = date(2024, 1, 1)  # jan/24
                print(f"[AUTOMAÇÃO] Portaria 090 detectada, corte: jan/24")
            # Portarias 121 com transição = 1
            elif (('Portaria nº 121/SMDHC/2019' in portaria or 'Portaria n° 121/SMDHC/2019' in portaria or \
                   'Portaria nº 121/SMDHC/2023' in portaria or 'Portaria n° 121/SMDHC/2023' in portaria) and transicao == 1):
                data_corte = date(2023, 3, 1)  # mar/23
                print(f"[AUTOMAÇÃO] Portaria 121 com transição, corte: mar/23")
            # Portarias 140 com transição = 1
            elif (('Portaria nº 140/SMDHC/2019' in portaria or 'Portaria n° 140/SMDHC/2019' in portaria or \
                   'Portaria nº 140/SMDHC/2023' in portaria or 'Portaria n° 140/SMDHC/2023' in portaria) and transicao == 1):
                data_corte = date(2024, 1, 1)  # jan/24
                print(f"[AUTOMAÇÃO] Portaria 140 com transição, corte: jan/24")

            # Aplicar automação apenas se houver data de corte definida
            if data_corte and ids_processados:
                print(f"[AUTOMAÇÃO] Aplicando regra para competências >= {data_corte}")
                print(f"[AUTOMAÇÃO] Regras: Apenas células VAZIAS + Competência >= corte + Créditos E Débitos")

                # OTIMIZAÇÃO: Buscar todos os dados de uma vez (evita N+1 queries)
                cur.execute("""
                    SELECT id, competencia, origem_destino, cat_transacao, credito, debito
                    FROM analises_pc.conc_extrato
                    WHERE numero_termo = %s AND id = ANY(%s)
                """, (numero_termo, ids_processados))
                linhas_map = {row['id']: row for row in cur.fetchall()}

                # Coletar pares (categoria, id, termo) para batch UPDATE
                atualizacoes = []

                for linha_id in ids_processados:
                    linha_data = linhas_map.get(linha_id)

                    if not linha_data:
                        continue

                    competencia = linha_data['competencia']
                    cat_transacao_atual = (linha_data['cat_transacao'] or '').strip()
                    origem_destino = (linha_data['origem_destino'] or '').strip()

                    # REGRA 1: Se competência não está preenchida, pular
                    if not competencia:
                        continue

                    # REGRA 2: Verificar se competência é >= data de corte
                    if competencia < data_corte:
                        continue

                    # REGRA 3: NUNCA sobrescrever categoria já preenchida (proteção total)
                    if cat_transacao_atual:
                        continue

                    # Determinar nova categoria baseada em Origem/Destino
                    if origem_destino:
                        nova_categoria = 'Destinatário Identificado'
                    else:
                        nova_categoria = 'Destinatário não Identificado'

                    atualizacoes.append((nova_categoria, linha_id, numero_termo))

                # OTIMIZAÇÃO: Batch UPDATE único em vez de N queries individuais
                if atualizacoes:
                    from psycopg2.extras import execute_values
                    execute_values(cur, """
                        UPDATE analises_pc.conc_extrato AS e
                        SET cat_transacao = v.nova_categoria,
                            cat_avaliacao = 'Avaliado'
                        FROM (VALUES %s) AS v(nova_categoria, id, numero_termo)
                        WHERE e.id = v.id::integer
                          AND e.numero_termo = v.numero_termo
                    """, atualizacoes)
                    print(f"[AUTOMAÇÃO] ✅ {len(atualizacoes)} linhas categorizadas automaticamente")

        # ============================================================
        # AUTOMAÇÃO: Preencher avaliacao_comprovante via palavra-chave
        # ============================================================
        # Quando cat_avaliacao = 'Glosar' e avaliacao_analista contém uma
        # palavra-chave conhecida (case-insensitive), preenche automaticamente
        # o campo correspondente em conc_analise — apenas se ainda estiver vazio.
        #
        # Para adicionar novas regras, inclua uma entrada em _AUTO_COMPROVANTE.
        _AUTO_COMPROVANTE = [
            ('cheque',  'Pago em Cheque'),
        ]

        if ids_processados:
            for palavra, valor_comprovante in _AUTO_COMPROVANTE:
                padrao = f'%{palavra}%'

                # 1. UPDATE: conc_analise já existe mas avaliacao_comprovante está vazio
                cur.execute("""
                    UPDATE analises_pc.conc_analise ca
                    SET avaliacao_comprovante = %s
                    FROM analises_pc.conc_extrato ce
                    WHERE ca.conc_extrato_id = ce.id
                      AND ce.id = ANY(%s)
                      AND ce.numero_termo = %s
                      AND ce.cat_avaliacao = 'Glosar'
                      AND LOWER(ce.avaliacao_analista) LIKE LOWER(%s)
                      AND (ca.avaliacao_comprovante IS NULL
                           OR TRIM(ca.avaliacao_comprovante) = '')
                """, (valor_comprovante, ids_processados, numero_termo, padrao))
                n_upd = cur.rowcount

                # 2. INSERT: extrato com critério mas sem registro em conc_analise
                cur.execute("""
                    INSERT INTO analises_pc.conc_analise
                        (conc_extrato_id, numero_termo, avaliacao_comprovante)
                    SELECT ce.id, ce.numero_termo, %s
                    FROM analises_pc.conc_extrato ce
                    WHERE ce.id = ANY(%s)
                      AND ce.numero_termo = %s
                      AND ce.cat_avaliacao = 'Glosar'
                      AND LOWER(ce.avaliacao_analista) LIKE LOWER(%s)
                      AND NOT EXISTS (
                          SELECT 1 FROM analises_pc.conc_analise ca
                          WHERE ca.conc_extrato_id = ce.id
                      )
                """, (valor_comprovante, ids_processados, numero_termo, padrao))
                n_ins = cur.rowcount

                total = n_upd + n_ins
                if total > 0:
                    print(f"[AUTO COMPROVANTE] '{palavra}' → '{valor_comprovante}': "
                          f"{n_upd} atualizados, {n_ins} inseridos")

        timings['automacoes_ms'] = (time.time() - t_auto) * 1000

        t_commit = time.time()
        db.commit()
        timings['commit_ms'] = (time.time() - t_commit) * 1000

        tempo_total = (time.time() - inicio) * 1000
        timings['total_ms'] = tempo_total
        print(
            f"\n[SAVE] Total: {tempo_total:.2f}ms | Linhas: {len(ids_processados)} | "
            f"Permissao: {timings['permissao_ms']:.2f}ms | "
            f"Lock wait: {timings['lock_wait_ms']:.2f}ms | "
            f"Delete: {timings['delete_ausentes_ms']:.2f}ms | "
            f"Upsert: {timings['upsert_linhas_ms']:.2f}ms | "
            f"Automacoes: {timings['automacoes_ms']:.2f}ms | "
            f"Commit: {timings['commit_ms']:.2f}ms"
        )

        tem_erros = len(erros_linhas) > 0
        return jsonify({
            'mensagem': (f'{len(ids_processados)} linhas salvas, {len(erros_linhas)} com erro'
                         if tem_erros else f'{len(ids_processados)} linhas salvas com sucesso'),
            'ids': ids_processados,
            'ids_inseridos': ids_inseridos,
            'ids_inseridos_map': ids_inseridos_map,
            'erros': erros_linhas   # [{indice, id, mensagem}] — linhas que falharam
        }), 200

    except DatabaseUnavailable:
        _rollback_quietly(db)
        raise
    except Exception as e:
        print(f"[ERRO] ao salvar extrato: {e}")
        _rollback_quietly(db)
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/extrato/<int:extrato_id>', methods=['DELETE'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_excluir_extrato(extrato_id):
    """API para excluir uma linha do extrato"""
    try:
        numero_termo = _request_numero_termo()
        if not numero_termo:
            return jsonify({'erro': 'numero_termo e obrigatorio'}), 400

        cur = get_cursor()
        db = get_db()

        ok, resposta = ensure_can_edit_termo(cur, numero_termo)
        if not ok:
            return resposta

        cur.execute(
            "DELETE FROM analises_pc.conc_extrato WHERE id = %s AND numero_termo = %s",
            (extrato_id, numero_termo)
        )
        if cur.rowcount == 0:
            db.rollback()
            return jsonify({'erro': 'Linha nao encontrada neste termo'}), 404
        db.commit()

        return jsonify({'mensagem': 'Linha excluída com sucesso'}), 200

    except Exception as e:
        print(f"[ERRO] ao excluir linha {extrato_id}: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/extrato/bulk', methods=['DELETE'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_excluir_extrato_bulk():
    """
    API: Exclui múltiplas linhas do extrato em 1 query (em vez de N chamadas DELETE).
    Body JSON: {"ids": [1, 2, 3, ...]}
    """
    try:
        dados = request.get_json() or {}
        ids = dados.get('ids', [])
        numero_termo = (dados.get('numero_termo') or '').strip()

        if not numero_termo:
            return jsonify({'erro': 'numero_termo e obrigatorio'}), 400

        if not ids:
            return jsonify({'mensagem': '0 linhas excluídas'}), 200

        # Validar que todos são inteiros
        ids_int = [int(i) for i in ids if str(i).isdigit()]
        if not ids_int:
            return jsonify({'erro': 'Nenhum ID válido fornecido'}), 400

        cur = get_cursor()
        db = get_db()

        ok, resposta = ensure_can_edit_termo(cur, numero_termo)
        if not ok:
            return resposta

        cur.execute(
            "DELETE FROM analises_pc.conc_extrato WHERE id = ANY(%s) AND numero_termo = %s",
            (ids_int, numero_termo)
        )
        deletados = cur.rowcount
        db.commit()

        print(f"[BULK DELETE] {deletados} linhas excluídas: {ids_int}")
        return jsonify({'mensagem': f'{deletados} linhas excluídas com sucesso', 'deletados': deletados}), 200

    except Exception as e:
        print(f"[ERRO] ao excluir linhas em bulk: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/termos', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_listar_termos():
    """API para listar números de termos (de parcerias + extratos existentes)"""
    try:
        cur = get_cursor()

        # Buscar termos de parcerias (todos os termos válidos) + termos com extrato existente
        cur.execute("""
            SELECT DISTINCT numero_termo
            FROM public.parcerias
            WHERE numero_termo IS NOT NULL
            UNION
            SELECT DISTINCT numero_termo
            FROM analises_pc.conc_extrato
            WHERE numero_termo IS NOT NULL
            ORDER BY numero_termo
        """)

        termos = [row['numero_termo'] for row in cur.fetchall()]

        return jsonify(termos), 200

    except Exception as e:
        print(f"[ERRO] ao listar termos: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-despesas', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_categorias_despesas():
    """API para listar categorias de despesas de um termo específico"""
    import time
    start_time = time.time()
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()
        filtro = request.args.get('filtro', '').strip()

        if not numero_termo:
            return jsonify([]), 200

        query = """
            SELECT DISTINCT categoria_despesa
            FROM public.parcerias_despesas
            WHERE numero_termo = %s
              AND categoria_despesa IS NOT NULL
        """
        params = [numero_termo]

        if filtro:
            query += " AND categoria_despesa ILIKE %s"
            params.append(f'%{filtro}%')

        query += " ORDER BY categoria_despesa"

        cur.execute(query, params)

        categorias = [{'categoria_despesa': row['categoria_despesa']} for row in cur.fetchall()]

        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/categorias-despesas: {elapsed:.2f}ms")
        return jsonify(categorias), 200

    except Exception as e:
        print(f"[ERRO] ao listar categorias de despesas: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-analise', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_categorias_analise():
    """API para listar categorias de análise"""
    import time
    start_time = time.time()
    try:
        cur = get_cursor()
        filtro = request.args.get('filtro', '').strip()

        query = """
            SELECT categoria_extra, tipo_transacao, descricao, correspondente
            FROM categoricas.c_dac_despesas_analise
        """
        params = []

        if filtro:
            query += " WHERE categoria_extra ILIKE %s"
            params.append(f'%{filtro}%')

        query += " ORDER BY categoria_extra"

        cur.execute(query, params)

        categorias = [dict(row) for row in cur.fetchall()]

        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/categorias-analise: {elapsed:.2f}ms")
        return jsonify(categorias), 200

    except Exception as e:
        print(f"[ERRO] ao listar categorias de análise: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/periodo-termo', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_periodo_termo():
    """API para obter período (datas início e final) de um termo de parceria"""
    import time
    start_time = time.time()
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()

        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400

        query = """
            SELECT inicio, final, sei_pc
            FROM public.parcerias
            WHERE numero_termo = %s
        """

        cur.execute(query, (numero_termo,))
        resultado = cur.fetchone()

        if not resultado:
            return jsonify({'erro': 'Termo não encontrado'}), 404

        periodo = dict(resultado)

        # Converter datas para string ISO
        if periodo.get('inicio'):
            periodo['inicio'] = periodo['inicio'].isoformat()
        if periodo.get('final'):
            periodo['final'] = periodo['final'].isoformat()

        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/periodo-termo: {elapsed:.2f}ms")

        return jsonify(periodo), 200

    except Exception as e:
        print(f"[ERRO] ao buscar período do termo: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/banco', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_get_banco():
    """API para obter o banco do extrato e conta específica de um termo"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()

        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400

        # Buscar banco_extrato e conta_execucao de analises_pc.conc_banco
        query_banco = """
            SELECT banco_extrato, conta_execucao
            FROM analises_pc.conc_banco
            WHERE numero_termo = %s
        """

        cur.execute(query_banco, (numero_termo,))
        resultado_banco = cur.fetchone()

        # Buscar conta de public.parcerias
        query_conta = """
            SELECT conta
            FROM public.parcerias
            WHERE numero_termo = %s
        """

        cur.execute(query_conta, (numero_termo,))
        resultado_conta = cur.fetchone()

        return jsonify({
            'banco_extrato': resultado_banco['banco_extrato'] if resultado_banco else None,
            'conta': resultado_conta['conta'] if resultado_conta else None,
            'conta_execucao': resultado_banco['conta_execucao'] if resultado_banco else None
        }), 200

    except Exception as e:
        print(f"[ERRO] ao buscar banco: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/salvar-termo-session', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_salvar_termo_session():
    """API para salvar o termo atual na session"""
    try:
        dados = request.get_json()
        numero_termo = dados.get('numero_termo')

        if numero_termo:
            session['numero_termo'] = numero_termo
            return jsonify({'sucesso': True}), 200
        else:
            return jsonify({'erro': 'numero_termo não fornecido'}), 400

    except Exception as e:
        print(f"[ERRO] Erro ao salvar termo na session: {str(e)}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/banco', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_save_banco():
    """API para salvar o banco do extrato e conta específica de um termo"""
    try:
        dados = request.get_json()
        numero_termo = dados.get('numero_termo')
        banco_extrato = dados.get('banco_extrato')
        conta = dados.get('conta')
        conta_execucao = dados.get('conta_execucao')

        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400

        cur = get_cursor()
        db = get_db()

        ok, resposta = ensure_can_edit_termo(cur, numero_termo)
        if not ok:
            return resposta

        # Salvar banco_extrato e conta_execucao em analises_pc.conc_banco
        if banco_extrato is not None or conta_execucao is not None:
            # Verificar se já existe
            cur.execute("""
                SELECT id FROM analises_pc.conc_banco
                WHERE numero_termo = %s
            """, (numero_termo,))

            existe = cur.fetchone()

            if existe:
                # Atualizar campos individualmente
                if banco_extrato is not None:
                    cur.execute("""
                        UPDATE analises_pc.conc_banco
                        SET banco_extrato = %s
                        WHERE numero_termo = %s
                    """, (banco_extrato, numero_termo))

                if conta_execucao is not None:
                    cur.execute("""
                        UPDATE analises_pc.conc_banco
                        SET conta_execucao = %s
                        WHERE numero_termo = %s
                    """, (conta_execucao, numero_termo))
            else:
                # Inserir
                cur.execute("""
                    INSERT INTO analises_pc.conc_banco (numero_termo, banco_extrato, conta_execucao)
                    VALUES (%s, %s, %s)
                """, (numero_termo, banco_extrato, conta_execucao))

        # Salvar conta em public.parcerias
        if conta is not None:
            cur.execute("""
                UPDATE public.parcerias
                SET conta = %s
                WHERE numero_termo = %s
            """, (conta, numero_termo))

        db.commit()

        return jsonify({'mensagem': 'Banco e conta salvos com sucesso'}), 200

    except Exception as e:
        print(f"[ERRO] ao salvar banco: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/notas-fiscais', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_listar_notas_fiscais():
    """API para listar notas fiscais de um termo"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()

        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400

        query = """
            SELECT
                id,
                conc_extrato_id,
                numero_nota,
                chave_acesso,
                cnpj_nota,
                numero_termo
            FROM analises_pc.conc_extrato_notas_fiscais
            WHERE numero_termo = %s
            ORDER BY conc_extrato_id ASC
        """

        cur.execute(query, (numero_termo,))
        notas = cur.fetchall()

        resultado = [dict(nota) for nota in notas]

        return jsonify(resultado), 200

    except Exception as e:
        print(f"[ERRO] ao listar notas fiscais: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/notas-fiscais', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_salvar_notas_fiscais():
    """API para salvar notas fiscais com UPSERT (UPDATE prioritário)"""
    db = None
    try:
        import time
        inicio = time.time()

        dados = request.get_json()
        notas = dados.get('notas', [])
        numero_termo = dados.get('numero_termo')

        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400

        cur = get_cursor()
        db = get_db()

        ok, resposta = ensure_can_edit_termo(cur, numero_termo)
        if not ok:
            return resposta

        if not _try_lock_termo(cur, numero_termo):
            return _resposta_termo_em_save()

        ids_processados = []
        ids_candidatos = [nota.get('conc_extrato_id') for nota in notas if nota.get('conc_extrato_id')]
        ids_validos = _ids_extrato_validos(cur, numero_termo, ids_candidatos)
        ids_invalidos = sorted({int(i) for i in ids_candidatos if int(i) not in ids_validos})

        for nota in notas:
            conc_extrato_id = nota.get('conc_extrato_id')

            if not conc_extrato_id:
                continue  # Pular se não tiver FK
            conc_extrato_id = int(conc_extrato_id)
            if conc_extrato_id not in ids_validos:
                continue

            # Verificar se tem dados preenchidos (não salvar linha vazia)
            numero_nota = nota.get('numero_nota')
            chave_acesso = nota.get('chave_acesso') or ''
            cnpj_nota = nota.get('cnpj_nota') or ''

            # Strip apenas se não for None
            chave_acesso = chave_acesso.strip() if chave_acesso else None
            cnpj_nota = cnpj_nota.strip() if cnpj_nota else None

            # Se não tem número da nota, deletar registro se existir
            if not numero_nota:
                cur.execute("""
                    DELETE FROM analises_pc.conc_extrato_notas_fiscais
                    WHERE conc_extrato_id = %s AND numero_termo = %s
                """, (conc_extrato_id, numero_termo))
                continue

            # Verificar se já existe registro para este conc_extrato_id
            cur.execute("""
                SELECT id FROM analises_pc.conc_extrato_notas_fiscais
                WHERE conc_extrato_id = %s AND numero_termo = %s
            """, (conc_extrato_id, numero_termo))

            existe = cur.fetchone()

            if existe:
                # UPDATE: registro já existe
                cur.execute("""
                    UPDATE analises_pc.conc_extrato_notas_fiscais SET
                        numero_nota = %s,
                        chave_acesso = %s,
                        cnpj_nota = %s
                    WHERE conc_extrato_id = %s AND numero_termo = %s
                    RETURNING id
                """, (
                    numero_nota,
                    chave_acesso,
                    cnpj_nota,
                    conc_extrato_id,
                    numero_termo
                ))
                result = cur.fetchone()
                if result:
                    ids_processados.append(result['id'])
            else:
                # INSERT: novo registro
                cur.execute("""
                    INSERT INTO analises_pc.conc_extrato_notas_fiscais (
                        conc_extrato_id, numero_nota, chave_acesso,
                        cnpj_nota, numero_termo
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    conc_extrato_id,
                    numero_nota,
                    chave_acesso,
                    cnpj_nota,
                    numero_termo
                ))
                novo_id = cur.fetchone()['id']
                ids_processados.append(novo_id)

        db.commit()

        tempo_total = (time.time() - inicio) * 1000
        print(f"\n[SAVE NF] Tempo total: {tempo_total:.2f}ms | Notas: {len(ids_processados)}")

        return jsonify({
            'mensagem': f'{len(ids_processados)} notas fiscais salvas',
            'ids': ids_processados,
            'ids_invalidos': ids_invalidos
        }), 200

    except DatabaseUnavailable:
        _rollback_quietly(db)
        raise
    except Exception as e:
        print(f"[ERRO] ao salvar notas fiscais: {e}")
        _rollback_quietly(db)
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-aplicabilidade', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_categorias_aplicabilidade():
    """API para buscar aplicabilidade de documentos por categoria"""
    import time
    start_time = time.time()
    try:
        cur = get_cursor()

        query = """
            SELECT categoria_extra, COALESCE(aplicacao, false) as aplicacao
            FROM categoricas.c_dac_despesas_analise
            WHERE categoria_extra IS NOT NULL
        """

        cur.execute(query)
        categorias = cur.fetchall()

        # Retornar como dicionário { categoria: aplicacao }
        resultado = {cat['categoria_extra']: cat['aplicacao'] for cat in categorias}

        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/categorias-aplicabilidade: {elapsed:.2f}ms")
        return jsonify(resultado), 200

    except Exception as e:
        print(f"[ERRO] ao buscar categorias aplicabilidade: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/categorias-rubricas', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_categorias_rubricas():
    """API para buscar rubricas das categorias por termo"""
    import time
    start_time = time.time()
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()

        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400

        query = """
            SELECT categoria_despesa, rubrica
            FROM public.parcerias_despesas
            WHERE numero_termo = %s
              AND categoria_despesa IS NOT NULL
              AND rubrica IS NOT NULL
        """

        cur.execute(query, (numero_termo,))
        categorias = cur.fetchall()

        # Retornar como dicionário { categoria: rubrica }
        resultado = {cat['categoria_despesa']: cat['rubrica'] for cat in categorias}

        elapsed = (time.time() - start_time) * 1000
        print(f"[BACKEND PERF] /api/categorias-rubricas: {elapsed:.2f}ms")
        return jsonify(resultado), 200

    except Exception as e:
        print(f"[ERRO] ao buscar rubricas: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/documentos-analise', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_listar_documentos_analise():
    """API para listar documentos de análise de um termo"""
    try:
        cur = get_cursor()
        numero_termo = request.args.get('numero_termo', '').strip()

        if not numero_termo:
            return jsonify({'erro': 'numero_termo é obrigatório'}), 400

        query = """
            SELECT
                id,
                conc_extrato_id,
                COALESCE(avaliacao_guia, 'pendente') as avaliacao_guia,
                COALESCE(avaliacao_comprovante, 'pendente') as avaliacao_comprovante,
                COALESCE(avaliacao_contratos, 'pendente') as avaliacao_contratos,
                COALESCE(avaliacao_fora_municipio, 'pendente') as avaliacao_fora_municipio,
                numero_termo
            FROM analises_pc.conc_analise
            WHERE numero_termo = %s
            ORDER BY conc_extrato_id ASC
        """

        cur.execute(query, (numero_termo,))
        documentos = cur.fetchall()

        resultado = [dict(doc) for doc in documentos]

        return jsonify(resultado), 200

    except Exception as e:
        print(f"[ERRO] ao listar documentos de análise: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/documentos-analise', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_salvar_documentos_analise():
    """API para salvar documentos de análise com UPSERT e auto-marcação"""
    db = None
    try:
        import time
        inicio = time.time()

        dados = request.get_json()
        documentos = dados.get('documentos', [])
        numero_termo = dados.get('numero_termo')

        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400

        cur = get_cursor()
        db = get_db()

        ok, resposta = ensure_can_edit_termo(cur, numero_termo)
        if not ok:
            return resposta

        if not _try_lock_termo(cur, numero_termo):
            return _resposta_termo_em_save()

        ids_processados = []

        # Filtrar documentos válidos
        docs_validos = [doc for doc in documentos if doc.get('conc_extrato_id')]
        if not docs_validos:
            db.commit()
            return jsonify({'mensagem': '0 documentos salvos', 'ids': [], 'ids_invalidos': []}), 200

        conc_ids = [int(doc['conc_extrato_id']) for doc in docs_validos]
        ids_validos = _ids_extrato_validos(cur, numero_termo, conc_ids)
        ids_invalidos = sorted({i for i in conc_ids if i not in ids_validos})
        docs_validos = [
            doc for doc in docs_validos
            if int(doc['conc_extrato_id']) in ids_validos
        ]
        conc_ids = [int(doc['conc_extrato_id']) for doc in docs_validos]

        if not docs_validos:
            db.commit()
            return jsonify({
                'mensagem': '0 documentos salvos',
                'ids': [],
                'ids_invalidos': ids_invalidos
            }), 200

        # OTIMIZAÇÃO: Buscar dados do extrato + aplicabilidade em UMA query
        cur.execute("""
            SELECT
                e.id, e.data, e.credito, e.debito, e.discriminacao, e.cat_transacao,
                e.competencia, e.origem_destino, e.cat_avaliacao,
                ca.aplicacao
            FROM analises_pc.conc_extrato e
            LEFT JOIN categoricas.c_dac_despesas_analise ca ON e.cat_transacao = ca.categoria_extra
            WHERE e.numero_termo = %s AND e.id = ANY(%s)
        """, (numero_termo, conc_ids))
        extrato_map = {row['id']: row for row in cur.fetchall()}

        # OTIMIZAÇÃO: Verificar registros existentes em UMA query
        cur.execute("""
            SELECT id, conc_extrato_id FROM analises_pc.conc_analise
            WHERE conc_extrato_id = ANY(%s) AND numero_termo = %s
        """, (conc_ids, numero_termo))
        existentes_map = {row['conc_extrato_id']: row['id'] for row in cur.fetchall()}

        for doc in docs_validos:
            conc_extrato_id = int(doc['conc_extrato_id'])

            avaliacao_guia = doc.get('avaliacao_guia', '')
            avaliacao_comprovante = doc.get('avaliacao_comprovante', '')
            avaliacao_contratos = doc.get('avaliacao_contratos', '')
            avaliacao_fora_municipio = doc.get('avaliacao_fora_municipio', '')

            # Usar dict lookup (O(1)) em vez de query individual
            linha_extrato = extrato_map.get(conc_extrato_id)

            if linha_extrato:
                categoria_nao_aplicavel = linha_extrato.get('aplicacao') == True

                if categoria_nao_aplicavel:
                    avaliacao_guia = ''
                    avaliacao_comprovante = ''
                    avaliacao_contratos = ''
                    avaliacao_fora_municipio = ''
                else:
                    linha_completa = (
                        linha_extrato['data'] is not None and
                        (linha_extrato['credito'] is not None or linha_extrato['debito'] is not None) and
                        linha_extrato['discriminacao'] is not None and
                        linha_extrato['cat_transacao'] is not None and linha_extrato['cat_transacao'].strip() != '' and
                        linha_extrato['competencia'] is not None and
                        linha_extrato['origem_destino'] is not None and linha_extrato['origem_destino'].strip() != '' and
                        linha_extrato['cat_avaliacao'] == 'Avaliado'
                    )

                    if linha_completa:
                        if not avaliacao_guia or avaliacao_guia.strip() == '':
                            avaliacao_guia = 'Guia apresentada'
                        if not avaliacao_comprovante or avaliacao_comprovante.strip() == '':
                            avaliacao_comprovante = 'Apresentado corretamente'
                        if not avaliacao_contratos or avaliacao_contratos.strip() == '':
                            avaliacao_contratos = 'Contratos apresentados'
                        if not avaliacao_fora_municipio or avaliacao_fora_municipio.strip() == '':
                            avaliacao_fora_municipio = 'São Paulo'

            id_existente = existentes_map.get(conc_extrato_id)

            if id_existente:
                cur.execute("""
                    UPDATE analises_pc.conc_analise SET
                        avaliacao_guia = %s,
                        avaliacao_comprovante = %s,
                        avaliacao_contratos = %s,
                        avaliacao_fora_municipio = %s
                    WHERE conc_extrato_id = %s AND numero_termo = %s
                    RETURNING id
                """, (
                    avaliacao_guia,
                    avaliacao_comprovante,
                    avaliacao_contratos,
                    avaliacao_fora_municipio,
                    conc_extrato_id,
                    numero_termo
                ))
                result = cur.fetchone()
                if result:
                    ids_processados.append(result['id'])
            else:
                cur.execute("""
                    INSERT INTO analises_pc.conc_analise (
                        conc_extrato_id, avaliacao_guia, avaliacao_comprovante,
                        avaliacao_contratos, avaliacao_fora_municipio, numero_termo
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    conc_extrato_id,
                    avaliacao_guia,
                    avaliacao_comprovante,
                    avaliacao_contratos,
                    avaliacao_fora_municipio,
                    numero_termo
                ))
                novo_id = cur.fetchone()['id']
                ids_processados.append(novo_id)
                existentes_map[conc_extrato_id] = novo_id

        db.commit()

        tempo_total = (time.time() - inicio) * 1000
        print(f"\n[SAVE DOC] Tempo total: {tempo_total:.2f}ms | Documentos: {len(ids_processados)}")

        return jsonify({
            'mensagem': f'{len(ids_processados)} documentos salvos',
            'ids': ids_processados,
            'ids_invalidos': ids_invalidos
        }), 200

    except DatabaseUnavailable:
        _rollback_quietly(db)
        raise
    except Exception as e:
        print(f"[ERRO] ao salvar documentos de análise: {e}")
        _rollback_quietly(db)
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/limpar-termo', methods=['DELETE'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_limpar_termo():
    """
    API para limpar TODOS os dados de um termo específico
    Remove: extrato, rendimentos, notas fiscais e contrapartida
    """
    try:
        numero_termo = request.args.get('numero_termo', '').strip()

        if not numero_termo:
            return jsonify({'erro': 'Número do termo é obrigatório'}), 400

        db = get_db()
        cur = get_cursor()

        ok, resposta = ensure_can_edit_termo(cur, numero_termo)
        if not ok:
            return resposta

        # Contar registros antes da exclusão
        cur.execute("SELECT COUNT(*) as total FROM analises_pc.conc_extrato WHERE numero_termo = %s", (numero_termo,))
        total_extrato = cur.fetchone()['total']

        cur.execute("SELECT COUNT(*) as total FROM analises_pc.conc_rendimentos WHERE numero_termo = %s", (numero_termo,))
        total_rendimentos = cur.fetchone()['total']

        cur.execute("SELECT COUNT(*) as total FROM analises_pc.conc_extrato_notas_fiscais WHERE numero_termo = %s", (numero_termo,))
        total_notas = cur.fetchone()['total']

        cur.execute("SELECT COUNT(*) as total FROM analises_pc.conc_contrapartida WHERE numero_termo = %s", (numero_termo,))
        total_contrapartida = cur.fetchone()['total']

        cur.execute("SELECT COUNT(*) as total FROM analises_pc.conc_analise WHERE numero_termo = %s", (numero_termo,))
        total_analise = cur.fetchone()['total']

        cur.execute("""
            SELECT id, nome_armazenado
            FROM analises_pc.conc_vinculacao_docs
            WHERE numero_termo = %s
        """, (numero_termo,))
        vinculacoes = cur.fetchall()
        total_vinculacoes = len(vinculacoes)

        if vinculacoes:
            try:
                s3 = _r2_prestacao_client()
                for doc in vinculacoes:
                    if doc.get('nome_armazenado'):
                        try:
                            s3.delete_object(Bucket=_R2_PRESTACAO_BUCKET, Key=doc['nome_armazenado'])
                        except Exception as r2_item_err:
                            print(f"[AVISO] Falha ao excluir R2 {doc['nome_armazenado']}: {r2_item_err}")
            except Exception as r2_err:
                print(f"[AVISO] Falha ao inicializar R2 na limpeza do termo: {r2_err}")

        # Deletar todos os dados do termo
        cur.execute("DELETE FROM analises_pc.conc_vinculacao_docs WHERE numero_termo = %s", (numero_termo,))
        cur.execute("DELETE FROM analises_pc.conc_analise WHERE numero_termo = %s", (numero_termo,))
        cur.execute("DELETE FROM analises_pc.conc_extrato_notas_fiscais WHERE numero_termo = %s", (numero_termo,))
        cur.execute("DELETE FROM analises_pc.conc_rendimentos WHERE numero_termo = %s", (numero_termo,))
        cur.execute("DELETE FROM analises_pc.conc_contrapartida WHERE numero_termo = %s", (numero_termo,))
        cur.execute("DELETE FROM analises_pc.conc_extrato WHERE numero_termo = %s", (numero_termo,))

        db.commit()

        print(f"[LIMPAR TERMO] Termo: {numero_termo}")
        print(f"  - Extrato: {total_extrato} registros deletados")
        print(f"  - Rendimentos: {total_rendimentos} registros deletados")
        print(f"  - Notas Fiscais: {total_notas} registros deletados")
        print(f"  - Contrapartida: {total_contrapartida} registros deletados")
        print(f"  - Analise: {total_analise} registros deletados")
        print(f"  - Vinculacoes: {total_vinculacoes} registros deletados")

        return jsonify({
            'mensagem': 'Dados do termo limpos com sucesso',
            'termo': numero_termo,
            'registros_deletados': {
                'extrato': total_extrato,
                'rendimentos': total_rendimentos,
                'notas_fiscais': total_notas,
                'contrapartida': total_contrapartida,
                'documentos_analise': total_analise,
                'vinculacao_docs': total_vinculacoes,
                'total': (
                    total_extrato + total_rendimentos + total_notas +
                    total_contrapartida + total_analise + total_vinculacoes
                )
            }
        }), 200

    except Exception as e:
        print(f"[ERRO] ao limpar termo: {e}")
        if get_db():
            get_db().rollback()
        return jsonify({'erro': str(e)}), 500


# ─────────────────────────────────────────────────────────────────────────────
# EXPORTAR PDF
# ─────────────────────────────────────────────────────────────────────────────

# Mapeamento: nome interno → (label header, largura relativa, alinhamento)
_PDF_COLUNAS = {
    'indice':           ('Nº',             1.0,  'center'),
    'data':             ('Data',           2.2,  'center'),
    'credito':          ('Crédito (R$)',   2.8,  'right'),
    'debito':           ('Débito (R$)',    2.8,  'right'),
    'discriminacao':    ('Composição',     2.8,  'right'),
    'cat_transacao':    ('Categoria',      4.5,  'left'),
    'competencia':      ('Competência',   2.5,  'center'),
    'origem_destino':   ('Origem/Destino', 4.5,  'left'),
    'cat_avaliacao':    ('Avaliação',      3.0,  'center'),
    'avaliacao_analista': ('Observações',  5.0,  'left'),
}

_PDF_COR_AVALIACAO = {
    'Avaliado':          (0.88, 0.97, 0.88),   # verde claro
    'Glosar':            (1.00, 0.88, 0.88),   # vermelho claro
    'Aguardando resposta': (1.00, 0.97, 0.80), # amarelo claro
    'Pessoa Gestora':    (0.88, 0.94, 1.00),   # azul claro
}


@bp.route('/api/exportar-pdf', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_exportar_pdf():
    """Gera PDF da conciliação bancária com as colunas selecionadas."""
    from io import BytesIO
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer)
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from flask import make_response

    numero_termo = request.args.get('numero_termo', '').strip()
    colunas_param = request.args.get('colunas', '').strip()

    if not numero_termo:
        return jsonify({'erro': 'numero_termo é obrigatório'}), 400

    # Filtrar apenas colunas válidas, mantendo a ordem original
    colunas_validas = [c for c in colunas_param.split(',') if c in _PDF_COLUNAS]
    if not colunas_validas:
        return jsonify({'erro': 'Nenhuma coluna válida selecionada'}), 400

    try:
        cur = get_cursor()
        cur.execute("""
            SELECT id, indice, data, credito, debito, discriminacao,
                   cat_transacao, competencia, origem_destino,
                   cat_avaliacao, avaliacao_analista
            FROM analises_pc.conc_extrato
            WHERE numero_termo = %s
            ORDER BY indice ASC, id ASC
        """, (numero_termo,))
        rows = cur.fetchall()
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

    # ── Helpers de formatação ──────────────────────────────────────────────
    def _fmt_date(v):
        if not v:
            return ''
        try:
            return v.strftime('%d/%m/%Y')
        except Exception:
            return str(v)

    def _fmt_brl(v):
        if v is None:
            return ''
        try:
            f = float(v)
            return f'R$ {f:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
        except Exception:
            return str(v)

    def _fmt_competencia(v):
        if not v:
            return ''
        try:
            return v.strftime('%m/%Y')
        except Exception:
            return str(v)

    _FORMATADORES = {
        'data':          _fmt_date,
        'credito':       _fmt_brl,
        'debito':        _fmt_brl,
        'discriminacao': _fmt_brl,
        'competencia':   _fmt_competencia,
    }

    # ── Estilos ────────────────────────────────────────────────────────────
    styles = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle(
        'Titulo', parent=styles['Heading2'],
        fontSize=13, spaceAfter=6, leading=16,
    )
    estilo_subtitulo = ParagraphStyle(
        'Subtitulo', parent=styles['Normal'],
        fontSize=9, spaceAfter=10, textColor=colors.HexColor('#555555'),
    )

    # Estilo de célula pequeno (para caber conteúdo longo em células)
    estilo_celula = ParagraphStyle(
        'Celula', parent=styles['Normal'],
        fontSize=7.5, leading=9, wordWrap='LTR',
    )
    estilo_celula_r = ParagraphStyle(
        'CelulaR', parent=estilo_celula, alignment=TA_RIGHT,
    )
    estilo_celula_c = ParagraphStyle(
        'CelulaC', parent=estilo_celula, alignment=TA_CENTER,
    )

    # ── Calcular larguras das colunas ──────────────────────────────────────
    page_width, page_height = landscape(A4)
    margin = 1.5 * cm
    usable_width = page_width - 2 * margin

    total_weight = sum(_PDF_COLUNAS[c][1] for c in colunas_validas)
    col_widths = [
        (_PDF_COLUNAS[c][1] / total_weight) * usable_width
        for c in colunas_validas
    ]

    # ── Construir dados da tabela ──────────────────────────────────────────
    _ALINHAMENTO_ESTILO = {
        'center': estilo_celula_c,
        'right':  estilo_celula_r,
        'left':   estilo_celula,
    }

    header = [
        Paragraph(f'<b>{_PDF_COLUNAS[c][0]}</b>', estilo_celula_c)
        for c in colunas_validas
    ]

    data_table = [header]
    # Cor de linha por avaliação (usada na TableStyle)
    row_colors = []  # lista de (linha_idx, cor_rgb)

    for row_idx, row in enumerate(rows, start=1):  # 1-based após header
        row_dict = dict(row)
        linha_avaliacao = row_dict.get('cat_avaliacao') or ''
        bg_color = _PDF_COR_AVALIACAO.get(linha_avaliacao)
        if bg_color:
            row_colors.append((row_idx, bg_color))

        cells = []
        for col in colunas_validas:
            val = row_dict.get(col)
            fmt = _FORMATADORES.get(col)
            texto = fmt(val) if fmt else (str(val) if val is not None else '')
            align = _PDF_COLUNAS[col][2]
            estilo = _ALINHAMENTO_ESTILO[align]
            cells.append(Paragraph(texto, estilo))
        data_table.append(cells)

    # ── TableStyle base ────────────────────────────────────────────────────
    ts = TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#343a40')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.white),
        ('ALIGN',      (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME',   (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',   (0, 0), (-1, 0), 7.5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5),
        ('TOPPADDING',    (0, 0), (-1, 0), 5),
        # Body
        ('FONTSIZE',   (0, 1), (-1, -1), 7),
        ('TOPPADDING',    (0, 1), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ('LEFTPADDING',   (0, 0), (-1, -1), 4),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 4),
        # Grid
        ('GRID',       (0, 0), (-1, -1), 0.25, colors.HexColor('#cccccc')),
        # Zebra stripe
        ('ROWBACKGROUNDS', (0, 1), (-1, -1),
         [colors.white, colors.HexColor('#f8f9fa')]),
    ])

    # Aplicar cores de avaliação por linha (sobrepõe zebra)
    for row_idx, (r, g, b) in row_colors:
        ts.add('BACKGROUND', (0, row_idx), (-1, row_idx), colors.Color(r, g, b))

    table = Table(data_table, colWidths=col_widths, repeatRows=1)
    table.setStyle(ts)

    # ── Montar documento ───────────────────────────────────────────────────
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=margin, rightMargin=margin,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm,
    )

    # Número de linhas e totais de crédito/débito para o subtítulo
    total_linhas = len(rows)
    total_credito = sum(float(dict(r)['credito'] or 0) for r in rows)
    total_debito  = sum(float(dict(r)['debito']  or 0) for r in rows)

    def _brl(v):
        return f'R$ {v:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')

    story = [
        Paragraph(f'Conciliação Bancária — {numero_termo}', estilo_titulo),
        Paragraph(
            f'{total_linhas} linhas  |  '
            f'Créditos: {_brl(total_credito)}  |  '
            f'Débitos: {_brl(total_debito)}  |  '
            f'Colunas: {len(colunas_validas)}/10',
            estilo_subtitulo
        ),
        Spacer(1, 0.3 * cm),
        table,
    ]

    # Rodapé com número de página
    def _rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.drawRightString(
            page_width - margin,
            0.6 * cm,
            f'Página {doc.page}'
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=_rodape, onLaterPages=_rodape)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    # Nome de arquivo seguro
    nome_arquivo = f"conc_banc_{numero_termo.replace('/', '_').replace(' ', '_')}.pdf"

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    response.headers['Content-Length'] = len(pdf_bytes)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 4 — VINCULAÇÃO DE DOCUMENTOS (Cloudflare R2)
# ─────────────────────────────────────────────────────────────────────────────

_R2_PRESTACAO_BUCKET = 'prestacao-bucket'
_R2_PRESTACAO_PUBLIC_BASE = 'https://pub-1fa0a2c3969349d89c2adfd82134cf95.r2.dev'


def _r2_prestacao_client():
    """Cria cliente boto3 para o bucket prestacao-bucket no Cloudflare R2."""
    return boto3.client(
        's3',
        endpoint_url=os.environ.get(
            'R2_PRESTACAO_ENDPOINT',
            'https://1229204919913a51f4090b769f8f0548.r2.cloudflarestorage.com'
        ),
        aws_access_key_id=os.environ.get('R2_PRESTACAO_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('R2_PRESTACAO_SECRET_ACCESS_KEY'),
        config=Config(signature_version='s3v4'),
        region_name='auto',
    )


@bp.route('/api/vinculacao-docs', methods=['GET'])
@login_required
@requires_access('conc_bancaria')
def api_listar_vinculacao_docs():
    """Lista todos os documentos vinculados de um termo, agrupados por extrato_id."""
    numero_termo = request.args.get('numero_termo', '').strip()
    if not numero_termo:
        return jsonify({'erro': 'numero_termo obrigatório'}), 400
    try:
        cur = get_cursor()
        cur.execute("""
            SELECT id, extrato_id, nome_original, nome_armazenado, url_publica,
                   mime_type, tamanho_bytes, uploaded_at, uploaded_by
            FROM analises_pc.conc_vinculacao_docs
            WHERE numero_termo = %s
            ORDER BY extrato_id, uploaded_at
        """, (numero_termo,))
        rows = cur.fetchall()
        result = {}
        for row in rows:
            eid = str(row['extrato_id'])
            if eid not in result:
                result[eid] = []
            result[eid].append({
                'id': row['id'],
                'nome_original': row['nome_original'],
                'nome_armazenado': row['nome_armazenado'],
                'url_publica': row['url_publica'],
                'mime_type': row['mime_type'] or '',
                'tamanho_bytes': row['tamanho_bytes'] or 0,
                'uploaded_at': row['uploaded_at'].isoformat() if row['uploaded_at'] else '',
                'uploaded_by': row['uploaded_by'] or '',
            })
        return jsonify(result), 200
    except Exception as e:
        print(f"[ERRO] listar vinculacao-docs: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/vinculacao-docs/upload', methods=['POST'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_upload_vinculacao_doc():
    """Faz upload de um arquivo para o R2 e registra no banco."""
    extrato_id = request.form.get('extrato_id')
    numero_termo = request.form.get('numero_termo', '').strip()
    arquivo = request.files.get('arquivo')

    if not extrato_id or not numero_termo or not arquivo:
        return jsonify({'erro': 'extrato_id, numero_termo e arquivo são obrigatórios'}), 400

    try:
        extrato_id_int = int(extrato_id)
    except ValueError:
        return jsonify({'erro': 'extrato_id inválido'}), 400

    cur = get_cursor()
    db = get_db()
    ok, resposta = ensure_can_edit_termo(cur, numero_termo)
    if not ok:
        return resposta
    if extrato_id_int not in _ids_extrato_validos(cur, numero_termo, [extrato_id_int]):
        return jsonify({'erro': 'extrato_id nao pertence ao termo informado'}), 403

    nome_original = secure_filename(arquivo.filename or 'arquivo')
    if not nome_original:
        nome_original = 'arquivo'
    ext = os.path.splitext(nome_original)[1].lower()
    uid = uuid.uuid4().hex
    nome_armazenado = f'conc_banc/{extrato_id_int}/{uid}{ext}'

    try:
        conteudo = arquivo.read()
        s3 = _r2_prestacao_client()
        s3.put_object(
            Bucket=_R2_PRESTACAO_BUCKET,
            Key=nome_armazenado,
            Body=conteudo,
            ContentType=arquivo.content_type or 'application/octet-stream',
        )
        url_publica = f'{_R2_PRESTACAO_PUBLIC_BASE}/{nome_armazenado}'

        cur.execute("""
            INSERT INTO analises_pc.conc_vinculacao_docs
                (extrato_id, numero_termo, nome_original, nome_armazenado,
                 url_publica, mime_type, tamanho_bytes, uploaded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, uploaded_at
        """, (
            extrato_id_int, numero_termo, nome_original, nome_armazenado,
            url_publica, arquivo.content_type or '', len(conteudo),
            session.get('user_name', session.get('username', 'desconhecido'))
        ))
        row = cur.fetchone()
        db.commit()

        return jsonify({
            'id': row['id'],
            'nome_original': nome_original,
            'nome_armazenado': nome_armazenado,
            'url_publica': url_publica,
            'mime_type': arquivo.content_type or '',
            'tamanho_bytes': len(conteudo),
            'uploaded_at': row['uploaded_at'].isoformat(),
            'uploaded_by': session.get('user_name', session.get('username', 'desconhecido')),
        }), 201

    except Exception as e:
        print(f"[ERRO] upload vinculacao-docs: {e}")
        return jsonify({'erro': str(e)}), 500


@bp.route('/api/vinculacao-docs/<int:doc_id>', methods=['DELETE'])
@login_required
@requires_access('conc_bancaria')
@requires_write_access('conc_bancaria')
def api_excluir_vinculacao_doc(doc_id):
    """Exclui documento do R2 e do banco."""
    try:
        numero_termo = _request_numero_termo()
        if not numero_termo:
            return jsonify({'erro': 'numero_termo e obrigatorio'}), 400

        cur = get_cursor()
        db = get_db()

        ok, resposta = ensure_can_edit_termo(cur, numero_termo)
        if not ok:
            return resposta

        cur.execute(
            "SELECT nome_armazenado FROM analises_pc.conc_vinculacao_docs WHERE id = %s AND numero_termo = %s",
            (doc_id, numero_termo)
        )
        row = cur.fetchone()
        if not row:
            return jsonify({'erro': 'Documento não encontrado'}), 404

        # Excluir do R2 (falha não crítica — continua mesmo se o objeto não existir)
        try:
            s3 = _r2_prestacao_client()
            s3.delete_object(Bucket=_R2_PRESTACAO_BUCKET, Key=row['nome_armazenado'])
        except Exception as r2_err:
            print(f"[AVISO] Erro ao excluir do R2 (continuando): {r2_err}")

        cur.execute(
            "DELETE FROM analises_pc.conc_vinculacao_docs WHERE id = %s AND numero_termo = %s",
            (doc_id, numero_termo)
        )
        db.commit()
        return jsonify({'mensagem': 'Documento excluído'}), 200

    except Exception as e:
        print(f"[ERRO] excluir vinculacao-docs: {e}")
        return jsonify({'erro': str(e)}), 500
