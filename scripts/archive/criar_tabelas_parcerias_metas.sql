-- =============================================================================
-- MÓDULO: Quadro de Metas — Plano de Trabalho
-- Criado em: 05/05/2026
-- Schema principal: celebracao
-- Schema categóricas: categoricas
--
-- LÓGICA DE meta_tipo_ids (INTEGER[]):
--   Cada ID referencia uma linha de categoricas.c_dgp_meta_tipos.
--   A coluna tipo_classificacao (TEXT livre) define o grupo ao qual o tipo
--   pertence (ex: "Tipo Q", "Tipo 2").
--   No front, checkboxes são agrupadas por tipo_classificacao.
--   Uma meta pode ter IDs de classificações diferentes (ex: Qualitativo+Impacto).
--   Consulta: WHERE 3 = ANY(meta_tipo_ids)
--   Inserção: ARRAY[1, 3, 5]::INTEGER[]
-- =============================================================================


-- =============================================================================
-- 1. categoricas.c_dgp_meta_tipos
--    Catálogo de tipos de meta, discriminado por tipo_classificacao (TEXT livre).
--    Valores iniciais sugeridos:
--      Tipo Q: Qualitativo, Quantitativo
--      Tipo 2: Implantação, Resultado, Impacto
-- =============================================================================
CREATE TABLE IF NOT EXISTS categoricas.c_dgp_meta_tipos (
    id                 SERIAL PRIMARY KEY,
    meta_tipo          TEXT NOT NULL,
    tipo_classificacao TEXT,
    descricao          TEXT,
    observacao         TEXT,
    criado_por         TEXT,
    criado_em          TIMESTAMP DEFAULT NOW()
);

-- Dados iniciais
INSERT INTO categoricas.c_dgp_meta_tipos (meta_tipo, tipo_classificacao, descricao, criado_por)
VALUES
    ('Qualitativo',  'Tipo Q', 'Meta mensurada por qualidade ou característica descritiva', 'sistema'),
    ('Quantitativo', 'Tipo Q', 'Meta mensurada por quantidade numérica',                   'sistema'),
    ('Implantação',  'Tipo 2', 'Meta relativa à implementação de ação ou serviço',          'sistema'),
    ('Resultado',    'Tipo 2', 'Meta relativa ao resultado direto da ação',                 'sistema'),
    ('Impacto',      'Tipo 2', 'Meta relativa ao impacto de médio/longo prazo',             'sistema')
ON CONFLICT DO NOTHING;


-- =============================================================================
-- 2. categoricas.c_dgp_indicadores
--    Catálogo de indicadores de aferição de metas.
-- =============================================================================
CREATE TABLE IF NOT EXISTS categoricas.c_dgp_indicadores (
    id          SERIAL PRIMARY KEY,
    indicador   TEXT NOT NULL,
    descricao   TEXT,
    observacao  TEXT,
    criado_por  TEXT,
    criado_em   TIMESTAMP DEFAULT NOW()
);


-- =============================================================================
-- 3. categoricas.c_dgp_meios_afericao
--    Catálogo de meios de aferição (formas de verificação das metas).
-- =============================================================================
CREATE TABLE IF NOT EXISTS categoricas.c_dgp_meios_afericao (
    id              SERIAL PRIMARY KEY,
    meios_afericao  TEXT NOT NULL,
    descricao       TEXT,
    observacao      TEXT,
    criado_por      TEXT,
    criado_em       TIMESTAMP DEFAULT NOW()
);


-- =============================================================================
-- 4. categoricas.c_dgp_plano_definicoes
--    Glossário de ajuda ao preenchimento. Espera-se uma linha ativa,
--    editável pela equipe sem necessidade de código.
--    Cada campo armazena o texto explicativo exibido como tooltip/ajuda
--    no modal de criação/edição de metas.
-- =============================================================================
CREATE TABLE IF NOT EXISTS categoricas.c_dgp_plano_definicoes (
    id                    SERIAL PRIMARY KEY,
    meta_definicao        TEXT,
    indicador_definicao   TEXT,
    meios_definicoes      TEXT,
    criado_por            TEXT,
    criado_em             TIMESTAMP DEFAULT NOW()
);

-- Inserir linha inicial com texto de exemplo (editável pelo painel de listas)
INSERT INTO categoricas.c_dgp_plano_definicoes (meta_definicao, indicador_definicao, meios_definicoes, criado_por)
VALUES (
    'Resultado concreto a ser alcançado com a execução do projeto, expresso de forma mensurável e com prazo definido.',
    'Parâmetro quantitativo ou qualitativo que permite verificar o cumprimento da meta.',
    'Fontes de dados, documentos ou instrumentos utilizados para verificar se o indicador foi atingido.'
    , 'sistema')
ON CONFLICT DO NOTHING;


-- =============================================================================
-- 5. celebracao.celebracao_metas
--    Tabela principal: múltiplas metas por processo SEI (1:N).
--
--    sei_numero: referência LÓGICA (sem FK declarada, conforme padrão do projeto).
--      Fontes possíveis:
--        - public.parcerias.sei_celeb
--        - celebracao.celebracao_parcerias.sei_celeb
--        - public.parcerias_edital.edital_processo_sei
--
--    meta_tipo_ids: INTEGER[] — array de IDs de c_dgp_meta_tipos.
--      Permite múltiplos tipos de múltiplas classificações.
--      Exemplo: {1, 4} = Qualitativo (Tipo Q) + Resultado (Tipo 2)
--
--    ordem: INTEGER — permite reordenar o quadro de metas por interface.
-- =============================================================================
CREATE TABLE IF NOT EXISTS celebracao.celebracao_metas (
    id                  SERIAL PRIMARY KEY,
    sei_numero          VARCHAR(30) NOT NULL,
    meta_titulo         VARCHAR(300) NOT NULL,
    meta_descricao      TEXT,
    meta_objetivo       TEXT,
    meta_tipo_ids       INTEGER[],
    indicadores_id      INTEGER,
    meta_obs_indicador  TEXT,
    meios_afericao_id   INTEGER,
    observacoes         TEXT,
    ordem               INTEGER DEFAULT 0,
    criado_por          TEXT,
    criado_em           TIMESTAMP DEFAULT NOW(),
    atualizado_por      TEXT,
    atualizado_em       TIMESTAMP
);

-- Índice para buscas frequentes por sei_numero
CREATE INDEX IF NOT EXISTS idx_celebracao_metas_sei_numero
    ON celebracao.celebracao_metas (sei_numero);

-- Índice GIN para consultas dentro do array meta_tipo_ids
CREATE INDEX IF NOT EXISTS idx_celebracao_metas_tipo_ids
    ON celebracao.celebracao_metas USING GIN (meta_tipo_ids);


-- =============================================================================
-- Verificação final
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ Tabelas criadas/verificadas com sucesso:';
    RAISE NOTICE '   categoricas.c_dgp_meta_tipos';
    RAISE NOTICE '   categoricas.c_dgp_indicadores';
    RAISE NOTICE '   categoricas.c_dgp_meios_afericao';
    RAISE NOTICE '   categoricas.c_dgp_plano_definicoes';
    RAISE NOTICE '   celebracao.celebracao_metas';
END $$;
