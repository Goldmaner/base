-- =============================================================================
-- Migração: Criação da tabela gestao_pessoas.relatos_usuarios
-- Sistema de reporte manual de erros, sugestões, melhorias e dúvidas
-- Data: 05/05/2026
-- =============================================================================

CREATE TABLE IF NOT EXISTS gestao_pessoas.relatos_usuarios (
    id                  SERIAL PRIMARY KEY,
    tipo_relato         VARCHAR(40)  NOT NULL,           -- 'Erro', 'Sugestão', 'Melhoria', 'Dúvida'
    modulo              VARCHAR(100) NOT NULL,           -- módulo do sistema onde ocorreu
    titulo              VARCHAR(255) NOT NULL,           -- resumo em uma linha
    descricao           TEXT         NOT NULL,           -- descrição detalhada
    passos_reproducao   TEXT,                            -- passos para reproduzir (somente tipo Erro)
    url_pagina          VARCHAR(500),                    -- URL da página, auto-capturado no front
    prioridade_usuario  VARCHAR(20)  NOT NULL DEFAULT 'Normal', -- 'Urgente', 'Normal', 'Baixa'
    status              VARCHAR(40)  NOT NULL DEFAULT 'Aberto', -- 'Aberto', 'Em análise', 'Resolvido', 'Descartado'
    resposta_admin      TEXT,                            -- resposta visível ao usuário
    detalhes_tecnicos   JSONB,                           -- browser, resolução, etc. (auto-capturado)
    usuario_email       VARCHAR(200) NOT NULL,           -- e-mail de quem reportou
    usuario_nome        VARCHAR(200),                    -- d_usuario (denormalizado)
    tipo_usuario        VARCHAR(50),                     -- tipo no momento do envio
    criado_em           TIMESTAMP   NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMP,
    resolvido_por       VARCHAR(200),                    -- e-mail do admin que resolveu/descartou
    resolvido_em        TIMESTAMP,

    CONSTRAINT chk_relatos_tipo      CHECK (tipo_relato IN ('Erro', 'Sugestão', 'Melhoria', 'Dúvida')),
    CONSTRAINT chk_relatos_prioridade CHECK (prioridade_usuario IN ('Urgente', 'Normal', 'Baixa')),
    CONSTRAINT chk_relatos_status    CHECK (status IN ('Aberto', 'Em análise', 'Resolvido', 'Descartado'))
);

-- Índice para listagem do usuário (aba "Meus Relatos")
CREATE INDEX IF NOT EXISTS idx_relatos_usuario_email
    ON gestao_pessoas.relatos_usuarios (usuario_email, criado_em DESC);

-- Índice para painel admin (filtro por status)
CREATE INDEX IF NOT EXISTS idx_relatos_status_data
    ON gestao_pessoas.relatos_usuarios (status, criado_em DESC);

-- Índice para contagem diária (controle de limite anti-spam)
CREATE INDEX IF NOT EXISTS idx_relatos_email_dia
    ON gestao_pessoas.relatos_usuarios (usuario_email, (criado_em::date));

COMMENT ON TABLE gestao_pessoas.relatos_usuarios
    IS 'Relatos manuais de usuários: erros, sugestões, melhorias e dúvidas reportados via modal na home.';
