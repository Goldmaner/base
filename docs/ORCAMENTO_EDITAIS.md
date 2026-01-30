# 📊 Orçamento de Editais - Documentação

## 🎯 Visão Geral

Nova funcionalidade para gerenciar o **cronograma orçamentário** de editais, permitindo o planejamento de repasses mensais por edital.

---

## 🗄️ Estrutura do Banco de Dados

### Tabela: `gestao_financeira.orcamento_edital_nova`

```sql
CREATE TABLE gestao_financeira.orcamento_edital_nova (
    id SERIAL PRIMARY KEY,
    edital_nome         VARCHAR(60),
    edital_tipo         VARCHAR(30),
    edital_unidade      VARCHAR(20),
    dotacao_formatada   VARCHAR(120),
    projeto_atividade   VARCHAR(10),
    valor_mes           NUMERIC(18,2),
    nome_mes            DATE,
    Etapa               VARCHAR(70),
    Observacoes         TEXT,
    created_por         VARCHAR(80),
    created_em          TIMESTAMP WITHOUT TIME ZONE DEFAULT now()
);
```

### 📝 Lógica de Armazenamento

- **Múltiplas linhas por edital**: Cada mês do cronograma é armazenado como uma linha separada
- **Visualização consolidada**: Na interface, cada edital aparece como uma única linha com:
  - **Valor Total**: Soma de todos os `valor_mes`
  - **Vigência**: Período do primeiro ao último mês (ex: "jan/26-dez/27 (24 meses)")

---

## 🔗 Rotas Criadas

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/editais/orcamento` | Lista todos os orçamentos (consolidado) |
| POST | `/editais/orcamento/criar` | Cria novo orçamento com cronograma |
| POST | `/editais/orcamento/editar/<edital_nome>` | Edita orçamento existente |
| POST | `/editais/orcamento/deletar/<edital_nome>` | Deleta todas as linhas do edital |
| GET | `/editais/orcamento/api/dotacoes?unidade=X` | Retorna dotações por unidade |
| GET | `/editais/orcamento/api/edital/<edital_nome>` | Retorna detalhes completos (todos os meses) |

---

## 📋 Campos do Formulário

### 1. **Nome do Edital** (obrigatório)
- Campo: `edital_nome`
- Tipo: Texto livre
- Validação: Único (não permite duplicatas)

### 2. **Tipo de Edital**
- Campo: `edital_tipo`
- Tipo: Lista suspensa
- Opções:
  - `-` (padrão)
  - Chamamento Público
  - Credenciamento
  - Dispensa de Chamamento Público

### 3. **Unidade** (obrigatório)
- Campo: `edital_unidade`
- Tipo: Lista suspensa
- Fonte: `categoricas.c_geral_dotacoes.coordenacao`
- Ação: Ao selecionar, carrega as dotações disponíveis

### 4. **Dotação Orçamentária** (obrigatório)
- Campo: `dotacao_formatada`
- Tipo: Lista suspensa (dinâmica)
- Fonte: `categoricas.c_geral_dotacoes.dotacao_numero` filtrado por unidade
- Exemplo: `78.10.08.605.3016.4.302.33503900.00.1.500.9001.1`

### 5. **Projeto-Atividade** (auto-preenchido)
- Campo: `projeto_atividade`
- Tipo: Somente leitura
- Lógica: Extraído da dotação formatada
  - Posição 5 + `.` + Posição 6 após split por `.`
  - Exemplo: `78.10.08.605.3016.4.302...` → `4.302`

### 6. **Etapa**
- Campo: `Etapa`
- Tipo: Lista suspensa
- Opções:
  - Em estudo preliminar (padrão)
  - Iniciado
  - Cancelado

### 7. **Observações**
- Campo: `Observacoes`
- Tipo: Textarea

### 8. **Cronograma de Repasses Mensais**
- Campos: `valor_mes` + `nome_mes`
- Tipo: Tabela dinâmica
- Funcionalidades:
  - ➕ **Adicionar Mês**: Cria nova linha (primeiro mês = mês atual)
  - 🗑️ **Remover Mês**: Deleta linha específica
  - 📅 **Mês/Ano**: Input type="month" (ex: jan/26)
  - 💰 **Valor**: Input type="number" (ex: 50000.00)
  - 📊 **Total**: Soma automática de todos os valores

---

## 🎨 Interface

### Tabela Principal

| Coluna | Descrição | Exemplo |
|--------|-----------|---------|
| Nome do Edital | Nome cadastrado | Edital Esporte 2026 |
| Tipo | Tipo do edital | Chamamento Público |
| Unidade | Coordenação | SESANA |
| Dotação Orçamentária | Código completo | 78.10.08.605.3016.4.302... |
| Projeto-Atividade | Código extraído | 4.302 |
| Valor Total | Soma dos meses | R$ 1.200.000,00 |
| Vigência | Período | jan/26-dez/27 (24 meses) |
| Etapa | Status atual | Em estudo preliminar |
| Observações | Texto resumido | Edital para projetos... |
| Criado por | Usuário | usuario@exemplo.com |
| Ações | Editar/Deletar | 🖊️ 🗑️ |

### Badges de Etapa

| Etapa | Cor | Ícone |
|-------|-----|-------|
| Em estudo preliminar | Amarelo (warning) | ⚠️ |
| Iniciado | Verde (success) | ✅ |
| Cancelado | Vermelho (danger) | ❌ |

---

## 🔄 Fluxo de Operações

### Criar Orçamento
1. Usuário clica em **"Cadastrar Orçamento"**
2. Modal abre com formulário vazio
3. Seleciona **Unidade** → Carrega dotações automaticamente
4. Seleciona **Dotação** → Projeto-Atividade preenchido automaticamente
5. Adiciona meses no cronograma (botão "Adicionar Mês")
6. Preenche valores para cada mês
7. Clica em **"Cadastrar"**
8. Sistema:
   - Valida nome único
   - Valida pelo menos 1 mês no cronograma
   - Insere **N linhas** (uma por mês) no banco
   - Identifica usuário via `session['username']`

### Editar Orçamento
1. Usuário clica em **"Editar"** (ícone 🖊️)
2. Sistema busca **todas as linhas** do edital
3. Modal carrega:
   - Dados gerais (nome, tipo, unidade, etc.)
   - Cronograma completo (todos os meses)
4. Usuário pode:
   - Alterar dados gerais
   - Adicionar novos meses
   - Remover meses existentes
   - Alterar valores
5. Clica em **"Salvar Alterações"**
6. Sistema:
   - **DELETA** todas as linhas antigas do edital
   - **INSERE** novas linhas com dados atualizados

### Deletar Orçamento
1. Usuário clica em **"Excluir"** (ícone 🗑️)
2. Confirmação: "Todas as linhas do cronograma serão excluídas"
3. Se confirmar:
   - Sistema **DELETA** todas as linhas do edital

---

## 🔒 Segurança e Auditoria

- **Autenticação**: `@login_required`
- **Autorização**: `@requires_access('editais')`
- **Auditoria**: Campo `created_por` registra usuário via `session['username']`
- **Timestamp**: Campo `created_em` registra data/hora automaticamente

---

## 📊 Query de Consolidação

```sql
SELECT 
    edital_nome,
    edital_tipo,
    edital_unidade,
    dotacao_formatada,
    projeto_atividade,
    Etapa,
    Observacoes,
    MIN(nome_mes) as vigencia_inicio,
    MAX(nome_mes) as vigencia_fim,
    SUM(valor_mes) as valor_total,
    COUNT(*) as qtd_meses,
    created_por,
    MAX(created_em) as ultima_atualizacao
