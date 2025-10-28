-- Script CORRIGIDO: NÃO cria coluna pessoa_gestora em Parcerias
-- A pessoa gestora é armazenada na tabela parcerias_pg
-- Data: 2024-10-24

-- Verificar estrutura da tabela parcerias_pg
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'parcerias_pg' 
ORDER BY ordinal_position;

-- Verificar registros existentes
SELECT 
    numero_termo, 
    nome_pg, 
    data_de_criacao, 
    usuario_id, 
    dado_anterior 
FROM parcerias_pg 
ORDER BY data_de_criacao DESC 
LIMIT 10;
