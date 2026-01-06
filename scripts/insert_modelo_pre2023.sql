-- Inserir modelo de texto para OSCs com parcerias pré-2023
INSERT INTO categoricas.c_geral_modelo_textos (titulo_texto, modelo_texto, criado_em)
VALUES (
    'Pesquisa de Parcerias: Parcerias pré-2023',
    'Em atendimento à solicitação registrada em SEI nº sei_informado_usuario - exercendo a atribuição conferida à Divisão de Análise de Contas - DAC -, realizamos o levantamento da(s) parceria(s) firmada(s) com a organização osc_informado_usuario, inscrita no CNPJ nº cnpj_informado_usuario.

Com base nas portarias revogadas, abaixo elencamos o(s) termo(s) identificado(s):

criar_tabela_informado_usuario(cabecalho: Número do Termo; Processo SEI PC; Nome do Projeto; Situação)

Desse modo, encaminhamos o presente para providências subsequentes.',
    NOW()
)
ON CONFLICT (titulo_texto) 
DO UPDATE SET 
    modelo_texto = EXCLUDED.modelo_texto,
    criado_em = NOW();
