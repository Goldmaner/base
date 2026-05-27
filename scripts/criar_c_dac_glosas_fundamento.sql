-- Migration: categoricas.c_dac_glosas_fundamento
-- Fundamentos legais (lei + artigo) por tipo de glosa
-- Criado: 2026-05-26

CREATE TABLE IF NOT EXISTS categoricas.c_dac_glosas_fundamento (
    id              SERIAL          PRIMARY KEY,
    glosa_id        INTEGER         NOT NULL
                        REFERENCES categoricas.c_dac_glosas(id)
                        ON DELETE CASCADE,
    glosa_lei       TEXT,
    glosa_artigo    TEXT,

    -- Auditoria
    criado_por      TEXT,
    criado_em       TIMESTAMP       NOT NULL DEFAULT NOW(),
    atualizado_por  TEXT,
    atualizado_em   TIMESTAMP
);

CREATE INDEX idx_c_dac_glosas_fundamento_glosa_id
    ON categoricas.c_dac_glosas_fundamento(glosa_id);

COMMENT ON TABLE categoricas.c_dac_glosas_fundamento IS 'Fundamentos legais (lei + artigo) vinculados a cada tipo de glosa de c_dac_glosas';
COMMENT ON COLUMN categoricas.c_dac_glosas_fundamento.glosa_id     IS 'FK → categoricas.c_dac_glosas.id (CASCADE DELETE)';
COMMENT ON COLUMN categoricas.c_dac_glosas_fundamento.glosa_lei    IS 'Nome ou número da lei/norma (ex: Lei 13.019/2014)';
COMMENT ON COLUMN categoricas.c_dac_glosas_fundamento.glosa_artigo IS 'Artigo(s) da lei que fundamentam a glosa';
