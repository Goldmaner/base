-- Migração: adicionar colunas de SEI e data assinatura em termos_alteracoes
-- Data: 2026-05-05
-- Objetivo: armazenar número SEI do documento e data de assinatura diretamente
--           na tabela de alterações, evitando complexidade com parcerias_sei

ALTER TABLE public.termos_alteracoes
    ADD COLUMN IF NOT EXISTS termo_sei_doc VARCHAR(12),
    ADD COLUMN IF NOT EXISTS data_assinatura DATE;

COMMENT ON COLUMN public.termos_alteracoes.termo_sei_doc IS 'Número SEI do documento da alteração concluída';
COMMENT ON COLUMN public.termos_alteracoes.data_assinatura IS 'Data de assinatura da alteração concluída';
