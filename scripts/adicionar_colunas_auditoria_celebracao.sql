-- Migration: adiciona colunas de auditoria à tabela celebracao.celebracao_parcerias
-- Execução: idempotente (IF NOT EXISTS)

ALTER TABLE celebracao.celebracao_parcerias
    ADD COLUMN IF NOT EXISTS criado_por    TEXT,
    ADD COLUMN IF NOT EXISTS atualizado_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS atualizado_por TEXT;

-- Comentários
COMMENT ON COLUMN celebracao.celebracao_parcerias.criado_por    IS 'E-mail do usuário que criou o registro';
COMMENT ON COLUMN celebracao.celebracao_parcerias.atualizado_at IS 'Timestamp da última atualização';
COMMENT ON COLUMN celebracao.celebracao_parcerias.atualizado_por IS 'E-mail do usuário que realizou a última atualização';
