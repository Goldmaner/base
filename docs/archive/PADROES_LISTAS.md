# Padrões e Regras para Listas Suspensas (Tabelas Categóricas)

**Versão:** 1.0  
**Data:** 13/02/2026  
**Sistema:** FAF (Fundo de Apoio ao Fomento)

---

## 📋 Índice

1. [Visão Geral](#visão-geral)
2. [Estrutura de Tabelas no Banco de Dados](#estrutura-de-tabelas-no-banco-de-dados)
3. [Configuração no Backend](#configuração-no-backend)
4. [Tipos de Campos Suportados](#tipos-de-campos-suportados)
5. [Funcionalidades Opcionais](#funcionalidades-opcionais)
6. [Convenções de Nomenclatura](#convenções-de-nomenclatura)
7. [Exemplos Práticos](#exemplos-práticos)
8. [Checklist para Nova Lista](#checklist-para-nova-lista)

---

## 🎯 Visão Geral

As **Listas Suspensas** são tabelas categóricas que armazenam dados de referência utilizados em todo o sistema. Elas são gerenciadas através de uma interface unificada (`/listas`) que permite:

- ✅ Criar, editar e excluir registros
- 🔍 Filtrar e ordenar dados
- ⚡ Edição inline (para campos simples)
- 🔢 Reordenação manual (quando aplicável)
- 📊 Colunas calculadas (quando necessário)

**Arquivo Frontend:** `templates/listas.html`  
**Arquivo Backend:** `routes/listas.py`  
**Schema Padrão:** `categoricas`

---

## 🗄️ Estrutura de Tabelas no Banco de Dados

### Estrutura Mínima Obrigatória

Toda tabela categórica **DEVE** ter:

```sql
CREATE TABLE categoricas.c_[prefixo]_[nome_tabela] (
    id SERIAL PRIMARY KEY,          -- Obrigatório: chave primária auto-incremento
    -- [colunas específicas da tabela]
    created_por TEXT                -- Obrigatório: auditoria de criação
);
```

### Estrutura Recomendada (com Auditoria Completa)

```sql
CREATE TABLE categoricas.c_[prefixo]_[nome_tabela] (
    id SERIAL PRIMARY KEY,
    -- [colunas específicas da tabela]
    created_por TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_por TEXT,
    updated_at TIMESTAMP
);
```

### Convenções para Colunas Comuns

| Coluna | Tipo | Descrição | Padrão |
|--------|------|-----------|--------|
| `id` | `SERIAL PRIMARY KEY` | Identificador único | Obrigatório |
| `created_por` | `TEXT` | RF do usuário criador | Obrigatório |
| `created_at` | `TIMESTAMP` | Data/hora de criação | Recomendado |
| `updated_por` | `TEXT` | RF do último editor | Recomendado |
| `updated_at` | `TIMESTAMP` | Data/hora de última atualização | Recomendado |
| `ordem` | `INTEGER` | Ordem customizada | Opcional (se `permite_reordenar: true`) |

### Convenções para Campos de Status

| Campo | Tipo | Valores Típicos |
|-------|------|-----------------|
| `status` | `VARCHAR(20)` | 'Ativo', 'Inativo' |
| `status_pg` | `VARCHAR(20)` | 'Ativo', 'Inativo', 'Desconhecido' |
| `status_c` | `VARCHAR(20)` | 'Ativo', 'Afastado', 'Inativo' |
| `status_tipo_doc` | `VARCHAR(20)` | 'Ativo', 'Inativo', 'Em Desuso' |

### Prefixos de Nomenclatura

| Prefixo | Significado | Exemplo |
|---------|-------------|---------|
| `c_dac_` | Divisão de Análise e Contabilidade | `c_dac_analistas` |
| `c_dgp_` | Divisão de Gestão de Parcerias | `c_dgp_analistas` |
| `c_dp_` | Divisão de Planejamento | `c_dp_status_edital` |
| `c_geral_` | Dados gerais (multi-divisão) | `c_geral_pessoa_gestora` |

---

## ⚙️ Configuração no Backend

A configuração de cada lista é feita no dicionário `TABELAS_CONFIG` em `routes/listas.py`.

### Estrutura Básica de Configuração

```python
'nome_da_tabela': {
    'nome': 'Nome Amigável da Tabela',              # Exibido no frontend
    'schema': 'categoricas',                         # Schema do banco (padrão: categoricas)
    'colunas_editaveis': ['coluna1', 'coluna2'],    # Colunas que o usuário pode editar
    'labels': {                                      # Labels amigáveis para cada coluna
        'coluna1': 'Nome da Coluna 1',
        'coluna2': 'Nome da Coluna 2'
    },
    'ordem': 'coluna1'                              # Ordenação padrão (SQL ORDER BY)
}
```

### Propriedades de Configuração Disponíveis

#### Propriedades Obrigatórias

| Propriedade | Tipo | Descrição |
|-------------|------|-----------|
| `nome` | `str` | Nome amigável exibido no dropdown e cabeçalho |
| `schema` | `str` | Schema do banco de dados (geralmente `'categoricas'`) |
| `colunas_editaveis` | `list` | Lista de colunas que podem ser criadas/editadas |
| `labels` | `dict` | Mapeamento `coluna: label` para exibição |
| `ordem` | `str` | Cláusula SQL ORDER BY (ex: `'nome'`, `'ordem NULLS LAST, nome'`) |

#### Propriedades Opcionais

| Propriedade | Tipo | Descrição | Exemplo |
|-------------|------|-----------|---------|
| `colunas_obrigatorias` | `list` | Colunas que não podem ser vazias | `['tipo_doc']` |
| `colunas_filtro` | `list` | Colunas com ícone de filtro | `['status', 'tipo']` |
| `colunas_ordenacao` | `list` | Colunas com ícone de ordenação | `['nome', 'setor']` |
| `colunas_calculadas` | `list` | Colunas computadas (não editáveis) | `['total_pareceres']` |
| `tipos_campo` | `dict` | Configuração de tipos de campos (ver seção específica) | Ver abaixo |
| `inline_edit` | `bool` | Habilita edição inline | `true` |
| `inline_columns` | `list` | Colunas editáveis inline (requer `inline_edit: true`) | `['status']` |
| `permite_reordenar` | `bool` | Adiciona botões ↑↓ para reordenar | `true` |

---

## 🎨 Tipos de Campos Suportados

A propriedade `tipos_campo` define como cada coluna será renderizada no formulário.

### 1. Campo de Texto Simples (`text`)

**Uso:** Campo de entrada de texto livre.

```python
'tipos_campo': {
    'tipo_doc': 'text'
}
```

**Frontend:** `<input type="text">`

---

### 2. Área de Texto (`textarea`)

**Uso:** Campo para textos longos/múltiplas linhas.

```python
'tipos_campo': {
    'descricao': 'textarea',
    'rows_descricao': 5  # Opcional: altura em linhas (padrão: 3)
}
```

**Frontend:** `<textarea rows="5">`

**Convenção:** Use `rows_[nome_campo]` para definir altura customizada.

---

### 3. Select Fixo (`select`)

**Uso:** Dropdown com opções pré-definidas.

```python
'tipos_campo': {
    'status_tipo_doc': 'select',
    'opcoes_status_tipo_doc': ['Ativo', 'Inativo', 'Em Desuso']
}
```

**Frontend:** `<select><option>...</select>`

**Convenção:** Use `opcoes_[nome_campo]` para listar as opções.

---

### 4. Select Dinâmico (`select_dinamico`)

**Uso:** Dropdown com valores vindos de query SQL (valores únicos existentes).

```python
'tipos_campo': {
    'setor': 'select_dinamico',
    'query_setor': 'SELECT DISTINCT setor FROM categoricas.c_geral_pessoa_gestora WHERE setor IS NOT NULL ORDER BY setor'
}
```

**Frontend:** `<select>` preenchido com resultados da query.

**Convenção:** Use `query_[nome_campo]` para a consulta SQL.

---

### 5. Texto com Datalist (`text_com_datalist`)

**Uso:** Input com auto-complete (permite valores novos).

```python
'tipos_campo': {
    'coordenacao': 'text_com_datalist',
    'query_coordenacao': 'SELECT DISTINCT coordenacao FROM categoricas.c_geral_coordenadores WHERE coordenacao IS NOT NULL ORDER BY coordenacao'
}
```

**Frontend:** `<input type="text" list="datalist_coordenacao">`

**Diferença:** Diferente do `select_dinamico`, permite entrada de novos valores.

---

### 6. Checkbox Simples (`checkbox`)

**Uso:** Campo booleano (true/false).

```python
'tipos_campo': {
    'aplicacao': 'checkbox'
}
```

**Frontend:** `<input type="checkbox">`

**Valor no Banco:** `boolean` ou `VARCHAR` ('true'/'false')

---

### 7. Checkbox Múltiplo (`checkbox_multiple`)

**Uso:** Múltiplas seleções armazenadas como string separada por `;`.

```python
'tipos_campo': {
    'areas_atuacao': 'checkbox_multiple',
    'opcoes_areas_atuacao': ['Saúde', 'Educação', 'Cultura', 'Esporte']
}
```

**Valor no Banco:** `TEXT` (ex: `'Saúde;Educação'`)

---

### 8. Campo de Data (`date`)

**Uso:** Seleção de data.

```python
'tipos_campo': {
    'data_inicio': 'date'
}
```

**Frontend:** `<input type="date">`

**Formato no Banco:** `DATE` (YYYY-MM-DD)

---

### 9. Campo Numérico (`number`)

**Uso:** Apenas números.

```python
'tipos_campo': {
    'ordem': 'number'
}
```

**Frontend:** `<input type="number">`

---

## 🎛️ Funcionalidades Opcionais

### Edição Inline

Permite editar campos diretamente na tabela sem abrir modal.

**Configuração:**
```python
'inline_edit': True,
'inline_columns': ['status']  # Colunas editáveis inline
```

**Comportamento:**
- Adiciona checkbox de seleção em cada linha
- Exibe botão "💾 Salvar" individual por linha
- Exibe botão "💾 Salvar Todos" global (aparece quando há alterações)
- Linha fica amarela quando alterada (classe `table-warning`)

**Restrições:**
- Ideal para campos simples (status, flags, selects)
- Não recomendado para textarea ou campos complexos

---

### Reordenação Manual

Permite reorganizar linhas com botões ↑/↓.

**Configuração:**
```python
'permite_reordenar': True
```

**Requisitos no Banco:**
- Tabela DEVE ter coluna `ordem INTEGER`

**Comportamento:**
- Adiciona botões "↑" e "↓" na coluna de ações
- Atualiza campo `ordem` automaticamente
- Ordenação padrão deve incluir `ordem NULLS LAST`

**Exemplo de ordem SQL:**
```python
'ordem': 'ordem NULLS LAST, nome_item'
```

---

### Filtros por Coluna

Adiciona ícone 🔍 no cabeçalho para filtrar valores.

**Configuração:**
```python
'colunas_filtro': ['tipo_doc', 'status_tipo_doc']
```

**Comportamento:**
- Campos de status: exibe prompt com opções pré-definidas
- Outros campos: permite busca por texto parcial
- Exibe botão "Limpar Filtros" quando ativo

---

### Ordenação por Coluna

Adiciona ícone de ordenação no cabeçalho (clique para alternar ASC/DESC).

**Configuração:**
```python
'colunas_ordenacao': ['tipo_doc', 'descricao']
```

**Comportamento:**
- Clique no ícone alterna entre crescente ⬆️ e decrescente ⬇️
- Ordenação por texto usa `localeCompare()`
- Ordenação por número usa subtração numérica

---

### Colunas Calculadas

Exibe valores computados que não são editáveis.

**Configuração:**
```python
'colunas_calculadas': ['total_pareceres', 'total_parcerias']
```

**Requisitos:**
- Backend deve retornar esses valores na query SELECT

**Exemplo de Query:**
```python
SELECT 
    pg.*, 
    COUNT(DISTINCT ap.id) AS total_pareceres,
    COUNT(DISTINCT p.id) AS total_parcerias
FROM categoricas.c_geral_pessoa_gestora pg
LEFT JOIN analises_pareceres ap ON ap.pessoa_gestora = pg.nome_pg
LEFT JOIN parcerias p ON p.pessoa_gestora = pg.nome_pg
GROUP BY pg.id
```

---

## 📐 Convenções de Nomenclatura

### Tabelas

**Padrão:** `c_[prefixo]_[nome_descritivo]`

- ✅ `c_geral_tipos_doc_sei`
- ✅ `c_dac_modelo_textos_inconsistencias`
- ❌ `tipos_documento` (falta prefixo c_)
- ❌ `c_tiposdoc` (falta prefixo de divisão)

### Colunas

**Convenções:**

| Tipo de Dado | Padrão de Nome | Exemplo |
|--------------|----------------|---------|
| Nome de pessoa | `nome_[sufixo]` | `nome_pg`, `nome_analista`, `nome_c` |
| Status | `status_[sufixo]` | `status_pg`, `status_c`, `status_tipo_doc` |
| E-mail | `email_[sufixo]` ou `e_mail_[sufixo]` | `email_pg`, `e_mail_c` |
| RF (Registro Funcional) | `rf_[sufixo]` ou `numero_rf` | `rf_c`, `numero_rf` |
| Descrições | `descricao` ou `[contexto]_descricao` | `descricao`, `tipo_descricao` |
| Tipo/Categoria | `tipo_[contexto]` | `tipo_doc`, `tipo_transacao` |

---

## 📝 Exemplos Práticos

### Exemplo 1: Lista Simples (Somente CRUD Básico)

```python
'c_geral_origem_recurso': {
    'nome': 'Geral: Origens de Recurso',
    'schema': 'categoricas',
    'colunas_editaveis': ['orgao', 'unidade', 'descricao'],
    'labels': {
        'orgao': 'Órgão',
        'unidade': 'Unidade',
        'descricao': 'Descrição'
    },
    'ordem': 'orgao, unidade'
}
```

**SQL da Tabela:**
```sql
CREATE TABLE categoricas.c_geral_origem_recurso (
    id SERIAL PRIMARY KEY,
    orgao VARCHAR(100),
    unidade VARCHAR(100),
    descricao TEXT,
    created_por TEXT
);
```

---

### Exemplo 2: Lista com Filtros e Selects

```python
'c_geral_tipos_doc_sei': {
    'nome': 'Geral: Tipos de Documento SEI',
    'schema': 'categoricas',
    'colunas_editaveis': ['tipo_doc', 'descricao', 'status_tipo_doc'],
    'colunas_obrigatorias': ['tipo_doc'],
    'labels': {
        'tipo_doc': 'Tipo de Documento',
        'descricao': 'Descrição',
        'status_tipo_doc': 'Status'
    },
    'colunas_filtro': ['tipo_doc', 'status_tipo_doc'],
    'colunas_ordenacao': ['tipo_doc'],
    'ordem': 'tipo_doc',
    'tipos_campo': {
        'tipo_doc': 'text',
        'descricao': 'textarea',
        'rows_descricao': 3,
        'status_tipo_doc': 'select',
        'opcoes_status_tipo_doc': ['Ativo', 'Inativo', 'Em Desuso']
    }
}
```

**SQL da Tabela:**
```sql
CREATE TABLE categoricas.c_geral_tipos_doc_sei (
    id SERIAL PRIMARY KEY,
    tipo_doc VARCHAR(50),
    descricao TEXT,
    status_tipo_doc VARCHAR(20),
    created_por TEXT
);
```

---

### Exemplo 3: Lista com Edição Inline

```python
'c_dac_analistas': {
    'nome': 'DAC: Analistas',
    'schema': 'categoricas',
    'colunas_editaveis': ['nome_analista', 'd_usuario', 'status'],
    'labels': {
        'nome_analista': 'Nome do Analista',
        'd_usuario': 'R.F.',
        'status': 'Status'
    },
    'ordem': 'nome_analista',
    'tipos_campo': {
        'status': ['Ativo', 'Inativo']
    },
    'inline_edit': True,
    'inline_columns': ['status']
}
```

---

### Exemplo 4: Lista com Reordenação Manual

```python
'c_dac_modelo_textos_inconsistencias': {
    'nome': 'DAC: Modelos de Textos de Inconsistências',
    'schema': 'categoricas',
    'colunas_editaveis': ['nome_item', 'tipo_inconsistencia', 'modelo_texto', 'ordem'],
    'colunas_obrigatorias': ['nome_item', 'tipo_inconsistencia'],
    'labels': {
        'nome_item': 'Nome do Item',
        'tipo_inconsistencia': 'Tipo',
        'modelo_texto': 'Modelo de Texto',
        'ordem': 'Ordem'
    },
    'ordem': 'ordem NULLS LAST, nome_item',
    'permite_reordenar': True,
    'tipos_campo': {
        'modelo_texto': 'textarea',
        'rows_modelo_texto': 15,
        'ordem': 'number'
    }
}
```

**SQL da Tabela:**
```sql
CREATE TABLE categoricas.c_dac_modelo_textos_inconsistencias (
    id SERIAL PRIMARY KEY,
    nome_item VARCHAR(255),
    tipo_inconsistencia VARCHAR(100),
    modelo_texto TEXT,
    ordem INTEGER,
    created_por TEXT
);
```

---

### Exemplo 5: Lista com Colunas Calculadas

```python
'c_geral_pessoa_gestora': {
    'nome': 'Geral: Pessoas Gestoras',
    'schema': 'categoricas',
    'colunas_editaveis': ['nome_pg', 'setor', 'numero_rf', 'status_pg', 'email_pg'],
    'colunas_calculadas': ['total_pareceres', 'total_parcerias'],
    'labels': {
        'nome_pg': 'Nome',
        'setor': 'Setor',
        'numero_rf': 'Número do R.F.',
        'status_pg': 'Status',
        'email_pg': 'E-mail',
        'total_pareceres': 'Total de Pareceres',
        'total_parcerias': 'Total de Parcerias'
    },
    'colunas_filtro': ['nome_pg', 'setor', 'status_pg'],
    'ordem': 'nome_pg',
    'tipos_campo': {
        'setor': 'select_dinamico',
        'query_setor': 'SELECT DISTINCT setor FROM categoricas.c_geral_pessoa_gestora WHERE setor IS NOT NULL ORDER BY setor',
        'status_pg': 'select',
        'opcoes_status_pg': ['Ativo', 'Inativo', 'Desconhecido']
    }
}
```

---

## ✅ Checklist para Nova Lista

### 1. Banco de Dados

- [ ] Criar tabela no schema `categoricas` com prefixo `c_[divisao]_`
- [ ] Adicionar coluna `id SERIAL PRIMARY KEY`
- [ ] Adicionar coluna `created_por TEXT`
- [ ] (Opcional) Adicionar colunas de auditoria: `created_at`, `updated_por`, `updated_at`
- [ ] (Se reordenável) Adicionar coluna `ordem INTEGER`
- [ ] Executar script SQL no banco

### 2. Backend (`routes/listas.py`)

- [ ] Adicionar entrada em `TABELAS_CONFIG` (ordem alfabética por chave)
- [ ] Definir `nome` amigável
- [ ] Definir `schema` (geralmente `'categoricas'`)
- [ ] Listar `colunas_editaveis`
- [ ] Definir `labels` para cada coluna
- [ ] Definir `ordem` SQL (lembrar de `NULLS LAST` se usar campo `ordem`)
- [ ] (Opcional) Definir `colunas_obrigatorias`
- [ ] (Opcional) Configurar `tipos_campo` para campos especiais
- [ ] (Opcional) Adicionar `colunas_filtro`
- [ ] (Opcional) Adicionar `colunas_ordenacao`
- [ ] (Opcional) Configurar `inline_edit` e `inline_columns`
- [ ] (Opcional) Habilitar `permite_reordenar`

### 3. Testes

- [ ] Acessar `/listas` no navegador
- [ ] Verificar se tabela aparece no dropdown
- [ ] Testar criação de novo registro
- [ ] Testar edição de registro existente
- [ ] Testar exclusão
- [ ] (Se filtros) Testar filtros por coluna
- [ ] (Se ordenação) Testar ordenação
- [ ] (Se inline_edit) Testar edição inline
- [ ] (Se permite_reordenar) Testar reordenação manual

### 4. Documentação

- [ ] Atualizar este documento se novos padrões forem criados
- [ ] Documentar regras de negócio específicas (se houver)

---

## 🔧 Manutenção e Troubleshooting

### Problema: Tabela não aparece no dropdown

**Causa:** Falta de configuração ou erro de sintaxe em `TABELAS_CONFIG`.

**Solução:**
1. Verificar se a chave está em ordem alfabética
2. Verificar sintaxe (vírgulas, aspas, colchetes)
3. Checar logs do Flask no terminal

---

### Problema: Erro ao salvar registro

**Causa 1:** Campo obrigatório não preenchido.

**Solução:** Adicionar campo à lista `colunas_obrigatorias`.

**Causa 2:** Tipo de dado incompatível.

**Solução:** Ajustar `tipos_campo` para corresponder ao tipo SQL.

**Causa 3:** Coluna `created_por` não existe.

**Solução:** Adicionar coluna ao banco de dados.

---

### Problema: Select dinâmico não carrega opções

**Causa:** Query SQL com erro ou retorna vazio.

**Solução:**
1. Testar query diretamente no banco
2. Verificar se há dados na tabela referenciada
3. Verificar sintaxe da query em `query_[campo]`

---

### Problema: Reordenação não funciona

**Causa:** Falta coluna `ordem` no banco.

**Solução:**
```sql
ALTER TABLE categoricas.c_[sua_tabela] ADD COLUMN ordem INTEGER;
```

---

## 📚 Referências

- **Arquivo Frontend:** `templates/listas.html`
- **Arquivo Backend:** `routes/listas.py`
- **Arquivo de Rotas:** `app.py` (registro do blueprint)
- **Schema do Banco:** `categoricas`

---

## 📝 Histórico de Alterações

| Data | Versão | Alterações |
|------|--------|------------|
| 13/02/2026 | 1.0 | Criação inicial do documento baseado em análise do sistema |

---

**Fim do Documento**
