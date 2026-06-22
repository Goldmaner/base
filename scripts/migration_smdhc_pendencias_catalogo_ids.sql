-- =============================================================================
-- Migration: SMDHC Pendencias - Catalogo por IDs
-- Data: 2026-06-17
-- Descricao: Normaliza os campos controlados de pendencias para usar IDs de
--            categoricas.c_geral_status, preservando colunas legadas em texto
--            como snapshot sincronizado para compatibilidade.
-- =============================================================================

BEGIN;

ALTER TABLE categoricas.c_geral_status
    ADD COLUMN IF NOT EXISTS ordem INTEGER NOT NULL DEFAULT 0;

ALTER TABLE pendencias.smdhc_pendencias
    ADD COLUMN IF NOT EXISTS tema_tipo_id INTEGER,
    ADD COLUMN IF NOT EXISTS tema_area_demandante_id INTEGER,
    ADD COLUMN IF NOT EXISTS tema_area_responsavel_ids INTEGER[] NOT NULL DEFAULT ARRAY[]::INTEGER[],
    ADD COLUMN IF NOT EXISTS tema_area_correlata_ids INTEGER[] NOT NULL DEFAULT ARRAY[]::INTEGER[],
    ADD COLUMN IF NOT EXISTS tema_status_id INTEGER;

ALTER TABLE pendencias.smdhc_pendencias_atualizacoes
    ADD COLUMN IF NOT EXISTS tema_atualizacao_tipo_id INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_smdhc_pendencias_tema_tipo_id'
    ) THEN
        ALTER TABLE pendencias.smdhc_pendencias
            ADD CONSTRAINT fk_smdhc_pendencias_tema_tipo_id
            FOREIGN KEY (tema_tipo_id) REFERENCES categoricas.c_geral_status(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_smdhc_pendencias_tema_area_demandante_id'
    ) THEN
        ALTER TABLE pendencias.smdhc_pendencias
            ADD CONSTRAINT fk_smdhc_pendencias_tema_area_demandante_id
            FOREIGN KEY (tema_area_demandante_id) REFERENCES categoricas.c_geral_status(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_smdhc_pendencias_tema_status_id'
    ) THEN
        ALTER TABLE pendencias.smdhc_pendencias
            ADD CONSTRAINT fk_smdhc_pendencias_tema_status_id
            FOREIGN KEY (tema_status_id) REFERENCES categoricas.c_geral_status(id);
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'fk_smdhc_pendencias_atualizacoes_tipo_id'
    ) THEN
        ALTER TABLE pendencias.smdhc_pendencias_atualizacoes
            ADD CONSTRAINT fk_smdhc_pendencias_atualizacoes_tipo_id
            FOREIGN KEY (tema_atualizacao_tipo_id) REFERENCES categoricas.c_geral_status(id);
    END IF;
END $$;

UPDATE categoricas.c_geral_status
SET ordem = CASE status
        WHEN 'Normatização e Atos Oficiais' THEN 10
        WHEN 'Gestão de Editais' THEN 20
        WHEN 'Saneamento de Passivo e Fluxo Processual' THEN 30
        WHEN 'Infraestrutura, Logística e RH' THEN 40
        WHEN 'Planejamento Estratégico e Compliance' THEN 50
        ELSE ordem
    END
WHERE schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_tipo';

UPDATE categoricas.c_geral_status
SET ordem = CASE status
        WHEN 'Gabinete' THEN 10
        WHEN 'Interno (DP)' THEN 20
        ELSE ordem
    END
WHERE schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_demandante';

UPDATE categoricas.c_geral_status
SET ordem = CASE status
        WHEN 'DP' THEN 10
        WHEN 'DGP' THEN 20
        WHEN 'DAC' THEN 30
        WHEN 'DGM' THEN 40
        ELSE ordem
    END
WHERE schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_responsavel';

