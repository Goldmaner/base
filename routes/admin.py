"""
Blueprint do painel administrativo — erros do sistema e testes de regressão.
Acesso restrito a usuários do tipo 'Agente Público'.
"""

from flask import Blueprint, render_template, jsonify, request, session, redirect, url_for, Response
from utils import login_required
from db import get_cursor, get_db
import subprocess
import sys
import json
import os
import time
import csv
import io
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _apenas_admin():
    """Retorna True se o usuário logado é Agente Público."""
    return session.get('tipo_usuario') == 'Agente Público'


# =============================================================================
# PAINEL DE ERROS
# =============================================================================

@admin_bp.route('/painel-erros')
@login_required
def painel_erros():
    if not _apenas_admin():
        return redirect(url_for('main.index'))

    cur = get_cursor()

    # ── Estatísticas resumidas ─────────────────────────────────────────────
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day')
                AS hoje,
            COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days')
                AS semana,
            COUNT(*) FILTER (WHERE NOT resolvido)
                AS pendentes,
            COUNT(*) FILTER (WHERE tipo_erro = 'http_erro'   AND NOT resolvido)
                AS http_erros,
            COUNT(*) FILTER (WHERE tipo_erro = 'query_lenta' AND NOT resolvido)
                AS queries_lentas,
            COUNT(*) FILTER (WHERE tipo_erro = 'api_externa' AND NOT resolvido)
                AS api_erros
        FROM gestao_pessoas.log_erros
    """)
    stats = cur.fetchone()

    # ── Filtros e paginação ────────────────────────────────────────────────
    tipo_filtro      = request.args.get('tipo', '').strip()
    resolvido_filtro = request.args.get('resolvido', 'pendentes')   # 'pendentes' | 'todos' | 'resolvidos'
    pagina           = max(1, int(request.args.get('pagina', 1)))
    por_pagina       = 50
    offset           = (pagina - 1) * por_pagina

    where_parts = ['1=1']
    params = []

    if tipo_filtro:
        where_parts.append('tipo_erro = %s')
        params.append(tipo_filtro)

    if resolvido_filtro == 'pendentes':
        where_parts.append('resolvido = FALSE')
    elif resolvido_filtro == 'resolvidos':
        where_parts.append('resolvido = TRUE')

    where_clause = ' AND '.join(where_parts)

    cur.execute(f"""
        SELECT id, tipo_erro, created_at, endpoint, metodo, status_codigo,
               usuario_email, ip_address, duracao_ms, query_preview,
               api_nome, api_endpoint, mensagem, detalhes,
               resolvido, resolvido_em, resolvido_por
        FROM gestao_pessoas.log_erros
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, params + [por_pagina, offset])
    erros = cur.fetchall()

    cur.execute(
        f"SELECT COUNT(*) AS total FROM gestao_pessoas.log_erros WHERE {where_clause}",
        params
    )
    total       = cur.fetchone()['total']
    total_pags  = max(1, -(-total // por_pagina))

    return render_template(
        'admin/painel_erros.html',
        stats=stats,
        erros=erros,
        tipo_filtro=tipo_filtro,
        resolvido_filtro=resolvido_filtro,
        pagina=pagina,
        total_paginas=total_pags,
        total=total,
    )


@admin_bp.route('/painel-erros/<int:erro_id>/resolver', methods=['POST'])
@login_required
def resolver_erro(erro_id):
    if not _apenas_admin():
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    db  = get_db()
    cur = get_cursor()
    cur.execute("""
        UPDATE gestao_pessoas.log_erros
        SET resolvido = TRUE,
            resolvido_em  = NOW(),
            resolvido_por = %s
        WHERE id = %s AND resolvido = FALSE
    """, (session.get('email'), erro_id))
    db.commit()
    return jsonify({'success': True})


@admin_bp.route('/painel-erros/resolver-todos', methods=['POST'])
@login_required
def resolver_todos():
    if not _apenas_admin():
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    tipo = request.get_json(silent=True, force=True) or {}
    tipo_erro = tipo.get('tipo_erro')

    db  = get_db()
    cur = get_cursor()

    if tipo_erro:
        cur.execute("""
            UPDATE gestao_pessoas.log_erros
            SET resolvido = TRUE, resolvido_em = NOW(), resolvido_por = %s
            WHERE resolvido = FALSE AND tipo_erro = %s
        """, (session.get('email'), tipo_erro))
    else:
        cur.execute("""
            UPDATE gestao_pessoas.log_erros
            SET resolvido = TRUE, resolvido_em = NOW(), resolvido_por = %s
            WHERE resolvido = FALSE
        """, (session.get('email'),))

    db.commit()
    return jsonify({'success': True})


@admin_bp.route('/painel-erros/exportar/<formato>')
@login_required
def exportar_erros(formato):
    """Exporta os erros pendentes (não resolvidos) em JSON ou Markdown."""
    if not _apenas_admin():
        return jsonify({'erro': 'Acesso negado'}), 403

    if formato not in ('json', 'md'):
        return jsonify({'erro': 'Formato inválido. Use: json, md'}), 400

    cur = get_cursor()
    cur.execute("""
        SELECT id, tipo_erro, created_at, endpoint, metodo, status_codigo,
               usuario_email, ip_address, duracao_ms, query_preview,
               api_nome, api_endpoint, mensagem, detalhes
        FROM gestao_pessoas.log_erros
        WHERE resolvido = FALSE
        ORDER BY created_at DESC
    """)
    erros = cur.fetchall()
    cur.close()

    data_str = datetime.now().strftime('%Y%m%d_%H%M')

    # ── JSON ─────────────────────────────────────────────────────────────
    if formato == 'json':
        def _serialize(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            return str(obj)
        payload = json.dumps(
            [dict(e) for e in erros],
            ensure_ascii=False, indent=2, default=_serialize
        )
        return Response(
            payload,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename=erros_pendentes_{data_str}.json'}
        )

    # ── Markdown ─────────────────────────────────────────────────────────
    if formato == 'md':
        tipo_labels = {'http_erro': 'HTTP', 'query_lenta': 'QUERY', 'api_externa': 'API'}
        tipo_icons  = {'http_erro': '🔴', 'query_lenta': '🟡', 'api_externa': '🔵'}

        lines = [
            '# Erros Pendentes — FAF',
            '',
            f'**Exportado em:** {datetime.now().strftime("%d/%m/%Y %H:%M")}  ',
            f'**Total pendente:** {len(erros)}  ',
            '',
            '---',
            '',
        ]

        for e in erros:
            tipo   = e.get('tipo_erro', '')
            icon   = tipo_icons.get(tipo, '⚪')
            label  = tipo_labels.get(tipo, tipo.upper())
            dt     = e['created_at'].strftime('%d/%m/%Y %H:%M') if e.get('created_at') else 'N/A'
            dur    = f"{e['duracao_ms']}ms" if e.get('duracao_ms') else '—'
            ep     = e.get('endpoint') or e.get('api_endpoint') or '—'

            lines += [
                f'## {icon} [{label}] #{e["id"]} — {dt}',
                '',
                f'- **Endpoint:** `{ep}`',
                f'- **Duração:** {dur}',
                f'- **Usuário:** {e.get("usuario_email") or "—"}',
                f'- **Mensagem:** {e.get("mensagem") or "—"}',
            ]
            if e.get('query_preview'):
                lines += ['', '**Query:**', '```sql', e['query_preview'].strip(), '```']
            if e.get('detalhes'):
                det = json.dumps(e['detalhes'], ensure_ascii=False, indent=2) \
                      if isinstance(e['detalhes'], dict) else str(e['detalhes'])
                lines += ['', '**Detalhes:**', '```json', det, '```']
            lines.append('')

        return Response(
            '\n'.join(lines),
            mimetype='text/markdown; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename=erros_pendentes_{data_str}.md'}
        )


# =============================================================================
# TESTES DE REGRESSÃO
# =============================================================================

@admin_bp.route('/testes')
@login_required
def painel_testes():
    if not _apenas_admin():
        return redirect(url_for('main.index'))

    # Ler último relatório gerado pelo pytest-json-report (se existir)
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'testes', '.last_report.json'
    )
    report = None
    report_date = ''
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            if report and report.get('created'):
                report_date = datetime.fromtimestamp(report['created']).strftime('%d/%m/%Y %H:%M')
        except Exception:
            report = None

    return render_template('admin/painel_testes.html', report=report, report_date=report_date)


@admin_bp.route('/testes/executar', methods=['POST'])
@login_required
def executar_testes():
    """
    Executa a suite de testes em background e salva o relatório JSON.
    Retorna imediatamente com status 202 — o cliente deve
    fazer polling em /admin/testes/status para ver o resultado.
    """
    if not _apenas_admin():
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    base_dir   = os.path.dirname(os.path.dirname(__file__))
    report_path = os.path.join(base_dir, 'testes', '.last_report.json')
    lock_path   = os.path.join(base_dir, 'testes', '.running')

    # Limpar lock file travado (>60s = stale)
    if os.path.exists(lock_path):
        age = time.time() - os.path.getmtime(lock_path)
        if age > 60:
            os.remove(lock_path)
        else:
            return jsonify({'success': False, 'erro': 'Testes já em execução'}), 409

    try:
        open(lock_path, 'w').close()
        result = subprocess.run(
            [
                sys.executable, '-m', 'pytest',
                '--json-report',
                f'--json-report-file={report_path}',
                '-q', '--tb=short',
                '--timeout=30',
            ],
            cwd=base_dir,
            capture_output=True,
            text=True,
            timeout=180,
        )
        return jsonify({
            'success': True,
            'returncode': result.returncode,
            'stdout': result.stdout[-3000:],
            'stderr': result.stderr[-1000:],
        })
    except subprocess.TimeoutExpired:
        return jsonify({'success': False, 'erro': 'Timeout ao executar testes'}), 504
    except Exception as e:
        return jsonify({'success': False, 'erro': str(e)}), 500
    finally:
        if os.path.exists(lock_path):
            os.remove(lock_path)


@admin_bp.route('/testes/status')
@login_required
def status_testes():
    if not _apenas_admin():
        return jsonify({'success': False}), 403

    base_dir    = os.path.dirname(os.path.dirname(__file__))
    report_path = os.path.join(base_dir, 'testes', '.last_report.json')
    lock_path   = os.path.join(base_dir, 'testes', '.running')

    rodando = os.path.exists(lock_path)
    report  = None
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
        except Exception:
            pass

    return jsonify({'rodando': rodando, 'report': report})


def _load_report():
    """Carrega o último relatório pytest JSON. Retorna None se não existir."""
    base_dir    = os.path.dirname(os.path.dirname(__file__))
    report_path = os.path.join(base_dir, 'testes', '.last_report.json')
    if not os.path.exists(report_path):
        return None
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


@admin_bp.route('/testes/exportar/<formato>')
@login_required
def exportar_testes(formato):
    """Exporta o último relatório de testes em JSON, CSV ou Markdown."""
    if not _apenas_admin():
        return jsonify({'erro': 'Acesso negado'}), 403

    if formato not in ('json', 'csv', 'md'):
        return jsonify({'erro': 'Formato inválido'}), 400

    report = _load_report()
    if not report:
        return jsonify({'erro': 'Nenhum relatório encontrado. Execute os testes primeiro.'}), 404

    summary  = report.get('summary', {})
    tests    = report.get('tests', [])
    created  = report.get('created')
    data_str = datetime.fromtimestamp(created).strftime('%Y%m%d_%H%M') if created else 'sem_data'
    duration = report.get('duration', 0)

    # ── JSON ─────────────────────────────────────────────────────────────
    if formato == 'json':
        payload = json.dumps(report, ensure_ascii=False, indent=2)
        return Response(
            payload,
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename=testes_{data_str}.json'}
        )

    # ── CSV ──────────────────────────────────────────────────────────────
    if formato == 'csv':
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(['nodeid', 'outcome', 'duration_s', 'erro'])
        for t in tests:
            longrepr = ''
            if t.get('call') and t['call'].get('longrepr'):
                longrepr = str(t['call']['longrepr'])[:300].replace('\n', ' ')
            writer.writerow([
                t.get('nodeid', ''),
                t.get('outcome', ''),
                round(t.get('duration', 0), 3),
                longrepr,
            ])
        return Response(
            buf.getvalue(),
            mimetype='text/csv; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename=testes_{data_str}.csv'}
        )

    # ── Markdown ─────────────────────────────────────────────────────────
    if formato == 'md':
        data_fmt = datetime.fromtimestamp(created).strftime('%d/%m/%Y %H:%M') if created else 'N/A'
        lines = [
            '# Relatório de Testes de Regressão',
            '',
            f'**Data:** {data_fmt}  ',
            f'**Duração total:** {duration:.1f}s  ',
            f'**Passaram:** {summary.get("passed", 0)}  ',
            f'**Falharam:** {summary.get("failed", 0)}  ',
            f'**Erros:** {summary.get("error", 0)}  ',
            f'**Total:** {summary.get("total", 0)}  ',
            '',
            '---',
            '',
            '## Resultados por Teste',
            '',
            '| Resultado | Teste | Duração |',
            '|-----------|-------|---------|',
        ]
        icons = {'passed': '✅', 'failed': '❌', 'error': '⚠️'}
        for t in tests:
            icon   = icons.get(t.get('outcome', ''), '❓')
            nodeid = t.get('nodeid', '')
            dur    = round(t.get('duration', 0), 3)
            lines.append(f'| {icon} {t.get("outcome", "")} | `{nodeid}` | {dur}s |')

        falhas = [t for t in tests if t.get('outcome') in ('failed', 'error')]
        if falhas:
            lines += ['', '---', '', '## Detalhes das Falhas', '']
            for t in falhas:
                lines.append(f'### `{t.get("nodeid", "")}`')
                longrepr = ''
                if t.get('call') and t['call'].get('longrepr'):
                    longrepr = str(t['call']['longrepr'])[:800]
                lines += ['```', longrepr, '```', '']

        return Response(
            '\n'.join(lines),
            mimetype='text/markdown; charset=utf-8',
            headers={'Content-Disposition': f'attachment; filename=testes_{data_str}.md'}
        )


