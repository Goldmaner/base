"""
Migração de arquivos locais (modelos/) para o Supabase Storage.

Mapeamento:
  modelos/Certidoes/**  →  bucket 'documentos' / Certidoes/**
  modelos/Manuais/**    →  bucket 'documentos' / Manuais/**
  modelos/<arquivo>     →  bucket 'documentos' / Modelos/<arquivo>

Uso:
  python scripts/migrar_modelos_supabase.py

Após execução bem-sucedida, altere .env:
  USE_SUPABASE_STORAGE=True
e reinicie o servidor.
"""

import os
import sys

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


def migrar():
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

    for dirpath, dirnames, filenames in os.walk(MODELOS_DIR):
        # Não entrar em pastas ocultas
        dirnames[:] = [d for d in dirnames if not d.startswith('.')]

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
    print(f'Resultado: {ok} enviados | {erros} erros | {ignorados} ignorados')

    if erros > 0:
        print('\nAtenção: alguns arquivos falharam. Corrija os erros e re-execute.')
        sys.exit(1)
    else:
        print('\nMigração concluída com sucesso!')
        print('Próximo passo: altere no .env  →  USE_SUPABASE_STORAGE=True')
        print('Depois reinicie o servidor.')


if __name__ == '__main__':
    migrar()