UPDATE categoricas.c_geral_status
SET ordem = CASE status
        WHEN 'DP' THEN 10
        WHEN 'DGP' THEN 20
        WHEN 'DAC' THEN 30
        WHEN 'DGM' THEN 40
        WHEN 'Gabinete' THEN 50
        WHEN 'AJ' THEN 60
        WHEN 'CAF' THEN 70
        WHEN 'CPDDH' THEN 80
        WHEN 'CPIR' THEN 90
        WHEN 'CPM' THEN 100
        WHEN 'SESANA' THEN 110
        WHEN 'SMADS' THEN 120
        WHEN 'Casa Civil' THEN 130
        WHEN 'CDHOC' THEN 140
        WHEN 'Outras' THEN 150
        ELSE ordem
    END
WHERE schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_correlata';

UPDATE categoricas.c_geral_status
SET ordem = CASE status
        WHEN 'Não iniciado' THEN 10
        WHEN 'Iniciado' THEN 20
        WHEN 'Aguardando Aprovação' THEN 30
        WHEN 'Concluído' THEN 40
        ELSE ordem
    END
WHERE schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_status';

UPDATE categoricas.c_geral_status
SET ordem = CASE status
        WHEN 'Reuniões' THEN 10
        WHEN 'Outros' THEN 20
        ELSE ordem
    END
WHERE schema_table_coluna_r = 'pendencias.smdhc_pendencias_atualizacoes.tema_atualizacao_tipo';

UPDATE pendencias.smdhc_pendencias p
SET tema_tipo_id = c.id
FROM categoricas.c_geral_status c
WHERE p.tema_tipo_id IS NULL
  AND p.tema_tipo IS NOT NULL
  AND c.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_tipo'
  AND c.status = p.tema_tipo;

UPDATE pendencias.smdhc_pendencias p
SET tema_area_demandante_id = c.id
FROM categoricas.c_geral_status c
WHERE p.tema_area_demandante_id IS NULL
  AND p.tema_area_demandante IS NOT NULL
  AND c.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_demandante'
  AND c.status = p.tema_area_demandante;

UPDATE pendencias.smdhc_pendencias p
SET tema_status_id = c.id
FROM categoricas.c_geral_status c
WHERE p.tema_status_id IS NULL
  AND p.tema_status IS NOT NULL
  AND c.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_status'
  AND c.status = p.tema_status;

UPDATE pendencias.smdhc_pendencias_atualizacoes a
SET tema_atualizacao_tipo_id = c.id
FROM categoricas.c_geral_status c
WHERE a.tema_atualizacao_tipo_id IS NULL
  AND a.tema_atualizacao_tipo IS NOT NULL
  AND c.schema_table_coluna_r = 'pendencias.smdhc_pendencias_atualizacoes.tema_atualizacao_tipo'
  AND c.status = a.tema_atualizacao_tipo;

UPDATE pendencias.smdhc_pendencias p
SET tema_area_responsavel_ids = COALESCE((
    SELECT ARRAY_AGG(c.id ORDER BY src.ord)
    FROM unnest(COALESCE(p.tema_area_responsavel, ARRAY[]::TEXT[])) WITH ORDINALITY AS src(label, ord)
    JOIN categoricas.c_geral_status c
      ON c.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_responsavel'
     AND c.status = src.label
), ARRAY[]::INTEGER[])
WHERE COALESCE(cardinality(p.tema_area_responsavel_ids), 0) = 0
  AND COALESCE(cardinality(p.tema_area_responsavel), 0) > 0;

UPDATE pendencias.smdhc_pendencias p
SET tema_area_correlata_ids = COALESCE((
    SELECT ARRAY_AGG(c.id ORDER BY src.ord)
    FROM unnest(COALESCE(p.tema_area_correlata, ARRAY[]::TEXT[])) WITH ORDINALITY AS src(label, ord)
    JOIN categoricas.c_geral_status c
      ON c.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_correlata'
     AND c.status = src.label
), ARRAY[]::INTEGER[])
WHERE COALESCE(cardinality(p.tema_area_correlata_ids), 0) = 0
  AND COALESCE(cardinality(p.tema_area_correlata), 0) > 0;

