-- =============================================================================
-- MIGRATION: Escalas de Teletrabalho e Almoço
-- Data: 2026-05-19
-- Descrição: Adiciona suporte a escalas semanais de teletrabalho e horário
--            de almoço fixo por servidor, com dois novos campos em usuarios_infos.
-- =============================================================================
-- COMO RODAR (no PowerShell, na raiz do projeto):
--   $h = (Get-Content .env | Where-Object { $_ -match '^DB_HOST=' } | ForEach-Object { $_ -replace '^DB_HOST=','' })
--   $p = (Get-Content .env | Where-Object { $_ -match '^DB_PORT=' } | ForEach-Object { $_ -replace '^DB_PORT=','' })
--   $u = (Get-Content .env | Where-Object { $_ -match '^DB_USER=' } | ForEach-Object { $_ -replace '^DB_USER=','' })
--   $d = (Get-Content .env | Where-Object { $_ -match '^DB_DATABASE=' } | ForEach-Object { $_ -replace '^DB_DATABASE=','' })
--   $env:PGPASSWORD = (Get-Content .env | Where-Object { $_ -match '^DB_PASSWORD=' } | ForEach-Object { $_ -replace '^DB_PASSWORD=','' })
--   psql "host=$h port=$p dbname=$d user=$u sslmode=require" -f scripts/migration_escalas.sql
-- =============================================================================

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Novas colunas em gestao_pessoas.usuarios_infos
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE gestao_pessoas.usuarios_infos
    ADD COLUMN IF NOT EXISTS usuario_escala_permissao BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS usuario_unidade_alocada  TEXT;

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Auto-popular usuario_unidade_alocada para usuários existentes
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE gestao_pessoas.usuarios_infos ui
SET usuario_unidade_alocada = CASE u.tipo_usuario
    WHEN 'Agente DAC' THEN 'Divisão de Análise de Contas'
    WHEN 'Agente DGP' THEN 'Divisão de Gestão de Parcerias'
    WHEN 'Agente DP'  THEN 'Departamento de Parcerias'
    ELSE ui.usuario_unidade_alocada  -- preserva valor existente (ou NULL)
END
FROM gestao_pessoas.usuarios u
WHERE ui.usuario_email = u.email
  AND u.tipo_usuario IN ('Agente DAC', 'Agente DGP', 'Agente DP');

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Auto-popular usuario_escala_permissao = TRUE para Agente Público e admin
-- ─────────────────────────────────────────────────────────────────────────────

UPDATE gestao_pessoas.usuarios_infos ui
SET usuario_escala_permissao = TRUE
FROM gestao_pessoas.usuarios u
WHERE ui.usuario_email = u.email
  AND u.tipo_usuario IN ('Agente Público', 'admin');

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Tabela: calendario.escala_teletrabalho
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS calendario.escala_teletrabalho (
    id                SERIAL PRIMARY KEY,
    usuario_email     TEXT    NOT NULL,
    semana_inicio     DATE    NOT NULL,   -- sempre a segunda-feira da semana
    data_teletrabalho DATE,               -- NULL = sem teletrabalho nessa semana
    observacoes       TEXT,
    criado_por        VARCHAR(100),
    criado_em         TIMESTAMP DEFAULT NOW(),
    atualizado_por    VARCHAR(100),
    atualizado_em     TIMESTAMP,
    CONSTRAINT uq_escala_tt UNIQUE (usuario_email, semana_inicio)
);

COMMENT ON TABLE calendario.escala_teletrabalho IS
    'Escala semanal de teletrabalho: um registro por servidor por semana. '
    'semana_inicio é sempre a segunda-feira. data_teletrabalho é o dia efetivo '
    '(ou NULL quando não há teletrabalho na semana).';

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Tabela: calendario.escala_almoco
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS calendario.escala_almoco (
    id             SERIAL PRIMARY KEY,
    usuario_email  TEXT NOT NULL UNIQUE,
    horario_inicio TIME NOT NULL,
    horario_fim    TIME NOT NULL,
    observacoes    TEXT,
    criado_por     VARCHAR(100),
    criado_em      TIMESTAMP DEFAULT NOW(),
    atualizado_por VARCHAR(100),
    atualizado_em  TIMESTAMP
);

COMMENT ON TABLE calendario.escala_almoco IS
    'Horário fixo de almoço por servidor. Um único registro por pessoa, '
    'válido para todos os dias úteis. Não aparece no calendário principal.';

COMMIT;

-- ─────────────────────────────────────────────────────────────────────────────
-- VERIFICAÇÃO (rodar separadamente após o COMMIT):
-- ─────────────────────────────────────────────────────────────────────────────
-- SELECT usuario_email, usuario_escala_permissao, usuario_unidade_alocada
-- FROM gestao_pessoas.usuarios_infos LIMIT 10;
--
-- SELECT table_name FROM information_schema.tables
-- WHERE table_schema = 'calendario'
-- ORDER BY table_name;
