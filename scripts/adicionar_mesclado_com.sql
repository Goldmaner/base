-- Adicionar coluna mesclado_com (array de inteiros) na tabela conc_extrato
-- Esta coluna armazena os índices das linhas mescladas com a linha atual

ALTER TABLE analises_pc.conc_extrato 
ADD COLUMN IF NOT EXISTS mesclado_com INTEGER[];

-- Comentário explicativo
COMMENT ON COLUMN analises_pc.conc_extrato.mesclado_com IS 'Array com índices das linhas mescladas (para débitos/créditos compostos). A primeira linha do grupo contém os índices das linhas secundárias.';