UPDATE pendencias.smdhc_pendencias p
SET tema_tipo = c.status
FROM categoricas.c_geral_status c
WHERE p.tema_tipo_id = c.id
  AND c.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_tipo'
  AND COALESCE(p.tema_tipo, '') IS DISTINCT FROM COALESCE(c.status, '');

UPDATE pendencias.smdhc_pendencias p
SET tema_area_demandante = c.status
FROM categoricas.c_geral_status c
WHERE p.tema_area_demandante_id = c.id
  AND c.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_demandante'
  AND COALESCE(p.tema_area_demandante, '') IS DISTINCT FROM COALESCE(c.status, '');

UPDATE pendencias.smdhc_pendencias p
SET tema_status = c.status
FROM categoricas.c_geral_status c
WHERE p.tema_status_id = c.id
  AND c.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_status'
  AND COALESCE(p.tema_status, '') IS DISTINCT FROM COALESCE(c.status, '');

UPDATE pendencias.smdhc_pendencias_atualizacoes a
SET tema_atualizacao_tipo = c.status
FROM categoricas.c_geral_status c
WHERE a.tema_atualizacao_tipo_id = c.id
  AND c.schema_table_coluna_r = 'pendencias.smdhc_pendencias_atualizacoes.tema_atualizacao_tipo'
  AND COALESCE(a.tema_atualizacao_tipo, '') IS DISTINCT FROM COALESCE(c.status, '');

UPDATE pendencias.smdhc_pendencias p
SET tema_area_responsavel = COALESCE((
    SELECT ARRAY_AGG(COALESCE(c.status, '') ORDER BY u.ord)
    FROM unnest(COALESCE(p.tema_area_responsavel_ids, ARRAY[]::INTEGER[])) WITH ORDINALITY AS u(catalog_id, ord)
    LEFT JOIN categoricas.c_geral_status c
      ON c.id = u.catalog_id
), ARRAY[]::TEXT[])
WHERE COALESCE(cardinality(p.tema_area_responsavel_ids), 0) > 0;

UPDATE pendencias.smdhc_pendencias p
SET tema_area_correlata = COALESCE((
    SELECT ARRAY_AGG(COALESCE(c.status, '') ORDER BY u.ord)
    FROM unnest(COALESCE(p.tema_area_correlata_ids, ARRAY[]::INTEGER[])) WITH ORDINALITY AS u(catalog_id, ord)
    LEFT JOIN categoricas.c_geral_status c
      ON c.id = u.catalog_id
), ARRAY[]::TEXT[])
WHERE COALESCE(cardinality(p.tema_area_correlata_ids), 0) > 0;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_status_id_ativos
    ON pendencias.smdhc_pendencias (tema_status_id)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_tipo_id_ativos
    ON pendencias.smdhc_pendencias (tema_tipo_id)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_area_demandante_id_ativos
    ON pendencias.smdhc_pendencias (tema_area_demandante_id)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_area_responsavel_ids_gin
    ON pendencias.smdhc_pendencias
    USING GIN (tema_area_responsavel_ids);

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_area_correlata_ids_gin
    ON pendencias.smdhc_pendencias
    USING GIN (tema_area_correlata_ids);

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_atualizacoes_tipo_id_ativos
    ON pendencias.smdhc_pendencias_atualizacoes (tema_atualizacao_tipo_id, tema_atualizacao_data DESC)
    WHERE ativo = TRUE;

