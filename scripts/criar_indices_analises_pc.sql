-- Script para criar índices no schema analises_pc
-- Melhora a performance das consultas por termo e meses

-- Índices para checklist_termo
CREATE INDEX IF NOT EXISTS idx_checklist_termo_numero_termo 
ON analises_pc.checklist_termo(numero_termo);

CREATE INDEX IF NOT EXISTS idx_checklist_termo_meses 
ON analises_pc.checklist_termo(meses_analisados);

CREATE INDEX IF NOT EXISTS idx_checklist_termo_composto 
ON analises_pc.checklist_termo(numero_termo, meses_analisados);

-- Índices para checklist_analista
CREATE INDEX IF NOT EXISTS idx_checklist_analista_numero_termo 
ON analises_pc.checklist_analista(numero_termo);

CREATE INDEX IF NOT EXISTS idx_checklist_analista_meses 
ON analises_pc.checklist_analista(meses_analisados);

CREATE INDEX IF NOT EXISTS idx_checklist_analista_composto 
ON analises_pc.checklist_analista(numero_termo, meses_analisados);

CREATE INDEX IF NOT EXISTS idx_checklist_analista_nome 
ON analises_pc.checklist_analista(nome_analista);

-- Índices para checklist_recursos
CREATE INDEX IF NOT EXISTS idx_checklist_recursos_numero_termo 
ON analises_pc.checklist_recursos(numero_termo);

CREATE INDEX IF NOT EXISTS idx_checklist_recursos_meses 
ON analises_pc.checklist_recursos(meses_analisados);

CREATE INDEX IF NOT EXISTS idx_checklist_recursos_composto 
ON analises_pc.checklist_recursos(numero_termo, meses_analisados);

CREATE INDEX IF NOT EXISTS idx_checklist_recursos_tipo 
ON analises_pc.checklist_recursos(numero_termo, meses_analisados, tipo_recurso);

-- Comentários nas tabelas para documentação
COMMENT ON TABLE analises_pc.checklist_termo IS 
'Armazena o checklist principal de análise de prestação de contas por termo e período';

COMMENT ON TABLE analises_pc.checklist_analista IS 
'Armazena os analistas responsáveis por cada análise (pode haver múltiplos analistas)';

COMMENT ON TABLE analises_pc.checklist_recursos IS 
'Armazena as fases recursais de cada análise (pode haver múltiplos recursos)';

-- Constraints adicionais para garantir integridade
ALTER TABLE analises_pc.checklist_termo 
ADD CONSTRAINT uk_checklist_termo_composto 
UNIQUE (numero_termo, meses_analisados);

-- Verificar se os índices foram criados
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'analises_pc'
ORDER BY tablename, indexname;
