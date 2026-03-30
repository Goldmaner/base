-- ============================================================
-- FIX: Atualizar os 28 registros que ficaram com placeholder
-- Execute este script no pgAdmin para corrigir as descrições
-- ============================================================

-- ── OPERAÇÕES GERAIS DA UNIDADE (COMPARTILHADAS) ──────────

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: produzir relatórios técnicos e gerenciais que subsidiem a tomada de decisão e oferecer assessoramento qualificado à chefia e às áreas envolvidas, abrangendo a elaboração de análises, pareceres e relatórios sobre demandas diversas, bem como o apoio técnico e estratégico à gestão da unidade.

Por ser uma operação de caráter flutuante, pode ser acionada conforme necessidades específicas, garantindo respostas ágeis e fundamentadas para processos internos e externos.'
WHERE manual_nome = 'Relatórios e assessoramento'
  AND manual_area = 'Operações Gerais da Unidade (Compartilhadas)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: externa e apoio.

Objetivo: elaborar respostas técnicas a questionamentos de órgãos de controle, fundamentadas em documentos oficiais e na legislação aplicável.

Esta operação envolve a preparação, revisão e envio de manifestações formais direcionadas a instâncias de controle (como controladorias, auditorias e tribunais de contas). O processo exige análise detalhada de documentos, registros administrativos e normas legais, garantindo a consistência técnica e a conformidade institucional.

Trata-se de uma atividade essencial para assegurar a transparência, a legalidade e a credibilidade da unidade diante dos órgãos fiscalizadores.'
WHERE manual_nome = 'Manifestação de órgãos controladores'
  AND manual_area = 'Operações Gerais da Unidade (Compartilhadas)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: responder a demandas externas e internas, esclarecendo dúvidas, prestando orientações e fortalecendo o relacionamento institucional com OSCs e demais áreas da administração pública, compreendendo o acolhimento e a resposta a solicitações recebidas por diferentes canais de comunicação — telefone, e-mail, WhatsApp ou presencialmente.

Inclui desde o esclarecimento de informações técnicas e procedimentais, até o encaminhamento de demandas específicas para os setores responsáveis, assegurando agilidade, cordialidade e qualidade no atendimento.'
WHERE manual_nome = 'Atendimento'
  AND manual_area = 'Operações Gerais da Unidade (Compartilhadas)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: interno e apoio.

Objetivo: assegurar a correta abertura, movimentação, organização e atualização de processos no Sistema Eletrônico de Informações (SEI), garantindo a regularidade dos registros e a adequada tramitação dos documentos administrativos.

Envolve também o gerenciamento integral dos processos eletrônicos, inserção e controle de documentos, acompanhamento de prazos, organização de pastas digitais e atualização constante das informações. O alvo central é assegurar transparência, rastreabilidade e eficiência na gestão documental, além de apoiar a tomada de decisão administrativa por meio de registros confiáveis e bem estruturados.'
WHERE manual_nome = 'Gestão do Sistema Eletrônico de Informações (SEI)'
  AND manual_area = 'Operações Gerais da Unidade (Compartilhadas)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: operação que envolve o planejamento, desenvolvimento e execução de ações formativas voltadas a organizações parceiras e áreas internas da SMDHC. O foco é capacitar gestores e equipes para aprimorar a gestão das parcerias, promovendo a disseminação de informações relevantes e práticas administrativas eficientes.

Além disso, busca fortalecer as competências institucionais e estimular a integração entre os diferentes atores envolvidos, garantindo que o conhecimento adquirido possa ser aplicado de forma prática na rotina das operações e na tomada de decisões. A capacitação contínua contribui para a uniformidade técnica e o alinhamento das práticas da unidade com suas diretrizes estratégicas.'
WHERE manual_nome = 'Capacitações'
  AND manual_area = 'Operações Gerais da Unidade (Compartilhadas)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: interno e apoio.

Objetivo: execução de consultas, cruzamentos, inserções e atualizações de informações no banco de dados da unidade, assegurando que os dados sejam confiáveis, completos e organizados. Ela garante a integridade das informações utilizadas nas análises e relatórios gerenciais.