# =============================================================================
# RELATOS DE USUÁRIOS
# =============================================================================

@admin_bp.route('/relatos', methods=['GET'])
@login_required
def listar_relatos():
    """API JSON para o painel admin — retorna relatos com filtros e paginação."""
    if not _apenas_admin():
        return jsonify({'erro': 'Acesso negado'}), 403

    cur = get_cursor()

    # ── Filtros ────────────────────────────────────────────────────────────
    status_filtro = request.args.get('status', '').strip()
    tipo_filtro   = request.args.get('tipo',   '').strip()
    modulo_filtro = request.args.get('modulo', '').strip()
    email_filtro  = request.args.get('email',  '').strip()
    pagina        = max(1, int(request.args.get('pagina', 1)))
    por_pagina    = 50
    offset        = (pagina - 1) * por_pagina

    where_parts = ['1=1']
    params      = []

    if status_filtro:
        where_parts.append('status = %s')
        params.append(status_filtro)
    if tipo_filtro:
        where_parts.append('tipo_relato = %s')
        params.append(tipo_filtro)
    if modulo_filtro:
        where_parts.append('modulo = %s')
        params.append(modulo_filtro)
    if email_filtro:
        where_parts.append('usuario_email ILIKE %s')
        params.append(f'%{email_filtro}%')

    where_clause = ' AND '.join(where_parts)

    cur.execute(f"""
        SELECT id, tipo_relato, modulo, titulo, descricao, passos_reproducao,
               prioridade_usuario, status, resposta_admin,
               usuario_email, usuario_nome, tipo_usuario,
               criado_em, atualizado_em, resolvido_por, resolvido_em
        FROM gestao_pessoas.relatos_usuarios
        WHERE {where_clause}
        ORDER BY
            CASE status WHEN 'Urgente' THEN 0 ELSE 1 END,
            CASE prioridade_usuario WHEN 'Urgente' THEN 0 WHEN 'Normal' THEN 1 ELSE 2 END,
            criado_em DESC
        LIMIT %s OFFSET %s
    """, params + [por_pagina, offset])
    relatos = cur.fetchall()

    cur.execute(
        f"SELECT COUNT(*) AS total FROM gestao_pessoas.relatos_usuarios WHERE {where_clause}",
        params
    )
    total = cur.fetchone()['total']

    # ── Stats gerais ───────────────────────────────────────────────────────
    cur.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status = 'Aberto')       AS abertos,
            COUNT(*) FILTER (WHERE status = 'Em análise')   AS em_analise,
            COUNT(*) FILTER (WHERE status = 'Resolvido')    AS resolvidos,
            COUNT(*) FILTER (WHERE status = 'Descartado')   AS descartados,
            COUNT(*) FILTER (WHERE criado_em >= NOW() - INTERVAL '7 days') AS semana
        FROM gestao_pessoas.relatos_usuarios
    """)
    stats = dict(cur.fetchone())

    resultado = []
    for r in relatos:
        resultado.append({
            'id':                r['id'],
            'tipo_relato':       r['tipo_relato'],
            'modulo':            r['modulo'],
            'titulo':            r['titulo'],
            'descricao':         r['descricao'],
            'passos_reproducao': r['passos_reproducao'],
            'prioridade_usuario': r['prioridade_usuario'],
            'status':            r['status'],
            'resposta_admin':    r['resposta_admin'],
            'usuario_email':     r['usuario_email'],
            'usuario_nome':      r['usuario_nome'],
            'tipo_usuario':      r['tipo_usuario'],
            'criado_em':         r['criado_em'].strftime('%d/%m/%Y %H:%M') if r['criado_em'] else None,
            'atualizado_em':     r['atualizado_em'].strftime('%d/%m/%Y %H:%M') if r['atualizado_em'] else None,
            'resolvido_por':     r['resolvido_por'],
            'resolvido_em':      r['resolvido_em'].strftime('%d/%m/%Y %H:%M') if r['resolvido_em'] else None,
        })

    return jsonify({
        'relatos':       resultado,
        'total':         total,
        'stats':         stats,
        'pagina':        pagina,
        'total_paginas': max(1, -(-total // por_pagina)),
    })


@admin_bp.route('/relatos/<int:relato_id>/status', methods=['PATCH'])
@login_required
def atualizar_status_relato(relato_id):
    """Atualiza status e resposta de um relato (somente admin)."""
    if not _apenas_admin():
        return jsonify({'success': False, 'erro': 'Acesso negado'}), 403

    data      = request.get_json(silent=True) or {}
    status    = (data.get('status')        or '').strip()
    resposta  = (data.get('resposta_admin') or '').strip()

    STATUS_VALIDOS = {'Aberto', 'Em análise', 'Resolvido', 'Descartado'}
    if status not in STATUS_VALIDOS:
        return jsonify({'success': False, 'erro': 'Status inválido.'}), 400

    db  = get_db()
    cur = get_cursor()

    cur.execute(
        "SELECT id FROM gestao_pessoas.relatos_usuarios WHERE id = %s",
        (relato_id,)
    )
    if not cur.fetchone():
        return jsonify({'success': False, 'erro': 'Relato não encontrado.'}), 404

    admin_email = session.get('email')

    if status == 'Resolvido':
        cur.execute("""
            UPDATE gestao_pessoas.relatos_usuarios
            SET status        = %s,
                resposta_admin = %s,
                atualizado_em  = NOW(),
                resolvido_por  = %s,
                resolvido_em   = NOW()
            WHERE id = %s
        """, (status, resposta or None, admin_email, relato_id))
    else:
        cur.execute("""
            UPDATE gestao_pessoas.relatos_usuarios
            SET status        = %s,
                resposta_admin = %s,
                atualizado_em  = NOW()
            WHERE id = %s
        """, (status, resposta or None, relato_id))

    db.commit()
    return jsonify({'success': True})
