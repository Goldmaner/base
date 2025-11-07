# Módulo de Análise de Prestação de Contas

## Visão Geral

Este módulo implementa um sistema completo de checklist para acompanhamento de análises de prestação de contas. Permite que múltiplos analistas gerenciem o progresso de análises por termo e período.

## Estrutura de Arquivos

```
routes/analises_pc/
├── __init__.py          # Inicialização do blueprint
└── routes.py            # Rotas e lógica de negócio

templates/analises_pc/
└── index.html           # Interface do checklist

scripts/
└── criar_indices_analises_pc.sql  # Índices para performance
```

## Estrutura do Banco de Dados

### Schema: `analises_pc`

#### 1. `checklist_termo`
Armazena o checklist principal de cada análise.

**Campos principais:**
- `numero_termo` (VARCHAR): Número do termo de parceria
- `meses_analisados` (VARCHAR): Período em análise (formato: MM/AAAA)
- `nome_analista` (VARCHAR): Analista principal
- Campos booleanos para cada etapa do checklist

**Chave composta:** `numero_termo` + `meses_analisados` (UNIQUE)

#### 2. `checklist_analista`
Armazena os analistas responsáveis (suporta múltiplos analistas).

**Campos:**
- `numero_termo` (VARCHAR)
- `meses_analisados` (VARCHAR)
- `nome_analista` (VARCHAR)

**Relacionamento:** 1:N com `checklist_termo`

#### 3. `checklist_recursos`
Armazena as fases recursais (pode haver múltiplas).

**Campos:**
- `numero_termo` (VARCHAR)
- `meses_analisados` (VARCHAR)
- `tipo_recurso` (INTEGER): Sequencial (1, 2, 3...)
- Campos booleanos para etapas do recurso

**Relacionamento:** 1:N com `checklist_termo`

## Funcionalidades

### 1. Seleção Inicial
- Seleção de termo (dropdown com dados de `public.parcerias`)
- Entrada de meses analisados (texto livre)
- Seleção de múltiplos analistas (multi-select)

### 2. Checklist de Etapas

**Etapas principais:**
1. Avaliação do processo de celebração
2. Avaliação do processo de prestação de contas/pagamento
3. Preenchimento de dados base
4. Preenchimento de orçamento anual
5. Preenchimento da conciliação bancária
6. Avaliação dos dados bancários
7. Extração, inclusão e encaminhamento de documentos no SEI
8. Avaliação das respostas de inconsistências
9. Emissão de parecer ou manifestação
10. Extração, inclusão e encaminhamento de documentos no SEI
11. Tratativas de restituição
12. Encaminhamentos para encerramento, CADIN ou prescrição

### 3. Fases Recursais
- Adição dinâmica de fases recursais
- Cada recurso tem 3 etapas próprias:
  - Avaliação das respostas recursais
  - Emissão de parecer recursal
  - Documentos no SEI

### 4. Marcação em Cascata
Quando uma etapa é marcada, todas as anteriores são automaticamente marcadas, garantindo que não se "pule fases".

### 5. Persistência
- Salvar todos os avanços no banco de dados
- Carregar estado anterior ao abrir um termo/período já iniciado
- Suporte a múltiplos analistas e recursos

## Rotas da API

### `GET /analises_pc/`
Página principal do checklist.

**Retorna:** Template HTML com dropdowns preenchidos

### `POST /analises_pc/api/carregar_checklist`
Carrega dados existentes de um checklist.

**Body:**
```json
{
  "numero_termo": "123/2024",
  "meses_analisados": "01/2024"
}
```

**Retorna:**
```json
{
  "checklist": { ... },
  "analistas": ["Nome 1", "Nome 2"],
  "recursos": [{ ... }]
}
```

### `POST /analises_pc/api/salvar_checklist`
Salva ou atualiza o checklist completo.

**Body:**
```json
{
  "numero_termo": "123/2024",
  "meses_analisados": "01/2024",
  "analistas": ["Nome 1", "Nome 2"],
  "checklist": {
    "avaliacao_celebracao": true,
    ...
  },
  "recursos": [
    {
      "tipo_recurso": 1,
      "avaliacao_resposta_recursal": true,
      ...
    }
  ]
}
```

## Índices de Performance

Os seguintes índices foram criados para otimizar consultas:

```sql
-- Índices compostos (chave de busca principal)
idx_checklist_termo_composto (numero_termo, meses_analisados)
idx_checklist_analista_composto (numero_termo, meses_analisados)
idx_checklist_recursos_composto (numero_termo, meses_analisados)

-- Índices individuais
idx_checklist_termo_numero_termo
idx_checklist_analista_nome
idx_checklist_recursos_tipo
```

## Fluxo de Uso

1. **Acesso:** Página Instruções → "Ir para o Formulário Inicial"
2. **Configuração:** Selecionar termo, meses e analistas → "Prosseguir"
3. **Preenchimento:** Marcar etapas concluídas
4. **Recursos (opcional):** Adicionar fases recursais conforme necessário
5. **Salvamento:** Clicar em "Salvar Avanços"
6. **Retorno:** Os dados são preservados para próxima consulta

## Tecnologias Utilizadas

- **Backend:** Flask (Python)
- **Frontend:** Bootstrap 5, jQuery, Select2
- **Banco de Dados:** PostgreSQL
- **Bibliotecas:** psycopg2 (conexão DB)

## Segurança e Integridade

- Constraint UNIQUE em `checklist_termo` para evitar duplicatas
- Transações atômicas no salvamento (commit/rollback)
- Validação de campos obrigatórios no frontend e backend
- Prepared statements para prevenir SQL injection

## Melhorias Futuras

- [ ] Histórico de alterações (audit log)
- [ ] Notificações por e-mail quando etapas forem concluídas
- [ ] Dashboard com estatísticas de progresso
- [ ] Exportação de relatórios em PDF
- [ ] Comentários e observações por etapa
- [ ] Anexação de documentos comprobatórios

## Manutenção

### Criar índices (primeira vez)
```bash
psql -U usuario -d banco -f scripts/criar_indices_analises_pc.sql
```

### Verificar índices criados
```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE schemaname = 'analises_pc';
```

## Suporte

Para dúvidas ou problemas, consulte a documentação principal do projeto FAF.
