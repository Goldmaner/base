-- =============================================================================
-- ÍNDICES DE PERFORMANCE — FAF
-- Criado em: 2026-04-24
-- Objetivo: Reduzir carga no banco sem alterar nenhuma função ou dado.
--           Todos os índices são criados com IF NOT EXISTS e podem ser
--           removidos com DROP INDEX sem qualquer impacto nos dados.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- VERIFICAÇÃO PRÉVIA
-- Execute antes para ver quais índices já existem:
--
-- SELECT schemaname, tablename, indexname, indexdef
-- FROM pg_indexes
-- WHERE tablename IN (
--     'parcerias', 'ultra_liquidacoes', 'ultra_liquidacoes_cronograma',
--     'parcerias_pg', 'parcerias_sei', 'parcerias_enderecos',
--     'parcerias_infos_adicionais', 'parcerias_despesas', 'log_atividades'
-- )
-- ORDER BY tablename, indexname;
-- -----------------------------------------------------------------------------


-- =============================================================================
-- QUERY 1: Lista principal de parcerias (avg 717ms, 393 chamadas)
-- Problema: 9 subqueries correlacionadas sem índices nas tabelas filhas.
-- =============================================================================

-- Tabela: gestao_financeira.ultra_liquidacoes
-- Cobre: subquery de total_pago (WHERE numero_termo + parcela_status)
CREATE INDEX IF NOT EXISTS idx_ultra_liq_termo_status
    ON gestao_financeira.ultra_liquidacoes(numero_termo, parcela_status);

-- Tabela: gestao_financeira.ultra_liquidacoes_cronograma
-- Cobre: subqueries de valor_mes_detalhado, valor_mes_23, valor_mes_24
CREATE INDEX IF NOT EXISTS idx_ulc_numero_termo
    ON gestao_financeira.ultra_liquidacoes_cronograma(numero_termo);

-- Tabela: public.parcerias_pg
-- Cobre: subqueries de pessoa_gestora, status_pg, solicitacao
--        (ORDER BY data_de_criacao DESC LIMIT 1)
CREATE INDEX IF NOT EXISTS idx_parcerias_pg_termo_data
    ON public.parcerias_pg(numero_termo, data_de_criacao DESC);

-- Tabela: public.parcerias_sei
-- Cobre: subquery de data_assinatura_termo (WHERE numero_termo + filtros de aditamento)
CREATE INDEX IF NOT EXISTS idx_parcerias_sei_termo_id
    ON public.parcerias_sei(numero_termo, id ASC);

-- Tabela: public.parcerias_enderecos
-- Cobre: subquery de endereco_completo
CREATE INDEX IF NOT EXISTS idx_parcerias_enderecos_termo
    ON public.parcerias_enderecos(numero_termo);

-- Tabela: public.parcerias_infos_adicionais
-- Cobre: subqueries de abrangencia, data_suspensao, data_retomada
CREATE INDEX IF NOT EXISTS idx_parcerias_infos_adicionais_termo
    ON public.parcerias_infos_adicionais(numero_termo);


-- =============================================================================
-- QUERY 2: Autocomplete de rubrica (avg 184ms, 1.335 chamadas — maior impacto)
-- Problema: Full scan em Parcerias_Despesas para cada keystroke do usuário.
-- SELECT rubrica, COUNT(*) FROM Parcerias_Despesas WHERE categoria_despesa = $1
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_despesas_categoria_rubrica
    ON public.parcerias_despesas(categoria_despesa, rubrica);


-- =============================================================================
-- QUERY 3: Totais de orçamento preenchido (avg 440ms, 298 chamadas)
-- Problema: LEFT JOIN em Parcerias_Despesas sem índice no lado direito do JOIN.
-- SELECT ... FROM Parcerias p LEFT JOIN Parcerias_Despesas pd ON p.numero_termo = pd.numero_termo
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_despesas_numero_termo
    ON public.parcerias_despesas(numero_termo);


-- =============================================================================
-- QUERY 4: Histórico de andamentos — log_atividades
-- Problema: WHERE recurso_tipo + recurso_id + operador JSONB ? sem índices.
-- =============================================================================

-- Índice composto para os filtros escalares:
CREATE INDEX IF NOT EXISTS idx_log_recurso_tipo_id
    ON gestao_pessoas.log_atividades(recurso_tipo, recurso_id);

-- Índice GIN para o operador ? no JSONB (busca de chave em detalhes):
CREATE INDEX IF NOT EXISTS idx_log_detalhes_gin
    ON gestao_pessoas.log_atividades USING GIN (detalhes);


-- =============================================================================
-- CONFIRMAÇÃO FINAL
-- Execute após a criação para verificar:
--
-- SELECT schemaname, tablename, indexname
-- FROM pg_indexes
-- WHERE indexname IN (
--     'idx_ultra_liq_termo_status',
--     'idx_ulc_numero_termo',
--     'idx_parcerias_pg_termo_data',
--     'idx_parcerias_sei_termo_id',
--     'idx_parcerias_enderecos_termo',
--     'idx_parcerias_infos_adicionais_termo',
--     'idx_despesas_categoria_rubrica',
--     'idx_despesas_numero_termo',
--     'idx_log_recurso_tipo_id',
--     'idx_log_detalhes_gin'
-- )
-- ORDER BY tablename;
-- =============================================================================
