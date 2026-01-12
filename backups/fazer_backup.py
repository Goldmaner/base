"""
Script de Backup do Banco de Dados PostgreSQL
==============================================

Este script cria um backup completo do banco de dados usando pg_dump.
As credenciais são lidas automaticamente do arquivo .env

Uso:
    python scripts/fazer_backup.py

Requisitos:
    - PostgreSQL instalado (pg_dump disponível no PATH)
    - Arquivo .env configurado com credenciais do banco
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

# Configurações do banco
DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_PORT = os.environ.get('DB_PORT', '5432')
DB_NAME = os.environ.get('DB_DATABASE', 'projeto_parcerias')
DB_USER = os.environ.get('DB_USER', 'postgres')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')

# Diretório de backups
BACKUP_DIR = Path(__file__).parent.parent / 'backups'
BACKUP_DIR.mkdir(exist_ok=True)

# Nome do arquivo com timestamp
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
backup_file = BACKUP_DIR / f'backup_faf_{timestamp}.sql'

print()
print("=" * 60)
print("  BACKUP DO BANCO DE DADOS FAF")
print("=" * 60)
print()
print(f"[INFO] Banco: {DB_NAME}")
print(f"[INFO] Host: {DB_HOST}:{DB_PORT}")
print(f"[INFO] Usuário: {DB_USER}")
print(f"[INFO] Arquivo destino: {backup_file}")
print()

# Montar comando pg_dump
comando = [
    'pg_dump',
    '-h', DB_HOST,
    '-p', DB_PORT,
    '-U', DB_USER,
    '-F', 'p',  # Formato plain (SQL)
    '-f', str(backup_file),
    '--clean',  # Incluir DROP antes de CREATE
    '--if-exists',  # Usar IF EXISTS nos DROP
    '--no-owner',  # Não incluir ownership
    '--no-privileges',  # Não incluir GRANT/REVOKE
    DB_NAME
]

# Configurar senha via variável de ambiente
env = os.environ.copy()
if DB_PASSWORD:
    env['PGPASSWORD'] = DB_PASSWORD

print("[INFO] Executando pg_dump...")
print()

try:
    # Executar pg_dump
    resultado = subprocess.run(
        comando,
        env=env,
        capture_output=True,
        text=True,
        check=True
    )
    
    # Verificar se arquivo foi criado
    if backup_file.exists():
        tamanho = backup_file.stat().st_size
        tamanho_mb = tamanho / (1024 * 1024)
        
        print()
        print("=" * 60)
        print("  BACKUP CONCLUÍDO COM SUCESSO!")
        print("=" * 60)
        print()
        print(f"[OK] Arquivo criado: {backup_file}")
        print(f"[OK] Tamanho: {tamanho:,} bytes ({tamanho_mb:.2f} MB)")
        print()
        print("[INFO] O backup pode ser restaurado com:")
        print(f"       psql -h {DB_HOST} -p {DB_PORT} -U {DB_USER} -d {DB_NAME} -f \"{backup_file}\"")
        print()
        
        # Listar todos os backups existentes
        backups = sorted(BACKUP_DIR.glob('backup_faf_*.sql'), reverse=True)
        
        # Manter apenas os 10 backups mais recentes
        MAX_BACKUPS = 10
        if len(backups) > MAX_BACKUPS:
            backups_para_deletar = backups[MAX_BACKUPS:]
            print(f"[INFO] Encontrados {len(backups)} backups. Mantendo os {MAX_BACKUPS} mais recentes.")
            print()
            print(f"[INFO] Deletando {len(backups_para_deletar)} backup(s) antigo(s):")
            
            for bkp in backups_para_deletar:
                try:
                    bkp_data = datetime.fromtimestamp(bkp.stat().st_mtime)
                    bkp.unlink()
                    print(f"  ✓ Deletado: {bkp.name} ({bkp_data.strftime('%d/%m/%Y %H:%M:%S')})")
                except Exception as e:
                    print(f"  ✗ Erro ao deletar {bkp.name}: {e}")
            print()
        
        if len(backups) > 1:
            # Atualizar lista após deleção
            backups = sorted(BACKUP_DIR.glob('backup_faf_*.sql'), reverse=True)
            print(f"[INFO] Total de backups na pasta: {len(backups)}")
            print()
            print("Últimos 5 backups:")
            for i, bkp in enumerate(backups[:5], 1):
                bkp_tamanho = bkp.stat().st_size / (1024 * 1024)
                bkp_data = datetime.fromtimestamp(bkp.stat().st_mtime)
                print(f"  {i}. {bkp.name} ({bkp_tamanho:.2f} MB) - {bkp_data.strftime('%d/%m/%Y %H:%M:%S')}")
            print()
    else:
        print()
        print("[ERRO] Arquivo de backup não foi criado!")
        print()

except subprocess.CalledProcessError as e:
    print()
    print("=" * 60)
    print("  ERRO AO CRIAR BACKUP!")
    print("=" * 60)
    print()
    print(f"[ERRO] Código de erro: {e.returncode}")
    print()
    
    if e.stderr:
        print("Mensagem de erro:")
        print(e.stderr)
        print()
    
    print("Possíveis causas:")
    print("  - pg_dump não encontrado no PATH")
    print("  - Senha incorreta no arquivo .env")
    print("  - Banco de dados não acessível")
    print("  - Permissões insuficientes")
    print()
    print("Verifique:")
    print(f"  1. PostgreSQL instalado: pg_dump --version")
    print(f"  2. Arquivo .env com DB_PASSWORD configurado")
    print(f"  3. Banco '{DB_NAME}' acessível em {DB_HOST}:{DB_PORT}")
    print()

except FileNotFoundError:
    print()
    print("=" * 60)
    print("  ERRO: pg_dump NÃO ENCONTRADO!")
    print("=" * 60)
    print()
    print("[ERRO] O comando 'pg_dump' não foi encontrado no PATH.")
    print()
    print("Solução:")
    print("  1. Instale o PostgreSQL: https://www.postgresql.org/download/")
    print("  2. Adicione o diretório 'bin' do PostgreSQL ao PATH")
    print("     Exemplo: C:\\Program Files\\PostgreSQL\\17\\bin")
    print()
    print("Para adicionar ao PATH:")
    print("  1. Painel de Controle > Sistema > Configurações avançadas")
    print("  2. Variáveis de Ambiente")
    print("  3. Editar variável PATH")
    print("  4. Adicionar caminho do PostgreSQL\\bin")
    print()

except Exception as e:
    print()
    print("=" * 60)
    print("  ERRO INESPERADO!")
    print("=" * 60)
    print()
    print(f"[ERRO] {type(e).__name__}: {e}")
    print()
