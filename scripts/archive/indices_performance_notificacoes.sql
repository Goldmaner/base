-- ============================================================
-- ÍNDICES PARA OTIMIZAÇÃO DE PERFORMANCE
-- Tabela: public.parcerias
-- Campo: numero_termo (autocomplete em Notificações)
-- Data: 11/12/2024
-- ============================================================

-- Índice para busca case-insensitive por numero_termo (usado no autocomplete)
-- Usa LOWER() para otimizar buscas ILIKE/LIKE
CREATE INDEX IF NOT EXISTS idx_parcerias_numero_termo_lower 
ON public.parcerias (LOWER(numero_termo));

-- Índice para busca por numero_termo exato (usado em JOINs)
CREATE INDEX IF NOT EXISTS idx_parcerias_numero_termo 
ON public.parcerias (numero_termo);

-- Índice para ordenação descendente (termos mais recentes primeiro)
CREATE INDEX IF NOT EXISTS idx_parcerias_numero_termo_desc 
ON public.parcerias (numero_termo DESC);

-- Comentários explicativos
COMMENT ON INDEX public.idx_parcerias_numero_termo_lower IS 
'Índice para otimizar buscas case-insensitive (ILIKE) no autocomplete de números de termo';

COMMENT ON INDEX public.idx_parcerias_numero_termo IS 
'Índice para otimizar JOINs e buscas exatas por numero_termo';

COMMENT ON INDEX public.idx_parcerias_numero_termo_desc IS 
'Índice para otimizar ordenação descendente (termos mais recentes)';

-- ============================================================
-- VERIFICAR ÍNDICES CRIADOS
-- ============================================================
-- Execute esta query para verificar os índices criados:
-- SELECT indexname, indexdef 
-- FROM pg_indexes 
-- WHERE schemaname = 'public' 
-- AND tablename = 'parcerias';

-- ============================================================
-- ESTATÍSTICAS E ANÁLISE
-- ============================================================
-- Atualizar estatísticas da tabela para melhor performance do planejador de queries
ANALYZE public.parcerias;

-- ============================================================
-- TESTES DE PERFORMANCE
-- ============================================================
-- Execute estas queries para testar se os índices estão sendo usados:

-- Teste 1: Autocomplete (deve usar idx_parcerias_numero_termo_lower)
-- EXPLAIN ANALYZE 
-- SELECT DISTINCT numero_termo
-- FROM public.parcerias
-- WHERE LOWER(numero_termo) LIKE LOWER('%tfm%')
-- ORDER BY numero_termo DESC
-- LIMIT 20;

-- Teste 2: Busca exata de termo (deve usar idx_parcerias_numero_termo)
-- EXPLAIN ANALYZE
-- SELECT *
-- FROM public.parcerias
-- WHERE numero_termo = 'TFM/142/2024/SMDHC/FUMCAD';

-- ============================================================
-- MANUTENÇÃO
-- ============================================================
-- Reindexar se necessário (após muitas inserções/atualizações):
-- REINDEX TABLE public.parcerias;

-- ============================================================
-- ROLLBACK (SE NECESSÁRIO)
-- ============================================================
-- Para remover os índices:
-- DROP INDEX IF EXISTS public.idx_parcerias_numero_termo_lower;
-- DROP INDEX IF EXISTS public.idx_parcerias_numero_termo;
-- DROP INDEX IF EXISTS public.idx_parcerias_numero_termo_desc;
