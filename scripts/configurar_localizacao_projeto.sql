-- ============================================
-- Configuração do tipo de alteração "Localização do projeto"
-- Permite editar múltiplos endereços (5 campos por endereço)
-- ============================================

-- Atualizar configuração do tipo "Localização do projeto"
UPDATE categoricas.c_alt_tipo 
SET 
    alt_campo_tipo = 'enderecos',
    alt_campo_placeholder = 'Os endereços atuais serão carregados para edição',
    alt_campo_maxlength = NULL,
    alt_campo_min = NULL
WHERE alt_tipo = 'Localização do projeto';

-- Verificar configuração
SELECT 
    id,
    alt_tipo,
    alt_campo_tipo,
    alt_campo_placeholder
FROM categoricas.c_alt_tipo
WHERE alt_tipo = 'Localização do projeto';

-- ============================================
-- COMPORTAMENTO ESPERADO:
-- ============================================
-- 
-- 1. Ao selecionar "Localização do projeto" nas alterações DGP:
--    - Sistema carrega TODOS os endereços existentes via API
--    - Usuário vê cards com os 5 campos de cada endereço:
--      * parceria_logradouro
--      * parceria_numero
--      * parceria_complemento
--      * parceria_cep
--      * parceria_distrito
--      * observacao
--
-- 2. Usuário pode:
--    - EDITAR qualquer campo dos endereços existentes
--    - REMOVER endereços (botão lixeira)
--    - ADICIONAR novos endereços (botão "+")
--
-- 3. Ao salvar (status = Concluído):
--    - alt_old_info: JSON com endereços ANTES da alteração
--    - alt_info: JSON com endereços APÓS a alteração
--    - Sistema executa:
--      * DELETE de endereços removidos (não estão no novo JSON)
--      * UPDATE de endereços editados (têm ID no JSON)
--      * INSERT de endereços novos (sem ID no JSON)
--
-- 4. Estrutura do JSON em alt_info:
-- [
--   {
--     "id": 123,  // Opcional - se presente, é UPDATE; se ausente, é INSERT
--     "parceria_logradouro": "Rua Exemplo",
--     "parceria_numero": "100",
--     "parceria_complemento": "Sala 5",
--     "parceria_cep": "12345-678",
--     "parceria_distrito": "Centro",
--     "observacao": "Próximo ao metrô"
--   }
-- ]
--
-- ============================================
