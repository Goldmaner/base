-- =============================================================================
-- Migration: Gestao Monitoramento - Escopo DGM
-- Data: 2026-06-17
-- Descricao: Cria schema/tabelas de apoio ao escopo DGM e importa termos de
--            colaboracao de public.parcerias.
-- =============================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS gestao_monitoramento;

CREATE TABLE IF NOT EXISTS gestao_monitoramento.parcerias_dgm_escopo (
    id                 SERIAL PRIMARY KEY,
    numero_termo       TEXT NOT NULL
        REFERENCES public.parcerias(numero_termo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    dgm_escopo_termo   BOOLEAN NOT NULL DEFAULT TRUE,
    ativo              BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por         TEXT,
    criado_em          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por     TEXT,
    atualizado_em      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_parcerias_dgm_escopo_numero_termo UNIQUE (numero_termo)
);

COMMENT ON TABLE gestao_monitoramento.parcerias_dgm_escopo IS
    'Termos de colaboracao acompanhados ou potencialmente acompanhados pela DGM.';
COMMENT ON COLUMN gestao_monitoramento.parcerias_dgm_escopo.dgm_escopo_termo IS
    'Indica se o termo esta no escopo atual de apoio da DGM.';

CREATE TABLE IF NOT EXISTS gestao_monitoramento.parcerias_equipamentos (
    id                SERIAL PRIMARY KEY,
    numero_termo      TEXT NOT NULL
        REFERENCES public.parcerias(numero_termo)
        ON UPDATE CASCADE
        ON DELETE RESTRICT,
    termo_equipamento TEXT NOT NULL,
    ativo             BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por        TEXT,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por    TEXT,
    atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_parcerias_equipamentos_nome
        CHECK (BTRIM(termo_equipamento) <> '')
);

COMMENT ON TABLE gestao_monitoramento.parcerias_equipamentos IS
    'Equipamentos vinculados a cada termo de parceria monitorado pela DGM.';

CREATE INDEX IF NOT EXISTS idx_parcerias_dgm_escopo_flag_ativos
    ON gestao_monitoramento.parcerias_dgm_escopo (dgm_escopo_termo, numero_termo)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_parcerias_equipamentos_termo_ativos
    ON gestao_monitoramento.parcerias_equipamentos (numero_termo, termo_equipamento)
    WHERE ativo = TRUE;

INSERT INTO gestao_monitoramento.parcerias_dgm_escopo (
    numero_termo,
    dgm_escopo_termo,
    ativo,
    criado_por,
    atualizado_por
)
SELECT
    p.numero_termo,
    (
        p.inicio <= CURRENT_DATE
        AND p.final >= CURRENT_DATE
        AND p.numero_termo ~* '(CPM|ODH|CPPSR)'
    ) AS dgm_escopo_termo,
    TRUE,
    'migration_gestao_monitoramento_dgm',
    'migration_gestao_monitoramento_dgm'
FROM public.parcerias p
WHERE unaccent(COALESCE(p.tipo_termo, '')) ILIKE unaccent('%Colabora%')
ON CONFLICT (numero_termo) DO UPDATE
SET dgm_escopo_termo = EXCLUDED.dgm_escopo_termo,
    ativo            = TRUE,
    atualizado_por   = EXCLUDED.atualizado_por,
    atualizado_em    = NOW();

ALTER TABLE gestao_monitoramento.parcerias_dgm_escopo ENABLE ROW LEVEL SECURITY;
ALTER TABLE gestao_monitoramento.parcerias_equipamentos ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "authenticated_acesso_total"
    ON gestao_monitoramento.parcerias_dgm_escopo;
CREATE POLICY "authenticated_acesso_total"
ON gestao_monitoramento.parcerias_dgm_escopo
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

DROP POLICY IF EXISTS "authenticated_acesso_total"
    ON gestao_monitoramento.parcerias_equipamentos;
CREATE POLICY "authenticated_acesso_total"
ON gestao_monitoramento.parcerias_equipamentos
FOR ALL
TO authenticated
USING (true)
WITH CHECK (true);

COMMIT;
