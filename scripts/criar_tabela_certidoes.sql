-- ==========================================
-- SCRIPT: Criação da Tabela public.certidoes
-- ==========================================
-- Data: 04/02/2026
-- Descrição: Tabela para gerenciamento centralizado de certidões por OSC/CNPJ
--
-- INSTRUÇÕES:
-- 1. Execute este script no PostgreSQL
-- 2. Certifique-se de que o usuário tem permissão CREATE TABLE no schema public
-- 3. A tabela armazenará os metadados das certidões, os arquivos ficam em modelos/Certidoes/
-- ==========================================

-- Criar tabela certidoes
CREATE TABLE IF NOT EXISTS public.certidoes (
    id                      SERIAL PRIMARY KEY,
    osc                     TEXT NOT NULL,
    cnpj                    VARCHAR(20) NOT NULL,
    certidao_nome           VARCHAR(120) NOT NULL,
    certidao_emissor        VARCHAR(100) NOT NULL,
    certidao_vencimento     DATE NOT NULL,
    certidao_path           TEXT,
    certidao_arquivo_nome   VARCHAR(255),
    certidao_arquivo_size   BIGINT,
    certidao_status         VARCHAR(30) DEFAULT 'válida',
    observacoes             TEXT,
    encartado_por           VARCHAR(80),
    created_at              TIMESTAMP DEFAULT now(),
    updated_at              TIMESTAMP
);

-- Criar índices para melhorar performance de consultas
CREATE INDEX IF NOT EXISTS idx_certidoes_cnpj ON public.certidoes(cnpj);
CREATE INDEX IF NOT EXISTS idx_certidoes_osc ON public.certidoes(osc);
CREATE INDEX IF NOT EXISTS idx_certidoes_vencimento ON public.certidoes(certidao_vencimento);
CREATE INDEX IF NOT EXISTS idx_certidoes_status ON public.certidoes(certidao_status);

-- Criar trigger para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_certidoes_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_certidoes_timestamp
BEFORE UPDATE ON public.certidoes
FOR EACH ROW
EXECUTE FUNCTION update_certidoes_timestamp();

-- Comentários na tabela e colunas (documentação)
COMMENT ON TABLE public.certidoes IS 'Tabela para gerenciamento centralizado de certidões de OSCs';
COMMENT ON COLUMN public.certidoes.id IS 'Identificador único da certidão';
COMMENT ON COLUMN public.certidoes.osc IS 'Nome da Organização da Sociedade Civil';
COMMENT ON COLUMN public.certidoes.cnpj IS 'CNPJ da OSC (formato: XX.XXX.XXX/XXXX-XX)';
COMMENT ON COLUMN public.certidoes.certidao_nome IS 'Nome/tipo da certidão (ex: Certidão Negativa de Débitos Federais)';
COMMENT ON COLUMN public.certidoes.certidao_emissor IS 'Órgão emissor da certidão (ex: Receita Federal)';
COMMENT ON COLUMN public.certidoes.certidao_vencimento IS 'Data de vencimento da certidão';
COMMENT ON COLUMN public.certidoes.certidao_path IS 'Caminho relativo do arquivo (pasta_osc/arquivo.pdf)';
COMMENT ON COLUMN public.certidoes.certidao_arquivo_nome IS 'Nome original do arquivo enviado';
COMMENT ON COLUMN public.certidoes.certidao_arquivo_size IS 'Tamanho do arquivo em bytes';
COMMENT ON COLUMN public.certidoes.certidao_status IS 'Status da certidão: válida, vencida, cancelada';
COMMENT ON COLUMN public.certidoes.observacoes IS 'Observações e notas adicionais';
COMMENT ON COLUMN public.certidoes.encartado_por IS 'Usuário que fez o upload da certidão';
COMMENT ON COLUMN public.certidoes.created_at IS 'Data/hora de criação do registro';
COMMENT ON COLUMN public.certidoes.updated_at IS 'Data/hora da última atualização';

-- Verificar se a tabela foi criada com sucesso
SELECT 
    'Tabela public.certidoes criada com sucesso!' as status,
    COUNT(*) as total_registros
FROM public.certidoes;

-- ==========================================
-- PERMISSÕES (ajuste conforme necessário)
-- ==========================================
-- Caso você use um usuário específico para a aplicação:
-- GRANT SELECT, INSERT, UPDATE, DELETE ON public.certidoes TO seu_usuario_app;
-- GRANT USAGE, SELECT ON SEQUENCE certidoes_id_seq TO seu_usuario_app;