Além de manter o banco de dados atualizado, esta operação subsidiará decisões estratégicas e apoiará o acompanhamento das atividades da unidade, fornecendo uma base sólida para o planejamento, monitoramento e avaliação das parcerias e demais processos administrativos.'
WHERE manual_nome = 'Operações no banco de dados'
  AND manual_area = 'Operações Gerais da Unidade (Compartilhadas)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: participação e condução de reuniões técnicas e de alinhamento, envolvendo membros da equipe, gestores e representantes de OSCs. O objetivo é promover a integração entre os participantes, garantir o compartilhamento de informações e alinhar procedimentos e prioridades.

Além disso, as reuniões permitem definir encaminhamentos estratégicos, monitorar o andamento de projetos e operações e resolver dúvidas ou obstáculos de forma colaborativa. Elas contribuem para a eficiência da unidade, fortalecendo a comunicação interna e externa e assegurando que as ações estejam coerentes com os objetivos institucionais.'
WHERE manual_nome = 'Reuniões'
  AND manual_area = 'Operações Gerais da Unidade (Compartilhadas)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: interna e apoio.

Objetivo: desenvolver e implementar práticas voltadas ao gerenciamento dos recursos humanos da unidade, abrangendo desde o controle administrativo (como frequência, folha de ponto e registros funcionais) até ações de capacitação, acompanhamento de desempenho e incentivo à formação contínua.

A operação também busca promover a valorização e o desenvolvimento da equipe, por meio de treinamentos internos periódicos, estímulo à troca de experiências e gestão equilibrada da rotatividade, assegurando que a unidade disponha de profissionais qualificados, motivados e alinhados aos objetivos institucionais.'
WHERE manual_nome = 'Gestão de Pessoas'
  AND manual_area = 'Operações Gerais da Unidade (Compartilhadas)';

-- ── DEPARTAMENTO DE PARCERIAS (DP) ────────────────────────

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e finalística.

Objetivo: O edital de chamamento público é o instrumento utilizado pelo Departamento de Parcerias da SMDHC para selecionar Organizações da Sociedade Civil (OSCs) interessadas em desenvolver projetos em colaboração com a Secretaria, nos termos da Lei Federal nº 13.019/2014.

Seu principal objetivo é garantir transparência, igualdade de condições e alinhamento das propostas às políticas públicas de direitos humanos e cidadania, permitindo que as parcerias firmadas atendam de forma efetiva às demandas da população.

Dessa forma, o edital de chamamento público não apenas formaliza o processo de seleção, mas também fortalece a relação entre o poder público e a sociedade civil organizada, garantindo que as parcerias firmadas estejam alinhadas às necessidades da população e às diretrizes da política pública de direitos humanos e cidadania.'
WHERE manual_nome = 'Gestão dos Editais de Parcerias'
  AND manual_area = 'Departamento de Parcerias (DP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e finalística.

Objetivo: através de um planejamento estratégico e meticuloso, o objetivo da gestão orçamentária é garantir que os recursos financeiros da secretaria sejam usados de forma eficiente, transparente e estratégica em todas as parcerias firmadas com a sociedade civil. Ela é uma ferramenta para garantir que as parcerias sejam bem-sucedidas, que os recursos públicos sejam usados com responsabilidade e que a missão da secretaria de promover e proteger os direitos humanos seja alcançada de forma eficaz.'
WHERE manual_nome = 'Gestão Orçamentária de Parcerias'
  AND manual_area = 'Departamento de Parcerias (DP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: iniciar o processo de celebração de emendas parlamentares em conjunto com o processo de pedido da respectiva emenda.

Assim como, o controle de informações dos processos, a elaboração e a inserção de um memorando unitário, que contém todas as informações necessárias para seguimento.'
WHERE manual_nome = 'Autuação de processos de celebração de emendas parlamentares'
  AND manual_area = 'Departamento de Parcerias (DP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: No âmbito da Secretaria Municipal de Direitos Humanos e Cidadania (SMDHC), o processo de imobilizado compreende o registro, controle, acompanhamento e baixa dos bens patrimoniais vinculados às diversas áreas da Pasta. Esse processo é essencial para garantir a correta gestão do patrimônio público, assegurando transparência, rastreabilidade e conformidade com as normas de contabilidade e administração pública.

A finalização do processo de imobilizado ocorre com a conclusão dos procedimentos de baixa patrimonial, devidamente homologados e registrados nos sistemas de controle, permitindo que o bem seja retirado da carga patrimonial da SMDHC de forma legal e transparente.

