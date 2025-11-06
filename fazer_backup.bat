@echo off
REM ========================================================================
REM Script de Backup do Banco de Dados PostgreSQL
REM ========================================================================
REM Este script cria um backup completo do banco de dados 'projeto_parcerias'
REM e salva na pasta 'backups' com timestamp no nome do arquivo.
REM
REM Requisitos:
REM - PostgreSQL instalado (pg_dump disponivel no PATH)
REM - Variavel PGPASSWORD configurada ou senha informada manualmente
REM ========================================================================

echo.
echo ========================================
echo  BACKUP DO BANCO DE DADOS FAF
echo ========================================
echo.

REM Configuracoes do banco de dados
set DB_HOST=localhost
set DB_PORT=5432
set DB_NAME=projeto_parcerias
set DB_USER=postgres

REM Gerar timestamp no formato YYYYMMDD_HHMMSS
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /value') do set datetime=%%I
set TIMESTAMP=%datetime:~0,4%%datetime:~4,2%%datetime:~6,2%_%datetime:~8,2%%datetime:~10,2%%datetime:~12,2%

REM Nome do arquivo de backup
set BACKUP_FILE=backups\backup_faf_%TIMESTAMP%.sql

echo [INFO] Iniciando backup do banco de dados...
echo [INFO] Banco: %DB_NAME%
echo [INFO] Host: %DB_HOST%:%DB_PORT%
echo [INFO] Usuario: %DB_USER%
echo [INFO] Arquivo destino: %BACKUP_FILE%
echo.

REM Verificar se a pasta backups existe
if not exist "backups" (
    echo [INFO] Criando pasta backups...
    mkdir backups
)

REM Executar pg_dump
REM Opcoes:
REM   -h: host
REM   -p: porta
REM   -U: usuario
REM   -F p: formato plain (SQL)
REM   -f: arquivo de saida
REM   -v: verbose
REM   --clean: incluir comandos DROP antes de CREATE
REM   --if-exists: usar IF EXISTS nos DROP
REM   --no-owner: nao incluir comandos de ownership
REM   --no-privileges: nao incluir comandos GRANT/REVOKE

echo [INFO] Executando pg_dump...
echo.

pg_dump -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -F p -f "%BACKUP_FILE%" -v --clean --if-exists --no-owner --no-privileges %DB_NAME%

REM Verificar se o backup foi criado com sucesso
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ========================================
    echo  BACKUP CONCLUIDO COM SUCESSO!
    echo ========================================
    echo.
    echo [OK] Arquivo criado: %BACKUP_FILE%
    
    REM Mostrar tamanho do arquivo
    for %%A in ("%BACKUP_FILE%") do (
        echo [OK] Tamanho: %%~zA bytes
    )
    
    echo.
    echo [INFO] O backup pode ser restaurado com:
    echo        psql -h %DB_HOST% -p %DB_PORT% -U %DB_USER% -d %DB_NAME% -f "%BACKUP_FILE%"
    echo.
) else (
    echo.
    echo ========================================
    echo  ERRO AO CRIAR BACKUP!
    echo ========================================
    echo.
    echo [ERRO] Codigo de erro: %ERRORLEVEL%
    echo.
    echo Possiveis causas:
    echo   - pg_dump nao encontrado no PATH
    echo   - Senha incorreta (configure PGPASSWORD ou use pgpass.conf)
    echo   - Banco de dados nao acessivel
    echo   - Permissoes insuficientes
    echo.
    echo Solucao para senha:
    echo   set PGPASSWORD=sua_senha
    echo   fazer_backup.bat
    echo.
)

pause
