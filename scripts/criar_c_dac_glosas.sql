-- Migration: categoricas.c_dac_glosas
-- Catálogo de tipos de glosa para conciliação bancária (DAC)
-- Criado: 2026-05-26

CREATE TABLE IF NOT EXISTS categoricas.c_dac_glosas (
    id                  SERIAL          PRIMARY KEY,
    glosa_nome          TEXT            NOT NULL,
    glosa_texto         TEXT,
    glosa_inconsistencia TEXT,

    -- Auditoria
    criado_por          TEXT,
    criado_em           TIMESTAMP       NOT NULL DEFAULT NOW(),
    atualizado_por      TEXT,
    atualizado_em       TIMESTAMP
);

COMMENT ON TABLE categoricas.c_dac_glosas IS 'Catálogo de tipos de glosa utilizados na conciliação bancária (DAC)';
COMMENT ON COLUMN categoricas.c_dac_glosas.glosa_nome          IS 'Nome curto do tipo de glosa (exibido em dropdowns)';
COMMENT ON COLUMN categoricas.c_dac_glosas.glosa_texto         IS 'Texto explicativo da glosa para o relatório';
COMMENT ON COLUMN categoricas.c_dac_glosas.glosa_inconsistencia IS 'Descrição da inconsistência associada a este tipo de glosa';
