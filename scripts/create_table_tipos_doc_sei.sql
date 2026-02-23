-- Script de criação da tabela c_geral_tipos_doc_sei
-- Tabela categórica para gerenciar tipos de documentos do SEI
-- Data: 13/02/2026

-- Criar tabela se não existir
CREATE TABLE IF NOT EXISTS categoricas.c_geral_tipos_doc_sei (
    id SERIAL PRIMARY KEY,
    tipo_doc VARCHAR(50) NOT NULL,
    descricao TEXT,
    status_tipo_doc VARCHAR(20) DEFAULT 'Ativo',
    created_por TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_por TEXT,
    updated_at TIMESTAMP
);

-- Comentários para documentação
COMMENT ON TABLE categoricas.c_geral_tipos_doc_sei IS 'Tipos de documentos utilizados no sistema SEI';
COMMENT ON COLUMN categoricas.c_geral_tipos_doc_sei.tipo_doc IS 'Nome/código do tipo de documento';
COMMENT ON COLUMN categoricas.c_geral_tipos_doc_sei.descricao IS 'Descrição detalhada do tipo de documento';
COMMENT ON COLUMN categoricas.c_geral_tipos_doc_sei.status_tipo_doc IS 'Status do tipo: Ativo, Inativo ou Em Desuso';

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_tipos_doc_sei_tipo ON categoricas.c_geral_tipos_doc_sei(tipo_doc);
CREATE INDEX IF NOT EXISTS idx_tipos_doc_sei_status ON categoricas.c_geral_tipos_doc_sei(status_tipo_doc);

-- Dados de exemplo (opcional - remover ou ajustar conforme necessário)
INSERT INTO categoricas.c_geral_tipos_doc_sei (tipo_doc, descricao, status_tipo_doc, created_por) VALUES
('Ofício', 'Documento formal de comunicação externa', 'Ativo', 'ADMIN'),
('Memorando', 'Documento de comunicação interna', 'Ativo', 'ADMIN'),
('Despacho', 'Manifestação sobre processos', 'Ativo', 'ADMIN'),
('Parecer Técnico', 'Análise técnica detalhada', 'Ativo', 'ADMIN'),
('Declaração', 'Documento declaratório', 'Ativo', 'ADMIN'),
('Termo de Referência', 'Especificações técnicas para contratações', 'Ativo', 'ADMIN'),
('Certidão', 'Documento certificatório', 'Ativo', 'ADMIN'),
('Portaria', 'Ato administrativo normativo', 'Ativo', 'ADMIN')
ON CONFLICT DO NOTHING;

-- Verificar inserções
SELECT * FROM categoricas.c_geral_tipos_doc_sei ORDER BY tipo_doc;
