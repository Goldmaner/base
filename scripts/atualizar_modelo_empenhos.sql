-- Atualizar modelo de encaminhamento de pagamento para usar placeholder dinâmico de empenhos
UPDATE categoricas.c_geral_modelo_textos 
SET modelo_texto = REPLACE(
    modelo_texto, 
    'no(s) </span><strong style="font-size: 12pt; text-indent: 25mm;">empenho(s) nº</strong><span style="font-weight: bolder; text-indent: 25mm;"> n_empenho_23_usuario</span><span style="font-weight: bolder; text-indent: 25mm;"> sob SEI nº</span><span style="font-weight: bolder; text-indent: 25mm;"> sei_empenho_23_usuario</span><span style="font-weight: bolder; text-indent: 25mm;"> e nº </span><strong style="font-size: 12pt; text-indent: 25mm;">n_empenho_24_usuario</strong><span style="font-weight: bolder; text-indent: 25mm;"> sob SEI nº</span><span style="font-weight: bolder; text-indent: 25mm;"> sei_empenho_24_usuario</span><span style="font-size: 12pt; text-indent: 25mm;">, respeitando seus respectivos elementos:',
    'no(s) </span><strong style="font-size: 12pt; text-indent: 25mm;">empenho(s) texto_empenhos_formatado</strong><span style="font-size: 12pt; text-indent: 25mm;">, respeitando seus respectivos elementos:'
)
WHERE id = 20;

SELECT 'Modelo atualizado com sucesso!' as resultado;
