-- Script para criar tabela de contrapartida
-- Execute este script no PostgreSQL

CREATE TABLE IF NOT EXISTS analises_pc.conc_contrapartida (
    id SERIAL PRIMARY KEY,
    numero_termo VARCHAR(100) NOT NULL,
    competencia DATE,
    categoria_despesa VARCHAR(255),
    valor_previsto NUMERIC(15, 2) DEFAULT 0,
    valor_executado NUMERIC(15, 2) DEFAULT 0,
    valor_considerado NUMERIC(15, 2) DEFAULT 0,
    guia VARCHAR(50),
    comprovante VARCHAR(50),
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Índice para melhorar performance de busca
CREATE INDEX IF NOT EXISTS idx_conc_contrapartida_termo 
ON analises_pc.conc_contrapartida(numero_termo);

-- Comentários na tabela
COMMENT ON TABLE analises_pc.conc_contrapartida IS 'Tabela para controle de contrapartidas em projetos';
COMMENT ON COLUMN analises_pc.conc_contrapartida.competencia IS 'Data de competência. Valor 2020-01-01 representa "Sem competência definida"';
COMMENT ON COLUMN analises_pc.conc_contrapartida.valor_previsto IS 'Valor previsto da contrapartida';
COMMENT ON COLUMN analises_pc.conc_contrapartida.valor_executado IS 'Valor executado da contrapartida';
COMMENT ON COLUMN analises_pc.conc_contrapartida.valor_considerado IS 'Valor considerado/aprovado da contrapartida';
