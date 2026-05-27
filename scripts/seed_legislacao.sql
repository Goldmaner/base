-- Seed: categoricas.c_geral_legislacao
-- Fonte: Índice de Legislações Aplicáveis — Departamento de Parcerias DP
-- Execute APÓS migrar_legislacao_upgrade.sql

BEGIN;

-- Limpa apenas registros sem uso em outras tabelas (colunas tipo_doc preenchidas)
-- Para preservar dados antigos, usamos INSERT ... ON CONFLICT (lei) DO UPDATE
-- Garante unicidade por (lei)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'categoricas.c_geral_legislacao'::regclass
          AND contype = 'u'
          AND conname LIKE '%lei%'
    ) THEN
        ALTER TABLE categoricas.c_geral_legislacao
            ADD CONSTRAINT c_geral_legislacao_lei_key UNIQUE (lei);
    END IF;
END $$;

-- ===========================================================================
-- LEIS
-- ===========================================================================
INSERT INTO categoricas.c_geral_legislacao (lei, tipo_doc, inicio, termino, descricao, link, status_vigencia) VALUES
('Lei nº 8.989/1979',    'Lei', '1979-10-29', NULL, 'Dispõe sobre o estatuto dos funcionários públicos do município de São Paulo, e dá providências correlatas.', 'https://legislacao.prefeitura.sp.gov.br/leis/lei-8989-de-29-de-outubro-de-1979', 'vigente'),
('Lei nº 11.247/1992',   'Lei', '1992-10-01', NULL, 'Cria o Fundo Municipal dos Direitos da Criança e do Adolescente - FUMCAD, e dá outras providências.', 'https://legislacao.prefeitura.sp.gov.br/leis/lei-11247-de-01-de-outubro-de-1992/', 'vigente'),
('Lei nº 8.666/1993',    'Lei', '1993-06-21', NULL, 'Regulamenta o art. 37, inciso XXI, da Constituição Federal, institui normas para licitações e contratos da Administração Pública e dá outras providências.', 'https://www.planalto.gov.br/ccivil_03/leis/l8666cons.htm', 'Revogado pela Lei nº 14.133/2021'),
('Lei nº 14.141/2006',   'Lei', '2006-03-27', NULL, 'Dispõe sobre o processo administrativo na Administração Pública Municipal.', 'https://legislacao.prefeitura.sp.gov.br/leis/lei-14141-de-27-de-marco-de-2006', 'vigente'),
('Lei nº 14.667/2008',   'Lei', '2008-01-14', NULL, 'Cria a Secretaria Municipal de Participação e Parceria - SMPP, bem como dispõe sobre seu quadro de cargos de provimento em comissão.', 'https://legislacao.prefeitura.sp.gov.br/leis/lei-14667-de-14-de-janeiro-de-2008/consolidado', 'vigente'),
('Lei nº 15.679/2012',   'Lei', '2012-12-21', NULL, 'Cria o Fundo Municipal do Idoso (FMID).', 'https://legislacao.prefeitura.sp.gov.br/leis/lei-15679-de-21-de-dezembro-de-2012/', 'vigente'),
('Lei nº 15.764/2013',   'Lei', '2013-05-27', NULL, 'Dispõe sobre a criação e alteração da estrutura organizacional das Secretarias Municipais que especifica, cria a Subprefeitura de Sapopemba e institui a Gratificação pela Prestação de Serviços de Controladoria.', 'https://legislacao.prefeitura.sp.gov.br/leis/lei-15764-de-27-de-maio-de-2013', 'vigente'),
('Lei nº 13.019/2014',   'Lei', '2014-07-31', NULL, 'Estabelece o regime jurídico das parcerias voluntárias (MROSC), envolvendo ou não transferências de recursos financeiros, entre a administração pública e as organizações da sociedade civil.', 'https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l13019.htm', 'vigente - alterada pela Lei nº 13.204/2015')
ON CONFLICT (lei) DO UPDATE SET
    tipo_doc        = EXCLUDED.tipo_doc,
    inicio          = EXCLUDED.inicio,
    termino         = EXCLUDED.termino,
    descricao       = EXCLUDED.descricao,
    link            = EXCLUDED.link,
    status_vigencia = EXCLUDED.status_vigencia;

