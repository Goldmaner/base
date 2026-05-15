-- Migração: adicionar temporalidade ao objetivo
-- Data: 2026-05-13

-- 1. Adicionar colunas
ALTER TABLE celebracao.celebracao_objetivos
    ADD COLUMN IF NOT EXISTS objetivo_inicio DATE,
    ADD COLUMN IF NOT EXISTS objetivo_fim    DATE;

-- 2. Preencher a partir de public.parcerias (prioridade) e celebracao.celebracao_parcerias (fallback)
UPDATE celebracao.celebracao_objetivos co
SET
    objetivo_inicio = COALESCE(p.inicio, cp.inicio),
    objetivo_fim    = COALESCE(p.final,  cp.final)
FROM (
    SELECT sei_celeb,
           MIN(inicio) AS inicio,
           MAX(final)  AS final
    FROM public.parcerias
    WHERE inicio IS NOT NULL OR final IS NOT NULL
    GROUP BY sei_celeb
) p
FULL JOIN (
    SELECT sei_celeb,
           MIN(inicio) AS inicio,
           MAX(final)  AS final
    FROM celebracao.celebracao_parcerias
    WHERE inicio IS NOT NULL OR final IS NOT NULL
    GROUP BY sei_celeb
) cp ON cp.sei_celeb = p.sei_celeb
WHERE co.sei_numero = COALESCE(p.sei_celeb, cp.sei_celeb)
  AND (co.objetivo_inicio IS NULL OR co.objetivo_fim IS NULL);

-- 3. Relatório rápido
SELECT
    COUNT(*)                                           AS total_objetivos,
    COUNT(*) FILTER (WHERE objetivo_inicio IS NOT NULL) AS com_inicio,
    COUNT(*) FILTER (WHERE objetivo_fim    IS NOT NULL) AS com_fim
FROM celebracao.celebracao_objetivos;
