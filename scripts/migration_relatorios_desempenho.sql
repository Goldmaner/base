-- =============================================================================
-- Migration: Relatórios de Desempenho
-- Descrição : Cria tabelas relatorios_desempenho e relatorios_desempenho_auxiliar
--             no schema gestao_pessoas e adiciona coluna de permissão em
--             usuarios_infos.
-- Como rodar: ver GUIA_BANCO_DADOS.md — sempre usar Supabase (não localhost).
-- =============================================================================

BEGIN;

-- 1. Coluna de permissão -------------------------------------------------------
ALTER TABLE gestao_pessoas.usuarios_infos
ADD COLUMN IF NOT EXISTS usuario_relatorios_permissao BOOLEAN DEFAULT FALSE;

-- 2. Tabela principal ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS gestao_pessoas.relatorios_desempenho (
    id               SERIAL PRIMARY KEY,
    usuario_email    TEXT NOT NULL,
    operacao_tipo    TEXT NOT NULL,   -- manual_area de public.manuais_lista
    operacao_nome    TEXT NOT NULL,   -- manual_nome de public.manuais_lista
    operacao_subtipo TEXT,
    criado_por       TEXT,
    criado_em        TIMESTAMP DEFAULT NOW(),
    atualizado_por   TEXT,
    atualizado_em    TIMESTAMP
);

-- 3. Tabela de aferições (1 registro → N aferições) ----------------------------
CREATE TABLE IF NOT EXISTS gestao_pessoas.relatorios_desempenho_auxiliar (
    id                     SERIAL PRIMARY KEY,
    operacao_id            INTEGER NOT NULL
        REFERENCES gestao_pessoas.relatorios_desempenho(id) ON DELETE CASCADE,
    operacao_tipo_afericao TEXT,   -- 'Processo SEI' | 'Outros'
    operacao_afericao      TEXT,
    operacao_descricao     TEXT,
    criado_por             TEXT,
    criado_em              TIMESTAMP DEFAULT NOW(),
    atualizado_por         TEXT,
    atualizado_em          TIMESTAMP
);

-- 4. Índices -------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_rel_desempenho_email
    ON gestao_pessoas.relatorios_desempenho (usuario_email);

CREATE INDEX IF NOT EXISTS idx_rel_desempenho_aux_op
    ON gestao_pessoas.relatorios_desempenho_auxiliar (operacao_id);

-- 5. RLS (mesmo padrão das demais tabelas do schema gestao_pessoas) ------------
ALTER TABLE gestao_pessoas.relatorios_desempenho           ENABLE ROW LEVEL SECURITY;
ALTER TABLE gestao_pessoas.relatorios_desempenho_auxiliar  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "authenticated_acesso_total" ON gestao_pessoas.relatorios_desempenho;
CREATE POLICY "authenticated_acesso_total"
    ON gestao_pessoas.relatorios_desempenho
    FOR ALL TO authenticated
    USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "authenticated_acesso_total" ON gestao_pessoas.relatorios_desempenho_auxiliar;
CREATE POLICY "authenticated_acesso_total"
    ON gestao_pessoas.relatorios_desempenho_auxiliar
    FOR ALL TO authenticated
    USING (true) WITH CHECK (true);

COMMIT;
