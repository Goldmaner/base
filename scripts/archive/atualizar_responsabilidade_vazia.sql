-- Script para atualizar responsabilidade_analise vazia (NULL)
-- Baseado na portaria do termo na tabela parcerias
--
-- Regras:
-- Portaria 021/SMDHC/2023 ou 090/SMDHC/2023 → Pessoa Gestora (3)
-- Portaria 121/SMDHC/2019 ou 140/SMDHC/2019 → Compartilhada (2)
-- Outras portarias → DP (1)
--
-- ATENÇÃO: Este script apenas atualiza valores NULL.
-- Não modifica registros que já têm responsabilidade definida.

BEGIN;

-- Atualizar registros vazios baseado na portaria do termo
UPDATE parcerias_analises pa
SET responsabilidade_analise = CASE
    -- Portarias pós-2023: Pessoa Gestora
    WHEN p.portaria ILIKE '%021/SMDHC/2023%' OR p.portaria ILIKE '%090/SMDHC/2023%' THEN 3
    
    -- Portarias de transição (2017-2023): Compartilhada
    WHEN p.portaria ILIKE '%121/SMDHC/2019%' OR p.portaria ILIKE '%140/SMDHC/2019%' THEN 2
    
    -- Todas as outras portarias: DP
    ELSE 1
END
FROM parcerias p
WHERE pa.numero_termo = p.numero_termo 
  AND pa.responsabilidade_analise IS NULL;

-- Verificar quantos registros foram atualizados
SELECT 
    'Registros atualizados' as descricao,
    COUNT(*) as quantidade
FROM parcerias_analises pa
JOIN parcerias p ON pa.numero_termo = p.numero_termo
WHERE pa.responsabilidade_analise IN (1, 2, 3);

-- Verificar distribuição após atualização
SELECT 
    CASE 
        WHEN pa.responsabilidade_analise = 1 THEN 'DP'
        WHEN pa.responsabilidade_analise = 2 THEN 'Compartilhada'
        WHEN pa.responsabilidade_analise = 3 THEN 'Pessoa Gestora'
        ELSE 'Vazia'
    END as responsabilidade,
    COUNT(*) as quantidade,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as percentual
FROM parcerias_analises pa
GROUP BY pa.responsabilidade_analise
ORDER BY pa.responsabilidade_analise;

-- Exemplos por portaria (primeiros 5 de cada tipo)
SELECT 
    p.portaria,
    CASE 
        WHEN pa.responsabilidade_analise = 1 THEN 'DP'
        WHEN pa.responsabilidade_analise = 2 THEN 'Compartilhada'
        WHEN pa.responsabilidade_analise = 3 THEN 'Pessoa Gestora'
        ELSE 'Vazia'
    END as responsabilidade,
    COUNT(*) as quantidade_prestacoes
FROM parcerias_analises pa
JOIN parcerias p ON pa.numero_termo = p.numero_termo
GROUP BY p.portaria, pa.responsabilidade_analise
ORDER BY p.portaria, pa.responsabilidade_analise;

COMMIT;

-- Para executar:
-- psql -U seu_usuario -d seu_banco -f atualizar_responsabilidade_vazia.sql