CREATE OR REPLACE FUNCTION pendencias.fn_sync_smdhc_pendencias_catalogo_snapshot()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP <> 'UPDATE' OR NEW.status IS NOT DISTINCT FROM OLD.status THEN
        RETURN NEW;
    END IF;

    IF NEW.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_tipo' THEN
        UPDATE pendencias.smdhc_pendencias
        SET tema_tipo = NEW.status,
            atualizado_por = COALESCE(atualizado_por, 'sync_c_geral_status'),
            atualizado_em = NOW()
        WHERE tema_tipo_id = NEW.id
          AND COALESCE(tema_tipo, '') IS DISTINCT FROM COALESCE(NEW.status, '');
    ELSIF NEW.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_demandante' THEN
        UPDATE pendencias.smdhc_pendencias
        SET tema_area_demandante = NEW.status,
            atualizado_por = COALESCE(atualizado_por, 'sync_c_geral_status'),
            atualizado_em = NOW()
        WHERE tema_area_demandante_id = NEW.id
          AND COALESCE(tema_area_demandante, '') IS DISTINCT FROM COALESCE(NEW.status, '');
    ELSIF NEW.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_status' THEN
        UPDATE pendencias.smdhc_pendencias
        SET tema_status = NEW.status,
            atualizado_por = COALESCE(atualizado_por, 'sync_c_geral_status'),
            atualizado_em = NOW()
        WHERE tema_status_id = NEW.id
          AND COALESCE(tema_status, '') IS DISTINCT FROM COALESCE(NEW.status, '');
    ELSIF NEW.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_responsavel' THEN
        UPDATE pendencias.smdhc_pendencias p
        SET tema_area_responsavel = COALESCE((
                SELECT ARRAY_AGG(COALESCE(c.status, '') ORDER BY u.ord)
                FROM unnest(COALESCE(p.tema_area_responsavel_ids, ARRAY[]::INTEGER[])) WITH ORDINALITY AS u(catalog_id, ord)
                LEFT JOIN categoricas.c_geral_status c
                  ON c.id = u.catalog_id
            ), ARRAY[]::TEXT[]),
            atualizado_por = COALESCE(p.atualizado_por, 'sync_c_geral_status'),
            atualizado_em = NOW()
        WHERE NEW.id = ANY(COALESCE(p.tema_area_responsavel_ids, ARRAY[]::INTEGER[]));
    ELSIF NEW.schema_table_coluna_r = 'pendencias.smdhc_pendencias.tema_area_correlata' THEN
        UPDATE pendencias.smdhc_pendencias p
        SET tema_area_correlata = COALESCE((
                SELECT ARRAY_AGG(COALESCE(c.status, '') ORDER BY u.ord)
                FROM unnest(COALESCE(p.tema_area_correlata_ids, ARRAY[]::INTEGER[])) WITH ORDINALITY AS u(catalog_id, ord)
                LEFT JOIN categoricas.c_geral_status c
                  ON c.id = u.catalog_id
            ), ARRAY[]::TEXT[]),
            atualizado_por = COALESCE(p.atualizado_por, 'sync_c_geral_status'),
            atualizado_em = NOW()
        WHERE NEW.id = ANY(COALESCE(p.tema_area_correlata_ids, ARRAY[]::INTEGER[]));
    ELSIF NEW.schema_table_coluna_r = 'pendencias.smdhc_pendencias_atualizacoes.tema_atualizacao_tipo' THEN
        UPDATE pendencias.smdhc_pendencias_atualizacoes
        SET tema_atualizacao_tipo = NEW.status,
            atualizado_por = COALESCE(atualizado_por, 'sync_c_geral_status'),
            atualizado_em = NOW()
        WHERE tema_atualizacao_tipo_id = NEW.id
          AND COALESCE(tema_atualizacao_tipo, '') IS DISTINCT FROM COALESCE(NEW.status, '');
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_sync_smdhc_pendencias_catalogo_snapshot ON categoricas.c_geral_status;

CREATE TRIGGER trg_sync_smdhc_pendencias_catalogo_snapshot
AFTER UPDATE OF status
ON categoricas.c_geral_status
FOR EACH ROW
EXECUTE FUNCTION pendencias.fn_sync_smdhc_pendencias_catalogo_snapshot();

