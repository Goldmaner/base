# 🔄 Backup Automático do Banco de Dados FAF

Sistema de backup automático diário para o banco de dados PostgreSQL do projeto FAF.

## 📋 Arquivos

- **`fazer_backup.bat`** - Script batch para executar backup manual ou automático
- **`fazer_backup.py`** - Script Python alternativo (mais recursos)
- **`agendar_backup_diario.ps1`** - Script PowerShell para configurar agendamento automático

## 🚀 Configuração do Backup Automático (Diário)

### Pré-requisitos

1. **PostgreSQL instalado** - `pg_dump` deve estar no PATH
2. **Arquivo `.env` configurado** - Com as credenciais do banco (especialmente `DB_PASSWORD`)
3. **PowerShell como Administrador**

### Passo a Passo

#### 1️⃣ Abrir PowerShell como Administrador

- Pressione `Win + X`
- Selecione **"Windows PowerShell (Admin)"** ou **"Terminal (Admin)"**

#### 2️⃣ Navegar até a pasta do projeto

```powershell
cd "c:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF"
```

#### 3️⃣ Executar o script de agendamento

```powershell
.\backups\agendar_backup_diario.ps1
```

#### 4️⃣ Confirmar a configuração

O script irá:
- ✅ Criar uma tarefa agendada chamada `FAF_Backup_Diario`
- ✅ Configurar para executar **todos os dias às 03:00**
- ✅ Executar apenas se o computador estiver ligado
- ✅ Oferecer opção de executar um teste imediato

## 🔧 Backup Manual

### Opção 1: Arquivo .bat (Windows)

```cmd
cd "c:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF"
backups\fazer_backup.bat
```

### Opção 2: Script Python (Mais completo)

```cmd
cd "c:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF"
python backups\fazer_backup.py
```

**Vantagens do script Python:**
- ✅ Mantém apenas os 10 backups mais recentes (limpa automaticamente)
- ✅ Mostra tamanho e data de cada backup
- ✅ Mensagens de erro mais detalhadas

## 📊 Gerenciar a Tarefa Agendada

### Ver todas as tarefas agendadas

```powershell
# Abrir interface gráfica
taskschd.msc

# Ver detalhes via PowerShell
Get-ScheduledTask -TaskName "FAF_Backup_Diario" | Get-ScheduledTaskInfo
```

### Executar backup manualmente (forçar)

```powershell
Start-ScheduledTask -TaskName "FAF_Backup_Diario"
```

### Desabilitar backup automático

```powershell
Disable-ScheduledTask -TaskName "FAF_Backup_Diario"
```

### Habilitar novamente

```powershell
Enable-ScheduledTask -TaskName "FAF_Backup_Diario"
```

### Remover agendamento

```powershell
Unregister-ScheduledTask -TaskName "FAF_Backup_Diario" -Confirm:$false
```

### Alterar horário

```powershell
# Exemplo: mudar para 23:00 (11PM)
$trigger = New-ScheduledTaskTrigger -Daily -At "23:00"
Set-ScheduledTask -TaskName "FAF_Backup_Diario" -Trigger $trigger
```

## 📁 Localização dos Backups

Os backups são salvos em:
```
c:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF\backups\
```

**Formato do nome:**
```
backup_faf_YYYYMMDD_HHMMSS.sql
```

**Exemplo:**
```
backup_faf_20260213_030000.sql  (13/02/2026 às 03:00:00)
```

## 🔄 Restaurar um Backup

### Opção 1: Via comando psql

```cmd
psql -h localhost -p 5432 -U postgres -d projeto_parcerias -f "backups\backup_faf_20260213_030000.sql"
```

### Opção 2: Via pgAdmin

1. Abrir pgAdmin
2. Selecionar o banco `projeto_parcerias`
3. Botão direito → **Restore**
4. Selecionar o arquivo `.sql`
5. Clicar em **Restore**

## ⚠️ Solução de Problemas

### Erro: "pg_dump não encontrado"

**Solução:** Adicionar PostgreSQL ao PATH

1. Encontre o diretório `bin` do PostgreSQL (ex: `C:\Program Files\PostgreSQL\17\bin`)
2. Adicione ao PATH do Windows:
   - Painel de Controle → Sistema → Configurações avançadas do sistema
   - Variáveis de Ambiente → PATH → Editar
   - Adicionar o caminho do PostgreSQL\bin

### Erro: "senha incorreta" ou "autenticação falhou"

**Solução:** Verificar arquivo `.env`

O arquivo `.env` na raiz do projeto deve conter:
```env
DB_PASSWORD=sua_senha_aqui
DB_HOST=localhost
DB_PORT=5432
DB_DATABASE=projeto_parcerias
DB_USER=postgres
```

### Tarefa não executa automaticamente

**Possíveis causas:**
1. Computador desligado no horário agendado
2. Tarefa desabilitada
3. Credenciais inválidas

**Verificar status:**
```powershell
Get-ScheduledTaskInfo -TaskName "FAF_Backup_Diario"
```

### Ver histórico de execução

1. Abrir `taskschd.msc`
2. Localizar tarefa `FAF_Backup_Diario`
3. Aba **"Histórico"**

Ou via PowerShell:
```powershell
Get-WinEvent -LogName "Microsoft-Windows-TaskScheduler/Operational" -MaxEvents 50 | 
    Where-Object { $_.Message -like "*FAF_Backup_Diario*" }
```

## 🔒 Segurança

- ⚠️ **NUNCA** commitar arquivos `.sql` no Git (já configurado no `.gitignore`)
- ⚠️ **NUNCA** compartilhar backups publicamente (contêm dados sensíveis)
- ✅ Backups locais são armazenados apenas na máquina
- ✅ A senha do banco é lida do `.env` (não hardcoded)

## 📝 Retenção de Backups

### Script Python (.py)
- Mantém automaticamente os **10 backups mais recentes**
- Deleta backups antigos automaticamente

### Script Batch (.bat)
- **Não** deleta backups antigos automaticamente
- Gerenciar manualmente ou usar script Python

### Limpar backups antigos manualmente

```powershell
# Manter apenas últimos 10 backups
cd "c:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF\backups"
Get-ChildItem backup_faf_*.sql | 
    Sort-Object LastWriteTime -Descending | 
    Select-Object -Skip 10 | 
    Remove-Item
```

## ✅ Verificação de Funcionamento

### Teste completo do sistema

```powershell
# 1. Executar backup manual
.\backups\fazer_backup.bat

# 2. Verificar se arquivo foi criado
dir backups\backup_faf_*.sql

# 3. Executar tarefa agendada manualmente
Start-ScheduledTask -TaskName "FAF_Backup_Diario"

# 4. Verificar próxima execução
Get-ScheduledTaskInfo -TaskName "FAF_Backup_Diario" | Select-Object NextRunTime
```

## 🆘 Suporte

Se ainda tiver problemas:

1. Verificar logs da tarefa agendada no Event Viewer
2. Testar backup manual primeiro (`.bat` ou `.py`)
3. Confirmar que PostgreSQL está acessível
4. Verificar permissões de escrita na pasta `backups\`

---

**Última atualização:** 13/02/2026  
**Autor:** Sistema FAF
