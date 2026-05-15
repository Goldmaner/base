-- ============================================================
-- MÓDULO MONITORAMENTO & AVALIAÇÃO — PRESTAÇÕES DE CONTAS
-- ============================================================
-- Execução: psql -d projeto_parcerias -f scripts/criar_tabelas_monit.sql
-- Data:     2026-05-13
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. categoricas.c_geral_status
--    Tabela universal de status por campo (schema.tabela.coluna)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categoricas.c_geral_status (
    id               SERIAL PRIMARY KEY,
    schema_table_coluna_r varchar(150) NOT NULL,
    status           varchar(100) NOT NULL,
    descricao        text,
    criado_em        timestamp DEFAULT now(),
    atualizado_em    timestamp DEFAULT now(),
    CONSTRAINT uq_c_geral_status UNIQUE (schema_table_coluna_r, status)
);

COMMENT ON TABLE categoricas.c_geral_status IS
  'Tabela universal de listas suspensas de status. '
  'schema_table_coluna_r identifica o campo no formato schema.tabela.coluna. '
  'Permite gerenciar todos os status do sistema em um único lugar.';

CREATE INDEX IF NOT EXISTS idx_c_geral_status_ref
  ON categoricas.c_geral_status (schema_table_coluna_r);

-- ------------------------------------------------------------
-- 2. public.parcerias_monit
--    Dados físicos de visita e monitoramento (1-para-1 com parcerias_analises)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.parcerias_monit (
    id                  SERIAL PRIMARY KEY,
    numero_termo        varchar(100) NOT NULL,
    tipo_prestacao      varchar(20)  NOT NULL,
    numero_prestacao    integer      NOT NULL,

    visita_status       varchar(100),
    visita_data         date,
    visita_horario      time,
    visita_responsavel  varchar(150),
    visita_avaliacao    varchar(100),

    monit_status        varchar(100),
    monit_responsavel   varchar(150),
    monit_avaliacao     varchar(100),
    monit_data          date,

    observacoes         text,

    criado_em           timestamp DEFAULT now(),
    atualizado_em       timestamp DEFAULT now(),
    criado_por          varchar(100),
    atualizado_por      varchar(100),

    CONSTRAINT uq_parcerias_monit_chave
        UNIQUE (numero_termo, tipo_prestacao, numero_prestacao)
);

COMMENT ON TABLE public.parcerias_monit IS
  'Dados físicos de M&A vinculados a parcerias_analises via chave composta '
  '(numero_termo, tipo_prestacao, numero_prestacao). '
  'Gerenciado por trigger de INSERT em parcerias_analises.';

CREATE INDEX IF NOT EXISTS idx_parcerias_monit_chave
  ON public.parcerias_monit (numero_termo, tipo_prestacao, numero_prestacao);

-- ------------------------------------------------------------
-- 3. public.parcerias_monit_adicional
--    Dados esparsos de justificativa e comissão (lazy insert)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.parcerias_monit_adicional (
    id                       SERIAL PRIMARY KEY,
    numero_termo             varchar(100) NOT NULL,
    tipo_prestacao           varchar(20)  NOT NULL,
    numero_prestacao         integer      NOT NULL,

    justificativa_status     varchar(100),
    justificativa_avaliacao  varchar(100),
    justificativa_data       date,
    justificativa_responsavel varchar(150),

    comissao_visita          varchar(100),
    comissao_ma              varchar(100),
    comissao_descumprimento  varchar(100),

    criado_em                timestamp DEFAULT now(),
    atualizado_em            timestamp DEFAULT now(),
    criado_por               varchar(100),
    atualizado_por           varchar(100),

    CONSTRAINT uq_parcerias_monit_adicional_chave
        UNIQUE (numero_termo, tipo_prestacao, numero_prestacao)
);

COMMENT ON TABLE public.parcerias_monit_adicional IS
  'Dados esparsos de justificativa e comissão. '
  'Linhas criadas apenas quando há dados (lazy). '
  'Vinculada a parcerias_analises via chave composta.';

CREATE INDEX IF NOT EXISTS idx_parcerias_monit_adicional_chave
  ON public.parcerias_monit_adicional (numero_termo, tipo_prestacao, numero_prestacao);

-- ------------------------------------------------------------
-- 4. Trigger: INSERT em parcerias_analises → auto-cria linha em parcerias_monit
--    ON CONFLICT DO NOTHING preserva dados existentes (ciclo DELETE+reinsert)
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_parcerias_analises_after_insert()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.parcerias_monit (numero_termo, tipo_prestacao, numero_prestacao)
    VALUES (NEW.numero_termo, NEW.tipo_prestacao, NEW.numero_prestacao)
    ON CONFLICT (numero_termo, tipo_prestacao, numero_prestacao) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_parcerias_analises_after_insert ON public.parcerias_analises;
CREATE TRIGGER trg_parcerias_analises_after_insert
    AFTER INSERT ON public.parcerias_analises
    FOR EACH ROW
    EXECUTE FUNCTION fn_parcerias_analises_after_insert();

