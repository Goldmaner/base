# Feature: Gestão de Pendências e Urgências

## Nome da funcionalidade

Nova seção da home:

**Gestão de Pendências e Urgências**

Página principal:

**`smdhc_pendencias.html`**

Objetivo: criar uma área estruturada para acompanhar pendências institucionais, urgências, responsáveis, atualizações, riscos e prioridade operacional da SMDHC.

---

## Objetivo funcional

A funcionalidade deve permitir:

* cadastrar pendências;
* listar pendências;
* filtrar pendências;
* visualizar pendência em detalhe;
* registrar atualizações;
* vincular processos SEI;
* vincular responsáveis e envolvidos;
* classificar prioridade com matriz própria;
* destacar urgências e riscos;
* apresentar visão gerencial, e não apenas tabela.

Essa área deve ajudar a responder:

* Qual pendência deve ser tratada primeiro?
* Quais estão sem prazo?
* Quais estão paradas?
* Quais dependem de aprovação?
* Quais têm risco legal, material ou político?
* Quem é o responsável?
* Qual foi a última atualização?
* Qual é a próxima ação?

---

## Estrutura esperada

### Blueprint

Criar nova blueprint, preferencialmente com prefixo:

* `/smdhc-pendencias`

ou, se o projeto já organizar assim:

* `/fparcerias/smdhc-pendencias`

### Estrutura de arquivos sugerida

```text
app/
  routes/
    smdhc_pendencias/
      __init__.py
      routes.py
      services.py
      forms.py

  templates/
    smdhc_pendencias/
      smdhc_pendencias.html
      smdhc_pendencia_detalhe.html
      smdhc_pendencia_form.html
      smdhc_pendencia_relatorio.html
      partials/
        cards_resumo.html
        filtros.html
        matriz_priorizacao.html
        lista_pendencias.html
        timeline_atualizacoes.html
        badges_pendencia.html
        modal_atualizacao.html
        modal_sei.html
        modal_responsaveis.html
```

---

## Rotas esperadas

```text
GET  /smdhc-pendencias
GET  /smdhc-pendencias/nova
POST /smdhc-pendencias/nova
GET  /smdhc-pendencias/<int:id>
GET  /smdhc-pendencias/<int:id>/editar
POST /smdhc-pendencias/<int:id>/editar
POST /smdhc-pendencias/<int:id>/excluir
POST /smdhc-pendencias/<int:id>/atualizacao
POST /smdhc-pendencias/<int:id>/sei
POST /smdhc-pendencias/<int:id>/responsaveis
POST /smdhc-pendencias/<int:id>/matriz
GET  /smdhc-pendencias/relatorio
GET  /smdhc-pendencias/api/resumo
GET  /smdhc-pendencias/api/matriz
GET  /smdhc-pendencias/api/usuarios
GET  /smdhc-pendencias/api/status-options
```

---

## Banco de dados

### Schema

Criar novo schema:

```sql
CREATE SCHEMA IF NOT EXISTS pendencias;
```

### Tabela principal

Tabela:

* `pendencias.smdhc_pendencias`

Campos esperados:

* `id SERIAL PRIMARY KEY`
* `tema_nome TEXT NOT NULL`
* `tema_tipo TEXT`
* `tema_descricao TEXT`
* `tema_area_demandante TEXT`
* `tema_area_responsavel TEXT[]`
* `tema_area_correlata TEXT[]`
* `tema_status TEXT`
* `tema_prazo_estimado DATE`
* `tema_observacoes TEXT`
* `situacao_automatica TEXT`
* `prioridade_manual INTEGER`
* `prioridade_observacao TEXT`
* `ativo BOOLEAN DEFAULT TRUE`
* `criado_por TEXT`
* `criado_em TIMESTAMPTZ DEFAULT now()`
* `atualizado_por TEXT`
* `atualizado_em TIMESTAMPTZ DEFAULT now()`

### Regras dos campos

#### `tema_tipo`

Lista controlada com estas opções:

* Normatização e Atos Oficiais
* Gestão de Editais
* Saneamento de Passivo e Fluxo Processual
* Infraestrutura, Logística e RH
* Planejamento Estratégico e Compliance

Cadastrar preferencialmente em:

* `categoricas.c_geral_status`

referência:

* `pendencias.smdhc_pendencias.tema_tipo`

#### `tema_area_demandante`

Opções exclusivas:

* Gabinete
* Interno (DP)

Cadastrar preferencialmente em:

* `categoricas.c_geral_status`

referência:

* `pendencias.smdhc_pendencias.tema_area_demandante`

#### `tema_area_responsavel`

Múltipla seleção via checkbox.

Opções iniciais:

* DP
* DGP
* DAC
* DGM

Salvar como `TEXT[]`.

#### `tema_area_correlata`

Múltipla seleção via checkbox.

Opções sugeridas:

* DP
* DGP
* DAC
* DGM
* Gabinete
* AJ
* CAF
* CPDDH
* CPIR
* CPM
* SESANA
* SMADS
* Casa Civil
* CDHOC
* Outras

