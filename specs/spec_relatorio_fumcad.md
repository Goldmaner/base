# SPEC — Página: Resultados FUMCAD
**Arquivo:** `relatorio_fumcad.html`  
**Contexto:** Gestão Orçamentária — Sistema de Gestão Financeira Municipal  
**Stack:** Flask (Python) + HTML/CSS/JS puro  
**Status:** ✅ Fechada — pronta para implementação

---

## 1. Objetivo

Exibir os valores **indisponíveis** do FUMCAD (Fundo Municipal dos Direitos da Criança e do Adolescente), permitindo calcular o saldo disponível real da conta bancária deduzindo compromissos financeiros pendentes, agrupados por tipo de instrumento: Termo de Fomento, Termo de Convênio e DEA.

---

## 2. Estrutura de Dados

### 2.1 Tabela principal
```
gestao_financeira.ultra_liquidacoes
```

| Coluna                      | Tipo          | Uso                                                                  |
|-----------------------------|---------------|----------------------------------------------------------------------|
| `numero_termo`              | varchar       | Identifica o instrumento e se é FUMCAD                               |
| `vigencia_inicial`          | date          | Início da vigência — usado como critério temporal                    |
| `vigencia_final`            | date          | Fim da vigência                                                      |
| `valor_previsto`            | numeric(18,2) | Valor total previsto da parcela                                      |
| `valor_pago`                | numeric(18,2) | Valor já pago (pode ser parcial)                                     |
| `parcela_status`            | varchar       | Status principal: `Pago` / `Encaminhado para Pagamento` / `Não Pago` |
| `parcela_status_secundario` | varchar       | Status secundário (valores conforme tabela categórica abaixo)        |

### 2.2 Tabela categórica de status (referência — sem JOIN em runtime)
```
categoricas.c_dac_status_pagamento
```

Os valores de `parcela_status_secundario` em `ultra_liquidacoes` são inseridos via dropdown referenciando essa tabela. Estão desnormalizados na coluna principal — não é necessário JOIN.

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
- Prefixo `TFM` → **Termo de Fomento**
- Prefixo `TCV` → **Termo de Convênio**

### 3.2 Critério temporal — filtro por mês selecionado
O filtro usa o **mês e ano de `vigencia_inicial`**:

```
EXTRACT(YEAR  FROM vigencia_inicial) = :ano_selecionado
AND
EXTRACT(MONTH FROM vigencia_inicial) = :mes_selecionado
```

Somente parcelas cujo `vigencia_inicial` cai no mês/ano escolhido são incluídas.

### 3.3 Cálculo do valor indisponível por parcela

```
CASE
  WHEN valor_pago > 0 THEN valor_previsto - valor_pago
  ELSE valor_previsto
END
```

Captura pagamentos parciais: o saldo remanescente (`previsto - pago`) ainda está comprometido.  
Aplica-se igualmente a **TFM e TCV**.

### 3.4 Elegibilidade de parcelas

| parcela_status             | parcela_status_secundario       | Entra no cálculo? |
|----------------------------|---------------------------------|-------------------|
| Pago                       | Integral                        | ❌ Não             |
| Pago                       | Parcial                         | ✅ Sim (saldo = previsto − pago) |
| Pago                       | Glosa                           | ✅ Sim (saldo = previsto − pago) |
| Encaminhado para Pagamento | -                               | ✅ Sim             |
| Não Pago                   | -                               | ✅ Sim             |
| Não Pago                   | Antigos                         | ❌ Não             |
| Não Pago                   | Falta Certidão                  | ✅ Sim *           |
| Não Pago                   | Aguardando Alteração            | ✅ Sim *           |
| Não Pago                   | Falta encarte de Prestações     | ✅ Sim *           |
| Não Pago                   | Rescisão                        | ✅ Sim *           |
| Não Pago                   | Glosa                           | ✅ Sim *           |

*Sujeitos à regra de exercício orçamentário (3.5).

### 3.5 Regra de exercício orçamentário — aplica-se APENAS ao TFM

O TFM respeita o exercício orçamentário anual. O **TCV não é afetado** por esta regra.

**Lógica da janela de transição** (calculada dinamicamente pelo ano corrente do servidor):

```
data_corte = 01/03/ano_atual   ← sempre 1º de março do ano corrente

SE CURRENT_DATE < data_corte:
    # Janela jan–fev: considera ano atual E ano anterior
    TFM: vigencia_inicial >= 01/01/(ano_atual - 1)

SE CURRENT_DATE >= data_corte:
    # A partir de março: apenas o ano vigente
    TFM: vigencia_inicial >= 01/01/ano_atual
```

Isso significa que registros de TFM do ano anterior são automaticamente descartados após 1º de março, sem nenhuma configuração manual.

---

## 4. Query SQL

> ⚠️ **Antes de executar em produção:** verificar existência de índices:
> ```sql
> SELECT indexname, indexdef
> FROM pg_indexes
> WHERE tablename = 'ultra_liquidacoes'
>   AND schemaname = 'gestao_financeira';
> ```
> Se não houver índices em `vigencia_inicial`, `numero_termo` ou `parcela_status`, criá-los antes de ir a produção.

```sql
SELECT
    CASE
        WHEN numero_termo ILIKE 'TFM%' THEN 'TFM'
        WHEN numero_termo ILIKE 'TCV%' THEN 'TCV'
    END AS tipo,
    SUM(
        CASE
            WHEN valor_pago > 0 THEN valor_previsto - valor_pago
            ELSE valor_previsto
        END
    ) AS valor_indisponivel

FROM gestao_financeira.ultra_liquidacoes

WHERE
    -- Apenas registros FUMCAD
    numero_termo ILIKE '%FUMCAD%'

    -- Filtro pelo mês/ano de início de vigência
    AND EXTRACT(YEAR  FROM vigencia_inicial) = :ano_selecionado
    AND EXTRACT(MONTH FROM vigencia_inicial) = :mes_selecionado

    -- Excluir Pago Integral (único "Pago" que sai)
    AND NOT (parcela_status = 'Pago' AND parcela_status_secundario = 'Integral')

    -- Excluir Não Pago Antigos
    AND NOT (parcela_status = 'Não Pago' AND parcela_status_secundario = 'Antigos')

    -- Regra de exercício orçamentário: aplica-se apenas ao TFM
    AND (
        -- TCV: sem restrição de ano
        numero_termo ILIKE 'TCV%'

        OR (
            -- TFM: aplica janela de transição
            numero_termo ILIKE 'TFM%'
            AND (
                -- Dentro da janela jan–fev: aceita ano atual e anterior
                (
                    CURRENT_DATE < DATE_TRUNC('year', CURRENT_DATE) + INTERVAL '2 months'
                    AND EXTRACT(YEAR FROM vigencia_inicial) >= EXTRACT(YEAR FROM CURRENT_DATE) - 1
                )
                OR
                -- A partir de março: apenas ano vigente
                (
                    CURRENT_DATE >= DATE_TRUNC('year', CURRENT_DATE) + INTERVAL '2 months'
                    AND EXTRACT(YEAR FROM vigencia_inicial) = EXTRACT(YEAR FROM CURRENT_DATE)
                )
            )
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