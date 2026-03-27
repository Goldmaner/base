-- ============================================================
-- SCRIPT: Correção e recriação de c_geral_tipos_documentos_manuais
-- Schema: categoricas
-- Data: 27/03/2026
--
-- PROBLEMA: tabela geral_tipos_documentos_manuais criada sem RLS
-- nem GRANT no schema → PostgreSQL retorna "does not exist" para
-- roles não-owner, embora o objeto exista no catálogo.
--
-- SOLUÇÃO:
--   1. Verificar o que existe no catálogo (ignora RLS)
--   2. Renomear a tabela problemática
--   3. Garantir GRANT no schema e na tabela
--   4. Habilitar RLS + criar policy permissiva para authenticated
-- ============================================================


-- ─────────────────────────────────────────────────────────────
-- PASSO 0 — DIAGNÓSTICO (rode isso primeiro para confirmar)
-- ─────────────────────────────────────────────────────────────
-- Confirma que a tabela existe no catálogo (bypassa RLS):
SELECT schemaname, tablename, tableowner
FROM pg_catalog.pg_tables
WHERE schemaname = 'categoricas'
  AND tablename IN (
    'geral_tipos_documentos_manuais',
    'c_geral_tipos_documentos_manuais'
  );

-- Verifica as policies existentes no schema:
SELECT schemaname, tablename, policyname, cmd, roles
FROM pg_policies
WHERE schemaname = 'categoricas'
ORDER BY tablename;

-- Verifica se RLS está habilitado nas tabelas do schema:
SELECT n.nspname AS schema, c.relname AS tabela,
       c.relrowsecurity AS rls_habilitado,
       c.relforcerowsecurity AS rls_forcado
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'categoricas'
ORDER BY c.relname;


-- ─────────────────────────────────────────────────────────────
-- PASSO 1 — RENOMEAR a tabela antiga (nome sem prefixo "c_")
-- Execute apenas se o PASSO 0 confirmou que ela existe
-- ─────────────────────────────────────────────────────────────
ALTER TABLE IF EXISTS categoricas.geral_tipos_documentos_manuais
  RENAME TO c_geral_tipos_documentos_manuais;


-- ─────────────────────────────────────────────────────────────
-- PASSO 2 — Renomear sequence e constraint (ainda com nome antigo)
-- Diagnóstico confirmou: só existe o role 'postgres' (superuser).
-- GRANTs e RLS são desnecessários — postgres bypassa tudo.
-- ─────────────────────────────────────────────────────────────

-- Renomear a sequence (ainda estava com nome antigo sem "c_")
ALTER SEQUENCE categoricas.geral_tipos_documentos_manuais_id_seq
  RENAME TO c_geral_tipos_documentos_manuais_id_seq;

-- Renomear a constraint de primary key (opcional, mas mantém consistência)
ALTER TABLE categoricas.c_geral_tipos_documentos_manuais
  RENAME CONSTRAINT geral_tipos_documentos_manuais_pkey
  TO c_geral_tipos_documentos_manuais_pkey;


-- ─────────────────────────────────────────────────────────────
-- PASSO 4 — VERIFICAÇÃO FINAL
-- ─────────────────────────────────────────────────────────────
SELECT * FROM categoricas.c_geral_tipos_documentos_manuais
ORDER BY id ASC;
