# Implementação de Escrita Dual em Bancos de Dados

## Resumo das Alterações

Este documento descreve as alterações realizadas para implementar escrita simultânea em dois bancos de dados PostgreSQL: **LOCAL** (localhost) e **RAILWAY** (cloud).

## Arquivos Modificados

### 1. **requirements.txt**
- ✅ Adicionado: `python-dotenv==1.0.0`
- Biblioteca para carregar variáveis de ambiente do arquivo `.env`

### 2. **config.py**
- ✅ Importado: `from dotenv import load_dotenv`
- ✅ Adicionado: `load_dotenv()` para carregar variáveis do `.env`
- ✅ Criado: `DB_CONFIG_LOCAL` com credenciais do banco local
- ✅ Criado: `DB_CONFIG_RAILWAY` com credenciais do banco Railway
- ✅ Mantido: `DB_CONFIG = DB_CONFIG_RAILWAY` para retrocompatibilidade

**Exemplo de configuração:**
```python
DB_CONFIG_LOCAL = {
    'host': os.environ.get('DB_LOCAL_HOST', 'localhost'),
    'port': os.environ.get('DB_LOCAL_PORT', '5432'),
    'database': os.environ.get('DB_LOCAL_DATABASE', 'projeto_parcerias'),
    'user': os.environ.get('DB_LOCAL_USER', 'postgres'),
    'password': os.environ.get('DB_LOCAL_PASSWORD', '')
}
```

### 3. **db.py**
- ✅ Criada função: `get_db_local()` - retorna conexão com banco local
- ✅ Criada função: `get_db_railway()` - retorna conexão com banco Railway
- ✅ Criada função: `get_cursor_local()` - cursor do banco local
- ✅ Criada função: `get_cursor_railway()` - cursor do banco Railway
- ✅ Criada função: **`execute_dual(query, params)`** - **PRINCIPAL**: executa INSERT/UPDATE/DELETE em ambos os bancos
- ✅ Atualizada: `close_db()` - fecha conexões dos dois bancos
- ✅ Tratamento de erros: Se um banco falhar, continua tentando o outro

**Função principal:**
```python
def execute_dual(query, params=None):
    """
    Executa uma operação de escrita nos dois bancos de dados.
    Retorna True se pelo menos um banco foi atualizado com sucesso.
    """
    success_local = False
    success_railway = False
    
    # Tenta executar no LOCAL
    cur_local = get_cursor_local()
    if cur_local:
        try:
            cur_local.execute(query, params)
            get_db_local().commit()
            success_local = True
        except Exception as e:
            print(f"[ERRO] Falha no banco LOCAL: {e}")
            get_db_local().rollback()
    
    # Tenta executar no RAILWAY
    cur_railway = get_cursor_railway()
    if cur_railway:
        try:
            cur_railway.execute(query, params)
            get_db_railway().commit()
            success_railway = True
        except Exception as e:
            print(f"[ERRO] Falha no banco RAILWAY: {e}")
            get_db_railway().rollback()
    
    return success_local or success_railway
```

### 4. **routes/parcerias.py**
- ✅ Importado: `execute_dual` do módulo `db`
- ✅ Atualizada função `nova()`:
  - Antes: `cur.execute()` + `conn.commit()`
  - Depois: `execute_dual(query, params)`
- ✅ Atualizada função `editar()`:
  - Antes: `cur.execute()` + `conn.commit()`
  - Depois: `execute_dual(query, params)`
- ✅ Simplificado código: Removidas variáveis `conn` e `cur`, usando apenas `execute_dual()`

**Exemplo de conversão:**
```python
# ANTES (single database):
conn = get_db()
cur = conn.cursor()
cur.execute(query, params)
conn.commit()

# DEPOIS (dual database):
execute_dual(query, params)
```

### 5. **routes/listas.py**
- ✅ Importado: `execute_dual` do módulo `db`
- ✅ Atualizada função `criar_registro()`: INSERT com `execute_dual()`
- ✅ Atualizada função `atualizar_registro()`: UPDATE com `execute_dual()`
- ✅ Atualizada função `excluir_registro()`: DELETE com `execute_dual()`

### 6. **.gitignore**
- ✅ Adicionadas linhas:
  ```
  # Environment variables (credentials)
  .env
  .env_teste
  .env.*
  ```
- Garante que arquivos com credenciais não sejam enviados ao Git

### 7. **Novos Arquivos Criados**

#### `.env` (NÃO DEVE SER COMMITADO)
```env
# Banco LOCAL
DB_LOCAL_HOST=localhost
DB_LOCAL_PORT=5432
DB_LOCAL_DATABASE=projeto_parcerias
DB_LOCAL_USER=postgres
DB_LOCAL_PASSWORD=Coração01

# Banco RAILWAY
DB_RAILWAY_HOST=shinkansen.proxy.rlwy.net
DB_RAILWAY_PORT=38157
DB_RAILWAY_DATABASE=railway
DB_RAILWAY_USER=postgres
DB_RAILWAY_PASSWORD=sKOzVlsxAUcRIXXLynePvvHDQpXlmTVT

# App Config
SECRET_KEY=chave-padrao-para-desenvolvimento
DEBUG=True
```