-- ------------------------------------------------------------
-- 5. Trigger: UPDATE de chave composta em parcerias_analises
--    Propaga mudanças de numero_termo / tipo_prestacao / numero_prestacao
--    (raro, mas garante consistência em edições diretas)
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_parcerias_analises_after_update()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.numero_termo    IS DISTINCT FROM NEW.numero_termo    OR
       OLD.tipo_prestacao  IS DISTINCT FROM NEW.tipo_prestacao  OR
       OLD.numero_prestacao IS DISTINCT FROM NEW.numero_prestacao THEN

        UPDATE public.parcerias_monit
           SET numero_termo     = NEW.numero_termo,
               tipo_prestacao   = NEW.tipo_prestacao,
               numero_prestacao = NEW.numero_prestacao,
               atualizado_em    = now()
         WHERE numero_termo     = OLD.numero_termo
           AND tipo_prestacao   = OLD.tipo_prestacao
           AND numero_prestacao = OLD.numero_prestacao;

        UPDATE public.parcerias_monit_adicional
           SET numero_termo     = NEW.numero_termo,
               tipo_prestacao   = NEW.tipo_prestacao,
               numero_prestacao = NEW.numero_prestacao,
               atualizado_em    = now()
         WHERE numero_termo     = OLD.numero_termo
           AND tipo_prestacao   = OLD.tipo_prestacao
           AND numero_prestacao = OLD.numero_prestacao;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_parcerias_analises_after_update ON public.parcerias_analises;
CREATE TRIGGER trg_parcerias_analises_after_update
    AFTER UPDATE ON public.parcerias_analises
    FOR EACH ROW
    EXECUTE FUNCTION fn_parcerias_analises_after_update();

-- ------------------------------------------------------------
-- 6. Seed: categoricas.c_geral_status
-- ------------------------------------------------------------
INSERT INTO categoricas.c_geral_status (schema_table_coluna_r, status) VALUES
    -- visita_avaliacao
    ('public.parcerias_monit.visita_avaliacao', '-'),
    ('public.parcerias_monit.visita_avaliacao', 'Visita não realizada - Encerrado'),
    ('public.parcerias_monit.visita_avaliacao', 'Não analisado'),
    ('public.parcerias_monit.visita_avaliacao', 'Notificado'),
    ('public.parcerias_monit.visita_avaliacao', 'Notificação respondida'),
    ('public.parcerias_monit.visita_avaliacao', 'Transporte agendado'),
    ('public.parcerias_monit.visita_avaliacao', 'Visita Realizada'),
    ('public.parcerias_monit.visita_avaliacao', 'Finalizado'),
    ('public.parcerias_monit.visita_avaliacao', 'Resposta de Visita'),
    ('public.parcerias_monit.visita_avaliacao', 'Acompanhamento Pessoa Gestora'),
    ('public.parcerias_monit.visita_avaliacao', 'Não registrado'),

    -- monit_status
    ('public.parcerias_monit.monit_status', '-'),
    ('public.parcerias_monit.monit_status', 'Não analisado'),
    ('public.parcerias_monit.monit_status', 'Notificado M&A'),
    ('public.parcerias_monit.monit_status', 'Notificado (Justificativa)'),
    ('public.parcerias_monit.monit_status', 'Relatório de Execução Financeira'),
    ('public.parcerias_monit.monit_status', 'Relatório M&A'),
    ('public.parcerias_monit.monit_status', 'Rescindido'),
    ('public.parcerias_monit.monit_status', 'Não analisado - Pessoa Gestora'),

    -- monit_avaliacao (nota: no Excel constava como parcerias_monit_status — typo corrigido)
    ('public.parcerias_monit.monit_avaliacao', 'Satisfatório'),
    ('public.parcerias_monit.monit_avaliacao', 'Parcial'),
    ('public.parcerias_monit.monit_avaliacao', 'Insatisfatório'),
    ('public.parcerias_monit.monit_avaliacao', '-'),
    ('public.parcerias_monit.monit_avaliacao', 'Da Pessoa Gestora'),

    -- justificativa_status
    ('public.parcerias_monit_adicional.justificativa_status', 'Respondido'),
    ('public.parcerias_monit_adicional.justificativa_status', 'Notificado'),
    ('public.parcerias_monit_adicional.justificativa_status', 'Analisado'),
    ('public.parcerias_monit_adicional.justificativa_status', 'Não Respondido'),

    -- comissao_visita
    ('public.parcerias_monit_adicional.comissao_visita', 'Encaminhado'),
    ('public.parcerias_monit_adicional.comissao_visita', 'Homologado'),
    ('public.parcerias_monit_adicional.comissao_visita', 'Não encaminhado')

ON CONFLICT (schema_table_coluna_r, status) DO NOTHING;

-- ------------------------------------------------------------
-- 7. Retroativo: criar linhas de parcerias_monit para análises existentes
-- ------------------------------------------------------------
INSERT INTO public.parcerias_monit (numero_termo, tipo_prestacao, numero_prestacao)
SELECT numero_termo, tipo_prestacao, numero_prestacao
FROM public.parcerias_analises
ON CONFLICT (numero_termo, tipo_prestacao, numero_prestacao) DO NOTHING;

COMMIT;

-- Verificação rápida
SELECT
    (SELECT COUNT(*) FROM categoricas.c_geral_status)       AS "c_geral_status rows",
    (SELECT COUNT(*) FROM public.parcerias_monit)           AS "parcerias_monit rows",
    (SELECT COUNT(*) FROM public.parcerias_monit_adicional) AS "parcerias_monit_adicional rows",
    (SELECT COUNT(*) FROM public.parcerias_analises)        AS "parcerias_analises rows (referência)";
