-- ============================================================
-- Adicionar colunas tipo_doc e publico_alvo em manuais_documentos
-- Execute no pgAdmin antes de usar os novos campos no sistema
-- ============================================================

ALTER TABLE public.manuais_documentos
    ADD COLUMN IF NOT EXISTS tipo_doc      VARCHAR(200),
    ADD COLUMN IF NOT EXISTS publico_alvo  VARCHAR(300);

-- Criar a tabela de tipos de documento (se ainda não existir)
CREATE TABLE IF NOT EXISTS categoricas.c_geral_tipos_documentos_manuais (
    id       SERIAL PRIMARY KEY,
    tipo_doc VARCHAR(200) NOT NULL UNIQUE
);

-- Inserir tipos básicos (ajuste conforme necessário)
INSERT INTO categoricas.c_geral_tipos_documentos_manuais (tipo_doc)
VALUES
    ('Manual Operacional'),
    ('Procedimento Interno'),
    ('Instrução Normativa'),
    ('Checklist'),
    ('Formulário'),
    ('Template / Modelo'),
    ('Fluxograma'),
    ('Relatório Técnico'),
    ('Guia Rápido'),
    ('Protocolo')
ON CONFLICT (tipo_doc) DO NOTHING;

-- Verificação
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'manuais_documentos'
  AND column_name  IN ('tipo_doc', 'publico_alvo')
ORDER BY column_name;
