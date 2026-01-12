-- Script para adicionar coluna numero_parcela na tabela temp_acomp_empenhos
-- Execute este script no PostgreSQL

-- Adicionar coluna numero_parcela se não existir
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'gestao_financeira' 
        AND table_name = 'temp_acomp_empenhos' 
        AND column_name = 'numero_parcela'
    ) THEN
        ALTER TABLE gestao_financeira.temp_acomp_empenhos 
        ADD COLUMN numero_parcela VARCHAR(10);
        
        RAISE NOTICE 'Coluna numero_parcela adicionada com sucesso!';
    ELSE
        RAISE NOTICE 'Coluna numero_parcela já existe.';
    END IF;
END $$;

-- Verificar estrutura da tabela
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_schema = 'gestao_financeira' 
AND table_name = 'temp_acomp_empenhos'
ORDER BY ordinal_position;
