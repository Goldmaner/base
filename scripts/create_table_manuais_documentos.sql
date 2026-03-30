-- ============================================================
-- CREATE TABLE: public.manuais_documentos
-- Versões/documentos vinculados a cada manual em manuais_lista
-- Executar antes de usar a página de detalhamento
-- Criado em: Março 2026
-- ============================================================

CREATE TABLE IF NOT EXISTS public.manuais_documentos (
    id                  SERIAL PRIMARY KEY,
    manual_id           INTEGER NOT NULL
                            REFERENCES public.manuais_lista(id) ON DELETE CASCADE,
    manual_nome         VARCHAR(500) NOT NULL,
    manual_versionamento VARCHAR(50),
    manual_status       VARCHAR(100),
    manual_descricao    TEXT,
    manual_doc          VARCHAR(1000),   -- caminho relativo: modelos/Manuais/<manual_id>/<arquivo>
    manual_link         VARCHAR(1000),
    criado_por          VARCHAR(100),
    criado_em           TIMESTAMP DEFAULT NOW(),
    atualizado_por      VARCHAR(100),
    atualizado_em       TIMESTAMP
);

-- Índice para consultas por manual_id
CREATE INDEX IF NOT EXISTS idx_manuais_documentos_manual_id
    ON public.manuais_documentos(manual_id);

-- Comentários
COMMENT ON TABLE  public.manuais_documentos IS 'Versões e documentos vinculados aos manuais/procedimentos operacionais';
COMMENT ON COLUMN public.manuais_documentos.manual_doc  IS 'Caminho relativo ao arquivo: modelos/Manuais/<manual_id>/<nome_arquivo>';
COMMENT ON COLUMN public.manuais_documentos.manual_link IS 'URL externa de acesso ao documento/referência';

-- ── Verificação ───────────────────────────────────────────────────────────
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public' AND table_name = 'manuais_documentos'
ORDER BY ordinal_position;
