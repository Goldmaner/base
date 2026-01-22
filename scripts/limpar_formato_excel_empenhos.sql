-- Limpar formato Excel ="número" dos dados já inseridos
-- Remove =" do início e " do fim das strings

UPDATE gestao_financeira.back_empenhos
SET cod_nro_pcss_sof = REPLACE(REPLACE(cod_nro_pcss_sof, '="', ''), '"', '')
WHERE cod_nro_pcss_sof LIKE '=%';

-- Verificar se limpou
SELECT DISTINCT cod_nro_pcss_sof 
FROM gestao_financeira.back_empenhos 
ORDER BY cod_nro_pcss_sof 
LIMIT 10;
