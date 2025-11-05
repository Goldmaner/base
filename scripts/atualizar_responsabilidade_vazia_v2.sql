-- Script para atualizar responsabilidade_analise vazia (NULL)
-- Baseado na portaria do termo E na data de término da vigência da prestação
--
-- Regras com períodos de transição:
--
-- Portaria 021 (TFM/TCL sem FUMCAD):
--   - Se vigencia_final >= 01/03/2023 → Pessoa Gestora (3)
--   - Se vigencia_final < 01/03/2023 → Compartilhada (2) [era Portaria 121]
--
-- Portaria 090 (TFM/TCL com FUMCAD/FMID):
--   - Se vigencia_final >= 01/01/2024 → Pessoa Gestora (3)
--   - Se vigencia_final < 01/01/2024 → Compartilhada (2) [era Portaria 140]
--
-- Portaria 121 ou 140 diretamente → Compartilhada (2)
-- Outras portarias antigas → DP (1)
--
-- ATENÇÃO: Este script apenas atualiza valores NULL.
-- Não modifica registros que já têm responsabilidade definida.

BEGIN;

-- Atualizar registros vazios baseado na portaria e vigência final
UPDATE parcerias_analises pa
SET responsabilidade_analise = CASE
    -- Portaria 021: verifica data de transição (01/03/2023)
    WHEN p.portaria ILIKE '%021/SMDHC/2023%' OR p.portaria ILIKE '%021%2023%' THEN
        CASE 
            WHEN pa.vigencia_final >= '2023-03-01' THEN 3  -- Pessoa Gestora
            ELSE 2  -- Compartilhada (ainda era Portaria 121)
        END
    
    -- Portaria 090: verifica data de transição (01/01/2024)
    WHEN p.portaria ILIKE '%090/SMDHC/2023%' OR p.portaria ILIKE '%090%2023%' THEN
        CASE 
            WHEN pa.vigencia_final >= '2024-01-01' THEN 3  -- Pessoa Gestora
            ELSE 2  -- Compartilhada (ainda era Portaria 140)
        END
    
    -- Portarias de transição (2017-2023): sempre Compartilhada
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
FROM parcerias_analises
WHERE responsabilidade_analise IS NOT NULL;

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

-- Exemplos de transição (prestações que atravessaram mudança de portaria)
SELECT 
    pa.numero_termo,
    p.portaria,
    pa.tipo_prestacao,
    pa.numero_prestacao,
    pa.vigencia_inicial,
    pa.vigencia_final,
    CASE 
        WHEN pa.responsabilidade_analise = 1 THEN 'DP'
        WHEN pa.responsabilidade_analise = 2 THEN 'Compartilhada'
        WHEN pa.responsabilidade_analise = 3 THEN 'Pessoa Gestora'
        ELSE 'Vazia'
    END as responsabilidade
FROM parcerias_analises pa
JOIN parcerias p ON pa.numero_termo = p.numero_termo
WHERE (p.portaria ILIKE '%021%' OR p.portaria ILIKE '%090%')
  AND pa.vigencia_final IS NOT NULL
ORDER BY pa.vigencia_final
LIMIT 20;

COMMIT;

-- Para executar:
-- psql -U seu_usuario -d seu_banco -f atualizar_responsabilidade_vazia_v2.sql
