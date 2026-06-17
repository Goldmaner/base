-- =============================================================================
-- Migration: SMDHC Pendencias - Links e Documentos Relacionados
-- Data: 2026-06-16
-- Descricao: Adiciona tabelas operacionais para links e documentos de apoio
--            vinculados a cada pendencia, com auditoria e exclusao logica.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_links (
    id                 SERIAL PRIMARY KEY,
    pendencia_id       INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE,
    tema_link_titulo   TEXT,
    tema_link_url      TEXT NOT NULL,
    tema_link_descricao TEXT,
    ativo              BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por         TEXT,
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por     TEXT,
    atualizado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE pendencias.smdhc_pendencias_links IS
    'Links externos, referencias e paginas relacionadas a uma pendencia.';

CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_documentos (
    id                     SERIAL PRIMARY KEY,
    pendencia_id           INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE,
    documento_titulo       TEXT,
    documento_descricao    TEXT,
    documento_nome_original TEXT NOT NULL,
    documento_storage_path TEXT NOT NULL,
    documento_content_type TEXT,
    documento_tamanho_bytes BIGINT,
    ativo                  BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por             TEXT,
    criado_em              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por         TEXT,
    atualizado_em          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_smdhc_pendencias_documentos_tamanho
        CHECK (documento_tamanho_bytes IS NULL OR documento_tamanho_bytes >= 0)
);

COMMENT ON TABLE pendencias.smdhc_pendencias_documentos IS
    'Documentos de apoio vinculados a uma pendencia, armazenados no bucket configurado.';

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_links_pendencia_ativos
    ON pendencias.smdhc_pendencias_links (pendencia_id, atualizado_em DESC, criado_em DESC, id DESC)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_documentos_pendencia_ativos
    ON pendencias.smdhc_pendencias_documentos (pendencia_id, atualizado_em DESC, criado_em DESC, id DESC)
    WHERE ativo = TRUE;

COMMIT;
