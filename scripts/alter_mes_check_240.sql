-- Migration: Ampliar limite da constraint parcerias_despesas_mes_check de 60 para 240 meses
-- Motivo: Parcerias de longa duração com aditivos ultrapassam 60 meses (ex: TCL/001/2018/SMDHC/CPCA)
-- Data: 2026-05-05

-- Verificar valor máximo atual antes de alterar
SELECT MAX(mes) AS max_mes_atual FROM parcerias_despesas;

-- Remover constraint antiga (limite: mes entre 1 e 60)
ALTER TABLE parcerias_despesas DROP CONSTRAINT parcerias_despesas_mes_check;

-- Recriar constraint com novo limite (240 meses = 20 anos)
ALTER TABLE parcerias_despesas ADD CONSTRAINT parcerias_despesas_mes_check
    CHECK (mes >= 1 AND mes <= 240);

-- Confirmar nova constraint
SELECT conname, consrc
FROM pg_constraint
WHERE conrelid = 'parcerias_despesas'::regclass
  AND conname = 'parcerias_despesas_mes_check';
