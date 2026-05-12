-- ============================================================
-- Índices de performance para o endpoint GET /parcerias/
-- Rodar uma vez no banco projeto_parcerias (como superuser ou owner)
-- ============================================================

-- 1. back_empenhos: lookup pelo processo SEI (JOIN da dotação orçamentária)
--    Maior ganho: permite index-lookup no LATERAL ao invés de full-scan
CREATE INDEX IF NOT EXISTS idx_back_empenhos_processo
    ON gestao_financeira.back_empenhos (cod_nro_pcss_sof)
    WHERE cod_nro_pcss_sof IS NOT NULL;

-- 2. parcerias: filtro por período de vigência (inicio/final)
CREATE INDEX IF NOT EXISTS idx_parcerias_vigencia
    ON public.parcerias (inicio, final);

-- 3. parcerias_pg: CTE last_pg usa ORDER BY numero_termo, data_de_criacao DESC
CREATE INDEX IF NOT EXISTS idx_parcerias_pg_termo_data
    ON public.parcerias_pg (numero_termo, data_de_criacao DESC);

-- 4. ultra_liquidacoes: CTE total_pago filtra por parcela_status = 'Pago'
CREATE INDEX IF NOT EXISTS idx_ultra_liq_status_termo
    ON gestao_financeira.ultra_liquidacoes (parcela_status, numero_termo)
    WHERE parcela_status = 'Pago';

-- 5. ultra_liquidacoes_cronograma: CTE cronograma agrupa por numero_termo
CREATE INDEX IF NOT EXISTS idx_ultra_liq_cron_termo
    ON gestao_financeira.ultra_liquidacoes_cronograma (numero_termo);

-- 6. parcerias_sei: CTE assinatura ordena por numero_termo, id
CREATE INDEX IF NOT EXISTS idx_parcerias_sei_termo_id
    ON public.parcerias_sei (numero_termo, id)
    WHERE (aditamento = '-' OR aditamento IS NULL)
      AND (apostilamento = '-' OR apostilamento IS NULL)
      AND termo_tipo_sei IS NULL;

-- 7. parcerias_enderecos: CTE enderecos agrupa por numero_termo
CREATE INDEX IF NOT EXISTS idx_parcerias_enderecos_termo
    ON public.parcerias_enderecos (numero_termo);

-- 8. parcerias_infos_adicionais: CTE infos ordena por numero_termo
CREATE INDEX IF NOT EXISTS idx_parcerias_infos_termo
    ON public.parcerias_infos_adicionais (numero_termo);