Esse fluxo garante que o patrimônio público seja gerido de forma responsável, em consonância com os princípios da legalidade, eficiência e economicidade.

A destinação do imobilizado pode ocorrer de diferentes formas, sempre seguindo a legislação e normas de gestão patrimonial: doação, cessão de uso, permuta, venda/alienação, reciclagem/reaproveitamento ou descarte, conforme o estado do bem e a legislação aplicável.'
WHERE manual_nome = 'Finalização processual e destinação de imobilizado'
  AND manual_area = 'Departamento de Parcerias (DP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: Promover o diálogo permanente, o alinhamento estratégico e a cooperação com órgãos públicos, organizações da sociedade civil, conselhos de políticas públicas e demais instituições externas, visando fortalecer a execução de parcerias, ampliar o alcance das políticas de direitos humanos e assegurar que as ações desenvolvidas sejam integradas, eficientes e socialmente impactantes.'
WHERE manual_nome = 'Articulação com as áreas externas'
  AND manual_area = 'Departamento de Parcerias (DP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: externo e apoio.

Objetivo: os três instrumentos — E-SIC, Informativo do Prefeito e Portal da Transparência — trabalham em conjunto para fortalecer a transparência e o controle social na administração pública. Juntos, eles criam um sistema completo: o Portal oferece os dados brutos, o E-SIC garante a busca por informações detalhadas, e o Informativo aproxima a gestão da comunidade, promovendo uma governança mais aberta e participativa.

O Portal da Transparência oferece a base fundamental ao exibir, de forma clara e acessível, os dados financeiros da gestão, como receitas e despesas. É a principal ferramenta de fiscalização em tempo real, permitindo que qualquer cidadão verifique como o dinheiro público está sendo utilizado.

O E-SIC tem como objetivo central fortalecer a transparência do departamento e assegurar o direito do cidadão ao acesso à informação. Nossa atuação se concentra em conduzir e coordenar o atendimento às solicitações de informações que não estão disponíveis nos canais de transparência, garantindo o cumprimento dos prazos legais e das exigências de clareza e precisão.

O Informativo do Prefeito tem como objetivo estratégico traduzir e comunicar de forma clara as ações, o impacto e os resultados das parcerias formalizadas com as Organizações da Sociedade Civil (OSCs), assegurando que a narrativa sobre esses projetos seja acessível e valorizada pela população.'
WHERE manual_nome = 'Tratativas externas: Informativo do Prefeito, E-SIC e Portal da Transparência'
  AND manual_area = 'Departamento de Parcerias (DP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: ferramenta que centraliza e padroniza todo o ciclo de vida de uma parceria com verbas federais, garantindo a legalidade, a transparência e o controle na aplicação desses recursos públicos.

A plataforma possibilita a formalização, repasse de verbas, acompanhamento e monitoramento, e prestação de contas de convênios e contratos que envolvem transferência de recursos do Governo Federal.

Formalização: É onde o departamento de parcerias da Secretaria registra e formaliza as propostas de convênios com as organizações sociais, antes da aprovação do governo federal.

Repasse de Verbas: O sistema gerencia a liberação e o fluxo das verbas federais para as contas das organizações parceiras, garantindo que o dinheiro seja transferido em etapas e de forma segura.

Acompanhamento e Monitoramento: Permite que a Secretaria e o órgão federal acompanhem a execução física e financeira do projeto em tempo real, verificando se as metas estão sendo cumpridas conforme o cronograma.

Prestação de Contas: É o ambiente digital para a organização parceira prestar contas sobre o uso dos recursos. Todos os documentos, notas fiscais e relatórios são enviados e analisados dentro do próprio sistema, garantindo transparência e controle.'
WHERE manual_nome = 'Gestão do SICONV / TransfereGOV'
  AND manual_area = 'Departamento de Parcerias (DP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: garantir que todos os colaboradores tenham os recursos necessários para desempenhar suas funções de forma eficiente, enquanto a unidade mantém o controle sobre os gastos e o inventário.'
WHERE manual_nome = 'Solicitações de materiais de escritório'
  AND manual_area = 'Departamento de Parcerias (DP)';

-- ── DIVISÃO DE GESTÃO DE PARCERIAS (DGP) ─────────────────

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e finalístico.

