# SPEC — Página: Resultados FUMCAD
**Arquivo:** `relatorio_fumcad.html`  
**Contexto:** Gestão Orçamentária — Sistema de Gestão Financeira Municipal  
**Stack:** Flask (Python) + HTML/CSS/JS puro  
**Status:** ✅ Atualizada — v2

---

## 1. Objetivo

Exibir os valores **indisponíveis** do FUMCAD (Fundo Municipal dos Direitos da Criança e do Adolescente), permitindo calcular o saldo disponível real da conta bancária deduzindo compromissos financeiros pendentes, agrupados por tipo de instrumento: Termo de Fomento, Termo de Convênio e DEA.

**Pergunta central que o relatório responde:**  
> "A partir de [mês/ano selecionado], qual é o total de dívidas comprometidas do FUMCAD?"

O seletor de mês/ano define o **ponto de corte para pagamentos já efetuados**: parcelas pagas a partir dessa data ainda são consideradas dívidas, pois o dinheiro já está comprometido no exercício vigente.

---

## 2. Estrutura de Dados

### 2.1 Tabela principal
```
gestao_financeira.ultra_liquidacoes
```

| Coluna                      | Tipo          | Uso                                                                  |
|-----------------------------|---------------|----------------------------------------------------------------------|
| `numero_termo`              | varchar       | Identifica o instrumento e se é FUMCAD                               |
| `vigencia_inicial`          | date          | Início da vigência                                                   |
| `vigencia_final`            | date          | Fim da vigência                                                      |
| `parcela_tipo`              | varchar       | Tipo da parcela: `Programada` / `Projetada`                         |
| `valor_previsto`            | numeric(18,2) | Valor total previsto da parcela — **coluna de soma**                 |
| `valor_pago`                | numeric(18,2) | Valor já pago (referência, não usado no SUM)                         |
| `parcela_status`            | varchar       | Status principal: `Pago` / `Encaminhado para Pagamento` / `Não Pago` |
| `parcela_status_secundario` | varchar       | Status secundário (valores conforme tabela categórica abaixo)        |
| `data_pagamento`            | date          | Data em que o pagamento foi realizado — filtro para status `Pago`    |

### 2.2 Tabela categórica de status (referência — sem JOIN em runtime)
```
categoricas.c_dac_status_pagamento
```

| status_principal           | status_secundario                   |
|----------------------------|-------------------------------------|
| Pago                       | Integral                            |
| Pago                       | Parcial                             |
| Pago                       | Glosa                               |
| Encaminhado para Pagamento | -                                   |
| Não Pago                   | -                                   |
| Não Pago                   | Antigos                             |
| Não Pago                   | Falta Certidão                      |
| Não Pago                   | Aguardando Alteração                |
| Não Pago                   | Falta encarte de Prestações         |
| Não Pago                   | Rescisão                            |
| Não Pago                   | Glosa                               |

---

## 3. Regras de Negócio

### 3.1 Identificação de registros FUMCAD
- `numero_termo ILIKE '%FUMCAD%'`
- Prefixo `TFM` ou `TCL` → **Termo de Fomento / Colaboração**
- Prefixo `TCV` → **Termo de Convênio**

### 3.2 Filtro de tipo de parcela
Apenas parcelas dos tipos:
```
parcela_tipo IN ('Programada', 'Projetada')
```

### 3.3 Cálculo do valor indisponível por parcela
A soma é sempre sobre `valor_previsto` — sem subtração:
```
SUM(valor_previsto)
```

### 3.4 Elegibilidade de parcelas — critério de status

| parcela_status             | parcela_status_secundario       | Entra no cálculo? | Condição adicional |
|----------------------------|---------------------------------|-------------------|--------------------|
| Encaminhado para Pagamento | qualquer                        | ✅ Sim             | — |
| Não Pago                   | NULL ou `-`                     | ✅ Sim             | — |
| Não Pago                   | Qualquer outro valor            | ❌ Não             | — |
| Pago                       | Integral                        | ✅ Sim             | `data_pagamento >= 1º dia do mês selecionado` |
| Pago                       | Parcial                         | ✅ Sim             | `data_pagamento >= 1º dia do mês selecionado` |
| Pago                       | Glosa                           | ❌ Não             | — |

**Lógica para `Pago`:** se o gestor seleciona "março/2026", todas as parcelas pagas a partir de 01/03/2026 são incluídas, pois o comprometimento financeiro já estava estabelecido nesse período.

### 3.5 Semântica do seletor de mês/ano

O seletor **não filtra por vigência** — filtra apenas o ponto de corte para pagamentos já realizados:

| Tipo de status             | Efeito do seletor de mês/ano                          |
|----------------------------|-------------------------------------------------------|
| Encaminhado para Pagamento | Sem efeito — sempre incluído                          |
| Não Pago (null/-)          | Sem efeito — sempre incluído                          |
| Pago (Integral/Parcial)    | Incluído se `data_pagamento >= MAKE_DATE(ano, mes, 1)` |

---

## 4. Query SQL

