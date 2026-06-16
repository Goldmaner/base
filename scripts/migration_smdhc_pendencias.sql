-- =============================================================================
-- Migration: SMDHC Pendencias
-- Data: 2026-06-16
-- Descricao: Cria o schema pendencias, suas tabelas-base, seeds iniciais
--            e a view de priorizacao da Gestao de Pendencias e Urgencias.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Schema
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS pendencias;

-- -----------------------------------------------------------------------------
-- 2. Tabela principal
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias (
    id                    SERIAL PRIMARY KEY,
    tema_nome             TEXT NOT NULL,
    tema_tipo             TEXT,
    tema_descricao        TEXT,
    tema_area_demandante  TEXT,
    tema_area_responsavel TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    tema_area_correlata   TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    tema_status           TEXT,
    tema_prazo_estimado   DATE,
    tema_observacoes      TEXT,
    situacao_automatica   TEXT,
    prioridade_manual     INTEGER,
    prioridade_observacao TEXT,
    ativo                 BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por            TEXT,
    criado_em             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por        TEXT,
    atualizado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE pendencias.smdhc_pendencias IS
    'Pendencias institucionais da SMDHC com foco em status, prazo, responsaveis e priorizacao.';

-- -----------------------------------------------------------------------------
-- 3. Tabelas relacionadas
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_sei (
    id                       SERIAL PRIMARY KEY,
    pendencia_id             INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE,
    tema_processo            TEXT,
    tema_processo_observacao TEXT,
    ativo                    BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por               TEXT,
    criado_em                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por           TEXT,
    atualizado_em            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_resp (
    id               SERIAL PRIMARY KEY,
    pendencia_id     INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE,
    tema_responsavel TEXT,
    tema_envolvidos  TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    ativo            BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por       TEXT,
    criado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por   TEXT,
    atualizado_em    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_atualizacoes (
    id                    SERIAL PRIMARY KEY,
    pendencia_id          INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE,
    tema_atualizacao      TEXT NOT NULL,
    tema_atualizacao_data DATE NOT NULL DEFAULT CURRENT_DATE,
    tema_acao_subsequente TEXT,
    ativo                 BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por            TEXT,
    criado_em             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por        TEXT,
    atualizado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -----------------------------------------------------------------------------
-- 4. Tabelas da matriz de priorizacao
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_principios (
    id                         SERIAL PRIMARY KEY,
    tema_principios            TEXT NOT NULL,
    tema_principios_descricao  TEXT,
    tema_principios_calculo    TEXT,
    tema_principios_ordem      INTEGER NOT NULL,
    ativo                      BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por                 TEXT,
    criado_em                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por             TEXT,
    atualizado_em              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_smdhc_pendencias_principios_nome
        UNIQUE (tema_principios),
    CONSTRAINT uq_smdhc_pendencias_principios_ordem
        UNIQUE (tema_principios_ordem)
);

CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_principios_notas (
    id                             SERIAL PRIMARY KEY,
    principio_id                   INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias_principios(id) ON DELETE CASCADE,
    tema_principios_nota_nome      TEXT NOT NULL,
    tema_principios_nota_valor     INTEGER NOT NULL,
    tema_principios_nota_descricao TEXT,
    tema_principios_nota_ordem     INTEGER,
    ativo                          BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por                     TEXT,
    criado_em                      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por                 TEXT,
    atualizado_em                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_smdhc_pendencias_principios_notas
        UNIQUE (principio_id, tema_principios_nota_nome),
    CONSTRAINT ck_smdhc_pendencias_principios_notas_valor
        CHECK (tema_principios_nota_valor >= 0)
);

CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_matriz (
    id                   SERIAL PRIMARY KEY,
    pendencia_id         INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias(id) ON DELETE CASCADE,
    principio_id         INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias_principios(id) ON DELETE CASCADE,
    tema_principios_nota INTEGER NOT NULL DEFAULT 0,
    ativo                BOOLEAN NOT NULL DEFAULT TRUE,
    criado_por           TEXT,
    criado_em            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por       TEXT,
    atualizado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_smdhc_pendencias_matriz
        UNIQUE (pendencia_id, principio_id),
    CONSTRAINT ck_smdhc_pendencias_matriz_nota
        CHECK (tema_principios_nota >= 0)
);

CREATE TABLE IF NOT EXISTS pendencias.smdhc_pendencias_matriz_fatores (
    id                SERIAL PRIMARY KEY,
    matriz_id         INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias_matriz(id) ON DELETE CASCADE,
    principio_nota_id INTEGER NOT NULL
        REFERENCES pendencias.smdhc_pendencias_principios_notas(id) ON DELETE CASCADE,
    criado_por        TEXT,
    criado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_smdhc_pendencias_matriz_fatores
        UNIQUE (matriz_id, principio_nota_id)
);

-- -----------------------------------------------------------------------------
-- 5. Indices
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_status_ativos
    ON pendencias.smdhc_pendencias (tema_status)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_tipo_ativos
    ON pendencias.smdhc_pendencias (tema_tipo)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_prazo_ativos
    ON pendencias.smdhc_pendencias (tema_prazo_estimado)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_area_demandante_ativos
    ON pendencias.smdhc_pendencias (tema_area_demandante)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_area_responsavel_gin
    ON pendencias.smdhc_pendencias
    USING GIN (tema_area_responsavel);

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_area_correlata_gin
    ON pendencias.smdhc_pendencias
    USING GIN (tema_area_correlata);

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_sei_pendencia_ativos
    ON pendencias.smdhc_pendencias_sei (pendencia_id, atualizado_em DESC, criado_em DESC, id DESC)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_resp_pendencia_ativos
    ON pendencias.smdhc_pendencias_resp (pendencia_id, atualizado_em DESC, criado_em DESC, id DESC)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_atualizacoes_pendencia_ativos
    ON pendencias.smdhc_pendencias_atualizacoes (
        pendencia_id,
        tema_atualizacao_data DESC,
        atualizado_em DESC,
        criado_em DESC,
        id DESC
    )
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_principios_notas_principio_ativos
    ON pendencias.smdhc_pendencias_principios_notas (principio_id, tema_principios_nota_ordem)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_matriz_pendencia_ativos
    ON pendencias.smdhc_pendencias_matriz (pendencia_id, principio_id)
    WHERE ativo = TRUE;

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_matriz_fatores_matriz
    ON pendencias.smdhc_pendencias_matriz_fatores (matriz_id);

CREATE INDEX IF NOT EXISTS idx_smdhc_pendencias_matriz_fatores_nota
    ON pendencias.smdhc_pendencias_matriz_fatores (principio_nota_id);

-- -----------------------------------------------------------------------------
-- 6. Seeds de listas controladas
-- -----------------------------------------------------------------------------
INSERT INTO categoricas.c_geral_status (
    schema_table_coluna_r,
    status,
    descricao,
    ativo,
    nome_item_fantasia
)
VALUES
    ('pendencias.smdhc_pendencias.tema_tipo', 'Normatização e Atos Oficiais', 'Pendencias ligadas a normativos, atos oficiais e formalizacao institucional.', TRUE, 'Pendencias SMDHC: Tipo do Tema'),
    ('pendencias.smdhc_pendencias.tema_tipo', 'Gestão de Editais', 'Pendencias relacionadas a editais, chamamentos e fluxos associados.', TRUE, 'Pendencias SMDHC: Tipo do Tema'),
    ('pendencias.smdhc_pendencias.tema_tipo', 'Saneamento de Passivo e Fluxo Processual', 'Pendencias de regularizacao, passivos e organizacao do fluxo processual.', TRUE, 'Pendencias SMDHC: Tipo do Tema'),
    ('pendencias.smdhc_pendencias.tema_tipo', 'Infraestrutura, Logística e RH', 'Pendencias envolvendo estrutura operacional, logistica e recursos humanos.', TRUE, 'Pendencias SMDHC: Tipo do Tema'),
    ('pendencias.smdhc_pendencias.tema_tipo', 'Planejamento Estratégico e Compliance', 'Pendencias ligadas a planejamento, governanca e conformidade institucional.', TRUE, 'Pendencias SMDHC: Tipo do Tema'),

    ('pendencias.smdhc_pendencias.tema_area_demandante', 'Gabinete', 'Demanda originada no Gabinete.', TRUE, 'Pendencias SMDHC: Área Demandante'),
    ('pendencias.smdhc_pendencias.tema_area_demandante', 'Interno (DP)', 'Demanda originada internamente no Departamento de Parcerias.', TRUE, 'Pendencias SMDHC: Área Demandante'),

    ('pendencias.smdhc_pendencias.tema_area_responsavel', 'DP', 'Departamento de Parcerias.', TRUE, 'Pendencias SMDHC: Área Responsável'),
    ('pendencias.smdhc_pendencias.tema_area_responsavel', 'DGP', 'Divisão de Gestão de Parcerias.', TRUE, 'Pendencias SMDHC: Área Responsável'),
    ('pendencias.smdhc_pendencias.tema_area_responsavel', 'DAC', 'Divisão de Análise de Contas.', TRUE, 'Pendencias SMDHC: Área Responsável'),
    ('pendencias.smdhc_pendencias.tema_area_responsavel', 'DGM', 'Divisão de Gestão e Monitoramento.', TRUE, 'Pendencias SMDHC: Área Responsável'),

    ('pendencias.smdhc_pendencias.tema_area_correlata', 'DP', 'Departamento de Parcerias.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'DGP', 'Divisão de Gestão de Parcerias.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'DAC', 'Divisão de Análise de Contas.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'DGM', 'Divisão de Gestão e Monitoramento.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'Gabinete', 'Gabinete da SMDHC.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'AJ', 'Assessoria Jurídica.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'CAF', 'Coordenadoria de Administracao e Financas.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'CPDDH', 'Coordenadoria de Politicas para Direitos Humanos.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'CPIR', 'Coordenadoria de Politicas para Igualdade Racial.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'CPM', 'Coordenadoria de Politicas para Mulheres.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'SESANA', 'Secretaria Executiva de Seguranca Alimentar e Nutricional.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'SMADS', 'Secretaria Municipal de Assistencia e Desenvolvimento Social.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'Casa Civil', 'Casa Civil.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'CDHOC', 'Coordenadoria de Direitos Humanos e Ouvidoria Central.', TRUE, 'Pendencias SMDHC: Área Correlata'),
    ('pendencias.smdhc_pendencias.tema_area_correlata', 'Outras', 'Outras areas correlatas.', TRUE, 'Pendencias SMDHC: Área Correlata'),

    ('pendencias.smdhc_pendencias.tema_status', 'Iniciado', 'Pendencia em andamento.', TRUE, 'Pendencias SMDHC: Status'),
    ('pendencias.smdhc_pendencias.tema_status', 'Não iniciado', 'Pendencia ainda nao iniciada.', TRUE, 'Pendencias SMDHC: Status'),
    ('pendencias.smdhc_pendencias.tema_status', 'Aguardando Aprovação', 'Pendencia aguardando validacao ou aprovacao.', TRUE, 'Pendencias SMDHC: Status'),
    ('pendencias.smdhc_pendencias.tema_status', 'Concluído', 'Pendencia concluida.', TRUE, 'Pendencias SMDHC: Status')
ON CONFLICT (schema_table_coluna_r, status) DO UPDATE
SET descricao          = EXCLUDED.descricao,
    ativo              = EXCLUDED.ativo,
    nome_item_fantasia = EXCLUDED.nome_item_fantasia,
    atualizado_em      = NOW();

-- -----------------------------------------------------------------------------
-- 7. Seeds de principios e notas
-- -----------------------------------------------------------------------------
WITH principios_seed (
    tema_principios,
    tema_principios_descricao,
    tema_principios_calculo,
    tema_principios_ordem
) AS (
    VALUES
        (
            'Proximidade',
            'Mede o quao proxima a pendencia esta da atuacao direta do DP.',
            'Maior prioridade para notas mais altas: DP > SMDHC > Externo.',
            10
        ),
        (
            'ENEM',
            'Criterio institucional ENEM conforme a matriz da SMDHC.',
            'Maior prioridade para notas mais altas: Baixa > Média > Difícil.',
            20
        ),
        (
            'Instabilidade',
            'Mede a estabilidade do tema e o risco de mudanca no cenario.',
            'Maior prioridade para notas mais altas: Instável > Estável.',
            30
        ),
        (
            'Nº de Riscos',
            'Soma cumulativa dos fatores de risco associados a pendencia.',
            'Somatorio das notas selecionadas para riscos político, material e legal.',
            40
        )
)
INSERT INTO pendencias.smdhc_pendencias_principios (
    tema_principios,
    tema_principios_descricao,
    tema_principios_calculo,
    tema_principios_ordem,
    ativo,
    criado_por,
    atualizado_por
)
SELECT
    tema_principios,
    tema_principios_descricao,
    tema_principios_calculo,
    tema_principios_ordem,
    TRUE,
    'migration_smdhc_pendencias',
    'migration_smdhc_pendencias'
FROM principios_seed
ON CONFLICT (tema_principios) DO UPDATE
SET tema_principios_descricao = EXCLUDED.tema_principios_descricao,
    tema_principios_calculo   = EXCLUDED.tema_principios_calculo,
    tema_principios_ordem     = EXCLUDED.tema_principios_ordem,
    ativo                     = EXCLUDED.ativo,
    atualizado_por            = EXCLUDED.atualizado_por,
    atualizado_em             = NOW();

WITH notas_seed (
    principio_nome,
    nota_nome,
    nota_valor,
    nota_descricao,
    nota_ordem
) AS (
    VALUES
        ('Proximidade', 'DP', 3, 'Tema diretamente concentrado no Departamento de Parcerias.', 10),
        ('Proximidade', 'SMDHC', 2, 'Tema interno a SMDHC, mas nao exclusivo do DP.', 20),
        ('Proximidade', 'Externo', 1, 'Tema dependente de articulacao externa predominante.', 30),

        ('ENEM', 'Baixa', 3, 'Baixa complexidade no criterio ENEM.', 10),
        ('ENEM', 'Média', 2, 'Complexidade intermediaria no criterio ENEM.', 20),
        ('ENEM', 'Difícil', 1, 'Maior dificuldade no criterio ENEM.', 30),

        ('Instabilidade', 'Instável', 2, 'Tema sujeito a instabilidade ou mudanca relevante.', 10),
        ('Instabilidade', 'Estável', 1, 'Tema mais estavel e previsivel.', 20),

        ('Nº de Riscos', 'Político', 4, 'Risco politico associado a pendencia.', 10),
        ('Nº de Riscos', 'Material', 2, 'Risco material associado a pendencia.', 20),
        ('Nº de Riscos', 'Legal', 1, 'Risco legal associado a pendencia.', 30)
)
INSERT INTO pendencias.smdhc_pendencias_principios_notas (
    principio_id,
    tema_principios_nota_nome,
    tema_principios_nota_valor,
    tema_principios_nota_descricao,
    tema_principios_nota_ordem,
    ativo,
    criado_por,
    atualizado_por
)
SELECT
    p.id,
    ns.nota_nome,
    ns.nota_valor,
    ns.nota_descricao,
    ns.nota_ordem,
    TRUE,
    'migration_smdhc_pendencias',
    'migration_smdhc_pendencias'
FROM notas_seed ns
JOIN pendencias.smdhc_pendencias_principios p
  ON p.tema_principios = ns.principio_nome
ON CONFLICT (principio_id, tema_principios_nota_nome) DO UPDATE
SET tema_principios_nota_valor     = EXCLUDED.tema_principios_nota_valor,
    tema_principios_nota_descricao = EXCLUDED.tema_principios_nota_descricao,
    tema_principios_nota_ordem     = EXCLUDED.tema_principios_nota_ordem,
    ativo                          = EXCLUDED.ativo,
    atualizado_por                 = EXCLUDED.atualizado_por,
    atualizado_em                  = NOW();

-- -----------------------------------------------------------------------------
-- 8. View de priorizacao
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW pendencias.vw_smdhc_pendencias_priorizacao AS
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
    p.tema_tipo,
    p.tema_status,
    p.tema_prazo_estimado,
    p.tema_area_demandante,
    p.tema_area_responsavel,
    COALESCE(mn.nota_proximidade, 0)  AS nota_proximidade,
    COALESCE(mn.nota_enem, 0)         AS nota_enem,
    COALESCE(mn.nota_instabilidade, 0) AS nota_instabilidade,
    COALESCE(mn.nota_riscos, 0)       AS nota_riscos,
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
            WHEN p.tema_status = 'Concluído' THEN 'Concluído'
            WHEN p.tema_status = 'Aguardando Aprovação' THEN 'Aguardando validação'
            WHEN p.tema_prazo_estimado IS NULL AND COALESCE(p.tema_status, '') <> 'Concluído' THEN 'Sem prazo'
            WHEN p.tema_prazo_estimado < CURRENT_DATE AND COALESCE(p.tema_status, '') <> 'Concluído' THEN 'Vencido'
            WHEN p.tema_prazo_estimado <= CURRENT_DATE + 30 AND COALESCE(p.tema_status, '') <> 'Concluído' THEN 'Prazo próximo'
            WHEN ua.ultima_atualizacao_data IS NULL
                 AND p.criado_em::DATE <= CURRENT_DATE - 30
                 AND COALESCE(p.tema_status, '') <> 'Concluído' THEN 'Parado'
            WHEN ua.ultima_atualizacao_data < CURRENT_DATE - 30
                 AND COALESCE(p.tema_status, '') <> 'Concluído' THEN 'Parado'
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
WHERE p.ativo = TRUE;

COMMENT ON VIEW pendencias.vw_smdhc_pendencias_priorizacao IS
    'Consolida notas da matriz, ranking operacional, ultimo responsavel e ultima atualizacao das pendencias ativas.';

COMMIT;
