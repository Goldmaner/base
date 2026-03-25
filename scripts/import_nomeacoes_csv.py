"""
Importa nomeações CDA a partir de um CSV externo para gestao_pessoas.smdhc_servidores.

Colunas utilizadas do CSV (separador ';', encoding UTF-8-SIG):
  Nome              → nome_servidor
  Referência        → cda  (ex: "CDA-5" → 5)
  RF/RG             → numero_rf
  A partir          → data_publicacao  (DD/MM/YYYY)
  Vaga              → numero_vaga
  Unidade de lotação→ unidade  (primeiros 200 chars)

Uso:
  python scripts/import_nomeacoes_csv.py <caminho_csv> [--dry-run]
"""

import csv
import re
import sys
from datetime import datetime

# ── adiciona raiz do projeto ao path ──────────────────────────────────────────
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from db import get_cursor, get_db, execute_batch


# ---------------------------------------------------------------------------
# Helpers (idênticos aos de routes/gestao_pessoas.py)
# ---------------------------------------------------------------------------

def _parse_int(value):
    if not value:
        return None
    digits = re.sub(r'\D', '', str(value))
    return int(digits) if digits else None


def _parse_date(value):
    if not value:
        return None
    s = str(value).strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _recalcular_encerramento(vagas):
    if not vagas:
        return
    cur = get_cursor()
    db = get_db()
    if not cur or not db:
        return
    try:
        placeholders = ','.join(['%s'] * len(vagas))
        cur.execute(f"""
            WITH recalc AS (
                SELECT id,
                    (LEAD(data_publicacao) OVER (
                        PARTITION BY numero_vaga ORDER BY data_publicacao ASC, id ASC
                    ) - INTERVAL '1 day')::date AS nova_enc
                FROM gestao_pessoas.smdhc_servidores
                WHERE numero_vaga IN ({placeholders})
            )
            UPDATE gestao_pessoas.smdhc_servidores AS s
            SET data_encerramento = r.nova_enc,
                observacoes = CASE
                    WHEN r.nova_enc IS NOT NULL THEN 'Exonerado(a)'
                    ELSE observacoes
                END
            FROM recalc r
            WHERE s.id = r.id
        """, vagas)
        db.commit()
    except Exception as e:
        print(f'[recalc] Erro: {e}')
        try:
            db.rollback()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Importação
# ---------------------------------------------------------------------------

def importar(csv_path: str, dry_run: bool = False):
    print(f'Lendo: {csv_path}')

    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)

    print(f'Linhas lidas: {len(rows)}')

    params_list = []
    erros = []

    for i, row in enumerate(rows, start=1):
        nome     = (row.get('Nome') or '').strip()
        ref      = (row.get('Referência') or '').strip()
        rf_raw   = (row.get('RF/RG') or '').strip()
        data_str = (row.get('A partir') or '').strip()
        vaga_raw = (row.get('Vaga') or '').strip()
        unidade  = (row.get('Unidade de lotação') or '').strip()

        cda     = _parse_int(re.sub(r'cda[-–]?', '', ref, flags=re.IGNORECASE))
        rf      = _parse_int(rf_raw)
        data    = _parse_date(data_str)
        vaga    = _parse_int(vaga_raw)

        if not cda:
            erros.append(f'  Linha {i}: Referência inválida "{ref}" — ignorada')
            continue
        if not vaga:
            erros.append(f'  Linha {i}: Vaga inválida "{vaga_raw}" — ignorada')
            continue

        params_list.append({
            'cda':              cda,
            'numero_vaga':      vaga,
            'nome_servidor':    nome or None,
            'numero_rf':        rf,
            'data_publicacao':  data,
            'unidade':          unidade[:200] if unidade else None,
            'numero_documento': None,
            'observacoes':      None,
        })

    if erros:
        print(f'\nAvisos de parsing ({len(erros)}):')
        for e in erros:
            print(e)

    print(f'\nRegistros válidos para importar: {len(params_list)}')

    if dry_run:
        print('\n[DRY-RUN] Nenhuma alteração feita no banco.')
        for p in params_list[:5]:
            print(' ', p)
        if len(params_list) > 5:
            print(f'  ... (e mais {len(params_list) - 5})')
        return

    # ── Checar duplicatas ─────────────────────────────────────────────────
    cur = get_cursor()
    existing_pairs = set()
    pairs = [(p['numero_vaga'], p['data_publicacao'])
             for p in params_list
             if p['numero_vaga'] is not None and p['data_publicacao'] is not None]

    if pairs:
        placeholders = ','.join(['(%s,%s)'] * len(pairs))
        flat = [x for pair in pairs for x in pair]
        cur.execute(
            f"SELECT numero_vaga, data_publicacao FROM gestao_pessoas.smdhc_servidores "
            f"WHERE (numero_vaga, data_publicacao) IN ({placeholders})",
            flat
        )
        existing_pairs = {(r['numero_vaga'], r['data_publicacao']) for r in cur.fetchall()}

    ignorados = 0
    novos = []
    for p in params_list:
        key = (p['numero_vaga'], p['data_publicacao'])
        if key[0] is not None and key[1] is not None and key in existing_pairs:
            ignorados += 1
        else:
            novos.append(p)

    # Todas as vagas do CSV precisam de recalculo, independente de serem novas ou já existentes
    todas_vagas = list({p['numero_vaga'] for p in params_list if p['numero_vaga']})

    print(f'  Duplicatas ignoradas: {ignorados}')
    print(f'  Novos registros a inserir: {len(novos)}')

    if novos:
        query = """
            INSERT INTO gestao_pessoas.smdhc_servidores
                (cda, numero_vaga, nome_servidor, numero_rf, data_publicacao,
                 unidade, numero_documento, observacoes)
            VALUES
                (%(cda)s, %(numero_vaga)s, %(nome_servidor)s, %(numero_rf)s,
                 %(data_publicacao)s, %(unidade)s, %(numero_documento)s, %(observacoes)s)
        """
        resultado = execute_batch(query, novos)
        if resultado['success']:
            print(f'\n✓ Inseridos: {resultado["count"]} registros')
        else:
            print('✗ Erro ao inserir no banco.')
            return
    else:
        print('\nNenhum registro novo a inserir.')

    # Recalcula encerramento para TODAS as vagas do CSV:
    # - Vagas recém-inseridas recebem data_encerramento correto
    # - Vagas já existentes (duplicatas) também são atualizadas caso haja
    #   uma nomeação mais recente no banco para a mesma vaga
    print(f'\n  Recalculando encerramento para {len(todas_vagas)} vagas...')
    _recalcular_encerramento(todas_vagas)
    print('  Concluído.')


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f'Uso: python {sys.argv[0]} <caminho_csv> [--dry-run]')
        sys.exit(1)

    csv_path = sys.argv[1]
    dry_run  = '--dry-run' in sys.argv

    if not os.path.isfile(csv_path):
        print(f'Arquivo não encontrado: {csv_path}')
        sys.exit(1)

    with app.app_context():
        importar(csv_path, dry_run=dry_run)