Objetivo: conduzir e coordenar as etapas iniciais dos processos de formalização de parcerias com Organizações da Sociedade Civil (OSCs), garantindo o cumprimento das exigências documentais, jurídicas e orçamentárias.

Essa atuação envolve a análise e instrução dos processos, o apoio técnico às áreas envolvidas, o esclarecimento de dúvidas e o acompanhamento das demandas até a formalização da parceria. Inclui ainda a elaboração de relatórios gerenciais, a participação em reuniões técnicas e a contribuição na definição de encaminhamentos, inclusive em situações que exigem respostas ágeis e articulação entre diferentes setores.'
WHERE manual_nome = 'Celebração de parcerias'
  AND manual_area = 'Divisão de Gestão de Parcerias (DGP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: externo e apoio.

Objetivo: gerenciar os processos de emissão, renovação e atualização do Certificado de Entidade do Terceiro Setor (CENTS), assegurando que as Organizações da Sociedade Civil (OSCs) atendam aos requisitos legais e documentais exigidos para celebração de parcerias com o poder público.

A área atua na análise técnica da documentação, instrução dos processos administrativos, controle da vigência dos certificados e orientação às OSCs e demais setores envolvidos, contribuindo para a regularidade e transparência nas parcerias institucionais.'
WHERE manual_nome = 'Gerenciamento do CENTS'
  AND manual_area = 'Divisão de Gestão de Parcerias (DGP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e finalístico.

Objetivo: Formalizar mudanças materiais nas cláusulas dos Termos de Fomento, Colaboração e Acordos de Cooperação a fim de atender solicitações realizadas por OSCs, Coordenações finalísticas e demais departamentos técnicos da SMDHC.

Envolve a verificação da necessidade e da legalidade de prorrogações de prazos, acréscimos ou reduções de valores, ajustes em cláusulas contratuais e outras modificações permitidas pela legislação. Para isso, o setor realiza estudos técnicos, consultas jurídicas e avaliações orçamentárias, garantindo que as alterações não causem prejuízos financeiros ou jurídicos ao município e estejam em conformidade com a Lei do Marco Regulatório das Sociedades Civis.

Além da parte técnica e normativa, o departamento também atua no registro, controle e monitoramento dos aditamentos realizados, mantendo a devida transparência e publicidade dos atos administrativos, encaminhando as alterações para publicação no Diário Oficial da Prefeitura de São Paulo.'
WHERE manual_nome = 'Alterações contratuais'
  AND manual_area = 'Divisão de Gestão de Parcerias (DGP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e finalístico.

Objetivo: Monitorar e avaliar a execução de parcerias em conformidade com o previsto em Termos de Colaboração e Termos de Fomento, promover a transparência, eficiência e efetividade da gestão pública, em consonância com o Marco Regulatório das Organizações da Sociedade Civil.

Essa atuação compreende a realização de visitas técnicas in loco, por meio de agendamento, registro em campo e preenchimento de relatórios; elaboração de Relatórios de Monitoramento e Avaliação, a partir da análise de indicadores e metas com ênfase na avaliação de resultados alcançados; emissão de pareceres técnicos; sistematização de dados para subsidiar a tomada de decisão e demais atividades de apoio à Pessoa Gestora da Parceria, à Organização parceira e às Coordenações.'
WHERE manual_nome = 'Monitoramento e avaliação'
  AND manual_area = 'Divisão de Gestão de Parcerias (DGP)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: Gerenciar o fluxo processual das prestações de contas das parcerias celebradas com Organizações da Sociedade Civil (OSCs), garantindo o controle, a tramitação adequada e o cumprimento dos prazos legais.

A área é responsável por receber as prestações de contas referentes às portarias 140/SMDHC/2019 e 121/SMDHC/2019, verificar se a documentação entregue corresponde aos documentos previstos na portaria, identificar e cobrar pendências ou atrasos, prestar auxílio às áreas finalísticas para análise técnica e fornecer informações, tanto internas quanto externas, sobre o andamento e a situação dos processos. Com isso, contribui para a transparência, a regularidade e a eficiência da gestão pública.'
WHERE manual_nome = 'Controle processual'
  AND manual_area = 'Divisão de Gestão de Parcerias (DGP)';

-- ── DIVISÃO DE ANÁLISE DE CONTAS (DAC) ───────────────────

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: interno e apoio.

