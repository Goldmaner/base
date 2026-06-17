"""
Abstração de armazenamento de arquivos: disco local ou Supabase Storage.

Controlada pela flag USE_SUPABASE_STORAGE no .env:
  USE_SUPABASE_STORAGE=True  → usa Supabase Storage (bucket 'documentos')
  USE_SUPABASE_STORAGE=False → usa disco local em modelos/ (comportamento original)

Para reverter: alterar USE_SUPABASE_STORAGE=False no .env + reiniciar servidor.

Mapeamento de paths (local ↔ Supabase):
  modelos/Certidoes/<osc>/<file>  ↔  Certidoes/<osc>/<file>
  modelos/Manuais/<id>/<file>     ↔  Manuais/<id>/<file>
  modelos/<arquivo>               ↔  Modelos/<arquivo>
"""

import os
import socket
import subprocess
import tempfile
from urllib.parse import quote

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BUCKET = 'documentos'
_client = None


def _use_supabase() -> bool:
    return os.environ.get('USE_SUPABASE_STORAGE', 'False').upper() == 'TRUE'


def _get_client():
    global _client
    if _client is None:
        from supabase import create_client
        url = os.environ.get('SUPABASE_URL', '').rstrip('/')
        key = os.environ.get('SUPABASE_SERVICE_KEY', '')
        if not url or not key:
            raise RuntimeError(
                'SUPABASE_URL e SUPABASE_SERVICE_KEY devem estar definidos no .env'
            )
        _client = create_client(url, key)
    return _client


def _get_supabase_credentials():
    url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    key = os.environ.get('SUPABASE_SERVICE_KEY', '')
    if not url or not key:
        raise RuntimeError(
            'SUPABASE_URL e SUPABASE_SERVICE_KEY devem estar definidos no .env'
        )
    return url, key


def _upload_via_http(storage_path: str, file_data, content_type: str) -> None:
    """
    Fallback direto em HTTP para uploads no Supabase Storage.

    Em alguns ambientes o client do pacote `supabase` falha de forma
    intermitente na resolução/conexão de upload; este caminho usa o endpoint
    REST do Storage com upsert explícito.
    """
    import httpx

    url, key = _get_supabase_credentials()
    encoded_path = quote(storage_path, safe='/')
    endpoint = f'{url}/storage/v1/object/{BUCKET}/{encoded_path}'
    headers = {
        'Authorization': f'Bearer {key}',
        'apikey': key,
        'x-upsert': 'true',
        'Content-Type': content_type,
    }
    response = httpx.post(endpoint, headers=headers, content=file_data, timeout=60.0)
    response.raise_for_status()


def _upload_via_curl_resolve(storage_path: str, file_data, content_type: str) -> None:
    """
    Fallback final usando curl com --resolve para contornar DNS instável.

    Mantém o hostname do Supabase no TLS/Host, mas fixa um IP já resolvido.
    """
    url, key = _get_supabase_credentials()
    host = url.replace('https://', '').split('/')[0]
    ip = socket.getaddrinfo(host, 443)[0][4][0]
    encoded_path = quote(storage_path, safe='/')
    endpoint = f'{url}/storage/v1/object/{BUCKET}/{encoded_path}'

    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(file_data)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [
                'curl.exe',
                '--silent',
                '--show-error',
                '--resolve',
                f'{host}:443:{ip}',
                '-X',
                'POST',
                endpoint,
                '-H',
                f'Authorization: Bearer {key}',
                '-H',
                f'apikey: {key}',
                '-H',
                'x-upsert: true',
                '-H',
                f'Content-Type: {content_type}',
                '--data-binary',
                f'@{tmp_path}',
            ],
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or 'curl upload falhou')


def _normalize(storage_path: str) -> str:
    """Garante que o storage_path usa barras normais e sem barra inicial."""
    return storage_path.replace('\\', '/').lstrip('/')


def _local_path(storage_path: str) -> str:
    """Converte storage_path em caminho absoluto local: {BASE}/modelos/{path}"""
    parts = _normalize(storage_path).split('/')
    return os.path.join(_BASE_DIR, 'modelos', *parts)


def _list_all_supabase_items(prefix: str, page_size: int = 1000) -> list:
    """
    Lista todos os itens de um prefixo no Supabase Storage com paginação.

    O endpoint de listagem retorna lotes limitados; sem paginação, diretórios com
    mais de 100 itens podem parecer incompletos e quebrar detecções de existência.
    """
    client = _get_client()
    offset = 0
    items = []

    while True:
        batch = client.storage.from_(BUCKET).list(
            prefix,
            {"limit": page_size, "offset": offset},
        ) or []
        items.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size

    return items


# ─────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────

def upload_file(storage_path: str, file_data, content_type: str = 'application/octet-stream') -> None:
    """
    Faz upload de um arquivo.

    storage_path: caminho relativo ao bucket, ex: 'Certidoes/OSC/file.pdf'
    file_data: bytes, bytearray ou objeto file-like (será lido integralmente)
    """
    storage_path = _normalize(storage_path)

    if not isinstance(file_data, (bytes, bytearray)):
        file_data = file_data.read()

    if _use_supabase():
        client = _get_client()
        try:
            client.storage.from_(BUCKET).upload(
                storage_path,
                file_data,
                file_options={"content-type": content_type, "upsert": "true"},
            )
        except Exception as exc:
            try:
                _upload_via_http(storage_path, file_data, content_type)
            except Exception as fallback_exc:
                try:
                    _upload_via_curl_resolve(storage_path, file_data, content_type)
                except Exception as curl_exc:
                    raise RuntimeError(
                        f'Erro no upload Supabase ({storage_path}): {exc} | fallback HTTP: {fallback_exc} | fallback curl: {curl_exc}'
                    ) from curl_exc
    else:
        local = _local_path(storage_path)
        os.makedirs(os.path.dirname(local), exist_ok=True)
        with open(local, 'wb') as fh:
            fh.write(file_data)


