-- ============================================================
-- INSERT: public.manuais_lista
-- Gerado em: Março 2026
-- Todos com manual_tipo = 'Operação', manual_status = NULL,
-- manual_relacionamento = NULL, manual_descricao = NULL
-- ============================================================

INSERT INTO public.manuais_lista
  (manual_tipo, manual_nome, manual_status, manual_relacionamento, manual_descricao, manual_area)
VALUES

-- ── OPERAÇÕES GERAIS DA UNIDADE (COMPARTILHADAS) ─────────────────────────
('Operação', 'Análise e desenvolvimento de metodologias',                               NULL, NULL, NULL, 'Operações Gerais da Unidade (Compartilhadas)'),
('Operação', 'Relatórios e assessoramento',                                             NULL, NULL, NULL, 'Operações Gerais da Unidade (Compartilhadas)'),
('Operação', 'Manifestação de órgãos controladores',                                   NULL, NULL, NULL, 'Operações Gerais da Unidade (Compartilhadas)'),
('Operação', 'Atendimento',                                                             NULL, NULL, NULL, 'Operações Gerais da Unidade (Compartilhadas)'),
('Operação', 'Gestão do Sistema Eletrônico de Informações (SEI)',                       NULL, NULL, NULL, 'Operações Gerais da Unidade (Compartilhadas)'),
('Operação', 'Capacitações',                                                            NULL, NULL, NULL, 'Operações Gerais da Unidade (Compartilhadas)'),
('Operação', 'Operações no banco de dados',                                             NULL, NULL, NULL, 'Operações Gerais da Unidade (Compartilhadas)'),
('Operação', 'Reuniões',                                                                NULL, NULL, NULL, 'Operações Gerais da Unidade (Compartilhadas)'),
('Operação', 'Gestão de Pessoas',                                                       NULL, NULL, NULL, 'Operações Gerais da Unidade (Compartilhadas)'),

-- ── DEPARTAMENTO DE PARCERIAS (DP) ────────────────────────────────────────
('Operação', 'Gestão dos Editais de Parcerias',                                         NULL, NULL, NULL, 'Departamento de Parcerias (DP)'),
('Operação', 'Gestão Orçamentária de Parcerias',                                       NULL, NULL, NULL, 'Departamento de Parcerias (DP)'),
('Operação', 'Autuação de processos de celebração de emendas parlamentares',           NULL, NULL, NULL, 'Departamento de Parcerias (DP)'),
('Operação', 'Finalização processual e destinação de imobilizado',                     NULL, NULL, NULL, 'Departamento de Parcerias (DP)'),
('Operação', 'Articulação com as áreas externas',                                      NULL, NULL, NULL, 'Departamento de Parcerias (DP)'),
('Operação', 'Tratativas externas: Informativo do Prefeito, E-SIC e Portal da Transparência', NULL, NULL, NULL, 'Departamento de Parcerias (DP)'),
('Operação', 'Gestão do SICONV / TransfereGOV',                                        NULL, NULL, NULL, 'Departamento de Parcerias (DP)'),
('Operação', 'Solicitações de materiais de escritório',                                NULL, NULL, NULL, 'Departamento de Parcerias (DP)'),

-- ── DIVISÃO DE GESTÃO DE PARCERIAS (DGP) ─────────────────────────────────
('Operação', 'Celebração de parcerias',                                                NULL, NULL, NULL, 'Divisão de Gestão de Parcerias (DGP)'),
('Operação', 'Gerenciamento do CENTS',                                                 NULL, NULL, NULL, 'Divisão de Gestão de Parcerias (DGP)'),
('Operação', 'Alterações contratuais',                                                 NULL, NULL, NULL, 'Divisão de Gestão de Parcerias (DGP)'),
('Operação', 'Monitoramento e avaliação',                                              NULL, NULL, NULL, 'Divisão de Gestão de Parcerias (DGP)'),
('Operação', 'Controle processual',                                                    NULL, NULL, NULL, 'Divisão de Gestão de Parcerias (DGP)'),

-- ── DIVISÃO DE ANÁLISE DE CONTAS (DAC) ───────────────────────────────────
('Operação', 'Pesquisas de Parcerias',                                                 NULL, NULL, NULL, 'Divisão de Análise de Contas (DAC)'),
('Operação', 'Gerenciamento financeiro',                                               NULL, NULL, NULL, 'Divisão de Análise de Contas (DAC)'),
('Operação', 'Análise de prestações de contas',                                        NULL, NULL, NULL, 'Divisão de Análise de Contas (DAC)'),
('Operação', 'Manifestações no âmbito financeiro',                                    NULL, NULL, NULL, 'Divisão de Análise de Contas (DAC)'),
('Operação', 'Gestão de processos físicos',                                            NULL, NULL, NULL, 'Divisão de Análise de Contas (DAC)'),
('Operação', 'Gestão de dados',                                                        NULL, NULL, NULL, 'Divisão de Análise de Contas (DAC)');

-- ── Verificação ───────────────────────────────────────────────────────────
SELECT manual_area, COUNT(*) AS total
FROM public.manuais_lista
GROUP BY manual_area
ORDER BY manual_area;