-- ===========================================================================
-- DECRETOS
-- ===========================================================================
INSERT INTO categoricas.c_geral_legislacao (lei, tipo_doc, inicio, termino, descricao, link, status_vigencia) VALUES
('Decreto nº 45.712/2005',  'Decreto', '2005-02-10', NULL, 'Dispõe sobre a organização administrativa da Secretaria Especial para Participação e Parceria.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-45712-de-10-de-fevereiro-de-2005', 'vigente'),
('Decreto nº 6.170/2007',   'Decreto', '2007-07-25', NULL, 'Dispõe sobre as normas relativas às transferências de recursos da União mediante convênios e contratos de repasse, e dá outras providências.', 'https://www.planalto.gov.br/ccivil_03/_ato2007-2010/2007/decreto/d6170.htm', 'Revogado pelo Decreto nº 11.531/2023'),
('Decreto nº 49.539/2008',  'Decreto', '2008-05-29', NULL, 'Dispõe sobre as normas relativas às transferências de recursos do Município de São Paulo mediante convênios.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-49539-de-29-de-maio-de-2008', 'vigente'),
('Decreto nº 53.484/2012',  'Decreto', '2012-10-19', NULL, 'Institui o Sistema de Bens Patrimoniais Móveis - SBPM no âmbito da Administração Direta do Município de São Paulo.', NULL, 'vigente'),
('Decreto nº 54.799/2014',  'Decreto', '2014-01-29', NULL, 'Confere nova regulamentação à Lei nº 11.247, de 1º de outubro de 1992, que cria o Fundo Municipal dos Direitos da Criança e do Adolescente - FUMCAD.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-54799-de-29-de-janeiro-de-2014', 'vigente'),
('Decreto nº 56.130/2015',  'Decreto', '2015-05-26', NULL, 'Institui, no âmbito do Poder Executivo, o Código de Conduta Funcional dos Agentes Públicos e da Alta Administração Municipal.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-56130-de-26-de-maio-de-2015/consolidado', 'vigente'),
('Decreto nº 57.575/2016',  'Decreto', '2016-12-29', NULL, 'Dispõe sobre a aplicação, no âmbito da Administração Direta e Indireta do Município, da Lei Federal nº 13.019/2014, que estabelece o regime jurídico das parcerias com organizações da sociedade civil.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-57575-de-29-de-dezembro-de-2016', 'vigente'),
('Decreto nº 57.580/2017',  'Decreto', '2017-01-19', NULL, 'Dispõe sobre a implementação de política de redução de despesas com contratos e instrumentos jurídicos congêneres, bem como a substituição do índice de reajustamento de preço contratual.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-57580-de-19-de-janeiro-de-2017', 'vigente'),
('Decreto nº 57.906/2017',  'Decreto', '2017-10-01', NULL, 'Regulamenta a Lei nº 15.679, de 21 de dezembro de 2012, que criou o Fundo Municipal do Idoso - FMID.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-57906-de-01-de-outubro-de-2017', 'vigente'),
('Decreto nº 58.079/2018',  'Decreto', '2018-01-24', NULL, 'Dispõe sobre a reorganização da Secretaria Municipal de Direitos Humanos e Cidadania, altera a denominação e a lotação dos cargos de provimento em comissão que especifica.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-58079-de-24-de-janeiro-de-2018', 'vigente'),
('Decreto nº 59.210/2020',  'Decreto', '2020-02-06', NULL, 'Estabelece procedimentos e prazos para a operacionalização de ações governamentais com recursos oriundos de emendas parlamentares.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-59210-de-6-de-fevereiro-de-2020', 'vigente'),
('Decreto nº 59.283/2020',  'Decreto', '2020-03-16', NULL, 'Declara situação de emergência no Município de São Paulo e define outras medidas para o enfrentamento da pandemia decorrente do coronavírus.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-59283-de-16-de-marco-de-2020/consolidado', 'vigente'),
('Decreto nº 61.990/2022',  'Decreto', '2022-11-18', NULL, 'Fixa normas e estabelece os procedimentos para a inserção de dados no Sistema de Orçamento e Finanças - SOF, no que se refere à inscrição dos saldos das notas de empenho em Restos a Pagar a partir do exercício de 2022.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-61990-de-18-de-novembro-de-2022', 'vigente'),
('Decreto nº 63.541/2024',  'Decreto', '2024-06-27', NULL, 'Introduz alterações no Decreto nº 57.575/2016, que dispõe sobre a aplicação da Lei Federal nº 13.019/2014 - regime jurídico das parcerias com organizações da sociedade civil.', 'https://legislacao.prefeitura.sp.gov.br/leis/decreto-63541-de-27-de-junho-de-2024', 'vigente')
ON CONFLICT (lei) DO UPDATE SET
    tipo_doc        = EXCLUDED.tipo_doc,
    inicio          = EXCLUDED.inicio,
    termino         = EXCLUDED.termino,
    descricao       = EXCLUDED.descricao,
    link            = EXCLUDED.link,
    status_vigencia = EXCLUDED.status_vigencia;