def download_file(storage_path: str) -> bytes:
    """
    Faz download de um arquivo e retorna os bytes.

    storage_path: ex: 'Certidoes/OSC/file.pdf'
    Lança FileNotFoundError se o arquivo não existir.
    """
    storage_path = _normalize(storage_path)

    if _use_supabase():
        client = _get_client()
        try:
            return client.storage.from_(BUCKET).download(storage_path)
        except Exception as exc:
            raise FileNotFoundError(
                f'Arquivo não encontrado no Supabase: {storage_path}'
            ) from exc
    else:
        local = _local_path(storage_path)
        if not os.path.isfile(local):
            raise FileNotFoundError(f'Arquivo não encontrado: {local}')
        with open(local, 'rb') as fh:
            return fh.read()


def list_files(prefix: str) -> list:
    """
    Lista arquivos (não pastas) dentro de um prefixo.

    prefix: ex: 'Modelos' ou 'Manuais/1'
    Retorna lista de nomes (sem o prefixo).
    """
    prefix = _normalize(prefix)

    if _use_supabase():
        try:
            items = _list_all_supabase_items(prefix)
            # Arquivos têm 'id' != None; pastas têm id == None
            return [item['name'] for item in (items or []) if item.get('id') is not None]
        except Exception:
            return []
    else:
        local = _local_path(prefix)
        if not os.path.isdir(local):
            return []
        return [
            f for f in os.listdir(local)
            if os.path.isfile(os.path.join(local, f))
        ]


def list_folders(prefix: str) -> list:
    """
    Lista subpastas dentro de um prefixo.

    prefix: ex: 'Certidoes'
    Retorna lista de nomes de pasta.
    """
    prefix = _normalize(prefix)

    if _use_supabase():
        try:
            items = _list_all_supabase_items(prefix)
            # Pastas têm id == None
            return [item['name'] for item in (items or []) if item.get('id') is None]
        except Exception:
            return []
    else:
        local = _local_path(prefix)
        if not os.path.isdir(local):
            return []
        return [
            d for d in os.listdir(local)
            if os.path.isdir(os.path.join(local, d))
        ]


def folder_exists(prefix: str) -> bool:
    """
    Verifica se uma pasta virtual/física existe.

    Para Supabase, considera a pasta existente se houver objetos/subpastas
    dentro dela ou se o prefixo aparecer na listagem do diretório pai.
    """
    prefix = _normalize(prefix).rstrip('/')
    if not prefix:
        return False

    if _use_supabase():
        parent_prefix, _, folder_name = prefix.rpartition('/')
        sibling_folders = list_folders(parent_prefix)
        if folder_name in sibling_folders:
            return True
        return bool(list_files(prefix) or list_folders(prefix))

    return os.path.isdir(_local_path(prefix))


def ensure_folder(prefix: str) -> None:
    """
    Garante a existência de uma pasta.

    No Supabase, cria um marcador `.keep` para materializar o prefixo.
    """
    prefix = _normalize(prefix).rstrip('/')
    if not prefix or folder_exists(prefix):
        return

    if _use_supabase():
        # Marcador não vazio: alguns backends do Storage ignoram objetos vazios
        # em listagens, o que quebra a detecção de diretórios virtualizados.
        upload_file(f'{prefix}/.keep', b'keep', 'text/plain')
    else:
        os.makedirs(_local_path(prefix), exist_ok=True)


def list_files_by_folder(prefix: str) -> dict:
    """
    Retorna {nome_pasta: [arquivos]} para todos os subdiretórios de prefix.

    Na versão Supabase dispara todas as requisições em paralelo (ThreadPoolExecutor)
    em vez de sequencialmente, reduzindo latência de 100 × RTT para ~1 × RTT.
    prefix: ex: 'Certidoes'
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    prefix = _normalize(prefix)
    folders = list_folders(prefix)
    if not folders:
        return {}

    result = {}
    if _use_supabase():
        def _fetch(folder_name):
            return folder_name, list_files(f'{prefix}/{folder_name}')

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = {executor.submit(_fetch, f): f for f in folders}
            for future in as_completed(futures):
                folder_name, files = future.result()
                result[folder_name] = files
    else:
        for folder in folders:
            result[folder] = list_files(f'{prefix}/{folder}')

    return result


def delete_file(storage_path: str) -> None:
    """
    Remove um arquivo. Falha silenciosa (não lança exceção).

    storage_path: ex: 'Certidoes/OSC/file.pdf'
    """
    storage_path = _normalize(storage_path)

    if _use_supabase():
        client = _get_client()
        try:
            client.storage.from_(BUCKET).remove([storage_path])
        except Exception as exc:
            print(f'[AVISO] delete_file falhou para {storage_path!r}: {exc}')
    else:
        local = _local_path(storage_path)
        try:
            if os.path.isfile(local):
                os.remove(local)
        except Exception as exc:
            print(f'[AVISO] delete_file local falhou para {local!r}: {exc}')
