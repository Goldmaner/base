-- Aumentar tamanho das colunas VARCHAR que podem estourar o limite
-- Script para back_empenhos

-- TXT_PROJ_ATVD_P estava estourando com 70 chars
ALTER TABLE gestao_financeira.back_empenhos 
    ALTER COLUMN txt_proj_atvd_p TYPE VARCHAR(200);

-- Outras colunas de texto longo que podem ter problema
ALTER TABLE gestao_financeira.back_empenhos 
    ALTER COLUMN txt_org_emp_exect TYPE VARCHAR(150);

ALTER TABLE gestao_financeira.back_empenhos 
    ALTER COLUMN txt_fcao_govr TYPE VARCHAR(150);

ALTER TABLE gestao_financeira.back_empenhos 
    ALTER COLUMN txt_pgm_govr TYPE VARCHAR(150);

ALTER TABLE gestao_financeira.back_empenhos 
    ALTER COLUMN txt_sub_fcao_govr TYPE VARCHAR(150);

ALTER TABLE gestao_financeira.back_empenhos 
    ALTER COLUMN txt_modl_lici TYPE VARCHAR(150);

ALTER TABLE gestao_financeira.back_empenhos 
    ALTER COLUMN txt_cta_desp TYPE VARCHAR(150);

ALTER TABLE gestao_financeira.back_empenhos 
    ALTER COLUMN txt_font_rec TYPE VARCHAR(150);

ALTER TABLE gestao_financeira.back_empenhos 
    ALTER COLUMN txt_font_rec_exec TYPE VARCHAR(150);

-- Verificar tamanhos atualizados
SELECT column_name, data_type, character_maximum_length 
FROM information_schema.columns 
WHERE table_schema = 'gestao_financeira' 
  AND table_name = 'back_empenhos' 
  AND column_name LIKE 'txt_%'
ORDER BY column_name;
