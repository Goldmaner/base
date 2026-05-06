-- ============================================================
-- MIGRATION: Kanban / Planner para Alterações DGP
-- Data: 2026-05-06
-- ============================================================

-- 1. Criar tabela de status categorizados
CREATE TABLE IF NOT EXISTS categoricas.c_alt_status_alteracao (
    id SERIAL PRIMARY KEY,
    alt_status TEXT NOT NULL UNIQUE,
    alt_status_descricao TEXT,
    alt_ordem INTEGER NOT NULL DEFAULT 99,
    observacoes TEXT,
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP
);

-- 2. Inserir os 14 status em ordem
INSERT INTO categoricas.c_alt_status_alteracao (alt_status, alt_status_descricao, alt_ordem) VALUES
    ('Pendente - DGP/ADIT',                             'Aguardando análise inicial da DGP/Aditamento', 1),
    ('Em análise - DGP/ADIT',                           'Em análise pela equipe DGP/Aditamento', 2),
    ('Aguardando decisão externa - DP/UG/OSC',          'Aguardando retorno de Diretoria de Parcerias, Unidade Gestora ou OSC', 3),
    ('Aguardando decisão externa - Conselho',            'Aguardando deliberação de Conselho', 4),
    ('Ateste de PC - DAC',                               'Aguardando ateste da Divisão de Análise de Contas', 5),
    ('Aguardando reserva - DOF',                         'Aguardando reserva orçamentária pelo DOF', 6),
    ('Aguardando parecer - AJ/AT',                       'Aguardando parecer jurídico ou técnico', 7),
    ('Despacho Autorizatório - GAB',                     'Aguardando despacho autorizatório do Gabinete', 8),
    ('Aguardando empenho - DEOF',                        'Aguardando empenho pelo DEOF', 9),
    ('Aguardando assinatura TA - DP/UG/OSC',             'Aguardando assinatura do Termo de Aditamento por DP/UG/OSC', 10),
    ('Aguardando assinatura TA - GAB',                   'Aguardando assinatura do Termo de Aditamento pelo Gabinete', 11),
    ('Publicação',                                       'Aguardando publicação no Diário Oficial', 12),
    ('Aguardando atualização da contratação - DEOF',     'Aguardando atualização da contratação pelo DEOF', 13),
    ('Concluído',                                        'Processo concluído', 14)
ON CONFLICT (alt_status) DO NOTHING;

-- 3. Adicionar colunas em public.termos_alteracoes
ALTER TABLE public.termos_alteracoes
    ADD COLUMN IF NOT EXISTS alt_prioridade TEXT,
    ADD COLUMN IF NOT EXISTS alt_data_inicio DATE DEFAULT CURRENT_DATE,
    ADD COLUMN IF NOT EXISTS alt_data_conclusao DATE,
    ADD COLUMN IF NOT EXISTS alt_oculto BOOLEAN DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS alt_marcadores TEXT;

-- 4. Migrar status existentes para os novos nomes
UPDATE public.termos_alteracoes
    SET alt_status = 'Pendente - DGP/ADIT'
    WHERE alt_status = 'Em análise prévia';

UPDATE public.termos_alteracoes
    SET alt_status = 'Em análise - DGP/ADIT'
    WHERE alt_status IN ('Iniciado', 'Em andamento');

-- 'Concluído' -> 'Concluído' (sem mudança)

-- 5. Criar tabela de cores dos marcadores
CREATE TABLE IF NOT EXISTS categoricas.c_kanban_marcadores_cores (
    id SERIAL PRIMARY KEY,
    marcador_nome TEXT NOT NULL UNIQUE,
    marcador_fonte TEXT,   -- 'tipo_contrato' | 'dotacao' | 'alt_tipo'
    marcador_cor TEXT NOT NULL DEFAULT 'Cinza',
    criado_em TIMESTAMP DEFAULT NOW(),
    atualizado_em TIMESTAMP
);

-- 6. Também adicionar colunas de auditoria na nova tabela de status (triggers opcionais)
-- (as colunas criado_em e atualizado_em já foram incluídas no CREATE TABLE)
