-- ============================================================
-- MIGRATION: Mover tabelas do schema public para calendario
-- Data: 2026-04-30
-- Tabelas: datas_importantes, datas_eventos, datas_eventos_responsaveis
--
-- SEGURANÇA: ALTER TABLE ... SET SCHEMA apenas move o registro no
-- catálogo do PostgreSQL. Os dados, índices e sequences são mantidos
-- integralmente. A FK entre datas_eventos_responsaveis e datas_eventos
-- é preservada porque ambas vão para o mesmo schema de destino.
-- ============================================================

BEGIN;

-- 1. Criar schema destino (idempotente)
CREATE SCHEMA IF NOT EXISTS calendario;

-- 2. Mover as tabelas
--    Ordem importa: responsaveis depende de datas_eventos (FK),
--    mas como ambas vão para o mesmo schema, o PG resolve internamente.
ALTER TABLE public.datas_eventos_responsaveis SET SCHEMA calendario;
ALTER TABLE public.datas_eventos               SET SCHEMA calendario;
ALTER TABLE public.datas_importantes           SET SCHEMA calendario;

-- 3. Verificação pós-migração
SELECT schemaname, tablename
FROM pg_tables
WHERE tablename IN ('datas_importantes', 'datas_eventos', 'datas_eventos_responsaveis')
ORDER BY tablename;

COMMIT;
