-- Seed: categoricas.c_dac_glosas
-- 14 tipos de glosa para conciliação bancária DAC
-- Criado: 2026-05-26

INSERT INTO categoricas.c_dac_glosas (glosa_nome, glosa_texto, glosa_inconsistencia, criado_em) VALUES

('Taxas Bancárias não devolvidas',
 'Execução com taxas bancárias, categoria de despesa vedada.',
 'Taxas bancárias',
 NOW()),

('Alteração de Vínculo sem esclarecimento',
 'Execução de contratado com vínculo trabalhista divergente do previsto em plano de trabalho.',
 'Alteração de vínculo de contratado',
 NOW()),

('Cartão de Crédito ou Cheque',
 'Execução de despesa por meio de cartão de crédito ou cheque, metodologia de pagamento não compatível com a legislação',
 'Pago por cartão de crédito; Pago em cheque',
 NOW()),

('Ausência de Comprovação Física (Guia)',
 'Execução de despesa, sem apresentação da guia adequada (ou possível identificação, por meio de consulta aos sites oficiais das notas fiscais) ou correto preenchimento do Demonstrativo, também não sendo encaminhada comprovação física da guia.',
 'Despesa sem guia',
 NOW()),

('Pago em espécie sem esclarecimento',
 'Execução de despesa por meio de espécie, meio de pagamento vedado.',
 'Pago em espécie',
 NOW()),

('Execução não prevista para o mês',
 'Execução de despesa em desacordo com o plano de trabalho e orçamento anual sem esclarecimento, justificativa, solicitação ou aprovação por parte da Administração.',
 'Despesas não previstas ; Despesa sem previsão no período ; Vigência extemporânea',
 NOW()),

('Execução de montante superior ao previsto',
 'Execução de despesa em valor superior ao previsto, em desacordo com o plano de trabalho e orçamento anual sem esclarecimento, justificativa, solicitação ou aprovação por parte da Administração.',
 'Execução de rubrica superior ao previsto',
 NOW()),

('Ausente Comprovação de Pagamento',
 'Execução de despesa transferida para conta da OSC, entretanto sem apresentação de comprovação de pagamento direcionada ao beneficiário final.',
 'Reembolsos sem comprovação',
 NOW()),

('Débitos não Identificados',
 'Execução de despesa não identificada e/ou descriminada em prestação de contas ou em resposta das notificações enviadas.',
 'Despesas sem guia e comprovação ; Ausência de descrição de despesa',
 NOW()),

('Fora do Município',
 'Contratação de prestadores de fora do município de São Paulo, despesa vedada, sem apresentação adequada de orçamentos que atestem preço inferior ao do município de São Paulo.',
 'Fora do Município',
 NOW()),

('Pagamento em duplicidade sem esclarecimento',
 'Pagamento de despesa em duplicidade, havendo pagamento anterior da mesma despesa, sem justificativa por parte da organização, em desacordo com o plano de trabalho e orçamento anual.',
 'Pagamento em duplicidade',
 NOW()),

('Pagamento para outro Favorecido',
 'Execução de despesa destinada a beneficiário final divergente do identificado na guia de pagamento (holerite, nota fiscal, recibo, cupom fiscal, etc.).',
 'Pagamento para outro Favorecido',
 NOW()),

('Multas e juros não restituídas',
 'Execução com multas e juros, categorias de despesas vedadas.',
 'Restituição de Multas e Juros',
 NOW()),

('Ausente guia e comprovação de pagamento',
 'Execução de despesa, sem apresentação da guia adequada (ou possível identificação, por meio de consulta aos sites oficiais das notas fiscais) ou correto preenchimento do Demonstrativo, também não sendo encaminhada comprovação física da guia. A execução de despesa também foi feita por meio de reembolso para a OSC, entretanto sem apresentação de comprovação de pagamento direcionada ao beneficiário final.',
 NULL,
 NOW());
