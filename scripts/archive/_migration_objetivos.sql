-- =============================================================================
-- Migração: Hierarquia Objetivo → Metas
-- Cria celebracao.celebracao_objetivos e vincula metas existentes
-- Executar UMA VEZ em dev/prod antes de reiniciar o servidor
-- =============================================================================

BEGIN;

-- 1. Criar nova tabela de objetivos
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS celebracao.celebracao_objetivos (
    id                   SERIAL PRIMARY KEY,
    sei_numero           VARCHAR(30) NOT NULL,
    objetivo             TEXT        NOT NULL,
    indicadores_ids      INTEGER[],
    indicadores_ni       BOOLEAN     NOT NULL DEFAULT FALSE,
    meta_obs_indicadores TEXT[],
    meios_afericao_ids   INTEGER[],
    meios_ni             BOOLEAN     NOT NULL DEFAULT FALSE,
    ordem                INTEGER     NOT NULL DEFAULT 0,
    criado_por           TEXT,
    criado_em            TIMESTAMP   NOT NULL DEFAULT NOW(),
    atualizado_por       TEXT,
    atualizado_em        TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_celebracao_objetivos_sei
    ON celebracao.celebracao_objetivos (sei_numero);

-- 2. Popular objetivos a partir das metas existentes
--    DISTINCT ON (sei_numero, objetivo_normalizado) — evita duplicatas por SEI
-- ----------------------------------------------------------------------------
INSERT INTO celebracao.celebracao_objetivos
    (sei_numero, objetivo, indicadores_ids, indicadores_ni,
     meta_obs_indicadores, meios_afericao_ids, meios_ni, ordem, criado_por, criado_em)
SELECT DISTINCT ON (cm.sei_numero, TRIM(COALESCE(cm.meta_objetivo, '')))
    cm.sei_numero,
    TRIM(COALESCE(cm.meta_objetivo, 'Objetivo não informado')),
    cm.indicadores_ids,
    COALESCE(cm.indicadores_ni, FALSE),
    cm.meta_obs_indicadores,
    cm.meios_afericao_ids,
    COALESCE(cm.meios_ni, FALSE),
    -- Ordem: sequencial por SEI com base na primeira ocorrência
    ROW_NUMBER() OVER (
        PARTITION BY cm.sei_numero
        ORDER BY cm.id
    )::INTEGER - 1,
    cm.criado_por,
    cm.criado_em
FROM celebracao.celebracao_metas cm
ORDER BY cm.sei_numero, TRIM(COALESCE(cm.meta_objetivo, '')), cm.id;

-- 3. Adicionar coluna objetivo_id em celebracao_metas (se não existir)
-- ----------------------------------------------------------------------------
ALTER TABLE celebracao.celebracao_metas
    ADD COLUMN IF NOT EXISTS objetivo_id INTEGER
        REFERENCES celebracao.celebracao_objetivos(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_celebracao_metas_objetivo_id
    ON celebracao.celebracao_metas (objetivo_id);

-- 4. Vincular metas existentes ao objetivo correspondente
-- ----------------------------------------------------------------------------
UPDATE celebracao.celebracao_metas cm
SET objetivo_id = co.id
FROM celebracao.celebracao_objetivos co
WHERE co.sei_numero = cm.sei_numero
  AND co.objetivo   = TRIM(COALESCE(cm.meta_objetivo, 'Objetivo não informado'))
  AND cm.objetivo_id IS NULL;

-- 5. Verificação antes de dropar colunas
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    orphans INTEGER;
BEGIN
    SELECT COUNT(*) INTO orphans
    FROM celebracao.celebracao_metas
    WHERE objetivo_id IS NULL;

    IF orphans > 0 THEN
        RAISE EXCEPTION 'Há % metas sem objetivo_id — não é seguro remover colunas.', orphans;
    END IF;
END $$;

-- 6. Remover colunas migradas de celebracao_metas
-- ----------------------------------------------------------------------------
ALTER TABLE celebracao.celebracao_metas
    DROP COLUMN IF EXISTS meta_objetivo,
    DROP COLUMN IF EXISTS indicadores_ids,
    DROP COLUMN IF EXISTS indicadores_ni,
    DROP COLUMN IF EXISTS meta_obs_indicadores,
    DROP COLUMN IF EXISTS meios_afericao_ids,
    DROP COLUMN IF EXISTS meios_ni;

-- 7. Confirmação
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    n_obj  INTEGER;
    n_meta INTEGER;
BEGIN
    SELECT COUNT(*) INTO n_obj  FROM celebracao.celebracao_objetivos;
    SELECT COUNT(*) INTO n_meta FROM celebracao.celebracao_metas;
    RAISE NOTICE 'Migração concluída: % objetivos criados, % metas vinculadas.', n_obj, n_meta;
END $$;

COMMIT;
