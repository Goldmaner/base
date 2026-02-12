-- Script para adicionar coluna ultima_atividade na tabela usuarios
-- Execução: psql -U postgres -d projeto_parcerias -f scripts/adicionar_coluna_ultima_atividade.sql

-- Adicionar coluna ultima_atividade se não existir
ALTER TABLE gestao_pessoas.usuarios 
ADD COLUMN IF NOT EXISTS ultima_atividade TIMESTAMP WITHOUT TIME ZONE;

-- Comentário na coluna
COMMENT ON COLUMN gestao_pessoas.usuarios.ultima_atividade IS 'Data/hora da última atividade do usuário no sistema';

-- Criar índice para melhorar performance de consultas
CREATE INDEX IF NOT EXISTS idx_usuarios_ultima_atividade 
ON gestao_pessoas.usuarios(ultima_atividade) 
WHERE ultima_atividade IS NOT NULL;

-- Atualizar usuários existentes com data atual
UPDATE gestao_pessoas.usuarios 
SET ultima_atividade = NOW() 
WHERE ultima_atividade IS NULL;

-- Mostrar resultado
SELECT 
    email, 
    tipo_usuario,
    ultima_atividade,
    CASE 
        WHEN ultima_atividade > NOW() - INTERVAL '15 minutes' THEN 'ATIVO'
        ELSE 'INATIVO'
    END as status
FROM gestao_pessoas.usuarios
ORDER BY ultima_atividade DESC NULLS LAST;