-- ===========================================================================
-- PORTARIAS
-- ===========================================================================
INSERT INTO categoricas.c_geral_legislacao (lei, tipo_doc, inicio, termino, descricao, link, status_vigencia) VALUES
('Portaria SF nº 29/2006',            'Portaria', '2006-03-07', NULL, 'Regulamenta a aquisição de bens patrimoniais com recursos financeiros transferidos a entidades filantrópicas e assistenciais / PMSP. Revoga P 56/02.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secret-mun-de-financas-e-desenv-economico-29-de-8-de-marco-de-2006', 'vigente'),
('Portaria Intersecretarial SF/SEMPLA nº 6/2008', 'Portaria', '2008-08-12', NULL, 'Dispõe sobre as normas relativas às transferências de recursos do Município de São Paulo mediante convênios.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-intersecretarial-secret-mun-de-financas-e-desenv-economico-6-de-13-de-agosto-de-2008', 'vigente'),
('Portaria SMPP nº 72/2012',          'Portaria', '2012-03-22', NULL, 'Estabelece normas para celebração de convênios que envolvam verbas advindas do Fundo Municipal da Criança e do Adolescente, cujos projetos tenham sido selecionados no Edital FUMCAD e autorizados pelo CMDCA.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-participacao-e-parceria-smpp-72-de-22-de-marco-de-2012/', 'vigente'),
('Portaria SF nº 92/2014',            'Portaria', '2014-05-16', NULL, 'Padroniza os procedimentos para liquidação e pagamento de despesas no âmbito da Administração Direta, das Autarquias e das Fundações de Direito Público do Município de São Paulo.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-financas-e-desenvolvimento-economico-sf-92-de-16-de-maio-de-2014', 'vigente'),
('Portaria SMDHC nº 9/2014',          'Portaria', '2014-05-22', NULL, 'Estabelece normas para celebração de Convênios que envolvam verbas advindas do FUMCAD.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-9-de-22-de-maio-de-2014', 'vigente'),
('Portaria SF nº 101/2016',           'Portaria', '2016-05-18', NULL, 'Dispõe sobre procedimentos para realização de pagamentos da Administração Direta em período de indisponibilidade do Sistema de Orçamento e Finanças - SOF.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-da-fazenda-101-de-19-de-maio-de-2016', 'vigente'),
('Portaria SMDHC nº 115/2016',        'Portaria', '2016-08-30', NULL, 'Estabelece normas para celebração de parcerias que envolvam recursos do FUMCAD com organizações da sociedade civil/administração pública, sob forma de termo de fomento/colaboração, ou convênio.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-direitos-humanos-e-cidadania-115-de-31-de-agosto-de-2016', 'vigente'),
('Portaria SMDHC nº 138/2016',        'Portaria', '2016-10-28', NULL, 'Estabelece norma para análise de prestação de contas de convênios que envolvam a aplicação de recursos do FUMCAD.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-direitos-humanos-e-cidadania-138-de-29-de-outubro-de-2016', 'vigente'),
('Portaria Intersecretarial SF/SMG nº 15/2017', 'Portaria', '2017-10-23', NULL, 'Regulamenta o §3º do artigo 2º do Decreto Municipal nº 57.580, de 19 de janeiro de 2017.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-conjunta-secretaria-municipal-da-fazenda-sf-15-de-23-de-outubro-de-2017', 'vigente'),
('Portaria SF nº 210/2017',           'Portaria', '2017-10-23', NULL, 'Dispõe sobre a abertura de conta corrente específica para as parcerias celebradas nos termos da Lei Federal nº 13.019/2014.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-da-fazenda-sf-210-de-23-de-outubro-de-2017', 'vigente'),
('Portaria SF nº 389/2017',           'Portaria', '2017-12-18', NULL, 'Dispõe sobre instruções para cumprimento excepcional do artigo 7º do Decreto nº 57.580, de 19 de janeiro de 2017.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-389-de-18-de-dezembro-de-2017', 'vigente'),
('Portaria SMDHC nº 51/2018',         'Portaria', '2018-04-23', NULL, 'Dispõe sobre os procedimentos para prestação de contas das parcerias firmadas mediante termo de colaboração e de fomento entre a SMDHC e as Organizações da Sociedade Civil (OSC).', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-51-de-23-de-abril-de-2018', 'Revogada pela Portaria SMDHC nº 121/2019'),
('Portaria SMDHC nº 86/2018',         'Portaria', '2018-06-26', NULL, 'Altera a Portaria nº 51/SMDHC/2018, que dispõe sobre os procedimentos para prestação de contas das parcerias firmadas mediante termo de colaboração e de fomento.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-86-de-26-de-junho-de-2018', 'Revogada pela Portaria SMDHC nº 121/2019'),
('Portaria SMDHC nº 143/2018',        'Portaria', '2018-12-21', NULL, 'Estabelece parâmetros de análise, fluxos de trabalho e formas de encaminhamento dos processos passivos referentes ao Fundo Municipal dos Direitos da Criança e do Adolescente - FUMCAD.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-143-de-21-de-dezembro-de-2018', 'vigente'),
('Portaria SMDHC nº 121/2019',        'Portaria', '2019-10-14', NULL, 'Estabelece normas de gestão de parcerias com organizações da sociedade civil sob a forma de termo de fomento, termo de colaboração e acordos de cooperação.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-121-de-14-de-outubro-de-2019/consolidado', 'Revogada pela Portaria SMDHC nº 21/2023'),
('Portaria SMDHC nº 140/2019',        'Portaria', '2019-10-15', NULL, 'Estabelece normas de gestão administrativa para as parcerias financiadas com recursos dos fundos especiais vinculados à SMDHC - FUMCAD e FMID - com Organizações da Sociedade Civil (OSCs).', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-140-de-15-de-outubro-de-2019', 'Revogada pela Portaria SMDHC nº 90/2023'),
('Portaria SMDHC nº 15/2021',         'Portaria', '2021-03-01', NULL, 'Tipifica os equipamentos públicos da Rede de Atendimento de Direitos Humanos no município de São Paulo.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-15-de-1-de-marco-de-2021', 'vigente'),
('Portaria SGM/SEGES nº 21/2022',     'Portaria', '2022-03-04', NULL, 'Dispõe sobre requisitos a serem observados nos processos destinados à formalização de contratos de aluguel pelos órgãos e entes da Administração Direta e Indireta e nos casos de repasses de recursos para custeio dos aluguéis contratados por entidades parceiras.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-de-governo-municipal-sgm-seges-21-de-4-de-marco-de-2022', 'vigente - Portaria SEGES nº 28/2023 revoga os §§1º e 2º do artigo 12 e §2º do artigo 13'),
('Portaria SF nº 90/2022',            'Portaria', '2022-04-20', NULL, 'Estabelece normas complementares e procedimentos quanto ao registro e controle de bens móveis no Sistema de Bens Patrimoniais Móveis - SBPM.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-90-de-20-de-abril-de-2022', 'vigente'),
('Portaria SMDHC nº 21/2023',         'Portaria', '2023-02-09', NULL, 'Estabelece normas de gestão de parcerias com Organizações da Sociedade Civil sob a forma de Termo de Colaboração, Termo de Fomento e Acordo de Cooperação.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-21-de-9-de-fevereiro-de-2023', 'vigente'),
('Portaria SEGES nº 28/2023',         'Portaria', '2023-05-22', NULL, 'Revoga os §§1º e 2º do artigo 12 e §2º do artigo 13 da Portaria SGM/SEGES nº 21/2022 (contratos de aluguel).', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-gestao-seges-28-de-22-de-maio-de-2023', 'vigente'),
('Portaria SMDHC nº 90/2023',         'Portaria', '2023-09-22', NULL, 'Estabelece normas de gestão de parcerias com Organizações da Sociedade Civil (OSC) financiadas com recursos dos fundos específicos vinculados à SMDHC (FUMCAD e FMID).', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-90-de-25-de-setembro-de-2023', 'vigente'),
('Portaria SMDHC nº 75/2024',         'Portaria', '2024-08-02', NULL, 'Dispõe sobre os procedimentos a serem adotados para transferência de recursos obtidos com a venda dos alimentos e produtos do Armazém Solidário.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-75-de-2-de-agosto-de-2024', 'vigente'),
('Portaria SMDHC nº 79/2025',         'Portaria', '2025-08-05', NULL, 'Delega competência à Secretária Adjunta da Secretaria Municipal de Direitos Humanos e Cidadania, bem como para a realização de atividades relacionadas à execução e procedimentos administrativos, orçamentários e financeiros.', 'https://legislacao.prefeitura.sp.gov.br/leis/portaria-secretaria-municipal-de-direitos-humanos-e-cidadania-smdhc-79-de-5-de-agosto-de-2025', 'vigente')
ON CONFLICT (lei) DO UPDATE SET
    tipo_doc        = EXCLUDED.tipo_doc,
    inicio          = EXCLUDED.inicio,
    termino         = EXCLUDED.termino,
    descricao       = EXCLUDED.descricao,
    link            = EXCLUDED.link,
    status_vigencia = EXCLUDED.status_vigencia;

-- ===========================================================================
-- ORIENTAÇÕES NORMATIVAS
-- ===========================================================================
INSERT INTO categoricas.c_geral_legislacao (lei, tipo_doc, inicio, termino, descricao, link, status_vigencia) VALUES
('Orientação Normativa PREF nº 1/2013', 'Orientação Normativa', '2013-04-17', NULL, 'Fixa prazo prescricional de 05 anos para a cobrança da dívida ativa não-tributária.', 'https://legislacao.prefeitura.sp.gov.br/leis/orientacao-normativa-gabinete-do-prefeito-1-de-18-de-abril-de-2013', 'vigente')
ON CONFLICT (lei) DO UPDATE SET
    tipo_doc        = EXCLUDED.tipo_doc,
    inicio          = EXCLUDED.inicio,
    termino         = EXCLUDED.termino,
    descricao       = EXCLUDED.descricao,
    link            = EXCLUDED.link,
    status_vigencia = EXCLUDED.status_vigencia;

-- ===========================================================================
-- RESOLUÇÕES
-- ===========================================================================
INSERT INTO categoricas.c_geral_legislacao (lei, tipo_doc, inicio, termino, descricao, link, status_vigencia) VALUES
('Resolução TCMSP nº 10/2023', 'Resolução', '2023-01-01', NULL, 'Regulamenta a prescrição para o exercício das pretensões punitiva e de ressarcimento no âmbito do Tribunal de Contas do Município de São Paulo.', 'https://portal.tcm.sp.gov.br/Pagina/60001', 'vigente')
ON CONFLICT (lei) DO UPDATE SET
    tipo_doc        = EXCLUDED.tipo_doc,
    inicio          = EXCLUDED.inicio,
    termino         = EXCLUDED.termino,
    descricao       = EXCLUDED.descricao,
    link            = EXCLUDED.link,
    status_vigencia = EXCLUDED.status_vigencia;

-- ===========================================================================
-- MANUAIS E GUIAS
-- ===========================================================================
INSERT INTO categoricas.c_geral_legislacao (lei, tipo_doc, inicio, termino, descricao, link, status_vigencia) VALUES
('Manual sobre Manuseio de Processos 2009',     'Manual', '2009-01-01', NULL, 'Manual sobre o manuseio de processos administrativos.', 'https://drive.prefeitura.sp.gov.br/cidade/secretarias/upload/Processos_1252082544.pdf', 'vigente'),
('Manual sobre Manuseio de Processos 2012',     'Manual', '2012-09-01', NULL, 'Manual sobre o manuseio de processos administrativos.', 'https://drive.prefeitura.sp.gov.br/cidade/secretarias/upload/infraestrutura/arquivos/ACESSO%20WEB%20novo/PERGUNTAS%20FREQUENTES/manual_de_processos_22_01_2014_1390489138.pdf', 'vigente'),
('Manual de Prestação de Contas — Emendas Parlamentares e Termos de Colaboração (SMDHC)', 'Manual', NULL, NULL, 'Manual de Prestação de Contas para OSCs sobre a execução e a prestação de contas de parcerias, regidas pela Portaria nº 121/SMDHC/2023.', 'https://drive.prefeitura.sp.gov.br/cidade/secretarias/upload/direitos_humanos/PARCERIAS/ANALISE%20CONTAS/MANUAL%20DE%20PRESTACAO%20DE%20CONTAS%20-%20EMENDAS_COLABORACAO.pdf', 'vigente'),
('Manual de Prestação de Contas — FUMCAD e FMID 2019 (SMDHC)', 'Manual', '2019-01-01', NULL, 'Manual de Prestação de Contas para OSCs sobre a execução e a prestação de contas de parcerias financiadas com recursos do FUMCAD e FMID, regidas pela Portaria nº 140/SMDHC/2023.', 'https://drive.prefeitura.sp.gov.br/cidade/secretarias/upload/direitos_humanos/PARCERIAS/ANALISE%20CONTAS/MANUAL%20DE%20PRESTACAO%20DE%20CONTAS%20-%20FUMCAD%20e%20FMID_2019.pdf', 'vigente'),
('Manual de Prestação de Contas — Portaria nº 021/SMDHC/2023 (DP)', 'Manual', '2023-01-01', NULL, 'Manual de Prestação de Contas para OSCs sobre a execução e a prestação de contas de parcerias, regidas pela Portaria nº 021/SMDHC/2023.', 'https://drive.prefeitura.sp.gov.br/cidade/secretarias/upload/direitos_humanos/PARCERIAS/ANALISE%20CONTAS/MANUAL_DE_PRESTACAO_CONTAS_FUNDOS_abril_24.pdf', 'vigente'),
('Guia de Emendas Parlamentares 2025', 'Guia', '2025-01-01', NULL, 'Guia contendo introdução com definição de emendas parlamentares e instruções sobre o formulário de aceite, celebração da parceria, execução do projeto e prestação de contas.', 'https://prefeitura.sp.gov.br/documents/d/direitos_humanos/guia-de-emendas-parlamentares-2025-pdf', 'vigente')
ON CONFLICT (lei) DO UPDATE SET
    tipo_doc        = EXCLUDED.tipo_doc,
    inicio          = EXCLUDED.inicio,
    termino         = EXCLUDED.termino,
    descricao       = EXCLUDED.descricao,
    link            = EXCLUDED.link,
    status_vigencia = EXCLUDED.status_vigencia;

COMMIT;