Objetivo: procedimento intrínseco ao fluxo de novas celebrações de parcerias, a pesquisa de parcerias objetiva indicar às áreas finalísticas e aos gestores dos projetos todas as parcerias formalizadas entre a SMDHC e a organização pesquisada. Cabe à área finalística verificar e atestar a entrega regular das prestações de contas exigíveis durante a vigência do(s) projeto(s), em conformidade com as normativas vigentes.

Abrange a formalização da pesquisa, realizada com base na consulta do banco de dados da unidade, o direcionamento das informações à coordenação, para ateste da pessoa gestora quanto à regularidade da entrega da(s) prestação(ões) de contas e o retorno à unidade, viabilizando a continuidade do fluxo de celebração pela área designada.'
WHERE manual_nome = 'Pesquisas de Parcerias'
  AND manual_area = 'Divisão de Análise de Contas (DAC)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e apoio.

Objetivo: planejamento, controle e gestão orçamentária de todos os repasses de recursos previamente reservados para efetivação a cada exercício financeiro da administração pública, voltados para o suprimento financeiro das parcerias formalizadas com a SMDHC.

Essa operação compreende: inserção e atualização de informações no banco de dados, emissão de solicitação de reserva e empenho e encaminhamento de pagamento aos agentes envolvidos no fluxo de pagamentos.'
WHERE manual_nome = 'Gerenciamento financeiro'
  AND manual_area = 'Divisão de Análise de Contas (DAC)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: flutuante e finalística.

Objetivo: esta operação é realizada em conformidade ao estabelecido nas legislações vigentes que norteiam os princípios e procedimentos administrativos de análise. Pode estar pautada na entrega documental da prestação de contas exigível, na solicitação de apoio técnico para avaliação de instrumentais apresentados para fins de avaliação financeira e de execução do objeto, bem como de execução financeira atrelada ao cumprimento de metas.'
WHERE manual_nome = 'Análise de prestações de contas'
  AND manual_area = 'Divisão de Análise de Contas (DAC)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: externo e finalística.

Objetivo: etapa pertinente ao fluxo de análise financeira das prestações de contas apresentadas pelas organizações parceiras. É expedida para ciência e providências da organização após formalização do parecer da pessoa gestora da parceria, quanto às ações do projeto e ao parecer financeiro que avalia a correta gestão financeira dos recursos repassados, concedendo o benefício de interposição recursal da organização e continuidade dos trâmites processuais antecedentes ao encerramento do processo da parceria, ou à aplicação de sanções administrativas cabíveis.'
WHERE manual_nome = 'Manifestações no âmbito financeiro'
  AND manual_area = 'Divisão de Análise de Contas (DAC)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: interno e apoio.

Objetivo: digitalização e armazenamento catalogado e classificado por tipo de processo e de coordenação, assegurando a organização documental. Possibilita rastreabilidade para consulta e inclusão de novos registros, garante celeridade e eficiência no atendimento das demandas e análises mais consistentes devido à ausência de dispersão de conteúdo apresentado pelas organizações para fins de prestação de contas, bem como de documentos internos gerados em cumprimento dos trâmites estabelecidos para o fluxo de análise financeira das parcerias.'
WHERE manual_nome = 'Gestão de processos físicos'
  AND manual_area = 'Divisão de Análise de Contas (DAC)';

UPDATE public.manuais_lista SET manual_descricao =
'Tipo: interno e apoio.

Objetivo: com intuito de oferecer dados concretos e atualizados e de auxiliar a alta cúpula da unidade na tomada de decisões, esta operação envolve a inserção e atualização tempestiva da base de dados pela área operacional, possibilitando a integração das informações e o registro de todas as movimentações ocorridas nos processos entre as áreas de atuação da unidade. Proporciona facilidade e agilidade na consulta de dados, além de eficiência no atendimento das demandas diárias.'
WHERE manual_nome = 'Gestão de dados'
  AND manual_area = 'Divisão de Análise de Contas (DAC)';

-- ── Verificação final ─────────────────────────────────────
SELECT
    manual_area,
    COUNT(*) AS total,
    COUNT(manual_descricao) AS com_descricao,
    COUNT(*) FILTER (WHERE manual_descricao LIKE '%Preencher%') AS ainda_placeholder
FROM public.manuais_lista
GROUP BY manual_area
ORDER BY manual_area;
