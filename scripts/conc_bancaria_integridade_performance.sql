-- Diagnostico e indices para conciliacao bancaria.
-- Execute fora de uma transacao, pois CREATE INDEX CONCURRENTLY nao aceita BEGIN.

-- Linhas de analise sem extrato correspondente.
SELECT ca.conc_extrato_id, ca.numero_termo, COUNT(*) AS total
FROM analises_pc.conc_analise ca
LEFT JOIN analises_pc.conc_extrato ce ON ce.id = ca.conc_extrato_id
WHERE ca.conc_extrato_id IS NOT NULL
  AND ce.id IS NULL
GROUP BY ca.conc_extrato_id, ca.numero_termo
ORDER BY total DESC;

-- Notas fiscais sem extrato correspondente.
SELECT nf.conc_extrato_id, nf.numero_termo, COUNT(*) AS total
FROM analises_pc.conc_extrato_notas_fiscais nf
LEFT JOIN analises_pc.conc_extrato ce ON ce.id = nf.conc_extrato_id
WHERE nf.conc_extrato_id IS NOT NULL
  AND ce.id IS NULL
GROUP BY nf.conc_extrato_id, nf.numero_termo
ORDER BY total DESC;

-- Linhas duplicadas por termo/indice.
SELECT numero_termo, indice, COUNT(*) AS total
FROM analises_pc.conc_extrato
WHERE indice IS NOT NULL
GROUP BY numero_termo, indice
HAVING COUNT(*) > 1
ORDER BY total DESC, numero_termo, indice;

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conc_extrato_termo_indice
    ON analises_pc.conc_extrato(numero_termo, indice);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conc_extrato_termo_id
    ON analises_pc.conc_extrato(numero_termo, id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conc_analise_extrato_termo
    ON analises_pc.conc_analise(conc_extrato_id, numero_termo);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_conc_nf_extrato_termo
    ON analises_pc.conc_extrato_notas_fiscais(conc_extrato_id, numero_termo);