```sql
SELECT
    CASE
        WHEN numero_termo ILIKE 'TFM%' OR numero_termo ILIKE 'TCL%' THEN 'TFM'
        WHEN numero_termo ILIKE 'TCV%'                               THEN 'TCV'
    END AS tipo,
    SUM(valor_previsto) AS valor_indisponivel

FROM gestao_financeira.ultra_liquidacoes

WHERE
    -- Apenas registros FUMCAD
    numero_termo ILIKE '%FUMCAD%'

    -- Tipos de parcela válidos
    AND parcela_tipo IN ('Programada', 'Projetada')

    -- Elegibilidade por status
    AND (
        -- Encaminhado para Pagamento: todos
        parcela_status = 'Encaminhado para Pagamento'

        OR (
            -- Não Pago: apenas sem status secundário
            parcela_status = 'Não Pago'
            AND (
                parcela_status_secundario IS NULL
                OR parcela_status_secundario = ''
                OR parcela_status_secundario = '-'
            )
        )

        OR (
            -- Pago Integral/Parcial: a partir do 1º dia do mês selecionado
            parcela_status = 'Pago'
            AND parcela_status_secundario IN ('Integral', 'Parcial')
            AND data_pagamento >= MAKE_DATE(:ano, :mes, 1)
        )
    )

GROUP BY tipo
```

---

## 5. Layout da Página

### 5.1 Estrutura visual

```
┌──────────────────────────────────────────────────────────────────┐
│  RESULTADOS FUMCAD              Mês: [jan ▼]  Ano: [2026]  [Buscar] │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  A  Saldo Bancário (editável)        R$ [_________________] ✎   │
│                                                                  │
│  B  Parcerias – Autorizadas a Liquidar                           │
│     ├── Termo de Fomento             R$ X.XXX.XXX,XX      [↗]   │
│     └── Termo de Convênio            R$ X.XXX.XXX,XX      [↗]   │
│                                                                  │
│  C  DEA (editável)                   R$ [_________________] ✎   │
│                                                                  │
├──────────────────────────────────────────────────────────────────┤
│  DISPONÍVEL CALCULADO                R$ X.XXX.XXX,XX            │
│  (A − Termo de Fomento − Termo de Convênio − DEA)               │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  Índice               │  Indisponível          │  Ação           │
├──────────────────────────────────────────────────────────────────┤
│  Termo de Fomento     │  R$ X.XXX.XXX,XX       │  [Copiar]       │
│  Termo de Convênio    │  R$ X.XXX.XXX,XX       │  [Copiar]       │
│  DEA                  │  R$ X.XXX.XXX,XX       │  [Copiar]       │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Campos manuais
- **Linha A — Saldo Bancário:** campo numérico editável. Começa vazio. Formatado como BRL ao perder foco.
- **Linha C — DEA:** campo numérico editável. Valor padrão: `R$ 0,00`.

### 5.3 Filtro de mês/ano
- Select de **mês** (jan–dez) + input numérico de **ano** (padrão: ano corrente).
- Valor padrão ao abrir: `jan / 2026`.
- Botão **Buscar** dispara requisição AJAX e atualiza TFM e TCV.
- Durante o carregamento: valores exibem `---` com indicador de loading.

### 5.4 Disponível Calculado
```
Disponível = A (Saldo Bancário) − TFM − TCV − C (DEA)
```
- Recalculado automaticamente sempre que A, B (via API) ou C mudam.
- Positivo → destaque **verde**.
- Negativo → destaque **vermelho**.
- Valores zerados exibem `R$ 0,00` (nunca ocultos).

---

## 6. Rotas Flask

### `GET /relatorio-fumcad`
Renderiza a página com estado inicial (mês `jan`, ano `2026`).

### `GET /api/fumcad/disponibilidade?mes=1&ano=2026`
Executa a query e retorna os valores do banco para o mês/ano informado.

**Response:**
```json
{
  "mes": 1,
  "ano": 2026,
  "termo_fomento": 258521.05,
  "termo_convenio": 0.00
}
```

> DEA e Saldo Bancário **não** são retornados pela API — são inseridos manualmente pelo usuário.

---

## 7. Frontend — JavaScript

Funções a implementar em `relatorio_fumcad.js`:

| Função | Responsabilidade |
|--------|-----------------|
| `fetchDisponibilidade(mes, ano)` | Chama a API e atualiza TFM e TCV na tela |
| `recalcularDisponivel()` | Recalcula `A − TFM − TCV − C` e atualiza o resultado |
| `copiarValor(valor)` | Copia o valor formatado via `navigator.clipboard` |
| `formatarMoeda(valor)` | Formata float para string BRL (`Intl.NumberFormat`) |
| `parseMoeda(str)` | Converte string BRL formatada de volta para float |

Event listeners:
- Campo A e Campo C: disparam `recalcularDisponivel()` ao alterar.
- Botão Buscar: dispara `fetchDisponibilidade(mes, ano)` e depois `recalcularDisponivel()`.

---

## 8. Checklist pré-produção

- [ ] Executar query de diagnóstico de índices (seção 4) e criar índices se necessário
- [ ] Confirmar `GRANT SELECT` para o usuário Flask em `gestao_financeira.ultra_liquidacoes`
- [ ] Validar query com dados reais para jan/2026
- [ ] Confirmar comportamento quando não há registros: exibir `R$ 0,00`
- [ ] Monitorar se novos `parcela_status_secundario` forem adicionados à tabela categórica (podem precisar de revisão de elegibilidade)

---

## 9. Fora do Escopo (desta entrega)

- Integração automática com planilha Excel para Saldo Bancário
- Persistência dos valores manuais (A e DEA) entre sessões
- Drill-down por parcela individual
- Exportação para PDF/Excel
- Autenticação e autorização