-- ============================================================
-- Migração: Índices de performance + Tabela data_feriados
-- Gerado em: 2026-05-19
-- Executar em: Supabase (ver GUIA_BANCO_DADOS.md)
-- ============================================================

BEGIN;

-- ── Índices de performance ──────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_escala_tt_semana
    ON calendario.escala_teletrabalho (semana_inicio);

CREATE INDEX IF NOT EXISTS idx_escala_tt_email
    ON calendario.escala_teletrabalho (usuario_email);

CREATE INDEX IF NOT EXISTS idx_datas_imp_email_nome
    ON calendario.datas_importantes (usuario_email, nome_data);

-- ── Tabela de feriados ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS calendario.data_feriados (
    id            SERIAL PRIMARY KEY,
    data_feriado  DATE        NOT NULL,
    nome_feriado  TEXT        NOT NULL,
    tipo_feriado  TEXT        NOT NULL DEFAULT 'municipal',
    ativo         BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMP   NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feriados_data
    ON calendario.data_feriados (data_feriado);

CREATE INDEX IF NOT EXISTS idx_feriados_ano
    ON calendario.data_feriados (EXTRACT(YEAR FROM data_feriado));

-- ── Feriados de 2026 (somente se ainda não inseridos) ───────

INSERT INTO calendario.data_feriados (data_feriado, nome_feriado, tipo_feriado)
SELECT data_feriado, nome_feriado, tipo_feriado
FROM (VALUES
    ('2026-01-01'::date, 'Confraternização Universal',                        'nacional'),
    ('2026-01-25'::date, 'Aniversário da Cidade de São Paulo',                'municipal'),
    ('2026-04-03'::date, 'Paixão de Cristo / Sexta-feira Santa',              'nacional'),
    ('2026-04-21'::date, 'Tiradentes',                                        'nacional'),
    ('2026-05-01'::date, 'Dia Mundial do Trabalho',                           'nacional'),
    ('2026-06-04'::date, 'Corpus Christi',                                    'estadual'),
    ('2026-07-09'::date, 'Data Magna do Estado de São Paulo',                 'estadual'),
    ('2026-09-07'::date, 'Independência do Brasil',                           'nacional'),
    ('2026-10-12'::date, 'Nossa Senhora Aparecida — Padroeira do Brasil',     'nacional'),
    ('2026-10-28'::date, 'Dia do Servidor Público — ponto facultativo',       'nacional'),
    ('2026-11-02'::date, 'Finados',                                           'nacional'),
    ('2026-11-15'::date, 'Proclamação da República',                          'nacional'),
    ('2026-11-20'::date, 'Dia Nacional de Zumbi e da Consciência Negra',      'nacional'),
    ('2026-12-25'::date, 'Natal',                                             'nacional')
) AS v(data_feriado, nome_feriado, tipo_feriado)
WHERE NOT EXISTS (
    SELECT 1 FROM calendario.data_feriados f
    WHERE f.data_feriado = v.data_feriado
);

-- ── RLS ─────────────────────────────────────────────────────

ALTER TABLE calendario.data_feriados ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE schemaname = 'calendario'
          AND tablename  = 'data_feriados'
          AND policyname = 'authenticated_acesso_total'
    ) THEN
        CREATE POLICY "authenticated_acesso_total"
            ON calendario.data_feriados
            FOR ALL TO authenticated
            USING (true)
            WITH CHECK (true);
    END IF;
END $$;

COMMIT;