FROM gestao_financeira.orcamento_edital_nova
GROUP BY edital_nome, edital_tipo, edital_unidade, dotacao_formatada, 
         projeto_atividade, Etapa, Observacoes, created_por
ORDER BY ultima_atualizacao DESC
```

---

## 🎯 Exemplo de Uso

### Cenário: Edital de Esporte 2026

**Dados Gerais:**
- Nome: Edital Esporte e Lazer 2026
- Tipo: Chamamento Público
- Unidade: SESANA
- Dotação: 78.10.08.605.3016.4.302.33503900.00.1.500.9001.1
- Projeto-Atividade: 4.302 (auto-preenchido)
- Etapa: Em estudo preliminar
- Observações: Edital para fomento de projetos esportivos

**Cronograma:**
| Mês | Valor |
|-----|-------|
| jan/26 | R$ 50.000,00 |
| fev/26 | R$ 50.000,00 |
| mar/26 | R$ 50.000,00 |
| abr/26 | R$ 50.000,00 |
| mai/26 | R$ 50.000,00 |
| jun/26 | R$ 50.000,00 |
| **TOTAL** | **R$ 300.000,00** |

**Resultado no Banco:**
- 6 linhas inseridas (uma por mês)
- Todas com `edital_nome = "Edital Esporte e Lazer 2026"`
- Cada linha com `valor_mes` e `nome_mes` específicos

**Visualização na Interface:**
- 1 linha na tabela
- Valor Total: R$ 300.000,00
- Vigência: jan/26-jun/26 (6 meses)

---

## ✅ Validações Implementadas

1. ✅ Nome do edital obrigatório
2. ✅ Unidade obrigatória
3. ✅ Dotação orçamentária obrigatória
4. ✅ Pelo menos 1 mês no cronograma
5. ✅ Nome do edital único (não permite duplicatas)
6. ✅ Valores numéricos positivos
7. ✅ Datas válidas (formato YYYY-MM-DD)

---

## 🚀 Acesso

1. Menu principal → **Gestão de Editais**
2. Botão azul → **"Orçamento de Editais"**
3. Interface dedicada com CRUD completo

---

## 📝 Observações Técnicas

- **Frontend**: Bootstrap 5.3.0 + JavaScript vanilla
- **Backend**: Flask Blueprint (routes/editais.py)
- **Banco de Dados**: PostgreSQL
- **JSON**: Comunicação via `meses_data` (campo hidden) para enviar cronograma
- **AJAX**: Carregamento dinâmico de dotações e detalhes do edital

---

## 🐛 Tratamento de Erros

- Flash messages para feedback ao usuário
- Try/catch em todas as rotas
- Rollback automático em caso de erro
- Logs detalhados no console (`print` + `traceback`)

---

## 🎨 Cores da Interface

- **Header**: Gradiente roxo (#6f42c1 → #5a32a3)
- **Botão Criar**: Verde (success)
- **Botão Editar**: Amarelo (warning)
- **Botão Deletar**: Vermelho (danger)
- **Badge "Em estudo"**: Amarelo
- **Badge "Iniciado"**: Verde
- **Badge "Cancelado"**: Vermelho
- **Valor Total**: Verde (#198754) com fonte Courier New

---

## 📞 Suporte

Desenvolvido para o sistema FAF - Fundação de Apoio à Faculdade.
Para dúvidas ou sugestões, consulte a equipe de desenvolvimento.
