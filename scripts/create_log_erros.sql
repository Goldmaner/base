-- =============================================================================
-- Migração: Tabela de Log de Erros do Sistema
-- Registra erros HTTP, queries lentas e falhas em APIs externas.
-- Executar como superuser ou owner do schema gestao_pessoas.
-- =============================================================================

CREATE TABLE IF NOT EXISTS gestao_pessoas.log_erros (
    id              SERIAL PRIMARY KEY,
    tipo_erro       VARCHAR(50)   NOT NULL,   -- 'http_erro' | 'query_lenta' | 'api_externa'
    created_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    -- Contexto HTTP (erros de rota Flask)
    endpoint        VARCHAR(500),
    metodo          VARCHAR(10),
    status_codigo   INTEGER,
    usuario_email   VARCHAR(255),
    ip_address      VARCHAR(45),

    -- Performance (queries lentas)
    duracao_ms      INTEGER,
    query_preview   TEXT,

    -- APIs externas (SOF, etc.)
    api_nome        VARCHAR(100),
    api_endpoint    VARCHAR(500),

    -- Genérico
    mensagem        TEXT,
    detalhes        JSONB,

    -- Gestão do painel
    resolvido       BOOLEAN       NOT NULL DEFAULT FALSE,
    resolvido_em    TIMESTAMPTZ,
    resolvido_por   VARCHAR(255)
);

-- Índices para as consultas do painel
CREATE INDEX IF NOT EXISTS idx_log_erros_created_at
    ON gestao_pessoas.log_erros (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_log_erros_tipo
    ON gestao_pessoas.log_erros (tipo_erro);

CREATE INDEX IF NOT EXISTS idx_log_erros_resolvido
    ON gestao_pessoas.log_erros (resolvido)
    WHERE resolvido = FALSE;
