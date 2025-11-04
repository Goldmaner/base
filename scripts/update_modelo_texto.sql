-- Atualizar modelo de texto para usar variáveis simples
UPDATE categoricas.c_modelo_textos
SET modelo_texto = 'Em atendimento à solicitação registrada em SEI nº sei_informado_usuario - exercendo a atribuição conferida à Divisão de Análise de Contas - DAC -, realizamos o levantamento da(s) parceria(s) firmada(s) com a organização osc_informado_usuario, inscrita no CNPJ nº cnpj_informado_usuario.'
WHERE titulo_texto = 'Pesquisa de Parcerias: OSC sem parcerias SMDHC';
