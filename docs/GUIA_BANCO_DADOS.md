# 🗄️ GUIA DO BANCO DE DADOS — FPDH

> **Referência completa de schemas, tabelas e colunas para uso em consultas e desenvolvimento via IA**  
> Gerado a partir do backup: `backup_faf_20260428_143800.sql`  
> Database: `projeto_parcerias` | PostgreSQL 17

---

## 📋 Índice

- [Visão Geral](#-visão-geral)
- [Schema `public`](#-schema-public--core-de-parcerias)
- [Schema `analises_pc`](#-schema-analises_pc--análises-de-prestação-de-contas)
- [Schema `gestao_financeira`](#-schema-gestao_financeira--gestão-financeira)
- [Schema `gestao_pessoas`](#-schema-gestao_pessoas--usuários-e-rh)
- [Schema `categoricas`](#-schema-categoricas--listas-suspensas-e-catálogos)
- [Schema `celebracao`](#-schema-celebracao--celebração-de-parcerias)
- [Módulo Quadro de Metas](#-módulo-quadro-de-metas)
- [Schema `auditoria_memoria`](#-schema-auditoria_memoria)
- [Schema `calendario`](#-schema-calendario--calendário-institucional)
- [Relacionamentos Principais](#-relacionamentos-principais)
- [Índices de Performance](#-índices-de-performance)
- [Extensões e Convenções](#-extensões-e-convenções)

---

## 🏗️ Visão Geral

| Schema | Tabelas | Descrição |
|--------|---------|-----------|
| `public` | 15 | Core de parcerias, certidões, editais, despesas |
| `analises_pc` | 14 | Conciliação bancária, checklists, inconsistências |
| `gestao_financeira` | 8 | Ultra liquidações, cronogramas, empenhos SOF |
| `gestao_pessoas` | 5 | Usuários, logs de atividade e erros |
| `categoricas` | 36 | Listas suspensas e catálogos editáveis |
| `celebracao` | 7 | Processo de celebração de novos termos e Quadro de Metas |
| `auditoria_memoria` | 1 | Auditoria de encaminhamentos de pagamento |
| `calendario` | 5 | Férias, registros pessoais, eventos e documentos |

**Chave primária universal**: `numero_termo` (text/varchar) identifica cada parceria em todas as tabelas relacionadas.

---

## 🟦 Schema `public` — Core de Parcerias

### `public.parcerias` ⭐
Tabela principal. Um registro por termo de parceria (TFM, TCC, TAP).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `numero_termo` | text **PK** | Identificador único do termo (ex: `TFM 001/2024`) |
| `osc` | text | Nome da organização parceira |
| `cnpj` | text | CNPJ da OSC |
| `projeto` | text | Nome do projeto |
| `tipo_termo` | text | TFM / TCC / TAP |
| `portaria` | text | Portaria de autorização |
| `inicio` | date | Início da vigência |
| `final` | date | Fim da vigência |
| `meses` | integer | Duração em meses |
| `total_previsto` | double precision | Valor total previsto |
| `total_pago` | double precision | Valor total pago |
| `conta` | text | Conta bancária da OSC |
| `transicao` | integer | Flag de transição |
| `sei_celeb` | text | Processo SEI da celebração |
| `sei_pc` | text | Processo SEI de prestação de contas |
| `sei_plano` | text | Processo SEI do plano de trabalho |
| `sei_orcamento` | text | Processo SEI do orçamento |
| `endereco` | text | Endereço principal |
| `contrapartida` | integer | Flag de contrapartida |
| `edital_nome` | varchar(50) | Edital de origem |
| `data_criacao` | timestamp | Data de cadastro |

---

### `public.parcerias_infos_adicionais`
Complemento da parceria com dados do projeto.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | Referência à parceria |
| `parceria_responsavel_legal` | varchar(300) | Responsável legal da OSC |
| `parceria_objeto` | text | Objeto do termo |
| `parceria_beneficiarios_diretos` | integer | Qtd beneficiários diretos |
| `parceria_beneficiarios_indiretos` | integer | Qtd beneficiários indiretos |
| `parceria_justificativa_projeto` | text | Justificativa do projeto |
| `parceria_abrangencia_projeto` | text | Abrangência territorial |
| `parceria_data_suspensao` | date | Data de suspensão (se houver) |
| `parceria_data_retomada` | date | Data de retomada (se houver) |
| `criado_em` | timestamp | |
| `atualizado_em` | timestamp | |

---

### `public.parcerias_enderecos`
Múltiplos endereços por parceria (locais de execução do projeto).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `parceria_logradouro` | text | Rua/Avenida |
| `parceria_complemento` | varchar(30) | Complemento |
| `parceria_numero` | integer | Número |
| `parceria_cep` | varchar(10) | CEP |
| `parceria_distrito` | varchar(100) | Distrito de SP |
| `observacao` | text | |
| `criado_em` | timestamp | |
| `atualizado_em` | timestamp | |

---

### `public.parcerias_sei`
Documentos SEI vinculados à parceria (aditamentos, apostilamentos, etc.).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `aditamento` | varchar(2) | Número do aditamento |
| `apostilamento` | varchar(2) | Número do apostilamento |
| `termo_sei_doc` | varchar(12) | Número do documento SEI |
| `termo_tipo_sei` | varchar(80) | Tipo do documento SEI |
| `termo_outros_sei` | varchar(30) | Outros documentos |
| `criado_em` | timestamp | |
| `data_assinatura` | date | Data de assinatura |

---

### `public.parcerias_pg`
Histórico de pessoas gestoras (PG) responsáveis por cada parceria.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(255) FK | |
| `nome_pg` | varchar(255) | Nome da pessoa gestora |
| `data_de_criacao` | timestamp | Data do vínculo |
| `usuario_id` | integer | FK para usuário |
| `dado_anterior` | varchar(200) | PG anterior (histórico) |
| `solicitacao` | boolean | É uma solicitação pendente |

---

### `public.termos_alteracoes` ⭐
Registro de todas as alterações DGP (25+ tipos).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(50) FK | |
| `instrumento_alteracao` | varchar(80) | Tipo de instrumento (Aditamento, Apostilamento...) |
| `alt_numero` | integer | Número sequencial da alteração |
| `alt_tipo` | varchar(100) | Tipo específico da alteração |
| `alt_status` | varchar(30) | Status atual |
| `alt_info` | text | Novo valor |
| `alt_old_info` | text | Valor anterior |
| `alt_responsavel` | varchar(80) | Responsável pela alteração |
| `alt_data_cadastro_inicio` | timestamp | Data de início do processo |
| `alt_data_cadastro_fim` | timestamp | Data de conclusão |
| `alt_observacao` | text | Observações |
| `criado_por` | varchar(80) | Usuário criador |
| `atualizado_por` | varchar(80) | Último usuário a editar |
| `atualizado_em` | timestamp | |

---

### `public.termos_rescisao`
Registro de termos rescindidos.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | bigint PK | |
| `numero_termo` | varchar(30) FK | |
| `data_rescisao` | date | Data da rescisão |
| `sei_rescisao` | varchar(12) | Processo SEI da rescisão |
| `responsavel_rescisao` | text | Responsável |

---

### `public.parcerias_despesas`
Despesas mensais por rubrica de cada parceria.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | text FK | |
| `rubrica` | text | Nome da rubrica |
| `quantidade` | integer | Quantidade (≥ 0) |
| `categoria_despesa` | text | Categoria (custeio, investimento...) |
| `valor` | double precision | Valor (≥ 0) |
| `mes` | integer | Mês (1–60) |
| `ano` | integer | Ano de referência |
| `aditivo` | integer | Número do aditivo |
| `criado_em` | timestamp | |

---

### `public.parcerias_despesas_obs`
Observações avulsas sobre despesas de uma parceria.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `observacoes` | text | |
| `responsavel` | varchar(100) | |
| `criado_em` | timestamp | |
| `atualizado_em` | timestamp | |

---

### `public.parcerias_analises`
Controle do fluxo de análise de prestação de contas.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `tipo_prestacao` | varchar(20) | Tipo (parcial, final...) |
| `numero_prestacao` | integer | Número da prestação |
| `vigencia_inicial` | date | |
| `vigencia_final` | date | |
| `numero_termo` | varchar(100) FK | |
| `responsabilidade_analise` | integer | FK para analista |
| `entregue` | boolean | Documentos entregues |
| `cobrado` | boolean | Cobrança realizada |
| `e_notificacao` | boolean | Notificação emitida |
| `e_parecer` | boolean | Parecer emitido |
| `e_fase_recursal` | boolean | Em fase recursal |
| `e_encerramento` | boolean | Encerrado |
| `data_parecer_dp` | date | Data do parecer DP |
| `valor_devolucao` | numeric(15,2) | Valor a devolver |
| `valor_devolvido` | numeric(15,2) | Valor efetivamente devolvido |
| `responsavel_dp` | integer | Analista DP responsável |
| `data_parecer_pg` | date | Data do parecer PG |
| `responsavel_pg` | varchar(100) | PG responsável |
| `observacoes` | text | |

---

### `public.parcerias_notificacoes`
Notificações e comunicados oficiais (DOC, AR, etc.).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `tipo_doc` | varchar(100) | Tipo (DOC, Portaria...) |
| `ano_doc` | integer | Ano do documento |
| `numero_doc` | integer | Número do documento |
| `numero_termo` | varchar(50) FK | |
| `nome_responsavel` | varchar(80) | |
| `data_doc` | date | Data de emissão |
| `data_pub` | date | Data de publicação |
| `data_email_ar` | timestamp with tz | Data de envio do e-mail AR |
| `dilacao` | boolean | Houve dilação de prazo |
| `dilacao_dias` | integer | Dias de dilação |
| `sei_doc` | varchar(12) | Número do documento SEI |
| `processo_doc` | varchar(30) | Número do processo SEI |
| `observacoes` | text | |
| `doc_respondido` | boolean | Já foi respondido |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

---

### `public.certidoes` ⭐
Central de certidões — 7 certidões obrigatórias por OSC.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `osc` | text | Nome da OSC |
| `cnpj` | varchar(20) | CNPJ da OSC |
| `certidao_nome` | varchar(120) | Nome (CNPJ, CND, CNDT, CRF, CADIN, CTM, CENTS) |
| `certidao_emissor` | varchar(100) | Órgão emissor |
| `certidao_vencimento` | date | Data de vencimento |
| `certidao_path` | text | Caminho do arquivo PDF |
| `certidao_arquivo_nome` | varchar(255) | Nome do arquivo |
| `certidao_arquivo_size` | bigint | Tamanho em bytes (máx. 300KB) |
| `certidao_status` | varchar(30) | `válida` / `vence breve` / `vencida` |
| `observacoes` | text | |
| `created_at` | timestamp | |
| `updated_at` | timestamp | |

---

### `public.parcerias_edital`
Cadastro de editais vinculados a parcerias.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `edital_tipo` | varchar(30) | Tipo do edital |
| `edital_nome` | varchar(40) | Nome do edital |
| `edital_ano` | integer | Ano |
| `edital_unidade_gestora` | varchar(60) | Unidade gestora |
| `edital_responsavel` | varchar(10) | RF do responsável |
| `edital_processo_sei` | varchar(20) | Processo SEI |
| `edital_objeto` | text | Objeto do edital |
| `edital_data_publicacao` | date | Data de publicação |
| `edital_data_homologacao` | date | Data de homologação |
| `status` | varchar(60) | Em elaboração / Publicado / Homologado / Cancelado |
| `criado_em` | timestamp | |

---

### `public.parcerias_emendas`
Emendas vereadores vinculadas a parcerias.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `sei_celeb` | varchar(30) | Processo SEI da celebração |
| `vereador_nome` | varchar(120) | |
| `status` | varchar(30) | |
| `valor` | numeric(14,2) | Valor da emenda |
| `celebracao_emenda_id` | integer | FK para `celebracao.celebracao_emendas` |
| `observacoes` | text | |
| `criado_em` | timestamp | |
| `atualizado_em` | timestamp | |

---

### `public.osc_contatos`
Contatos das organizações parceiras.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `osc` | varchar(200) | Nome da OSC |
| `contato_nome` | varchar(100) | |
| `contato_posicao` | varchar(100) | Cargo/função |
| `contato_tipo` | varchar(40) | E-mail / Telefone / WhatsApp |
| `contato_info` | text | Dado de contato |
| `responsavel` | varchar(100) | Servidor que cadastrou |
| `status` | varchar(20) | Ativo / Inativo |
| `observacao` | text | |
| `criado_em` | timestamp | |
| `atualizado_em` | timestamp | |
| `atualizado_por` | varchar(100) | |

---

### `public.o_pesquisa_parcerias`
Registro de pesquisas de parcerias (consultas de termos).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_pesquisa` | integer | |
| `sei_informado` | varchar(20) | SEI informado na pesquisa |
| `nome_osc` | varchar(150) | |
| `cnpj` | varchar(18) | |
| `nome_emissor` | varchar(100) | |
| `osc_identificada` | boolean | Se a OSC foi localizada |
| `respondido` | boolean | Se a pesquisa foi respondida |
| `psei_pesquisa` | varchar(20) | Processo SEI da pesquisa |
| `obs` | text | |
| `criado_em` | timestamp | |

---

### `public.instrucoes`
Instruções e checklists do sistema.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `titulo` | text | |
| `texto` | text | Conteúdo HTML |
| `categoria` | text | |
| `data_criacao` | timestamp | |

---

### `public.manuais_documentos`
Documentos/arquivos dos manuais.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `manual_id` | integer FK | Referência para `manuais_lista` |
| `manual_nome` | text | Nome do documento |
| `manual_doc` | text | Arquivo ou conteúdo |
| `manual_link` | text | URL ou caminho |
| `manual_versionamento` | text | Versão |
| `manual_status` | varchar(30) | Ativo / Arquivado |
| `manual_descricao` | text | |
| `tipo_doc` | text | |
| `publico_alvo` | text | |
| `manual_pendencias` | text | |
| `criado_por` | varchar(100) | |
| `criado_em` | timestamp with tz | |
| `atualizado_por` | varchar(100) | |
| `atualizado_em` | timestamp with tz | |

---

### `public.manuais_lista`
Catálogo de manuais disponíveis.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `manual_tipo` | text | Tipo do manual |
| `manual_nome` | text | Nome |
| `manual_status` | text | |
| `manual_relacionamento` | text | |
| `manual_descricao` | text | |
| `manual_area` | text | Área responsável |
| `criado_por` | text | |
| `criado_em` | timestamp with tz | |

---

### `public.contatos_vereadores`
Contatos de gabinetes de vereadores.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `vereador_nome` | varchar(200) | |
| `contato_nome` | varchar(100) | |
| `contato_posicao` | varchar(100) | |
| `contato_tipo` | varchar(40) | |
| `contato_info` | text | |
| `responsavel` | varchar(100) | |
| `status` | varchar(20) | |
| `observacao` | text | |
| `criado_em` | timestamp | |

---

## 🟩 Schema `analises_pc` — Análises de Prestação de Contas

### `analises_pc.checklist_termo` ⭐
Controle das 15 etapas da análise de PC por parceria/período.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | bigint PK | |
| `numero_termo` | varchar(80) FK | |
| `meses_analisados` | varchar(8) | Período analisado (ex: `01-2024`) |
| `avaliacao_celebracao` | boolean | Etapa 1 |
| `avaliacao_prestacao_contas` | boolean | Etapa 2 |
| `preenchimento_dados_base` | boolean | Etapa 3 |
| `preenchimento_orcamento_anual` | boolean | Etapa 4 |
| `preenchimento_conciliacao_bancaria` | boolean | Etapa 5 |
| `avaliacao_dados_bancarios` | boolean | Etapa 6 |
| `documentos_sei_1` | boolean | Etapa 7 |
| `avaliacao_resposta_inconsistencia` | boolean | Etapa 8 |
| `emissao_parecer` | boolean | Etapa 9 |
| `documentos_sei_2` | boolean | Etapa 10 |
| `tratativas_restituicao` | boolean | Etapa 11 |
| `encaminhamento_encerramento` | boolean | Etapa 12 |

---

### `analises_pc.checklist_analista`
Analista responsável por um processo de análise.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | bigint PK | |
| `numero_termo` | varchar(80) FK | |
| `meses_analisados` | varchar(8) | Período |
| `nome_analista` | varchar(80) | |

---

### `analises_pc.checklist_change_log`
Log de alterações no checklist de análise.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | bigint PK | |
| `numero_termo` | varchar(80) FK | |
| `meses_analisados` | varchar(8) | |
| `tabela_origem` | varchar(40) | Tabela alterada |
| `coluna_alterada` | varchar(40) | Campo alterado |
| `valor_anterior` | varchar(120) | Valor antes |
| `valor_novo` | varchar(120) | Valor depois |
| `usuario` | varchar(120) | Usuário responsável |
| `data_alteracao` | timestamp | |

---

### `analises_pc.checklist_recursos`
Etapas de fases recursais.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | bigint PK | |
| `numero_termo` | varchar(80) FK | |
| `meses_analisados` | varchar(8) | |
| `tipo_recurso` | integer | Número do recurso |
| `avaliacao_resposta_recursal` | boolean | |
| `emissao_parecer_recursal` | boolean | |
| `documentos_sei` | boolean | |

---

### `analises_pc.conc_extrato` ⭐
Extrato bancário importado para conciliação.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `indice` | integer | Ordem no extrato |
| `data` | date | Data da transação |
| `credito` | numeric(18,2) | Valor de crédito |
| `debito` | numeric(18,2) | Valor de débito |
| `discriminacao` | numeric(18,2) | |
| `cat_transacao` | text | Categoria (IA ou manual) |
| `competencia` | date | Competência da despesa |
| `origem_destino` | text | Favorecido/origem |
| `cat_avaliacao` | varchar(30) | `Aprovado` / `Com ressalva` / `Reprovado` |
| `avaliacao_analista` | text | Comentário do analista |
| `numero_termo` | varchar(80) FK | |
| `mesclado_com` | integer[] | IDs mesclados (array) |

---

### `analises_pc.conc_extrato_notas_fiscais`
Notas fiscais vinculadas a lançamentos do extrato.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `conc_extrato_id` | integer FK | |
| `numero_nota` | integer | |
| `chave_acesso` | varchar(100) | Chave NF-e |
| `cnpj_nota` | varchar(20) | CNPJ do emitente |
| `numero_termo` | varchar(80) FK | |

---

### `analises_pc.conc_analise`
Avaliações de comprovantes por lançamento.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `conc_extrato_id` | integer FK | |
| `avaliacao_guia` | varchar(50) | Guia de recolhimento |
| `avaliacao_comprovante` | varchar(50) | Comprovante de pagamento |
| `avaliacao_contratos` | varchar(50) | Contratos |
| `avaliacao_fora_municipio` | varchar(50) | Despesa fora do município |
| `created_at` | timestamp | |

---

### `analises_pc.conc_banco`
Dados gerais da conta bancária analisada.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `banco_extrato` | text | Banco do extrato |
| `descontos_realizados` | numeric(18,2) | |
| `conta_execucao` | varchar(30) | Número da conta |

---

### `analises_pc.conc_contrapartida`
Contrapartida da OSC por competência.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `competencia` | date | Mês/ano de referência |
| `categoria_despesa` | varchar(200) | |
| `valor_previsto` | numeric(18,2) | |
| `valor_executado` | numeric(18,2) | |
| `valor_considerado` | numeric(18,2) | |
| `guia` | varchar(50) | |
| `comprovante` | varchar(50) | |
| `observacoes` | text | |
| `created_at` | timestamp | |

---

### `analises_pc.conc_rendimentos`
Rendimentos de aplicações financeiras.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `rendimento_bruto` | numeric(18,2) | |
| `rendimento_ir` | numeric(18,2) | IR retido |
| `rendimento_iof` | numeric(18,2) | IOF retido |
| `data_referencia` | date | |
| `observacoes` | text | |
| `created_at` | timestamp | |

---

### `analises_pc.lista_inconsistencias`
Inconsistências identificadas na análise.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `nome_item` | varchar(60) | Tipo de inconsistência |
| `id_conc_extrato` | integer FK | Lançamento relacionado |
| `data` | date | |
| `credito` | numeric(18,2) | |
| `debito` | numeric(18,2) | |
| `status` | varchar(20) | `Não atendida` / `Atendida` |
| `usuario_registro` | varchar(80) | |
| `numero_termo` | varchar(80) FK | |
| `criado_em` | timestamp | |
| `atualizado_em` | timestamp | |

---

### `analises_pc.lista_inconsistencias_agregadas`
Inconsistências por grupo (rubrica, competência, etc.).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `nome_item` | varchar(255) | |
| `numero_termo` | varchar(50) FK | |
| `tipo_agregacao` | varchar(50) | |
| `campo1` | varchar(255) | |
| `campo2` | varchar(50) | |
| `valor_previsto` | numeric(15,2) | |
| `valor_executado` | numeric(15,2) | |
| `diferenca` | numeric(15,2) | |
| `status` | varchar(50) | |
| `usuario` | varchar(255) | |
| `data_registro` | timestamp | |

---

### `analises_pc.lista_inconsistencias_globais`
Inconsistências consolidadas (texto final).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `nome_item` | varchar(255) | |
| `numero_termo` | varchar(50) FK | |
| `status` | varchar(50) | |
| `texto` | text | Texto final da inconsistência |
| `usuario` | varchar(255) | |
| `data_ratificacao` | timestamp | |

---

### `analises_pc.conc_extrato_inconsistencia_recursos`
Recursos recursais vinculados a inconsistências.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `inconsistencia_id` | integer FK | |
| `recurso_numero` | integer | |
| `valor_supressao_desconto` | numeric(18,2) | |
| `valor_manutencao_desconto` | numeric(18,2) | |
| `argumentacao_analista` | text | |
| `data_recurso` | date | |
| `numero_termo` | varchar(80) FK | |
| `created_at` | timestamp | |

---

## 🟨 Schema `gestao_financeira` — Gestão Financeira

### `gestao_financeira.ultra_liquidacoes` ⭐
Cronograma de parcelas e liquidações por termo.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `vigencia_inicial` | date | |
| `vigencia_final` | date | |
| `parcela_tipo` | varchar(80) | `Programada` / `Projetada` / `Parcela Única` |
| `parcela_numero` | varchar(50) | Identificador da parcela |
| `valor_elemento_53_23` | numeric(18,2) | Elemento de despesa 53-23 (custeio) |
| `valor_elemento_53_24` | numeric(18,2) | Elemento de despesa 53-24 (investimento) |
| `valor_previsto` | numeric(18,2) | Valor total previsto |
| `valor_subtraido` | numeric(18,2) | Valor subtraído |
| `valor_encaminhado` | numeric(18,2) | Valor encaminhado |
| `valor_pago` | numeric(18,2) | Valor efetivamente pago |
| `parcela_status` | varchar(80) | `Não Pago` / `Pago` / `Cancelado`... |
| `parcela_status_secundario` | varchar(30) | Status complementar |
| `parcela_andamento` | varchar(300) | Andamento atual |
| `data_pagamento` | date | Data do pagamento |
| `observacoes` | text | |
| `created_por` | varchar(80) | |
| `created_em` | timestamp | |
| `atualizado_por` | varchar(80) | |
| `atualizado_em` | timestamp | |

---

### `gestao_financeira.ultra_liquidacoes_cronograma`
Cronograma mensal detalhado por parcela (FASE 1/2/3).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `parcela_numero` | varchar(50) | Referência para `ultra_liquidacoes` |
| `nome_mes` | date | Data (primeiro dia do mês) |
| `valor_mes` | numeric(18,2) | Valor total do mês |
| `valor_mes_23` | numeric(18,2) | Elemento 53-23 do mês |
| `valor_mes_24` | numeric(18,2) | Elemento 53-24 do mês |
| `info_alteracao` | text | Motivo da última alteração |
| `created_por` | varchar(80) | |
| `created_em` | timestamp | |
| `atualizado_por` | varchar(80) | |
| `atualizado_em` | timestamp | |

---

### `gestao_financeira.temp_reservas_empenhos`
Controle de reservas e empenhos por parcela.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(80) FK | |
| `vigencia_inicial` | date | |
| `vigencia_final` | date | |
| `aditivo` | varchar(2) | |
| `numero_parcela` | varchar(60) | |
| `tipo_parcela` | varchar(40) | |
| `elemento_23` | numeric(18,2) | |
| `elemento_24` | numeric(18,2) | |
| `parcela_total_previsto` | numeric(18,2) | |
| `observacao` | text | |
| `usuario_registro` | varchar(80) | |
| `criado_em` | timestamp | |
| `atualizado_em` | timestamp | |

---

### `gestao_financeira.temp_acomp_empenhos`
Acompanhamento de notas de empenho por parcela.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero` | integer | |
| `aditivo` | varchar(2) | |
| `numero_termo` | varchar(80) FK | |
| `responsavel` | varchar(100) | |
| `status` | varchar(30) | Default: `DEOF: Enviado para empenho` |
| `nota_empenho_23` | varchar(60) | NE elemento 53-23 |
| `sei_nota_empenho_23` | varchar(12) | SEI da NE 53-23 |
| `nota_empenho_24` | varchar(60) | NE elemento 53-24 |
| `sei_nota_empenho_24` | varchar(12) | SEI da NE 53-24 |
| `total_empenhado_23` | numeric(18,2) | |
| `total_empenhado_24` | numeric(18,2) | |
| `observacoes` | text | |
| `criado_em` | timestamp | |

---

### `gestao_financeira.orcamento_edital_nova`
Orçamento por edital (nova estrutura).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `edital_nome` | varchar(60) | |
| `edital_tipo` | varchar(30) | |
| `edital_unidade` | varchar(20) | |
| `dotacao_formatada` | varchar(120) | Código da dotação |
| `projeto_atividade` | varchar(10) | |
| `valor_mes` | numeric(18,2) | Valor do mês |
| `nome_mes` | date | Primeiro dia do mês |
| `etapa` | varchar(70) | |
| `observacoes` | text | |
| `created_por` | varchar(80) | |
| `created_em` | timestamp | |

---

### `gestao_financeira.back_dotacao`
Backup de dotações orçamentárias importadas do SOF.

> Tabela de importação do SOF (Sistema de Orçamento e Finanças da PMSP). Contém ~50 colunas com códigos e valores orçamentários. Principais campos:

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `cod_idt_dota` | integer PK | |
| `dotacao_formatada` | varchar(255) | Dotação completa formatada |
| `orcado_atual` | varchar(40) | Orçado atual |
| `orcado_disponivel` | varchar(40) | Saldo disponível |
| `saldo_dotacao` | varchar(40) | Saldo da dotação |
| `saldo_empenhado` | varchar(40) | |
| `saldo_reservado` | varchar(40) | |
| `criado_em` | timestamp | |

---

### `gestao_financeira.back_empenhos`
Backup de empenhos importados do SOF.

> Tabela de importação do SOF. Principais campos:

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `cod_idt_eph` | integer PK | |
| `dt_eph` | timestamp | Data do empenho |
| `cod_eph` | integer | Número do empenho |
| `val_tot_eph` | varchar(40) | Valor total |
| `val_tot_lqdc_eph` | varchar(40) | Valor liquidado |
| `val_tot_pago_eph` | varchar(40) | Valor pago |
| `nom_rzao_soci_sof` | varchar(120) | Razão social do credor |
| `cod_cpf_cnpj_sof` | varchar(20) | CPF/CNPJ do credor |
| `txt_dotacao_fmt` | varchar(255) | Dotação formatada |
| `fonte_relatorio` | varchar(20) | |

---

### `gestao_financeira.back_reservas`
Backup de reservas orçamentárias importadas do SOF.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `cod_resv_dota_sof` | integer PK | |
| `dt_efet_resv` | timestamp | Data da reserva |
| `dotacao_formatada` | varchar(60) | |
| `vl_resv` | varchar(30) | Valor da reserva |
| `vl_saldo_resv` | varchar(30) | Saldo da reserva |
| `fonte_relatorio` | text | |

---

### `gestao_financeira.back_liquidacao`
Backup de liquidações importadas do SOF.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `cod_idt_eph_mvto` | text PK | |
| `dt_mvto_eph` | date | Data do movimento |
| `val_mvto_eph` | text | Valor do movimento |
| `dt_pgto` | date | Data do pagamento |
| `vl_liquido` | text | Valor líquido |
| `nom_rzao_soci_sof` | text | Razão social do credor |
| `cod_cpf_cnpj_sof` | text | |

---

## 🟪 Schema `gestao_pessoas` — Usuários e RH

### `gestao_pessoas.usuarios` ⭐
Controle de autenticação e acesso ao sistema.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `email` | text UNIQUE | Login do usuário |
| `senha` | text | Hash (scrypt via Werkzeug) |
| `tipo_usuario` | text | `Agente Público` / `Pessoa Gestora` |
| `d_usuario` | varchar(10) | Código do usuário |
| `acessos` | text | Módulos separados por `;` (ex: `parcerias;orcamento`) |
| `data_criacao` | timestamp | |
| `data_ultimo_login` | timestamp | |
| `session_token` | text | Token de sessão ativo |
| `reset_token` | varchar(6) | Token de redefinição de senha |
| `reset_token_expira` | timestamp | Expiração do token de redefinição |
| `ultima_atividade` | timestamp | Última ação registrada |

---

### `gestao_pessoas.usuarios_infos`
Informações pessoais dos usuários.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `usuario_email` | text FK | |
| `usuario_status` | text | Ativo / Inativo |
| `usuario_nome` | text | Nome completo |
| `usuario_aniversario` | date | Data de aniversário (usado no calendário) |
| `usuario_vinculo` | text | Tipo de vínculo funcional |
| `visualizar_todos_eventos` | boolean | Permite ver todos os eventos institucionais |
| `criado_por` | text | |
| `criado_em` | timestamp | |

---

### `gestao_pessoas.smdhc_servidores`
Cadastro de servidores da SMDHC.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `cda` | integer | Código CDA |
| `numero_vaga` | integer | |
| `nome_servidor` | text | |
| `numero_rf` | bigint | Registro funcional |
| `unidade` | text | Unidade de lotação |
| `nome_unidade` | text | Nome da unidade |
| `data_publicacao` | date | |
| `data_encerramento` | date | |
| `observacoes` | text | |
| `created_at` | timestamp with tz | |

---

### `gestao_pessoas.log_atividades` ⭐
Auditoria completa de todas as ações dos usuários.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `usuario_nome` | varchar(200) | |
| `usuario_email` | varchar(200) | |
| `tipo_usuario` | varchar(50) | |
| `acao_tipo` | varchar(50) | `CREATE` / `UPDATE` / `DELETE` / `VIEW` |
| `acao_categoria` | varchar(100) | Módulo/categoria da ação |
| `acao_endpoint` | varchar(500) | URL acessada |
| `acao_metodo` | varchar(10) | HTTP method |
| `recurso_tipo` | varchar(100) | Tipo do recurso (parceria, certidão...) |
| `recurso_id` | varchar(200) | ID do recurso afetado |
| `acao_descricao` | text | Descrição legível da ação |
| `ip_address` | varchar(45) | IP do usuário |
| `user_agent` | text | |
| `status_codigo` | integer | HTTP status |
| `sucesso` | boolean | |
| `erro_mensagem` | text | |
| `duracao_ms` | integer | Tempo de resposta em ms |
| `detalhes` | jsonb | Dados adicionais em JSON |
| `created_at` | timestamp | |

---

### `gestao_pessoas.log_erros` ⭐
Log de erros HTTP, queries lentas e falhas em APIs externas.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `tipo_erro` | varchar(50) | `http_error` / `slow_query` / `api_failure` |
| `endpoint` | varchar(500) | |
| `metodo` | varchar(10) | |
| `status_codigo` | integer | |
| `usuario_email` | varchar(255) | |
| `ip_address` | varchar(45) | |
| `duracao_ms` | integer | |
| `query_preview` | text | Trecho da query lenta |
| `api_nome` | varchar(100) | API que falhou |
| `api_endpoint` | varchar(500) | |
| `mensagem` | text | Mensagem de erro |
| `detalhes` | jsonb | |
| `resolvido` | boolean | Se o erro foi marcado como resolvido |
| `resolvido_em` | timestamp with tz | |
| `resolvido_por` | varchar(255) | |
| `created_at` | timestamp with tz | |

---

## 🟧 Schema `categoricas` — Listas Suspensas e Catálogos

> Todas as tabelas neste schema seguem o padrão de **catálogos editáveis** pelo módulo de Listas (`/listas`).

### Catálogos DGP

| Tabela | Descrição | Colunas-chave |
|--------|-----------|---------------|
| `c_dgp_analistas` | Agentes da DGP | `nome_analista`, `rf`, `email`, `status`, `visualizacao_geral` |
| `c_dgp_celebracao_status` | Status de celebração | `status_novo`, `status_antigo`, `status_generico` |
| `c_dgp_celebracao_substatus` | Substatus de celebração | `substatus`, `responsabilidade_status`, `substatus_limite` |
| `c_dgp_cents_status` | Status de CENTS | `cents_status`, `descricao`, `status_status` |
| `c_dgp_meta_tipos` | ⭐ **Novo** Tipos de meta (Qualitativo, Impacto...) | `meta_tipo`, `tipo_classificacao` |
| `c_dgp_indicadores` | ⭐ **Novo** Catálogo de indicadores | `indicador`, `descricao` |
| `c_dgp_meios_afericao` | ⭐ **Novo** Meios de aferição | `meios_afericao`, `descricao` |
| `c_dgp_plano_definicoes` | ⭐ **Novo** Glossário de ajuda ao preenchimento | `meta_definicao`, `indicador_definicao`, `meios_definicoes` |

### Catálogos DAC

| Tabela | Descrição | Colunas-chave |
|--------|-----------|---------------|
| `c_dac_analistas` | Analistas da DAC | `nome_analista`, `status`, `posicao_analista`, `contrato_inicio`, `contrato_fim` |
| `c_dac_despesas_analise` | Categorias de despesa | `categoria_extra`, `tipo_transacao`, `correspondente`, `aplicacao` |
| `c_dac_despesas_provisao` | Despesas de provisão | `despesa_provisao`, `descricao` |
| `c_dac_modelo_textos_inconsistencias` | Modelos de inconsistência | `nome_item`, `tipo_inconsistencia`, `modelo_texto`, `nivel_gravidade` |
| `c_dac_parcela_andamento_status` | Status de andamento | `status_parcela`, `status_status` |
| `c_dac_responsabilidade_analise` | Setores responsáveis | `nome_setor` |
| `c_dac_status_pagamento` | Status de pagamento | `status_principal`, `status_secundario` |
| `c_dac_tipos_parcelas` | Tipos de parcelas | `parcela_tipo`, `status` |

### Catálogos de Alterações (ALT)

| Tabela | Descrição | Colunas-chave |
|--------|-----------|---------------|
| `c_alt_tipo` | ⭐ 25+ tipos de alteração | `alt_tipo`, `alt_modalidade`, `alt_escopo`, `alt_campo`, `alt_instrumento`, `alt_principios` |
| `c_alt_instrumento` | Instrumentos jurídicos | `instrumento_alteracao`, `descricao`, `status` |
| `c_alt_normas` | Normas e regimentos | `norma`, `regimento`, `referencia_legal`, `data_aplicacao` |
| `c_alt_principios` | Princípios aplicáveis | `nome_principio`, `descricao_principio`, `exemplo_principio` |

### Catálogos Gerais

| Tabela | Descrição | Colunas-chave |
|--------|-----------|---------------|
| `c_geral_certidoes` | 7 tipos de certidão | `certidao_nome_completo`, `certidao_nome_resumido`, `certidao_prazo` |
| `c_geral_dotacoes` | Dotações orçamentárias | `dotacao_numero`, `programa_aplicacao`, `coordenacao` |
| `c_geral_legislacao` | Portarias e leis | `lei`, `inicio`, `termino` |
| `c_geral_modelo_textos` | Modelos de texto geral | `titulo_texto`, `modelo_texto`, `categoria_texto` |
| `c_geral_origem_recurso` | Origens de recurso | `orgao`, `unidade` |
| `c_geral_pessoa_gestora` | Pessoas gestoras | `nome_pg`, `setor`, `numero_rf`, `status_pg`, `email_pg` |
| `c_geral_regionalizacao` | Distritos de SP | `distrito`, `subprefeitura`, `regiao`, `codigo_distrital` |
| `c_geral_tipo_contrato` | Tipos de contrato | `informacao`, `sigla` |
| `c_geral_tipos_doc_sei` | Tipos de documentos SEI | `tipo_doc`, `descricao` |
| `c_geral_tipos_documentos_manuais` | Tipos de manuais | `tipos_documentos` |
| `c_geral_coordenadores` | Coordenadores por setor | `coordenacao`, `nome_c`, `rf_c`, `email_c`, `pronome` |
| `c_geral_status_documentos` | Status de documentos | `status_manuais` |
| `c_geral_vereadores` | Vereadores da Câmara | `vereador_nome`, `partido`, `legislatura_numero`, `situacao` |

### Catálogos de Documentos

| Tabela | Descrição | Colunas-chave |
|--------|-----------|---------------|
| `c_dp_documentos` | Documentos obrigatórios | `tipo_documento`, `orgao_emissor`, `prazo_doc`, `tipo_usuario` |
| `c_documentos_dp_prazos` | Prazos legais | `tipo_documento`, `lei`, `prazo_dias` |
| `c_dp_status_edital` | Status de editais | `status`, `descricao` |

### `categoricas.central_modelos`
Modelos de documentos disponíveis no sistema.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `nome` | varchar(255) | Nome do modelo |
| `arquivo` | varchar(255) | Caminho do arquivo |
| `icone` | varchar(10) | Emoji de ícone |
| `descricao` | text | |
| `ordem` | integer | Ordem de exibição |
| `ativo` | boolean | |
| `criado_em` | timestamp | |

---

## 🟥 Schema `celebracao` — Celebração de Parcerias

### `celebracao.celebracao_parcerias` ⭐
Processo de celebração de novos termos (pré-assinatura).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(60) | Número do termo (após formalização) |
| `sei_celeb` | varchar(30) | Processo SEI da celebração |
| `edital_nome` | varchar(60) | |
| `unidade_gestora` | varchar(10) | |
| `tipo_termo` | varchar(60) | TFM / TCC / TAP |
| `osc` | text | |
| `cnpj` | varchar(60) | |
| `status` | varchar(100) | Status da celebração |
| `substatus` | varchar(200) | Substatus |
| `status_generico` | varchar(40) | Status simplificado |
| `projeto` | text | |
| `endereco_sede` | text | |
| `meses` | integer | |
| `dias` | integer | |
| `total_previsto` | numeric(18,2) | |
| `conta` | varchar(40) | Conta bancária |
| `lei` | varchar(40) | Lei de referência |
| `nome_pg` | varchar(255) | Pessoa gestora |
| `responsavel` | varchar(300) | Responsável legal |
| `numeracao_termo` | integer | Número sequencial |
| `inicio` | date | |
| `final` | date | |
| `assinatura` | date | Data de assinatura |
| `celebracao_secretaria` | varchar(10) | |
| `observacoes` | text | |
| `created_por` | text | |
| `created_at` | timestamp | |
| `atualizado_por` | varchar(150) | |
| `atualizado_at` | timestamp | |

---

### `celebracao.celebracao_parcerias_enderecos`
Endereços do processo de celebração.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `sei_celeb` | varchar(30) FK | |
| `parceria_logradouro` | text | |
| `parceria_complemento` | varchar(255) | |
| `parceria_numero` | integer | |
| `parceria_cep` | varchar(12) | |
| `parceria_distrito` | varchar(120) | |
| `observacao` | text | |
| `criado_em` | timestamp | |
| `atualizado_em` | timestamp | |

---

### `celebracao.celebracao_parcerias_infos_adicionais`
Informações adicionais do processo de celebração.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `sei_celeb` | varchar(30) FK | |
| `parceria_responsavel_legal` | varchar(300) | |
| `parceria_objeto` | text | |
| `parceria_beneficiarios_diretos` | integer | |
| `parceria_beneficiarios_indiretos` | integer | |
| `parceria_justificativa_projeto` | text | |
| `parceria_abrangencia_projeto` | text | |
| `criado_em` | timestamp | |
| `atualizado_em` | timestamp | |

---

### `celebracao.celebracao_parcerias_sei`
Documentos SEI do processo de celebração.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `sei_celeb` | varchar(30) FK | |
| `termo_sei_doc` | varchar(12) | Número do documento SEI |
| `termo_tipo_sei` | varchar(80) | Tipo do documento |
| `created_por` | varchar(150) | |
| `created_at` | timestamp | |

---

### `celebracao.celebracao_emendas`
Emendas parlamentares vinculadas a celebrações.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `sei_orcamentario` | varchar(30) | |
| `sei_celeb` | varchar(30) FK | |
| `projeto` | text | |
| `numero_memorando` | integer | |
| `numero_consulta` | integer | |
| `disponibilidade_orcamentaria` | varchar(50) | |
| `status` | varchar(30) | |
| `criado_por` | varchar(150) | |
| `created_at` | timestamp | |

---

### `celebracao.celebracao_objetivos` ⭐
Catálogo de Objetivos do Plano de Trabalho. Um objetivo agrega um conjunto de metas para um processo SEI.

> **Criado em:** 11/05/2026 (migração `scripts/archive/_migration_objetivos.sql`)  
> **Referência:** Módulo Parcerias Metas (`/parcerias-metas`)

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `sei_numero` | varchar(30) NOT NULL | Referência lógica a processo SEI |
| `objetivo` | text NOT NULL | Texto do objetivo específico |
| `indicadores_ids` | integer[] | IDs de `categoricas.c_dgp_indicadores` |
| `indicadores_ni` | boolean DEFAULT false | Indicadores "não identificados" |
| `meta_obs_indicadores` | text[] | Observações por indicador (paralelo ao array acima) |
| `meios_afericao_ids` | integer[] | IDs de `categoricas.c_dgp_meios_afericao` |
| `meios_ni` | boolean DEFAULT false | Meios "não identificados" |
| `ordem` | integer DEFAULT 0 | Ordem de exibição dentro do SEI |
| `criado_por` | text | |
| `criado_em` | timestamp DEFAULT NOW() | |
| `atualizado_por` | text | |
| `atualizado_em` | timestamp | |

**Índice:**
```sql
CREATE INDEX idx_celebracao_objetivos_sei ON celebracao.celebracao_objetivos (sei_numero);
```

---

### `celebracao.celebracao_metas` ⭐
Metas do Plano de Trabalho. Cada meta pertence a um Objetivo (FK `objetivo_id`).  
Hierarquia: **SEI → Objetivo (`celebracao_objetivos`) → Metas (`celebracao_metas`)**.

> **Reestruturado em:** 11/05/2026 — colunas de objetivo/indicadores/meios movidas para `celebracao_objetivos`  
> **Referência:** Módulo Parcerias Metas (`/parcerias-metas`)

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `objetivo_id` | integer FK NOT NULL | → `celebracao_objetivos.id` ON DELETE CASCADE |
| `sei_numero` | varchar(30) NOT NULL | Denormalizado para facilitar queries diretas |
| `meta_titulo` | varchar(300) NOT NULL | Título conciso da meta |
| `meta_descricao` | text | Descrição detalhada |
| `meta_tipo_ids` | **integer[]** | IDs de `categoricas.c_dgp_meta_tipos` — ver nota abaixo |
| `tipos_ni` | boolean DEFAULT false | Tipos "não identificados" |
| `observacoes` | text | Observações gerais |
| `ordem` | integer DEFAULT 0 | Ordem dentro do objetivo |
| `criado_por` | text | |
| `criado_em` | timestamp DEFAULT NOW() | |
| `atualizado_por` | text | |
| `atualizado_em` | timestamp | |

**Índices:**
```sql
CREATE INDEX idx_celebracao_metas_objetivo_id  ON celebracao.celebracao_metas (objetivo_id);
CREATE INDEX idx_celebracao_metas_sei_numero   ON celebracao.celebracao_metas (sei_numero);
CREATE INDEX idx_celebracao_metas_tipo_ids     ON celebracao.celebracao_metas USING GIN (meta_tipo_ids);
```

**Fontes do campo `sei_numero`** (union query na API `/api/sei-numeros`):
```sql
SELECT sei_celeb AS sei_numero, 'Parceria'   FROM public.parcerias
UNION
SELECT sei_celeb,               'Celebração' FROM celebracao.celebracao_parcerias
UNION
SELECT edital_processo_sei,     'Edital'     FROM public.parcerias_edital
```

---

### `celebracao.gestao_cents`
Gestão de CENTS (Certidão de Entidade do Terceiro Setor).

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `osc` | text | |
| `osc_cnpj` | varchar(20) | |
| `cents_sei` | varchar(40) | Processo SEI da CENTS |
| `cents_responsavel` | varchar(120) | |
| `cents_requerimento` | date | Data do requerimento |
| `cents_ultima_not` | date | Data da última notificação |
| `cents_publicacao` | date | Data de publicação |
| `cents_vencimento` | date | Data de vencimento |
| `cents_status` | varchar(40) | Status atual |
| `cents_prioridade` | varchar(40) | |
| `observacoes` | text | |
| `created_em` | timestamp | |

---

## � Schema `calendario` — Calendário Institucional

> Centraliza todas as tabelas de agenda, férias, registros pessoais e eventos. Migrado de `public` e `gestao_pessoas` em 30/04/2026.

### `calendario.datas_ferias`
Períodos de férias dos servidores.

| Coluna | Tipo | Descrição |
|--------|------|-----------||
| `id` | integer PK | |
| `d_usuario` | varchar(20) | Código do usuário |
| `nome_completo` | varchar(100) | |
| `ferias_inicio` | date | Início das férias |
| `ferias_fim` | date | Fim das férias |
| `aquisitivo_inicio` | date | Início do período aquisitivo |
| `aquisitivo_fim` | date | Fim do período aquisitivo |

---

### `calendario.datas_importantes`
Registros pessoais de cada servidor (abonos, folgas, consultas médicas, etc.).

| Coluna | Tipo | Descrição |
|--------|------|-----------||
| `id` | integer PK | |
| `nome_data` | text | Tipo de registro (ex: Abono, Folga, Consulta) |
| `data_inicio` | date | Data de início |
| `data_fim` | date | Data de fim (opcional) |
| `horario_inicio` | time | Horário de início |
| `horario_fim` | time | Horário de fim |
| `observacoes` | text | |
| `d_usuario` | varchar(20) | Código do usuário |
| `usuario_email` | text | E-mail do usuário |
| `tipo_usuario` | text | Tipo do usuário no momento do registro |
| `created_at` | timestamp | |
| `created_por` | varchar(100) | |
| `updated_at` | timestamp | |
| `updated_por` | varchar(100) | |

---

### `calendario.datas_eventos` ⭐
Atividades e eventos institucionais.

| Coluna | Tipo | Descrição |
|--------|------|-----------||
| `id` | integer PK | |
| `nome_atividade` | text | Nome do evento/atividade |
| `descritivo` | text | Descrição detalhada |
| `data_inicio` | date | Data principal |
| `datas_adicionais` | text | Datas extras (texto livre) |
| `participacao` | varchar(50) | Organizador / Participante / Apoiador / Convidado |
| `local` | text | Local do evento |
| `necessita_infraestrutura` | boolean | Requer suporte de infraestrutura |
| `valor_alimentacao` | numeric(12,2) | Valor de alimentação previsto |
| `alinhamento_aev` | boolean | Alinhado com a Agenda Estratégica de Vida |
| `observacoes` | text | |
| `cancelado` | boolean DEFAULT FALSE | Se o evento foi cancelado |
| `d_usuario` | varchar(20) | |
| `usuario_email` | text | |
| `tipo_usuario` | text | |
| `created_at` | timestamp | |
| `created_por` | varchar(100) | |
| `updated_at` | timestamp | |
| `updated_por` | varchar(100) | |

---

### `calendario.datas_eventos_responsaveis`
Responsáveis vinculados a cada evento.

| Coluna | Tipo | Descrição |
|--------|------|-----------||
| `id` | integer PK | |
| `datas_evento_id` | integer FK → `datas_eventos(id)` CASCADE | |
| `nome_atividade` | text | Denormalização do nome do evento |
| `responsavel_atividade` | text | Nome do responsável |
| `responsavel_tipo` | text | Ponto Focal / Apresentador(a) / Participante |
| `created_at` | timestamp | |
| `created_por` | varchar(100) | |

---

### `calendario.datas_eventos_documentos`
Documentos e links vinculados a cada evento.

| Coluna | Tipo | Descrição |
|--------|------|-----------||
| `id` | integer PK | |
| `datas_evento_id` | integer FK → `datas_eventos(id)` CASCADE | |
| `nome_atividade` | text | Referência denormalizada do nome do evento |
| `nome_doc` | text NOT NULL | Nome do documento (sanitizado para uso como arquivo) |
| `nome_doc_link` | text | Link externo (OneDrive, SharePoint, etc.) |
| `created_at` | timestamp DEFAULT NOW() | |
| `created_por` | varchar(100) | |
| `updated_at` | timestamp | |
| `updated_por` | varchar(100) | |

---

## �🟫 Schema `auditoria_memoria`

### `auditoria_memoria.auditoria_enc_pagamento`
Snapshot de encaminhamentos de pagamento para auditoria.

| Coluna | Tipo | Descrição |
|--------|------|-----------|
| `id` | integer PK | |
| `numero_termo` | varchar(120) FK | |
| `enc_pagamento_completo` | text | JSON/texto completo do encaminhamento |
| `numero_sei` | varchar(30) | Processo SEI |
| `parcela_numero` | text | Identificador da parcela |
| `created_por` | varchar(80) | |
| `created_em` | timestamp | |

---

## 🎯 Módulo Quadro de Metas

> **Criado em:** 05/05/2026 | **Blueprint:** `/parcerias-metas` | **Script DDL:** `scripts/criar_tabelas_parcerias_metas.sql`

O módulo de Quadro de Metas armazena as metas do Plano de Trabalho vinculadas a um processo SEI. Hierarquia de 3 níveis: **SEI → Objetivo → Metas**.

### Tabelas do módulo

| Tabela | Schema | Função |
|--------|--------|--------|
| `celebracao.celebracao_objetivos` | celebracao | Objetivo por SEI — 1:N por `sei_numero` |
| `celebracao.celebracao_metas` | celebracao | Meta por Objetivo — 1:N via FK `objetivo_id` |
| `categoricas.c_dgp_meta_tipos` | categoricas | Catálogo de tipos (`tipo_classificacao` livre) |
| `categoricas.c_dgp_indicadores` | categoricas | Catálogo de indicadores |
| `categoricas.c_dgp_meios_afericao` | categoricas | Catálogo de meios de aferição |
| `categoricas.c_dgp_plano_definicoes` | categoricas | Glossário de ajuda (1 linha ativa) |

---

### Padrão `INTEGER[]` — tipos de meta com múltipla seleção

A coluna `meta_tipo_ids INTEGER[]` em `celebracao_metas` armazena um **array nativo do PostgreSQL** com os IDs selecionados de `c_dgp_meta_tipos`. Isso permite que uma meta tenha múltiplos tipos de múltiplas classificações sem colunas extras.

**Como `c_dgp_meta_tipos` é estruturada:**

| id | meta_tipo | tipo_classificacao |
|----|-----------|-------------------|
| 1 | Qualitativo | Tipo Q |
| 2 | Quantitativo | Tipo Q |
| 3 | Implantação | Tipo 2 |
| 4 | Resultado | Tipo 2 |
| 5 | Impacto | Tipo 2 |

O campo `tipo_classificacao` é **TEXT livre** — a equipe pode criar novas classificações sem alteração de schema.

**Exemplos de uso SQL:**

```sql
-- Inserir meta com tipos Qualitativo + Resultado + Impacto
INSERT INTO celebracao.celebracao_metas (sei_numero, meta_titulo, meta_tipo_ids, ...)
VALUES ('2025-0.123.456-0', 'Meta de atendimento', ARRAY[1, 4, 5]::INTEGER[], ...);

-- Buscar metas que tenham o tipo "Resultado" (id=4)
SELECT * FROM celebracao.celebracao_metas
WHERE 4 = ANY(meta_tipo_ids);

-- Buscar metas com todos os tipos de "Tipo 2"
SELECT cm.*, array_agg(mt.meta_tipo) AS tipos
FROM celebracao.celebracao_metas cm
JOIN categoricas.c_dgp_meta_tipos mt ON mt.id = ANY(cm.meta_tipo_ids)
WHERE mt.tipo_classificacao = 'Tipo 2'
GROUP BY cm.id;

-- Exibir labels dos tipos numa query de listagem
SELECT cm.id, cm.meta_titulo,
       (SELECT STRING_AGG(mt.meta_tipo || ' (' || COALESCE(mt.tipo_classificacao,'') || ')', ' | '
                          ORDER BY mt.tipo_classificacao, mt.meta_tipo)
        FROM categoricas.c_dgp_meta_tipos mt
        WHERE mt.id = ANY(cm.meta_tipo_ids)) AS tipos_labels
FROM celebracao.celebracao_metas cm;
```

**No frontend (JavaScript):** os tipos são carregados via `GET /parcerias-metas/api/meta-tipos`, que retorna um objeto agrupado por `tipo_classificacao`. Cada grupo é renderizado como um bloco de checkboxes independente.

---

### Query union: fontes do campo `sei_numero`

```sql
SELECT sei_celeb      AS sei_numero, 'Parceria'   AS fonte FROM public.parcerias
  WHERE sei_celeb IS NOT NULL AND TRIM(sei_celeb) != ''
UNION
SELECT sei_celeb,                    'Celebração'          FROM celebracao.celebracao_parcerias
  WHERE sei_celeb IS NOT NULL AND TRIM(sei_celeb) != ''
UNION
SELECT edital_processo_sei,          'Edital'              FROM public.parcerias_edital
  WHERE edital_processo_sei IS NOT NULL AND TRIM(edital_processo_sei) != ''
ORDER BY sei_numero;
```

---

## 🔗 Relacionamentos Principais

```
public.parcerias.numero_termo
    ├── public.parcerias_infos_adicionais.numero_termo  (1:1)
    ├── public.parcerias_enderecos.numero_termo          (1:N)
    ├── public.parcerias_despesas.numero_termo           (1:N)
    ├── public.parcerias_despesas_obs.numero_termo       (1:1)
    ├── public.parcerias_pg.numero_termo                 (1:N histórico)
    ├── public.parcerias_sei.numero_termo                (1:N)
    ├── public.parcerias_analises.numero_termo           (1:N)
    ├── public.parcerias_notificacoes.numero_termo       (1:N)
    ├── public.termos_alteracoes.numero_termo            (1:N)
    ├── public.termos_rescisao.numero_termo              (1:1)
    ├── analises_pc.checklist_termo.numero_termo         (1:N por período)
    ├── analises_pc.conc_extrato.numero_termo            (1:N)
    ├── analises_pc.conc_banco.numero_termo              (1:1 por análise)
    ├── analises_pc.conc_contrapartida.numero_termo      (1:N)
    ├── analises_pc.conc_rendimentos.numero_termo        (1:N)
    ├── analises_pc.lista_inconsistencias.numero_termo   (1:N)
    ├── gestao_financeira.ultra_liquidacoes.numero_termo (1:N)
    └── gestao_financeira.ultra_liquidacoes_cronograma.numero_termo (1:N)

celebracao.celebracao_parcerias.sei_celeb
    ├── celebracao.celebracao_parcerias_enderecos.sei_celeb    (1:N)
    ├── celebracao.celebracao_parcerias_infos_adicionais.sei_celeb (1:1)
    └── celebracao.celebracao_parcerias_sei.sei_celeb          (1:N)

-- Quadro de Metas: hierarquia SEI → Objetivo → Meta
celebracao.celebracao_objetivos.sei_numero
    ← public.parcerias.sei_celeb                  (lógica, sem FK)
    ← celebracao.celebracao_parcerias.sei_celeb   (lógica, sem FK)
    ← public.parcerias_edital.edital_processo_sei (lógica, sem FK)
celebracao.celebracao_objetivos.indicadores_ids[]
    ← categoricas.c_dgp_indicadores.id            (N:N via array)
celebracao.celebracao_objetivos.meios_afericao_ids[]
    ← categoricas.c_dgp_meios_afericao.id         (N:N via array)
celebracao.celebracao_objetivos.id
    └── celebracao.celebracao_metas.objetivo_id   (1:N, CASCADE DELETE)
celebracao.celebracao_metas.meta_tipo_ids[]
    ← categoricas.c_dgp_meta_tipos.id             (N:N via array)

gestao_financeira.ultra_liquidacoes.parcela_numero
    └── gestao_financeira.ultra_liquidacoes_cronograma.parcela_numero (1:N)

gestao_pessoas.usuarios.email
    └── gestao_pessoas.usuarios_infos.usuario_email (1:1)

calendario.datas_eventos.id
    ├── calendario.datas_eventos_responsaveis.datas_evento_id (1:N, CASCADE)
    └── calendario.datas_eventos_documentos.datas_evento_id  (1:N, CASCADE)
```

---

## ⚡ Índices de Performance

```sql
-- Parcerias
CREATE INDEX idx_parcerias_pg_termo_data ON public.parcerias_pg(numero_termo, data_de_criacao DESC);
CREATE INDEX idx_parcerias_sei_termo_id ON public.parcerias_sei(numero_termo, id ASC);
CREATE INDEX idx_parcerias_enderecos_termo ON public.parcerias_enderecos(numero_termo);
CREATE INDEX idx_parcerias_infos_adicionais_termo ON public.parcerias_infos_adicionais(numero_termo);
CREATE INDEX idx_despesas_categoria_rubrica ON public.parcerias_despesas(categoria_despesa, rubrica);
CREATE INDEX idx_despesas_numero_termo ON public.parcerias_despesas(numero_termo);

-- Ultra Liquidações
CREATE INDEX idx_ultra_liq_termo_status ON gestao_financeira.ultra_liquidacoes(numero_termo, parcela_status);
CREATE INDEX idx_ulc_numero_termo ON gestao_financeira.ultra_liquidacoes_cronograma(numero_termo);

-- Conciliação Bancária (analises_pc)
-- Cobre: WHERE numero_termo = %s ORDER BY indice ASC  (~1.6s → <100ms esperado)
CREATE INDEX idx_conc_extrato_termo_indice ON analises_pc.conc_extrato(numero_termo, indice);

-- Back-empenhos SOF (gestao_financeira)
-- Cobre: WHERE cod_cta_desp = '33503900' AND cod_nro_pcss_sof IS NOT NULL  (~3.1s → <500ms esperado)
CREATE INDEX idx_back_empenhos_cta_desp ON gestao_financeira.back_empenhos(cod_cta_desp);

-- Quadro de Metas (celebracao)
CREATE INDEX idx_celebracao_objetivos_sei      ON celebracao.celebracao_objetivos (sei_numero);
CREATE INDEX idx_celebracao_metas_objetivo_id  ON celebracao.celebracao_metas (objetivo_id);
CREATE INDEX idx_celebracao_metas_sei_numero   ON celebracao.celebracao_metas (sei_numero);
CREATE INDEX idx_celebracao_metas_tipo_ids     ON celebracao.celebracao_metas USING GIN (meta_tipo_ids);

-- Log / Auditoria
CREATE INDEX idx_log_recurso_tipo_id ON gestao_pessoas.log_atividades(recurso_tipo, recurso_id);
CREATE INDEX idx_log_detalhes_gin ON gestao_pessoas.log_atividades USING GIN (detalhes);
```

---

## 🔧 Extensões e Convenções

### Extensões PostgreSQL ativas
```sql
CREATE EXTENSION IF NOT EXISTS unaccent;   -- Busca sem acentos
CREATE EXTENSION IF NOT EXISTS pg_trgm;    -- Busca por similaridade (fuzzy)
```

### Convenções de nomenclatura

| Padrão | Exemplo | Uso |
|--------|---------|-----|
| `numero_termo` | `TFM 001/2024` | Chave de relacionamento universal |
| `sei_celeb` | `6013.2024/0001234-5` | Processo SEI da celebração |
| `created_em` / `criado_em` | timestamp | Data de criação |
| `atualizado_em` | timestamp | Data de última atualização |
| `created_por` / `criado_por` | varchar | E-mail ou nome do usuário |
| `status` | varchar | Status textual do registro |
| `c_*` prefix | `c_dgp_analistas` | Tabelas do schema `categoricas` |
| `back_*` prefix | `back_empenhos` | Backups de importações do SOF |
| `temp_*` prefix | `temp_reservas_empenhos` | Tabelas de trabalho/transição |
| `conc_*` prefix | `conc_extrato` | Tabelas de conciliação bancária |

### Tipos monetários
- `numeric(18,2)` — Valores financeiros (padrão)
- `double precision` — Valores legados (tabela `parcerias`)
- Formatação BR: `R$ 1.234,56`

### Padrão de auditoria
Tabelas que armazenam ações do usuário sempre incluem:
- `created_por` / `criado_por` — quem criou
- `created_em` / `criado_em` — quando criou
- `atualizado_por` — quem editou por último
- `atualizado_em` — quando foi editado

---

*Última atualização: 28/04/2026 | Fonte: `backup_faf_20260428_143800.sql`*
