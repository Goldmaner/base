-- Script para criar índice na coluna numero_termo para melhorar performance
-- de buscas LIKE e autocomplete

-- Criar índice para busca LIKE 'texto%' (começa com)
-- O operador de classe text_pattern_ops permite uso de índice em LIKE 'abc%'
CREATE INDEX IF NOT EXISTS idx_parcerias_numero_termo_pattern 
ON public.parcerias (numero_termo text_pattern_ops);

-- Criar índice simples para JOINs e buscas exatas
CREATE INDEX IF NOT EXISTS idx_parcerias_numero_termo 
ON public.parcerias (numero_termo);

-- Criar índice na tabela termos_rescisao para NOT IN query
CREATE INDEX IF NOT EXISTS idx_termos_rescisao_numero_termo 
ON public.termos_rescisao (numero_termo);
