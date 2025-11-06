-- Script para adicionar colunas respondido e obs na tabela o_pesquisa_parcerias
-- Execute este script no PostgreSQL caso as colunas ainda não existam

-- Adicionar coluna respondido (boolean, default false)
ALTER TABLE public.o_pesquisa_parcerias 
ADD COLUMN IF NOT EXISTS respondido BOOLEAN DEFAULT FALSE;

-- Adicionar coluna obs (text, pode ser null)
ALTER TABLE public.o_pesquisa_parcerias 
ADD COLUMN IF NOT EXISTS obs TEXT;

-- Verificar estrutura da tabela
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'public' 
  AND table_name = 'o_pesquisa_parcerias'
ORDER BY ordinal_position;

-- Comentar as colunas
COMMENT ON COLUMN public.o_pesquisa_parcerias.respondido IS 'Indica se a pesquisa foi respondida (Sim/Não)';
COMMENT ON COLUMN public.o_pesquisa_parcerias.obs IS 'Observações sobre a pesquisa';
