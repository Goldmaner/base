-- =============================================================================
-- Tabela: gestao_pessoas.smdhc_servidores
-- Finalidade: Registro de nomeações CDA da SMDHC importadas do Diário Oficial
-- =============================================================================

CREATE TABLE IF NOT EXISTS gestao_pessoas.smdhc_servidores (
    id              SERIAL PRIMARY KEY,
    cda             INTEGER,
    numero_vaga     INTEGER,
    nome_servidor   TEXT,
    numero_rf       BIGINT,
    data_publicacao DATE,
    unidade         TEXT,
    numero_documento BIGINT,
    observacoes     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE gestao_pessoas.smdhc_servidores IS 'Registro de nomeações CDA da SMDHC importadas do Diário Oficial';
COMMENT ON COLUMN gestao_pessoas.smdhc_servidores.cda IS 'Nível CDA (ex: CDA-2 → 2)';
COMMENT ON COLUMN gestao_pessoas.smdhc_servidores.numero_rf IS 'Registro Funcional (somente dígitos, sem pontos)';
COMMENT ON COLUMN gestao_pessoas.smdhc_servidores.numero_documento IS 'Número do documento no D.O. (somente dígitos)';
