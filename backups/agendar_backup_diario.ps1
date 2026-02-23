# ========================================================================
# Script para Agendar Backup Diário Automático no Windows
# ========================================================================
# Este script cria uma tarefa agendada no Windows Task Scheduler para
# executar o backup do banco de dados diariamente às 03:00 da manhã.
#
# Requisitos:
# - Executar PowerShell como Administrador
# - PostgreSQL instalado
# - Arquivo .env configurado
#
# Uso:
#   .\backups\agendar_backup_diario.ps1
# ========================================================================

# Requer privilégios de administrador
#Requires -RunAsAdministrator

Write-Host ""
Write-Host "=" -NoNewline -ForegroundColor Cyan
Write-Host ("=" * 58) -ForegroundColor Cyan
Write-Host "  CONFIGURAR BACKUP DIÁRIO AUTOMÁTICO" -ForegroundColor Yellow
Write-Host ("=" * 60) -ForegroundColor Cyan
Write-Host ""

# Obter diretório do projeto
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$projetoDir = Split-Path -Parent $scriptPath
$batPath = Join-Path $scriptPath "fazer_backup.bat"

Write-Host "[INFO] Diretório do projeto: $projetoDir" -ForegroundColor White
Write-Host "[INFO] Script de backup: $batPath" -ForegroundColor White
Write-Host ""

# Verificar se o arquivo .bat existe
if (-not (Test-Path $batPath)) {
    Write-Host "[ERRO] Arquivo fazer_backup.bat não encontrado!" -ForegroundColor Red
    Write-Host "[ERRO] Caminho esperado: $batPath" -ForegroundColor Red
    Write-Host ""
    exit 1
}

# Configurações da tarefa agendada
$taskName = "FAF_Backup_Diario"
$taskDescription = "Backup diário automático do banco de dados FAF (projeto_parcerias)"
$taskTriggerTime = "03:00" # Horário padrão: 3h da manhã

Write-Host "[INFO] Nome da tarefa: $taskName" -ForegroundColor White
Write-Host "[INFO] Horário: $taskTriggerTime (todos os dias)" -ForegroundColor White
Write-Host ""

# Verificar se já existe tarefa com este nome
$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue

if ($existingTask) {
    Write-Host "[AVISO] Já existe uma tarefa agendada com o nome '$taskName'" -ForegroundColor Yellow
    Write-Host ""
    
    $resposta = Read-Host "Deseja SUBSTITUIR a tarefa existente? (S/N)"
    
    if ($resposta -ne "S" -and $resposta -ne "s") {
        Write-Host ""
        Write-Host "[INFO] Operação cancelada pelo usuário." -ForegroundColor Yellow
        Write-Host ""
        exit 0
    }
    
    Write-Host ""
    Write-Host "[INFO] Removendo tarefa existente..." -ForegroundColor White
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "[OK] Tarefa removida." -ForegroundColor Green
    Write-Host ""
}

# Criar ação: executar o arquivo .bat
# O parâmetro "auto" evita o "pause" no final do .bat
$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$batPath`" auto" `
    -WorkingDirectory $projetoDir

# Criar gatilho: diariamente às 03:00
$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $taskTriggerTime

# Configurações adicionais
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable:$false `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1)

# Criar principal: executar com usuário atual
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType S4U `
    -RunLevel Highest

Write-Host "[INFO] Registrando tarefa agendada..." -ForegroundColor White
Write-Host ""

try {
    # Registrar tarefa
    Register-ScheduledTask `
        -TaskName $taskName `
        -Description $taskDescription `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Principal $principal `
        -ErrorAction Stop | Out-Null
    
    Write-Host ""
    Write-Host "=" -NoNewline -ForegroundColor Green
    Write-Host ("=" * 58) -ForegroundColor Green
    Write-Host "  BACKUP DIÁRIO CONFIGURADO COM SUCESSO!" -ForegroundColor Green
    Write-Host ("=" * 60) -ForegroundColor Green
    Write-Host ""
    
    Write-Host "[OK] Tarefa '$taskName' criada com sucesso!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Configurações:" -ForegroundColor White
    Write-Host "  • Frequência: Diária" -ForegroundColor White
    Write-Host "  • Horário: $taskTriggerTime" -ForegroundColor White
    Write-Host "  • Script: $batPath" -ForegroundColor White
    Write-Host "  • Usuário: $env:USERNAME" -ForegroundColor White
    Write-Host ""
    
    Write-Host "Próxima execução:" -ForegroundColor White
    $task = Get-ScheduledTask -TaskName $taskName
    $taskInfo = Get-ScheduledTaskInfo -TaskName $taskName
    
    if ($taskInfo.NextRunTime) {
        Write-Host "  " $taskInfo.NextRunTime -ForegroundColor Cyan
    } else {
        Write-Host "  Será executado amanhã às $taskTriggerTime" -ForegroundColor Cyan
    }
    Write-Host ""
    
    Write-Host "Comandos úteis:" -ForegroundColor Yellow
    Write-Host "  • Ver tarefa: " -NoNewline -ForegroundColor White
    Write-Host "taskschd.msc" -ForegroundColor Cyan
    Write-Host "  • Executar agora: " -NoNewline -ForegroundColor White
    Write-Host "Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor Cyan
    Write-Host "  • Desabilitar: " -NoNewline -ForegroundColor White
    Write-Host "Disable-ScheduledTask -TaskName '$taskName'" -ForegroundColor Cyan
    Write-Host "  • Remover: " -NoNewline -ForegroundColor White
    Write-Host "Unregister-ScheduledTask -TaskName '$taskName'" -ForegroundColor Cyan
    Write-Host ""
    
    # Perguntar se deseja executar um teste agora
    $testar = Read-Host "Deseja executar um TESTE agora? (S/N)"
    
    if ($testar -eq "S" -or $testar -eq "s") {
        Write-Host ""
        Write-Host "[INFO] Executando teste do backup..." -ForegroundColor White
        Write-Host ""
        
        Start-ScheduledTask -TaskName $taskName
        
        Write-Host "[OK] Tarefa iniciada! Aguarde a conclusão..." -ForegroundColor Green
        Write-Host "[INFO] Verifique a pasta backups\ para confirmar o arquivo gerado." -ForegroundColor White
        Write-Host ""
    }
    
} catch {
    Write-Host ""
    Write-Host "=" -NoNewline -ForegroundColor Red
    Write-Host ("=" * 58) -ForegroundColor Red
    Write-Host "  ERRO AO CRIAR TAREFA AGENDADA!" -ForegroundColor Red
    Write-Host ("=" * 60) -ForegroundColor Red
    Write-Host ""
    Write-Host "[ERRO] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "Possíveis causas:" -ForegroundColor Yellow
    Write-Host "  • PowerShell não executado como Administrador" -ForegroundColor White
    Write-Host "  • Permissões insuficientes" -ForegroundColor White
    Write-Host "  • Política de execução de scripts restritiva" -ForegroundColor White
    Write-Host ""
    Write-Host "Solução:" -ForegroundColor Yellow
    Write-Host "  1. Feche o PowerShell" -ForegroundColor White
    Write-Host "  2. Clique com botão direito no PowerShell" -ForegroundColor White
    Write-Host "  3. Selecione 'Executar como Administrador'" -ForegroundColor White
    Write-Host "  4. Execute este script novamente" -ForegroundColor White
    Write-Host ""
    exit 1
}

Write-Host "Pressione qualquer tecla para fechar..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
