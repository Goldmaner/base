-- ============================================================================
-- Script: add_unique_constraint_ultra_liquidacoes.sql
-- Descrição: Adiciona constraint UNIQUE em (numero_termo, vigencia_inicial)
--            para permitir UPSERT no modo de parcelas projetadas
-- Data: 2026-01-26
-- ============================================================================

-- Verificar se já existe a constraint
DO $$
BEGIN
    -- Tentar adicionar a constraint UNIQUE
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'ultra_liquidacoes_termo_vigencia_key'
    ) THEN
        ALTER TABLE gestao_financeira.ultra_liquidacoes
        ADD CONSTRAINT ultra_liquidacoes_termo_vigencia_key 
        UNIQUE (numero_termo, vigencia_inicial);
        
        RAISE NOTICE 'Constraint UNIQUE adicionada com sucesso!';
    ELSE
        RAISE NOTICE 'Constraint já existe, nada a fazer.';
    END IF;
END $$;

-- Verificar se foi criada
SELECT 
    conname AS constraint_name,
    contype AS constraint_type,
    pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conrelid = 'gestao_financeira.ultra_liquidacoes'::regclass
AND conname = 'ultra_liquidacoes_termo_vigencia_key';