Salvar como `TEXT[]`.

#### `tema_status`

Lista controlada com:

* Iniciado
* Não iniciado
* Aguardando Aprovação
* Concluído

Cadastrar preferencialmente em:

* `categoricas.c_geral_status`

referência:

* `pendencias.smdhc_pendencias.tema_status`

---

## Tabelas relacionadas

### Processos SEI

Tabela:

* `pendencias.smdhc_pendencias_sei`

Campos:

* `id SERIAL PRIMARY KEY`
* `pendencia_id INTEGER NOT NULL REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE`
* `tema_processo TEXT`
* `tema_processo_observacao TEXT`
* colunas de auditoria

### Responsáveis

Tabela:

* `pendencias.smdhc_pendencias_resp`

Campos:

* `id SERIAL PRIMARY KEY`
* `pendencia_id INTEGER NOT NULL REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE`
* `tema_responsavel TEXT`
* `tema_envolvidos TEXT[]`
* colunas de auditoria

Os nomes devem vir preferencialmente de:

* `gestao_pessoas.usuarios_infos.usuario_nome`

### Atualizações

Tabela:

* `pendencias.smdhc_pendencias_atualizacoes`

Campos:

* `id SERIAL PRIMARY KEY`
* `pendencia_id INTEGER NOT NULL REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE`
* `tema_atualizacao TEXT NOT NULL`
* `tema_atualizacao_data DATE DEFAULT CURRENT_DATE`
* `tema_acao_subsequente TEXT`
* colunas de auditoria

Essa tabela deve alimentar a timeline da pendência.

---

## Matriz de priorização

### Tabela de princípios

Tabela:

* `pendencias.smdhc_pendencias_principios`

Princípios iniciais:

1. Proximidade
2. ENEM
3. Instabilidade
4. Nº de Riscos

Campos principais:

* `tema_principios`
* `tema_principios_descricao`
* `tema_principios_calculo`
* `tema_principios_ordem`

Sugestão de ordem:

* Proximidade = 10
* ENEM = 20
* Instabilidade = 30
* Nº de Riscos = 40

### Tabela de notas dos princípios

Tabela:

* `pendencias.smdhc_pendencias_principios_notas`

Carga inicial:

#### Proximidade

* DP = 3
* SMDHC = 2
* Externo = 1

#### ENEM

* Baixa = 3
* Média = 2
* Difícil = 1

#### Instabilidade

* Instável = 2
* Estável = 1

#### Nº de Riscos

* Político = 4
* Material = 2
* Legal = 1

### Tabela matriz

Tabela:

* `pendencias.smdhc_pendencias_matriz`

Campos:

* `id SERIAL PRIMARY KEY`
* `pendencia_id INTEGER NOT NULL REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE`
* `principio_id INTEGER NOT NULL REFERENCES pendencias.smdhc_pendencias_principios(id) ON DELETE CASCADE`
* `tema_principios_nota INTEGER NOT NULL DEFAULT 0`
* colunas de auditoria
* `UNIQUE (pendencia_id, principio_id)`

### Tabela complementar de fatores

Tabela:

* `pendencias.smdhc_pendencias_matriz_fatores`

Campos:

* `id SERIAL PRIMARY KEY`
* `matriz_id INTEGER NOT NULL REFERENCES pendencias.smdhc_pendencias_matriz(id) ON DELETE CASCADE`
* `principio_nota_id INTEGER NOT NULL REFERENCES pendencias.smdhc_pendencias_principios_notas(id) ON DELETE CASCADE`
* colunas mínimas de criação
* `UNIQUE (matriz_id, principio_nota_id)`

Essa tabela é obrigatória para registrar os fatores marcados, especialmente em princípios cumulativos como risco.

---

## Regra da priorização

A ordem da prioridade **não deve ser por soma simples**.

A prioridade deve ser definida por critérios sucessivos:

1. maior nota em Proximidade
2. empate → maior nota em ENEM
3. empate → maior nota em Instabilidade
4. empate → maior nota em Nº de Riscos
5. empate → prazo mais próximo
6. empate final → menor `id`

Exemplo:

```text
Tema | Próximo | ENEM | Instabilidade | Riscos | Ordem
A    | 3       | 3    | 2             | 3      | 1
B    | 3       | 1    | 2             | 7      | 3
C    | 3       | 2    | 1             | 1      | 2
D    | 2       | 1    | 2             | 3      | 4
```

---

## View SQL

Criar view para facilitar ranking e frontend:

* `pendencias.vw_smdhc_pendencias_priorizacao`

Campos mínimos esperados:

* `pendencia_id`
* `tema_nome`
* `tema_tipo`
* `tema_status`
* `tema_prazo_estimado`
* `tema_area_demandante`
* `tema_area_responsavel`
* `nota_proximidade`
* `nota_enem`
* `nota_instabilidade`
* `nota_riscos`
* `ordem_prioridade`
* `situacao_automatica`
* `responsavel`
* `ultima_atualizacao`
* `proxima_acao`

Se necessário no futuro, avaliar materialized view.

---

