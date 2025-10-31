@echo off
REM ============================================
REM Script de Backup do Banco de Dados FAF
REM ============================================

echo.
echo ============================================
echo   BACKUP FAF - Sistema de Parcerias
echo ============================================
echo.

REM Executar o script Python de backup
python backup_database.py

echo.
echo Pressione qualquer tecla para fechar...
pause > nul
