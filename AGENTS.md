# AGENTS.md

## Contexto do projeto

Este repositório contém o sistema `fparcerias`, construído em Flask + Jinja + PostgreSQL, com múltiplos módulos internos da SMDHC.

O objetivo do agente é implementar novas funcionalidades respeitando:

* a arquitetura já existente do projeto;
* os padrões visuais do sistema;
* os padrões de rotas, blueprints e templates;
* as convenções de banco de dados;
* a integração com catálogos e tabelas já existentes;
* os helpers e serviços já adotados no projeto.

Antes de implementar qualquer funcionalidade, o agente deve:

1. ler a estrutura atual do projeto;
2. identificar blueprints, services e templates semelhantes;
3. reutilizar padrões existentes em vez de inventar uma arquitetura paralela;
4. evitar duplicação desnecessária;
5. manter consistência com módulos já existentes.

---

## Regras gerais de implementação

### Arquitetura

Sempre que criar uma nova funcionalidade estruturada, preferir a separação:

* `routes.py`
* `services.py`
* `forms.py`
* pasta própria em `templates/`

Se o projeto já tiver outro padrão consolidado para determinados módulos, seguir o padrão existente.

### Banco de dados

O sistema usa PostgreSQL.

Antes de escrever migrations, sempre:

1. verificar o schema correto;
2. verificar se já existe tabela semelhante;
3. verificar se há catálogos ou tabelas gerais reutilizáveis;
4. evitar criar estrutura redundante.

Quando o campo for uma lista controlada ou dropdown, preferir reutilizar:

* `categoricas.c_geral_status`

quando isso fizer sentido para o padrão do projeto.

### Chaves estrangeiras

Preferir sempre relacionamentos por `id` numérico ou chave estável.

Evitar usar campos textuais mutáveis como chave estrangeira, como nomes, títulos ou descrições.

### Auditoria

Sempre que criar novas tabelas operacionais, incluir colunas mínimas de auditoria, salvo se o padrão do projeto for diferente:

* `ativo`
* `criado_por`
* `criado_em`
* `atualizado_por`
* `atualizado_em`

Sempre que fizer sentido, preferir exclusão lógica em vez de exclusão física.

### Logs e rastreabilidade

Se existir helper ou serviço de logs do sistema, registrar:

* criação;
* edição;
* exclusão lógica;
* mudanças de status;
* alterações relevantes de prioridade, matriz ou relacionamento.

---

## Regras de UX/UI

Seguir a padronização visual do sistema.

### Visual

Usar os padrões visuais já adotados no projeto, incluindo quando disponíveis:

* `page-header`
* `.btn-parc`
* `.filter-section`
* `.content-card`
* Bootstrap 5.3
* Bootstrap Icons

### Experiência

Evitar transformar telas de gestão em “planilhas gigantes”.

Priorizar:

* leitura rápida;
* cards;
* badges;
* filtros claros;
* accordion;
* blocos visuais;
* painéis executivos;
* páginas de detalhe bem organizadas.

Tabelas extensas devem ser secundárias, colapsáveis ou ficar em abas separadas.

### Escaneabilidade

Toda tela principal deve responder rapidamente:

* o que é mais importante;
* o que está parado;
* o que precisa de ação;
* quem é responsável;
* qual é o próximo passo.

---

## Regras de código

### Backend

Preferir funções pequenas e reutilizáveis.

Ao criar services:

* separar leitura, escrita, cálculo e resumo;
* evitar lógica SQL espalhada em várias rotas;
* concentrar regras de negócio no service.

### SQL

Quando necessário:

* criar índices coerentes com os filtros principais;
* nomear índices e constraints de forma legível;
* comentar trechos complexos se a regra não for óbvia;
* evitar queries mágicas sem contexto.

### Templates

Nos templates Jinja:

* manter blocos reutilizáveis em partials;
* evitar HTML monolítico;
* separar filtros, cards, lista e modais;
* usar nomes claros.

---

## Regras de entrega

Ao implementar uma feature, o agente deve entregar, quando aplicável:

1. migration SQL;
2. estrutura de arquivos;
3. blueprint;
4. rotas;
5. services;
6. forms;
7. templates;
8. integração com banco;
9. filtros e listagem;
10. página de detalhe;
11. observações finais e sugestões.

---

## O que evitar

Não:

* criar uma solução paralela completamente diferente do resto do projeto;
* usar nomes de tabelas ou rotas inconsistentes com o padrão existente;
* usar FK textual mutável;
* criar dropdown hardcoded quando houver catálogo reaproveitável;
* transformar dashboard em tabela bruta;
* esconder a lógica principal dentro da rota;
* ignorar auditoria.

---

## Como responder às tarefas

Sempre que receber uma tarefa, o agente deve:

1. ler também os arquivos `.md` específicos da feature, quando existirem;
2. resumir internamente o plano;
3. implementar em etapas;
4. explicitar suposições técnicas importantes;
5. apontar melhorias e riscos.

Se houver ambiguidade pequena, fazer a escolha mais consistente com o projeto atual e registrar isso na resposta.