"""
Migração de arquivos locais (modelos/) para o Supabase Storage.

Mapeamento:
  modelos/Certidoes/**  →  bucket 'documentos' / Certidoes/**
  modelos/Manuais/**    →  bucket 'documentos' / Manuais/**
  modelos/<arquivo>     →  bucket 'documentos' / Modelos/<arquivo>

Uso:
  python scripts/migrar_modelos_supabase.py
  python scripts/migrar_modelos_supabase.py --certidoes-only
  python scripts/migrar_modelos_supabase.py --folders-only

Após execução bem-sucedida, altere .env:
  USE_SUPABASE_STORAGE=True
e reinicie o servidor.
"""

import os
import sys
import argparse

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Forçar modo Supabase para este script independente da flag
os.environ['USE_SUPABASE_STORAGE'] = 'TRUE'

import utils_storage as storage

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELOS_DIR = os.path.join(BASE_DIR, 'modelos')

EXTENSOES_VALIDAS = {
    '.pdf', '.xlsx', '.xls', '.docx', '.doc',
    '.pptx', '.ppt', '.txt', '.png', '.jpg', '.jpeg', '.odt', '.ods'
}

CONTENT_TYPES = {
    '.pdf':  'application/pdf',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xls':  'application/vnd.ms-excel',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.doc':  'application/msword',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.ppt':  'application/vnd.ms-powerpoint',
    '.txt':  'text/plain',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.odt':  'application/vnd.oasis.opendocument.text',
    '.ods':  'application/vnd.oasis.opendocument.spreadsheet',
}


def obter_storage_path(local_path: str) -> str | None:
    """
    Converte um caminho local em storage_path para o bucket 'documentos'.
    Retorna None se o arquivo não deve ser migrado.
    """
    rel = os.path.relpath(local_path, MODELOS_DIR).replace('\\', '/')

    if rel.startswith('Certidoes/'):
        return rel
    if rel.startswith('Manuais/'):
        return rel
    if '/' not in rel:
        # Arquivo na raiz de modelos/
        ext = os.path.splitext(rel)[1].lower()
        if ext in EXTENSOES_VALIDAS:
            return f'Modelos/{rel}'

    # Ignorar outros subdiretórios (documentos_eventos, etc.)
    return None


def materializar_pastas_certidoes():
    """
    Materializa todas as pastas locais de modelos/Certidoes no Supabase.

    Isso cobre inclusive OSCs sem arquivos ainda, criando um marcador `.keep`
    para que a pasta exista no bucket e seja detectada pela aplicação.
    """
    certidoes_dir = os.path.join(MODELOS_DIR, 'Certidoes')
    if not os.path.isdir(certidoes_dir):
        return 0, 0, 0, 0

    criadas = 0
    existentes = 0
    erros = 0

    pastas_locais = [
        entry.name
        for entry in sorted(os.scandir(certidoes_dir), key=lambda item: item.name.lower())
        if entry.is_dir() and not entry.name.startswith('.')
    ]
    pastas_remotas = set(storage.list_folders('Certidoes'))

    for nome_pasta in pastas_locais:
        if nome_pasta in pastas_remotas:
            existentes += 1
            continue
        try:
            storage.upload_file(
                f'Certidoes/{nome_pasta}/.keep',
                b'keep',
                'text/plain',
            )
            print(f'  PASTA {nome_pasta}')
            criadas += 1
        except Exception as exc:
            print(f'  ERRO PASTA Certidoes/{nome_pasta}: {exc}')
            erros += 1

    return len(pastas_locais), existentes, criadas, erros


def migrar(certidoes_only: bool = False, folders_only: bool = False):
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_KEY', '')

    if not url or not key:
        print('\nERRO: SUPABASE_URL e SUPABASE_SERVICE_KEY não estão definidos no .env')
        sys.exit(1)

    if not os.path.isdir(MODELOS_DIR):
        print(f'\nERRO: pasta modelos/ não encontrada em {MODELOS_DIR}')
        sys.exit(1)

    print(f'Origem : {MODELOS_DIR}')
    print(f'Destino: bucket "{storage.BUCKET}" em {url}')
    print('-' * 60)

    ok = erros = ignorados = 0

    print('Materializando pastas de Certidoes...')
    total_local, pastas_existentes, pastas_ok, pastas_erros = materializar_pastas_certidoes()
    erros += pastas_erros
    print(
        f'Pastas locais: {total_local} | '
        f'já existentes no Supabase: {pastas_existentes} | '
        f'materializadas agora: {pastas_ok} | erros: {pastas_erros}'
    )
    print('-' * 60)

    if folders_only:
        print('Modo somente pastas finalizado.')
        if erros > 0:
            print('\nAtenção: algumas pastas falharam. Corrija os erros e re-execute.')
            sys.exit(1)
        print('\nMaterialização concluída com sucesso!')
        print('Próximo passo: reinicie o servidor para a Central refletir a listagem atualizada.')
        return

    for dirpath, dirnames, filenames in os.walk(MODELOS_DIR):
        # Não entrar em pastas ocultas
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]

        if certidoes_only:
            rel_dir = os.path.relpath(dirpath, MODELOS_DIR).replace('\\', '/')
            if rel_dir != '.' and not rel_dir.startswith('Certidoes'):
                continue

        for filename in filenames:
            ext = os.path.splitext(filename)[1].lower()

            # Ignorar arquivos de controle
            if filename.startswith('.') or ext not in EXTENSOES_VALIDAS:
                ignorados += 1
                continue

            local_path = os.path.join(dirpath, filename)
            storage_path = obter_storage_path(local_path)

            if storage_path is None:
                ignorados += 1
                continue

            try:
                with open(local_path, 'rb') as fh:
                    file_bytes = fh.read()

                ct = CONTENT_TYPES.get(ext, 'application/octet-stream')
                storage.upload_file(storage_path, file_bytes, ct)
                print(f'  OK    {storage_path}')
                ok += 1

            except Exception as exc:
                print(f'  ERRO  {storage_path}: {exc}')
                erros += 1

    print('-' * 60)
    print(f'Resultado: {ok} enviados | {erros} erros | {ignorados} ignorados | {pastas_ok} pastas materializadas')

    if erros > 0:
        print('\nAtenção: alguns arquivos falharam. Corrija os erros e re-execute.')
        sys.exit(1)
    else:
        print('\nMigração concluída com sucesso!')
        print('Próximo passo: altere no .env  →  USE_SUPABASE_STORAGE=True')
        print('Depois reinicie o servidor.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Migra modelos locais para o Supabase Storage.')
    parser.add_argument(
        '--certidoes-only',
        action='store_true',
        help='Sincroniza apenas modelos/Certidoes',
    )
    parser.add_argument(
        '--folders-only',
        action='store_true',
        help='Materializa apenas as pastas de modelos/Certidoes no Supabase, sem subir arquivos',
    )
    args = parser.parse_args()
    migrar(certidoes_only=args.certidoes_only, folders_only=args.folders_only)
