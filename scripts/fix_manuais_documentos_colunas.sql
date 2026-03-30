-- ============================================================
-- FIX: Adicionar colunas faltantes em public.manuais_documentos
-- Execute este script para corrigir o erro 500 no detalhamento
-- ============================================================

-- Verificar estrutura atual da tabela
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'manuais_documentos'
ORDER BY ordinal_position;

-- Adicionar colunas faltantes (IF NOT EXISTS evita erro se já existirem)
ALTER TABLE public.manuais_documentos
    ADD COLUMN IF NOT EXISTS manual_id           INTEGER REFERENCES public.manuais_lista(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS manual_nome         VARCHAR(500),
    ADD COLUMN IF NOT EXISTS manual_versionamento VARCHAR(50),
    ADD COLUMN IF NOT EXISTS manual_status       VARCHAR(100),
    ADD COLUMN IF NOT EXISTS manual_descricao    TEXT,
    ADD COLUMN IF NOT EXISTS manual_doc          VARCHAR(1000),
    ADD COLUMN IF NOT EXISTS manual_link         VARCHAR(1000),
    ADD COLUMN IF NOT EXISTS criado_por          VARCHAR(100),
    ADD COLUMN IF NOT EXISTS criado_em           TIMESTAMP DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS atualizado_por      VARCHAR(100),
    ADD COLUMN IF NOT EXISTS atualizado_em       TIMESTAMP;

-- Criar índice se não existir
CREATE INDEX IF NOT EXISTS idx_manuais_documentos_manual_id
    ON public.manuais_documentos(manual_id);

-- Verificar resultado
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'manuais_documentos'
ORDER BY ordinal_position;