## Situação automática e badges

Implementar lógica para gerar sinais automáticos como:

* Sem prazo
* Parado
* Crítico
* Aguardando validação
* Prazo próximo
* Vencido
* Concluído
* Risco legal
* Risco material
* Risco político
* Alta prioridade

Regras sugeridas:

### Sem prazo

Quando `tema_prazo_estimado IS NULL` e não estiver concluído.

### Vencido

Quando o prazo já passou e o status não for concluído.

### Prazo próximo

Quando faltar até 30 dias.

### Parado

Quando não houver atualização recente.

### Aguardando validação

Quando status = `Aguardando Aprovação`.

### Crítico

Quando combinar posição alta na matriz com sinais de urgência/riscos/prazo.

---

## UX/UI

A página principal **não deve ser uma tabela gigante**.

Ela deve funcionar como painel gerencial.

### Elementos esperados

* cabeçalho da página;
* cards de resumo;
* filtros;
* alertas;
* matriz visual;
* lista em cards ou accordion;
* visão tabular apenas como apoio.

### Cabeçalho

Título:

* Gestão de Pendências e Urgências

Subtítulo:

* Painel de acompanhamento das pendências institucionais, prioridades, riscos, responsáveis e próximas ações da SMDHC.

Botões sugeridos:

* Nova Pendência
* Atualizar Matriz
* Exportar
* Voltar

### Cards de resumo

Exibir:

* total de pendências ativas;
* iniciadas;
* não iniciadas;
* aguardando aprovação;
* concluídas;
* sem prazo;
* vencidas;
* paradas;
* com risco legal;
* com risco material;
* com risco político;
* críticas.

### Lista principal

Preferir cards ou accordion contendo:

* tema;
* tipo;
* descrição curta;
* status;
* áreas;
* prazo;
* responsável;
* última atualização;
* próxima ação;
* posição da matriz;
* badges automáticos.

### Página de detalhe

Arquivo:

* `smdhc_pendencia_detalhe.html`

Deve mostrar:

1. cabeçalho;
2. badges;
3. descrição;
4. áreas;
5. processos SEI;
6. responsáveis;
7. prazo;
8. observações;
9. timeline de atualizações;
10. próxima ação;
11. matriz de priorização;
12. fatores selecionados;
13. ações da pendência.

A timeline deve ser elemento central.

---

## Forms

Criar `forms.py` para suportar:

* criação;
* edição;
* atualização;
* vínculos SEI;
* responsáveis;
* matriz.

Campos com lista controlada devem puxar dados dos catálogos.

Campos de pessoa devem usar fonte de `gestao_pessoas.usuarios_infos`.

---

## Services esperados

Criar funções como:

* `listar_pendencias`
* `obter_pendencia`
* `criar_pendencia`
* `atualizar_pendencia`
* `excluir_pendencia_logicamente`
* `listar_status_options`
* `listar_tema_tipos`
* `listar_area_demandante`
* `listar_usuarios_infos`
* `listar_principios`
* `listar_notas_principios`
* `salvar_matriz_pendencia`
* `calcular_matriz_pendencia`
* `calcular_matriz_geral`
* `obter_resumo_dashboard`
* `obter_alertas_dashboard`
* `obter_timeline_pendencia`
* `obter_badges_pendencia`
* `calcular_situacao_automatica`
* `registrar_atualizacao`
* `registrar_processo_sei`
* `registrar_responsaveis`

---

## Auditoria

Todas as tabelas operacionais devem ter:

* `ativo`
* `criado_por`
* `criado_em`
* `atualizado_por`
* `atualizado_em`

Preferir exclusão lógica.

Registrar ações importantes no log do sistema, se houver integração disponível.

---

## Permissões

A funcionalidade deve respeitar o padrão atual de permissões do projeto.

Perfis/ações mínimas a considerar:

* visualizar
* criar
* editar
* excluir
* alterar matriz
* exportar

Não reinventar autorização se o projeto já tiver um padrão consolidado.

---

## Exportação futura

Preparar a arquitetura para futura exportação:

* PDF
* Excel
* CSV

Relatórios desejáveis:

* executivo;
* matriz;
* por status;
* por responsável;
* sem prazo;
* críticas.

---

## Resultado esperado

Ao implementar a feature, entregar:

1. migration SQL;
2. schema e tabelas;
3. inserts iniciais;
4. view SQL;
5. blueprint;
6. routes;
7. services;
8. forms;
9. templates;
10. filtros;
11. cards;
12. listagem;
13. detalhe;
14. timeline;
15. matriz;
16. badges automáticos;
17. observações e sugestões técnicas.

---

## Sugestões permanentes

Sempre considerar:

* usar `pendencia_id` em vez de `tema_nome` como FK;
* usar `categoricas.c_geral_status` para dropdowns;
* manter timeline como centro da leitura;
* evitar “tabelão”;
* permitir expansão futura com anexos;
* preparar view ou materialized view para ranking;
* prever exportações;
* destacar visualmente “sem prazo”, “parado”, “vencido”, “crítico” e “aguardando validação”.