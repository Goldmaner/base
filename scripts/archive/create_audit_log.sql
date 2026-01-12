-- Tabela de auditoria para checklist de análises de prestação de contas
-- Registra todas as alterações feitas nas tabelas do schema analises_pc

CREATE TABLE IF NOT EXISTS analises_pc.checklist_change_log (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    numero_termo VARCHAR(80) NOT NULL,
    meses_analisados VARCHAR(8),
    tabela_origem VARCHAR(40) NOT NULL,         -- checklist_termo, checklist_recursos, checklist_analista
    coluna_alterada VARCHAR(40) NOT NULL,       -- nome do campo alterado
    valor_anterior VARCHAR(120),                -- antigo valor (sempre como texto)
    valor_novo VARCHAR(120),                    -- novo valor (sempre como texto)
    usuario VARCHAR(120),                       -- email do usuário que fez a alteração
    data_alteracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_audit_numero_termo 
ON analises_pc.checklist_change_log(numero_termo);

CREATE INDEX IF NOT EXISTS idx_audit_data 
ON analises_pc.checklist_change_log(data_alteracao DESC);

CREATE INDEX IF NOT EXISTS idx_audit_usuario 
ON analises_pc.checklist_change_log(usuario);

CREATE INDEX IF NOT EXISTS idx_audit_tabela 
ON analises_pc.checklist_change_log(tabela_origem);

-- Comentários
COMMENT ON TABLE analises_pc.checklist_change_log IS 
'Log de auditoria de todas as alterações feitas nos checklists de análise de prestação de contas';

COMMENT ON COLUMN analises_pc.checklist_change_log.numero_termo IS 
'Número do termo relacionado à alteração';

COMMENT ON COLUMN analises_pc.checklist_change_log.tabela_origem IS 
'Nome da tabela onde ocorreu a alteração (checklist_termo, checklist_recursos, checklist_analista)';

COMMENT ON COLUMN analises_pc.checklist_change_log.coluna_alterada IS 
'Nome da coluna/campo que foi alterado';

COMMENT ON COLUMN analises_pc.checklist_change_log.valor_anterior IS 
'Valor antes da alteração (convertido para texto)';

COMMENT ON COLUMN analises_pc.checklist_change_log.valor_novo IS 
'Valor após a alteração (convertido para texto)';

COMMENT ON COLUMN analises_pc.checklist_change_log.usuario IS 
'Email do usuário que realizou a alteração';

-- Verificar criação
SELECT 
    table_name,
    column_name,
    data_type
FROM information_schema.columns
WHERE table_schema = 'analises_pc' 
  AND table_name = 'checklist_change_log'
ORDER BY ordinal_position;
