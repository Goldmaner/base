-- =============================================================================
-- SCRIPT: Criação das tabelas datas_importantes e c_geral_eventos
-- Data: 2026-04-29
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Tabela categórica: categoricas.c_geral_eventos
-- Catálogo de tipos de evento (lista suspensa para datas_importantes)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categoricas.c_geral_eventos (
    id                   SERIAL PRIMARY KEY,
    nome_data            TEXT NOT NULL,
    descricao_nome_data  TEXT,
    status               CHARACTER VARYING(20) DEFAULT 'ativo',
    created_at           TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_por          CHARACTER VARYING(100),
    updated_at           TIMESTAMP WITHOUT TIME ZONE,
    updated_por          CHARACTER VARYING(100)
);

-- Seed data
INSERT INTO categoricas.c_geral_eventos (nome_data, descricao_nome_data, created_por)
VALUES
    ('Abono',           'Dia de abono remunerado conforme legislação vigente.',                   'sistema'),
    ('Folga',           'Folga compensatória por serviço extraordinário ou banco de horas.',      'sistema'),
    ('Evento',          'Evento institucional, compromisso de serviço ou atividade externa.',     'sistema'),
    ('Consulta Médica', 'Consulta médica, odontológica ou procedimento de saúde correlato.',      'sistema')
ON CONFLICT DO NOTHING;

-- -----------------------------------------------------------------------------
-- 2. Tabela principal: public.datas_importantes
-- Registro de abonos, folgas, consultas e eventos por usuário
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.datas_importantes (
    id              SERIAL PRIMARY KEY,
    nome_data       TEXT NOT NULL,                              -- valor vindo de c_geral_eventos
    data_inicio     DATE NOT NULL,
    data_fim        DATE,
    horario_inicio  TIME WITHOUT TIME ZONE,
    horario_fim     TIME WITHOUT TIME ZONE,
    observacoes     TEXT,
    d_usuario       CHARACTER VARYING(20),                      -- RF do usuário (dono do registro)
    usuario_email   TEXT,                                       -- e-mail do usuário
    tipo_usuario    CHARACTER VARYING(100),                     -- unidade para filtro no calendário
    created_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_por     CHARACTER VARYING(100),
    updated_at      TIMESTAMP WITHOUT TIME ZONE,
    updated_por     CHARACTER VARYING(100)
);

-- Índices de performance
CREATE INDEX IF NOT EXISTS idx_datas_imp_d_usuario    ON public.datas_importantes (d_usuario);
CREATE INDEX IF NOT EXISTS idx_datas_imp_tipo_usuario ON public.datas_importantes (tipo_usuario);
CREATE INDEX IF NOT EXISTS idx_datas_imp_nome_data    ON public.datas_importantes (nome_data);
CREATE INDEX IF NOT EXISTS idx_datas_imp_data_inicio  ON public.datas_importantes (data_inicio);
