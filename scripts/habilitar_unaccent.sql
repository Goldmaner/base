-- Script para habilitar extensão unaccent no PostgreSQL
-- Necessário para busca case-insensitive sem acentos

-- Criar extensão se não existir
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Testar funcionamento
SELECT 
    'Associação de Proteção à Maternidade e à Infância de Sorocaba' as original,
    unaccent('Associação de Proteção à Maternidade e à Infância de Sorocaba') as sem_acentos,
    unaccent(REGEXP_REPLACE('Associação de Proteção à Maternidade e à Infância de Sorocaba', '[^a-zA-Z0-9 ]', '', 'g')) as limpo;

-- Verificar se extensão está instalada
SELECT * FROM pg_extension WHERE extname = 'unaccent';
