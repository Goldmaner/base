-- Migration: upgrade categoricas.c_geral_legislacao
-- Adds: id PK, tipo_doc, descricao, link, status_vigencia
-- Run against Supabase (see GUIA_BANCO_DADOS.md)

BEGIN;

-- 1. Garantir que existe coluna id serial PK
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'categoricas'
          AND table_name   = 'c_geral_legislacao'
          AND column_name  = 'id'
    ) THEN
        ALTER TABLE categoricas.c_geral_legislacao
            ADD COLUMN id SERIAL PRIMARY KEY;
    END IF;
END $$;

-- 2. tipo_doc
ALTER TABLE categoricas.c_geral_legislacao
    ADD COLUMN IF NOT EXISTS tipo_doc VARCHAR(50);

-- 3. descricao
ALTER TABLE categoricas.c_geral_legislacao
    ADD COLUMN IF NOT EXISTS descricao TEXT;

-- 4. link
ALTER TABLE categoricas.c_geral_legislacao
    ADD COLUMN IF NOT EXISTS link TEXT;

-- 5. status_vigencia
ALTER TABLE categoricas.c_geral_legislacao
    ADD COLUMN IF NOT EXISTS status_vigencia VARCHAR(100) DEFAULT 'vigente';

-- 6. Classificar registros já existentes como 'Portaria' caso tipo_doc seja nulo
UPDATE categoricas.c_geral_legislacao
   SET tipo_doc = 'Portaria'
 WHERE tipo_doc IS NULL;

COMMIT;
