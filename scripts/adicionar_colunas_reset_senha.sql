-- Script para adicionar colunas de reset de senha por token
-- Execute este script no PostgreSQL antes de usar a funcionalidade

-- Adicionar coluna reset_token (token de 6 dígitos)
ALTER TABLE gestao_pessoas.usuarios 
ADD COLUMN IF NOT EXISTS reset_token VARCHAR(6);

-- Adicionar coluna reset_token_expira (timestamp de expiração do token)
ALTER TABLE gestao_pessoas.usuarios 
ADD COLUMN IF NOT EXISTS reset_token_expira TIMESTAMP WITHOUT TIME ZONE;

-- Criar índice para melhorar performance nas buscas por token
CREATE INDEX IF NOT EXISTS idx_usuarios_reset_token 
ON gestao_pessoas.usuarios(reset_token) 
WHERE reset_token IS NOT NULL;

-- Comentários nas colunas
COMMENT ON COLUMN gestao_pessoas.usuarios.reset_token IS 'Token de 6 dígitos para reset de senha (enviado por e-mail)';
COMMENT ON COLUMN gestao_pessoas.usuarios.reset_token_expira IS 'Data/hora de expiração do token de reset (válido por 30 minutos)';

-- Verificar resultado
SELECT 
    column_name, 
    data_type, 
    is_nullable
FROM information_schema.columns
WHERE table_schema = 'gestao_pessoas' 
  AND table_name = 'usuarios'
  AND column_name IN ('reset_token', 'reset_token_expira')
ORDER BY ordinal_position;
