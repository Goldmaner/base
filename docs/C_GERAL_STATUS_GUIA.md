# Guia — `categoricas.c_geral_status`

## Propósito

`categoricas.c_geral_status` é o catálogo universal de valores controlados
(enumerações/dropdowns) para campos de status em qualquer tabela do sistema.

Ele substitui progressivamente as tabelas individuais de categoria que
existiam antes (ex.: `c_analises_status`, `c_visita_status`), centralizando
tudo num único lugar e facilitando manutenção.

---

## Estrutura da Tabela

```sql
CREATE TABLE categoricas.c_geral_status (
    id                    SERIAL PRIMARY KEY,
    schema_table_coluna_r TEXT NOT NULL,  -- chave de referência (ver formato abaixo)
    status                TEXT NOT NULL,  -- valor que será gravado na coluna destino
    descricao             TEXT,           -- rótulo exibido ao usuário (pode ser NULL)
    ordem                 INT  DEFAULT 0, -- ordena o dropdown (menor = primeiro)
    ativo                 BOOLEAN DEFAULT TRUE,
    criado_em             TIMESTAMPTZ DEFAULT now()
);
```

---

## Formato de `schema_table_coluna_r`

```
<schema>.<tabela>.<coluna>
```

Exemplos:
| `schema_table_coluna_r`                                  | Campo destino                                    |
|----------------------------------------------------------|--------------------------------------------------|
| `public.parcerias_monit.visita_status`                   | `parcerias_monit.visita_status`                  |
| `public.parcerias_monit.visita_avaliacao`                | `parcerias_monit.visita_avaliacao`               |
| `public.parcerias_monit.monit_status`                    | `parcerias_monit.monit_status`                   |
| `public.parcerias_monit.monit_avaliacao`                 | `parcerias_monit.monit_avaliacao`                |
| `public.parcerias_monit_adicional.justificativa_status`  | `parcerias_monit_adicional.justificativa_status` |
| `public.parcerias_monit_adicional.comissao_visita`       | `parcerias_monit_adicional.comissao_visita`      |

---

## Valores Atualmente Cadastrados

### `public.parcerias_monit.visita_status`
| status            | descrição                                |
|-------------------|------------------------------------------|
| Agendada          | Visita agendada                          |
| Realizada         | Visita realizada                         |
| Cancelada         | Visita cancelada                         |
| Não realizada     | Visita não realizada                     |
| -                 | Sem informação                           |

### `public.parcerias_monit.visita_avaliacao`
| status            | descrição                                |
|-------------------|------------------------------------------|
| Satisfatório      | Avaliação satisfatória                   |
| Parcial           | Avaliação parcialmente satisfatória      |
| Insatisfatório    | Avaliação insatisfatória                 |
| -                 | Sem avaliação                            |

### `public.parcerias_monit.monit_status`
| status            | descrição                                |
|-------------------|------------------------------------------|
| Pendente          | Monitoramento pendente                   |
| Em andamento      | Monitoramento em andamento               |
| Concluído         | Monitoramento concluído                  |
| -                 | Sem informação                           |

### `public.parcerias_monit.monit_avaliacao`
| status              | descrição                              |
|---------------------|----------------------------------------|
| Satisfatório        | Avaliação satisfatória                 |
| Parcial             | Avaliação parcialmente satisfatória    |
| Insatisfatório      | Avaliação insatisfatória               |
| -                   | Sem avaliação                          |
| Da Pessoa Gestora   | Avaliação da Pessoa Gestora            |

### `public.parcerias_monit_adicional.justificativa_status`
| status            | descrição                                |
|-------------------|------------------------------------------|
| Apresentada       | Justificativa apresentada                |
| Não apresentada   | Justificativa não apresentada            |
| Aceita            | Justificativa aceita                     |
| Rejeitada         | Justificativa rejeitada                  |
| -                 | Sem informação                           |

### `public.parcerias_monit_adicional.comissao_visita`
| status            | descrição                                |
|-------------------|------------------------------------------|
| Sim               | Houve comissão na visita                 |
| Não               | Não houve comissão na visita             |
| -                 | Sem informação                           |

---

## Como Adicionar Novos Valores

```sql
-- Exemplo: adicionar status "Em recurso" para visita_status
INSERT INTO categoricas.c_geral_status
    (schema_table_coluna_r, status, descricao, ordem)
VALUES
    ('public.parcerias_monit.visita_status', 'Em recurso', 'Visita em fase recursal', 6);
```

---

## Como Adicionar um Novo Campo (nova coluna/tabela)

1. Crie a coluna na tabela de destino (ou certifique-se que ela existe).
2. Insira os valores desejados em `c_geral_status` usando o formato
   `schema.tabela.coluna` na coluna `schema_table_coluna_r`.
3. No backend, use o endpoint `/analises/api/status-disponiveis?campo=<ref>`
   para popular o dropdown dinamicamente:

   ```python
   cur.execute("""
       SELECT status, descricao
       FROM categoricas.c_geral_status
       WHERE schema_table_coluna_r = %s
         AND ativo = true
       ORDER BY ordem, status
   """, ('public.parcerias_monit.novo_campo',))
   ```

4. No template Jinja, passe os valores via `status_options['novo_campo']`
   (já feito para os campos do módulo M&A).

---

## Plano de Migração Futuro

| Tabela antiga               | Campos cobertos         | Status    |
|-----------------------------|-------------------------|-----------|
| `c_analises_status`         | status financeiro       | Pendente  |
| `c_visita_status`           | visita_status           | Migrado ✅|
| `c_monit_avaliacao`         | monit_avaliacao         | Migrado ✅|
| (campos inline/free text)   | comissao_ma, etc.       | Migrado ✅|

A migração completa é opcional: `c_geral_status` e as tabelas antigas podem
coexistir. A recomendação é usar `c_geral_status` para **todos os novos campos**
e migrar os antigos conforme necessidade operacional.
