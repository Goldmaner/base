"""
Script de Backup do Banco de Dados PostgreSQL
Gera dump completo do banco e salva na pasta backups/ com timestamp
"""

import os
import subprocess
from datetime import datetime
from config import DB_CONFIG

def fazer_backup():
    """
    Realiza backup do banco de dados PostgreSQL usando pg_dump
    """
    try:
        # Extrair informações de conexão do DB_CONFIG
        db_host = DB_CONFIG['host']
        db_port = DB_CONFIG['port']
        db_name = DB_CONFIG['database']
        db_user = DB_CONFIG['user']
        db_password = DB_CONFIG['password']
        
        # Criar pasta backups se não existir
        backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
        os.makedirs(backup_dir, exist_ok=True)
        
        # Nome do arquivo com timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f'backup_faf_{timestamp}.sql')
        
        print(f"[INFO] Iniciando backup do banco de dados...")
        print(f"[INFO] Host: {db_host}")
        print(f"[INFO] Database: {db_name}")
        print(f"[INFO] Arquivo: {backup_file}")
        
        # Configurar variável de ambiente para senha
        env = os.environ.copy()
        env['PGPASSWORD'] = db_password
        
        # Comando pg_dump
        comando = [
            'pg_dump',
            '-h', db_host,
            '-p', str(db_port),
            '-U', db_user,
            '-d', db_name,
            '-F', 'p',  # Formato plain (SQL)
            '--no-owner',  # Não incluir comandos de proprietário
            '--no-acl',  # Não incluir comandos de privilégios
            '-f', backup_file
        ]
        
        # Executar pg_dump
        result = subprocess.run(
            comando,
            env=env,
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            # Verificar tamanho do arquivo
            tamanho = os.path.getsize(backup_file)
            tamanho_mb = tamanho / (1024 * 1024)
            
            print(f"\n✅ [SUCESSO] Backup realizado com sucesso!")
            print(f"📁 Arquivo: {backup_file}")
            print(f"📊 Tamanho: {tamanho_mb:.2f} MB")
            print(f"🕒 Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
            
            # Listar backups existentes
            listar_backups(backup_dir)
            
        else:
            print(f"\n❌ [ERRO] Falha ao criar backup:")
            print(result.stderr)
            
    except Exception as e:
        print(f"\n❌ [ERRO] Exceção durante backup: {str(e)}")
        import traceback
        traceback.print_exc()


def listar_backups(backup_dir):
    """
    Lista todos os backups existentes na pasta
    """
    print(f"\n📋 Backups disponíveis em {backup_dir}:")
    print("-" * 80)
    
    arquivos = []
    for arquivo in os.listdir(backup_dir):
        if arquivo.startswith('backup_faf_') and arquivo.endswith('.sql'):
            caminho = os.path.join(backup_dir, arquivo)
            tamanho = os.path.getsize(caminho)
            data_modificacao = os.path.getmtime(caminho)
            data_formatada = datetime.fromtimestamp(data_modificacao).strftime('%d/%m/%Y %H:%M:%S')
            
            arquivos.append({
                'nome': arquivo,
                'tamanho': tamanho / (1024 * 1024),
                'data': data_formatada,
                'timestamp': data_modificacao
            })
    
    # Ordenar por data (mais recente primeiro)
    arquivos.sort(key=lambda x: x['timestamp'], reverse=True)
    
    for arq in arquivos:
        print(f"  • {arq['nome']}")
        print(f"    Tamanho: {arq['tamanho']:.2f} MB | Data: {arq['data']}")
    
    print("-" * 80)
    print(f"Total: {len(arquivos)} backup(s)")


def limpar_backups_antigos(dias=30):
    """
    Remove backups com mais de X dias (opcional)
    """
    backup_dir = os.path.join(os.path.dirname(__file__), 'backups')
    
    if not os.path.exists(backup_dir):
        return
    
    from datetime import timedelta
    limite = datetime.now() - timedelta(days=dias)
    
    removidos = 0
    for arquivo in os.listdir(backup_dir):
        if arquivo.startswith('backup_faf_') and arquivo.endswith('.sql'):
            caminho = os.path.join(backup_dir, arquivo)
            data_modificacao = datetime.fromtimestamp(os.path.getmtime(caminho))
            
            if data_modificacao < limite:
                try:
                    os.remove(caminho)
                    print(f"🗑️  Backup antigo removido: {arquivo}")
                    removidos += 1
                except Exception as e:
                    print(f"⚠️  Erro ao remover {arquivo}: {e}")
    
    if removidos > 0:
        print(f"\n🧹 {removidos} backup(s) antigo(s) removido(s)")


if __name__ == '__main__':
    print("=" * 80)
    print("  BACKUP DO BANCO DE DADOS FAF")
    print("=" * 80)
    print()
    
    # Fazer backup
    fazer_backup()
    
    # Opcional: Descomentar para limpar backups com mais de 30 dias
    # print("\n🧹 Verificando backups antigos...")
    # limpar_backups_antigos(dias=30)
    
    print("\n" + "=" * 80)
    print("  Backup concluído!")
    print("=" * 80)
