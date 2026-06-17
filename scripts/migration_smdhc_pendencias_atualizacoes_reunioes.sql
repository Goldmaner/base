-- =============================================================================
-- Migration: SMDHC Pendencias - Tipos de Atualizacao e Participantes de Reuniao
-- Data: 2026-06-17
-- Descricao: Adiciona tipo de atualizacao e estrutura de participantes
--            internos/externos para registros de reuniao.
-- =============================================================================

BEGIN;

ALTER TABLE pendencias.smdhc_pendencias_atualizacoes
    ADD COLUMN IF NOT EXISTS tema_atualizacao_tipo TEXT;

UPDATE pendencias.smdhc_pendencias_atualizacoes
SET tema_atualizacao_tipo = 'Outros'
WHERE tema_atualizacao_tipo IS NULL
   OR btrim(tema_atualizacao_tipo) = '';

ALTER TABLE pendencias.smdhc_pendencias_atualizacoes
    ALTER COLUMN tema_atualizacao_tipo SET DEFAULT 'Outros';

CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_atualizacoes_participantes (
    id                         SERIAL PRIMARY KEY,
    atualizacao_id             INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias_atualizacoes(id) ON DELETE CASCADE,
    participante_origem        TEXT NOT NULL,
    usuario_id                 INTEGER
        REFERENCES gestao_pessoas.usuarios(id),
    participante_nome_externo  TEXT,
    participante_setor_externo TEXT,
    ativo                      BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por                 TEXT,
    criado_em                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por             TEXT,
    atualizado_em              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_smdhc_pendencias_atualizacoes_participantes_origem
        CHECK (participante_origem IN ('usuario_sistema', 'externo')),
    CONSTRAINT ck_smdhc_pendencias_atualizacoes_participantes_dados
        CHECK (
            (
                participante_origem = 'usuario_sistema'
                AND usuario_id IS NOT NULL
                AND participante_nome_externo IS NULL
                AND participante_setor_externo IS NULL
            )
            OR
            (
                participante_origem = 'externo'
                AND usuario_id IS NULL
                AND participante_nome_externo IS NOT NULL
                AND participante_setor_externo IS NOT NULL
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_atualizacoes_tipo_ativos
    ON pendencias.smdhc_pendencias_atualizacoes (tema_atualizacao_tipo, tema_atualizacao_data DESC)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_atual_participantes_atualizacao_ativos
    ON pendencias.smdhc_pendencias_atualizacoes_participantes (atualizacao_id, id)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_atual_participantes_usuario_ativos
    ON pendencias.smdhc_pendencias_atualizacoes_participantes (usuario_id, atualizacao_id)
    WHERE ativo = TRUE;

INSERT INTO categoricas.c_geral_status (
    schema_table_coluna_r,
    status,
    descricao,
    ativo,
    nome_item_fantasia
)
VALUES
    (
        'pendencias.smdhc_pendencias_atualizacoes.tema_atualizacao_tipo',
        'Reunião',
        'Atualização registrada a partir de reunião, com participantes internos e/ou externos.',
        TRUE,
        'Pendencias SMDHC: Tipo de Atualizacao'
    ),
    (
        'pendencias.smdhc_pendencias_atualizacoes.tema_atualizacao_tipo',
        'Outros',
        'Atualização operacional geral sem necessidade de participantes de reunião.',
        TRUE,
        'Pendencias SMDHC: Tipo de Atualizacao'
    )
ON CONFLICT (schema_table_coluna_r, status) DO UPDATE
SET descricao          = EXCLUDED.descricao,
    ativo              = EXCLUDED.ativo,
    nome_item_fantasia = EXCLUDED.nome_item_fantasia,
    atualizado_em      = NOW();

COMMIT;
