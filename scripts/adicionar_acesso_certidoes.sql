-- ==========================================
-- SCRIPT: Adicionar acesso 'certidoes' aos usuários
-- ==========================================
-- Data: 04/02/2026
-- Descrição: Adiciona o módulo 'certidoes' aos acessos dos usuários
--
-- OPÇÃO 1: Adicionar para todos os Agentes Públicos (admins)
-- ==========================================

-- Ver quem são os Agentes Públicos (já tem acesso total, mas vamos adicionar explicitamente)
SELECT id, email, tipo_usuario, acessos 
FROM gestao_pessoas.usuarios 
WHERE tipo_usuario = 'Agente Público';

-- Adicionar 'certidoes' aos acessos de todos os Agentes Públicos
UPDATE gestao_pessoas.usuarios
SET acessos = CASE 
    WHEN acessos IS NULL OR acessos = '' THEN 'certidoes'
    WHEN acessos NOT LIKE '%certidoes%' THEN acessos || ';certidoes'
    ELSE acessos
END
WHERE tipo_usuario = 'Agente Público';

-- ==========================================
-- OPÇÃO 2: Adicionar para um usuário específico
-- ==========================================

-- Ver acessos atuais de um usuário específico (substitua o email)
SELECT id, email, tipo_usuario, acessos 
FROM gestao_pessoas.usuarios 
WHERE email = 'seu_email@exemplo.com';

-- Adicionar 'certidoes' para um usuário específico (substitua o email)
UPDATE gestao_pessoas.usuarios
SET acessos = CASE 
    WHEN acessos IS NULL OR acessos = '' THEN 'certidoes'
    WHEN acessos NOT LIKE '%certidoes%' THEN acessos || ';certidoes'
    ELSE acessos
END
WHERE email = 'seu_email@exemplo.com';

-- ==========================================
-- OPÇÃO 3: Adicionar para todos os usuários
-- ==========================================

-- Adicionar 'certidoes' para TODOS os usuários
UPDATE gestao_pessoas.usuarios
SET acessos = CASE 
    WHEN acessos IS NULL OR acessos = '' THEN 'certidoes'
    WHEN acessos NOT LIKE '%certidoes%' THEN acessos || ';certidoes'
    ELSE acessos
END;

-- ==========================================
-- VERIFICAÇÃO: Ver todos os usuários com acesso a certidões
-- ==========================================
SELECT id, email, tipo_usuario, acessos 
FROM gestao_pessoas.usuarios 
WHERE acessos LIKE '%certidoes%' OR tipo_usuario = 'Agente Público'
ORDER BY tipo_usuario, email;
