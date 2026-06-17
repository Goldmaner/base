#!/usr/bin/env python3
"""
Arquiva empenhos anteriores a 2026 no Supabase Storage e remove da tabela back_empenhos.

Cada ano vira um arquivo comprimido:
  documentos/arquivo_empenhos/back_empenhos_<ano>.json.gz

Uso:
  python scripts/arquivar_empenhos_historico.py            # executa de verdade
  python scripts/arquivar_empenhos_historico.py --dry-run  # só faz upload, não deleta
"""

import gzip
import json
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

import psycopg2
import psycopg2.extras
from utils_storage import upload_file

BUCKET_FOLDER = 'arquivo_empenhos'
ANO_CORTE = 2026


def _serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f'Tipo não serializável: {type(obj)}')


def main():
    dry_run = '--dry-run' in sys.argv
    if dry_run:
        print('[DRY RUN] Uploads serão feitos, mas nenhuma linha será deletada.\n')

    conn = psycopg2.connect(
        host=os.environ['DB_HOST'],
        port=int(os.environ.get('DB_PORT', 5432)),
        dbname=os.environ['DB_DATABASE'],
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'],
        sslmode=os.environ.get('DB_SSLMODE', 'require'),
    )
    conn.autocommit = False

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT ano_eph, COUNT(*) AS n
                FROM gestao_financeira.back_empenhos
                WHERE ano_eph < %s
                GROUP BY ano_eph
                ORDER BY ano_eph
            """, (ANO_CORTE,))
            anos_info = cur.fetchall()

        if not anos_info:
            print(f'Nenhum dado anterior a {ANO_CORTE} encontrado. Nada a fazer.')
            return

        print(f'Anos a arquivar (< {ANO_CORTE}):')
        total_linhas = 0
        for r in anos_info:
            print(f"  {r['ano_eph']}: {r['n']} linhas")
            total_linhas += r['n']
        print(f'  Total: {total_linhas} linhas\n')

        total_deletado = 0

        for r in anos_info:
            ano = r['ano_eph']

            # 1. Ler ano completo
            print(f'[{ano}] Lendo {r["n"]} linhas...', end='', flush=True)
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM gestao_financeira.back_empenhos
                    WHERE ano_eph = %s
                    ORDER BY cod_idt_eph
                """, (ano,))
                rows = [dict(row) for row in cur.fetchall()]
            print(f' {len(rows)} linhas lidas.')

            # 2. Serializar e comprimir
            payload = json.dumps(rows, default=_serial, ensure_ascii=False)
            compressed = gzip.compress(payload.encode('utf-8'), compresslevel=9)
            size_kb = len(compressed) / 1024
            storage_path = f'{BUCKET_FOLDER}/back_empenhos_{ano}.json.gz'

            # 3. Upload
            print(f'[{ano}] Upload -> documentos/{storage_path} ({size_kb:.0f} KB)...', end='', flush=True)
            upload_file(storage_path, compressed, 'application/gzip')
            print(' OK')

            # 4. Deletar (commit por ano — seguro para retomar se falhar)
            if not dry_run:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM gestao_financeira.back_empenhos
                        WHERE ano_eph = %s
                    """, (ano,))
                    deleted = cur.rowcount
                conn.commit()
                total_deletado += deleted
                print(f'[{ano}] {deleted} linhas deletadas e commit feito.')
            else:
                print(f'[{ano}] --dry-run: delete pulado.')

        print()
        if not dry_run:
            print(f'Total removido: {total_deletado} linhas.')
            print('Espaço será recuperado pelo autovacuum (ou via VACUUM ANALYZE no dashboard do Supabase).')
        else:
            print('[DRY RUN] Uploads concluídos. Banco não foi alterado.')

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    print('\nConcluído!')


if __name__ == '__main__':
    main()
