-- =============================================================================
-- SCRIPT: Criação da tabela public.datas_eventos
-- Baseada nas colunas do levantamento de atividades institucionais (planilha)
-- Data: 2026-04-29
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.datas_eventos (
    id                          SERIAL PRIMARY KEY,

    -- Identificação da atividade
    nome_atividade              TEXT NOT NULL,
    descritivo                  TEXT,                             -- Breve descritivo sobre o evento

    -- Histórico de edições anteriores
    realizado_2024              BOOLEAN DEFAULT FALSE,            -- Evento foi realizado em 2024?
    realizado_2025_previsao     BOOLEAN DEFAULT FALSE,            -- Realizado em 2025 ou tem previsão?

    -- Datas
    data_inicio                 DATE,                             -- Data (apenas) inicial
    datas_adicionais            TEXT,                             -- Datas adicionais (texto livre, ex: "10, 11 ou 12")

    -- Participação e local
    participacao                CHARACTER VARYING(80),            -- Ex: Organizador, Participante, Apoiador
    local                       TEXT,                             -- Local de realização
    previsao_participantes      INTEGER,                          -- Previsão de participantes

    -- Orçamento e infraestrutura
    constou_ploa_2025           BOOLEAN DEFAULT FALSE,            -- Atividade constou em previsão da PLOA 2025?
    necessita_infraestrutura    BOOLEAN DEFAULT FALSE,            -- Necessita infraestrutura?
    infraestrutura_mesma_edicao BOOLEAN DEFAULT FALSE,            -- Estrutura prevista será a mesma da edição anterior?
    valor_alimentacao           NUMERIC(14, 2),                   -- Valor alimentação (R$)
    alinhamento_aev             BOOLEAN DEFAULT FALSE,            -- Necessário alinhamento com equipe AEV?

    -- Observações gerais
    observacoes                 TEXT,

    -- Vínculo com usuário (dono do registro)
    d_usuario                   CHARACTER VARYING(20),
    usuario_email               TEXT,
    tipo_usuario                CHARACTER VARYING(100),           -- Para filtro de unidade no calendário

    -- Auditoria
    created_at                  TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    created_por                 CHARACTER VARYING(100),
    updated_at                  TIMESTAMP WITHOUT TIME ZONE,
    updated_por                 CHARACTER VARYING(100)
);

-- Índices de performance
CREATE INDEX IF NOT EXISTS idx_datas_eventos_d_usuario    ON public.datas_eventos (d_usuario);
CREATE INDEX IF NOT EXISTS idx_datas_eventos_tipo_usuario ON public.datas_eventos (tipo_usuario);
CREATE INDEX IF NOT EXISTS idx_datas_eventos_data_inicio  ON public.datas_eventos (data_inicio);
CREATE INDEX IF NOT EXISTS idx_datas_eventos_nome         ON public.datas_eventos (nome_atividade);
