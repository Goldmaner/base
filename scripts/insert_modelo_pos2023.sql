-- Script para inserir modelo de texto "Pesquisa de Parcerias: Parcerias pós-2023"
-- Este modelo é usado quando a OSC possui termos com responsabilidade de Pessoa Gestora (2) ou Compartilhado (3)
-- Gera múltiplos encaminhamentos, um para cada coordenação identificada

INSERT INTO categoricas.c_modelo_textos (titulo_texto, modelo_texto, criado_em)
VALUES (
    'Pesquisa de Parcerias: Parcerias pós-2023',
    'coordenacao_informado_usuario
PESSOA GESTORA

 

Em atendimento à solicitação registrada em SEI nº sei_informado_usuario - exercendo a atribuição conferida à Divisão de Análise de Contas - DAC -, realizamos o levantamento das parcerias firmadas, até a presente data, com a organização osc_informado_usuario, inscrita no CNPJ nº cnpj_informado_usuario e encaminhamos o presente para providências.

Em cumprimento às diretrizes das normativas vigentes, que estabelecem novas normas de gestão de parcerias no âmbito da SMDHC, conferindo à Pessoa Gestora o acompanhamento da entrega da prestação de contas das parcerias firmadas, abaixo elencamos os termos identificados para consulta e verificação da regular entrega das prestações de contas exigíveis, como seguem:

 

criar_tabela_pos2023(cabeçalho: Número do Termo; Processo SEI PC; Nome do Projeto)
 

Desse modo, solicitamos:

Para entrega de prestação de contas REGULAR, a Pessoa Gestora da parceria deve encartar neste processo a informação de regularidade da prestação e encaminhar à unidade SMDHC/DP/DGP para prosseguimento do fluxo.

Para AUSÊNCIA de entrega de prestação de contas, ou apresentação IRREGULAR, a Pessoa Gestora deve avisar a organização acerca da irregularidade, ou atraso da prestação de contas por meio de e-mail, solicitando breve providência.

Destaca-se que, em caso de irregularidade:

Somente após a efetiva apresentação da prestação de contas exigível, com encarte documental no respectivo processo SEI de prestação de contas, deverá ser formalizado o ateste de regularidade neste processo, com envio à unidade SMDHC/DP/DGP para prosseguimento.',
    NOW()
)
ON CONFLICT (titulo_texto) 
DO UPDATE SET 
    modelo_texto = EXCLUDED.modelo_texto,
    criado_em = NOW();