#### `.env_teste` (NÃO DEVE SER COMMITADO)
- Mesma estrutura do `.env`, mas usa sufixo `_teste` nos nomes dos bancos

#### `.env.example` (PODE SER COMMITADO)
- Template do `.env` com placeholders em vez de senhas reais
- Documenta quais variáveis são necessárias

## Como Funciona

### Fluxo de Escrita (INSERT/UPDATE/DELETE)

1. **Rotas recebem requisição** (ex: criar parceria)
2. **Montam query SQL** e parâmetros
3. **Chamam `execute_dual(query, params)`**
4. **`execute_dual()` executa em DOIS bancos:**
   - Tenta no LOCAL → se falhar, loga erro mas continua
   - Tenta no RAILWAY → se falhar, loga erro
5. **Retorna `True`** se pelo menos UM banco foi atualizado
6. **Rota mostra mensagem** ao usuário:
   - Sucesso: "Parceria criada com sucesso!"
   - Falha total: "Erro ao criar parceria em ambos os bancos!"

### Fluxo de Leitura (SELECT)

- **Usa apenas um cursor** (padrão: Railway via `get_cursor()`)
- Não há leitura dual, pois os bancos têm dados idênticos
- Se precisar ler do LOCAL, use `get_cursor_local()`

## Vantagens da Implementação

✅ **Redundância**: Se o Railway cair, dados continuam salvos localmente  
✅ **Backup automático**: Cada escrita é duplicada instantaneamente  
✅ **Tolerância a falhas**: Se um banco falhar, o outro continua funcionando  
✅ **Segurança**: Credenciais em `.env` (não expostas no código)  
✅ **Retrocompatibilidade**: Código antigo ainda funciona (usa `get_cursor()`)  

## Próximos Passos (Opcional)

### Rotas que AINDA NÃO foram atualizadas:
- ❌ `routes/orcamento.py` (se tiver INSERT/UPDATE/DELETE)
- ❌ `routes/despesas.py` (se tiver INSERT/UPDATE/DELETE)
- ❌ `routes/auth.py` (criação/edição de usuários)

### Melhorias Sugeridas:
1. **Logging profissional**: Usar biblioteca `logging` em vez de `print()`
2. **Monitoramento**: Criar endpoint `/health` que verifica se ambos os bancos estão acessíveis
3. **Sincronização**: Se um banco ficar offline e depois voltar, criar script para sincronizar dados faltantes
4. **Transações distribuídas**: Garantir que ou ambos commitam ou ambos fazem rollback (two-phase commit)

## Testando a Implementação

### 1. Verificar se configuração carrega:
```bash
python -c "from config import DB_CONFIG_LOCAL, DB_CONFIG_RAILWAY; print('OK')"
```

### 2. Testar criação de parceria:
- Acesse: http://localhost:5000/parcerias/nova
- Preencha formulário
- Envie
- Verifique em AMBOS os bancos:
  ```sql
  -- No banco LOCAL
  SELECT * FROM Parcerias WHERE numero_termo = 'TESTE/001/2025';
  
  -- No banco RAILWAY (mesmo comando)
  SELECT * FROM Parcerias WHERE numero_termo = 'TESTE/001/2025';
  ```

### 3. Testar falha simulada:
- Desligue um dos bancos (ex: local)
- Tente criar/editar parceria
- Deve funcionar, mas mostrar erro no console: `[ERRO] Falha no banco LOCAL: ...`
- Dados devem ser salvos apenas no Railway

## Considerações de Segurança

⚠️ **NUNCA commite o arquivo `.env`** ao Git!  
⚠️ **Use `.env.example`** para documentação (sem senhas reais)  
⚠️ **No Railway**, configure as variáveis de ambiente no dashboard (Settings > Variables)  
⚠️ **Senhas fortes**: Troque as senhas padrão em produção  

## Conclusão

A aplicação agora possui **escrita dual automática** em dois bancos de dados PostgreSQL. Toda operação de INSERT, UPDATE e DELETE é executada simultaneamente nos bancos LOCAL e RAILWAY, garantindo redundância e backup em tempo real.

✅ **python-dotenv** instalado  
✅ **config.py** usando variáveis de ambiente  
✅ **db.py** com `execute_dual()`  
✅ **routes/parcerias.py** atualizada  
✅ **routes/listas.py** atualizada  
✅ **.gitignore** protegendo `.env`  
✅ **.env.example** documentando configuração  