DROP VIEW IF EXISTS pendencias.vw_smdhc_pendencias_priorizacao;

CREATE VIEW pendencias.vw_smdhc_pendencias_priorizacao AS
WITH matriz_resolvida AS (
    SELECT
        m.id,
        m.pendencia_id,
        m.principio_id,
        COALESCE(
            SUM(pn.tema_principios_nota_valor) FILTER (WHERE mf.id IS NOT NULL),
            MAX(m.tema_principios_nota),
            0
        )::INTEGER AS nota_resolvida
    FROM pendencias.smdhc_pendencias_matriz m
    LEFT JOIN pendencias.smdhc_pendencias_matriz_fatores mf
        ON mf.matriz_id = m.id
    LEFT JOIN pendencias.smdhc_pendencias_principios_notas pn
        ON pn.id = mf.principio_nota_id
       AND pn.ativo = TRUE
    WHERE m.ativo = TRUE
    GROUP BY m.id, m.pendencia_id, m.principio_id
),
matriz_notas AS (
    SELECT
        mr.pendencia_id,
        MAX(CASE WHEN ppr.tema_principios_ordem = 10 THEN mr.nota_resolvida END) AS nota_proximidade,
        MAX(CASE WHEN ppr.tema_principios_ordem = 20 THEN mr.nota_resolvida END) AS nota_enem,
        MAX(CASE WHEN ppr.tema_principios_ordem = 30 THEN mr.nota_resolvida END) AS nota_instabilidade,
        MAX(CASE WHEN ppr.tema_principios_ordem = 40 THEN mr.nota_resolvida END) AS nota_riscos
    FROM matriz_resolvida mr
    JOIN pendencias.smdhc_pendencias_principios ppr
      ON ppr.id = mr.principio_id
     AND ppr.ativo = TRUE
    GROUP BY mr.pendencia_id
),
responsavel_atual AS (
    SELECT DISTINCT ON (r.pendencia_id)
        r.pendencia_id,
        r.tema_responsavel AS responsavel
    FROM pendencias.smdhc_pendencias_resp r
    WHERE r.ativo = TRUE
    ORDER BY
        r.pendencia_id,
        r.atualizado_em DESC NULLS LAST,
        r.criado_em DESC NULLS LAST,
        r.id DESC
),
ultima_atualizacao AS (
    SELECT DISTINCT ON (a.pendencia_id)
        a.pendencia_id,
        a.tema_atualizacao      AS ultima_atualizacao,
        a.tema_atualizacao_data AS ultima_atualizacao_data,
        a.tema_acao_subsequente AS proxima_acao
    FROM pendencias.smdhc_pendencias_atualizacoes a
    WHERE a.ativo = TRUE
    ORDER BY
        a.pendencia_id,
        a.tema_atualizacao_data DESC NULLS LAST,
        a.atualizado_em DESC NULLS LAST,
        a.criado_em DESC NULLS LAST,
        a.id DESC
)
SELECT
    p.id AS pendencia_id,
    p.tema_nome,
    COALESCE(tipo_cat.status, p.tema_tipo) AS tema_tipo,
    p.tema_tipo_id,
    COALESCE(status_cat.status, p.tema_status) AS tema_status,
    p.tema_status_id,
    status_cat.ordem AS tema_status_ordem,
    p.tema_prazo_estimado,
    COALESCE(demandante_cat.status, p.tema_area_demandante) AS tema_area_demandante,
    p.tema_area_demandante_id,
    CASE
        WHEN COALESCE(cardinality(p.tema_area_responsavel_ids), 0) > 0 THEN
            ARRAY(
                SELECT COALESCE(c.status, '')
                FROM unnest(COALESCE(p.tema_area_responsavel_ids, ARRAY[]::INTEGER[])) WITH ORDINALITY AS u(catalog_id, ord)
                LEFT JOIN categoricas.c_geral_status c
                  ON c.id = u.catalog_id
                ORDER BY u.ord
            )
        ELSE COALESCE(p.tema_area_responsavel, ARRAY[]::TEXT[])
    END AS tema_area_responsavel,
    p.tema_area_responsavel_ids,
    CASE
        WHEN COALESCE(cardinality(p.tema_area_correlata_ids), 0) > 0 THEN
            ARRAY(
                SELECT COALESCE(c.status, '')
                FROM unnest(COALESCE(p.tema_area_correlata_ids, ARRAY[]::INTEGER[])) WITH ORDINALITY AS u(catalog_id, ord)
                LEFT JOIN categoricas.c_geral_status c
                  ON c.id = u.catalog_id
                ORDER BY u.ord
            )
        ELSE COALESCE(p.tema_area_correlata, ARRAY[]::TEXT[])
    END AS tema_area_correlata,
    p.tema_area_correlata_ids,
    COALESCE(mn.nota_proximidade, 0) AS nota_proximidade,
    COALESCE(mn.nota_enem, 0) AS nota_enem,
    COALESCE(mn.nota_instabilidade, 0) AS nota_instabilidade,
    COALESCE(mn.nota_riscos, 0) AS nota_riscos,
    ROW_NUMBER() OVER (
        ORDER BY
            COALESCE(mn.nota_proximidade, 0) DESC,
            COALESCE(mn.nota_enem, 0) DESC,
            COALESCE(mn.nota_instabilidade, 0) DESC,
            COALESCE(mn.nota_riscos, 0) DESC,
            CASE WHEN p.tema_prazo_estimado IS NULL THEN 1 ELSE 0 END,
            p.tema_prazo_estimado ASC NULLS LAST,
            p.id ASC
    ) AS ordem_prioridade,
    COALESCE(
        NULLIF(BTRIM(p.situacao_automatica), ''),
        CASE
            WHEN COALESCE(status_cat.ordem, 0) = 40 THEN 'Concluído'
            WHEN COALESCE(status_cat.ordem, 0) = 30 THEN 'Aguardando validação'
            WHEN p.tema_prazo_estimado IS NULL AND COALESCE(status_cat.ordem, 0) <> 40 THEN 'Sem prazo'
            WHEN p.tema_prazo_estimado < CURRENT_DATE AND COALESCE(status_cat.ordem, 0) <> 40 THEN 'Vencido'
            WHEN p.tema_prazo_estimado <= CURRENT_DATE + 30 AND COALESCE(status_cat.ordem, 0) <> 40 THEN 'Prazo próximo'
            WHEN ua.ultima_atualizacao_data IS NULL
                 AND p.criado_em::DATE <= CURRENT_DATE - 30
                 AND COALESCE(status_cat.ordem, 0) <> 40 THEN 'Parado'
            WHEN ua.ultima_atualizacao_data < CURRENT_DATE - 30
                 AND COALESCE(status_cat.ordem, 0) <> 40 THEN 'Parado'
            ELSE NULL
        END
    ) AS situacao_automatica,
    ra.responsavel,
    ua.ultima_atualizacao,
    ua.ultima_atualizacao_data,
    ua.proxima_acao
FROM pendencias.smdhc_pendencias p
LEFT JOIN matriz_notas mn
    ON mn.pendencia_id = p.id
LEFT JOIN responsavel_atual ra
    ON ra.pendencia_id = p.id
LEFT JOIN ultima_atualizacao ua
    ON ua.pendencia_id = p.id
LEFT JOIN categoricas.c_geral_status tipo_cat
    ON tipo_cat.id = p.tema_tipo_id
LEFT JOIN categoricas.c_geral_status status_cat
    ON status_cat.id = p.tema_status_id
LEFT JOIN categoricas.c_geral_status demandante_cat
    ON demandante_cat.id = p.tema_area_demandante_id
WHERE p.ativo = TRUE;

COMMIT;
