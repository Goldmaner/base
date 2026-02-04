-- Script para atualizar o modelo de Encaminhamento de Pagamento (ID 20)
-- com a nova estrutura de tabela e lógica condicional
-- ENCODING: UTF-8

SET client_encoding = 'UTF8';

UPDATE categoricas.c_geral_modelo_textos 
SET modelo_texto = $$<p class="Texto_Fundo_Cinza_Maiusculas_Negrito" style="margin: 8px;"><span style="color: rgb(0, 0, 0); font-size: medium;">À</span></p>
<p class="Texto_Fundo_Cinza_Maiusculas_Negrito" style="margin: 8px;"><span style="color: rgb(0, 0, 0); font-size: medium;">COORDENAÇÃO_INFORMADO_USUARIO</span></p>
<p class="Texto_Fundo_Cinza_Maiusculas_Negrito" style="margin: 8px;"><span style="font-size:medium"><span style="overflow-wrap:normal"><span style="color:#000000">Senhor(A) Coordenador(a) e/ou Pessoa Gestora</span></span></span></p>
<p><br></p>

<p class="Texto_Justificado_Recuo_Primeira_Linha">Trata o presente da solicitação de pagamento da <b>n_parcela_usuario</b> para o período de <b>mes_vigencia_inicial_usuario</b>[mes_vigencia_final_usuario:  a <b>mes_vigencia_final_usuario</b>], condizente ao <b>Termo de Aditamento nº numero_aditamento_usuario</b>, sob SEI nº <b>sei_aditamento_usuario</b> do <b>numero_termo_usuario</b>, sob SEI nº <b>sei_termo_usuario</b>.</p>
<p class="Texto_Justificado_Recuo_Primeira_Linha"><br></p>

<p class="Texto_Justificado_Recuo_Primeira_Linha">Sendo assim, abaixo detalhamos os valores do pagamento, que totaliza <b>total_previsto_usuario (valor_extenso)</b>, no(s) empenho(s) <b>texto_empenhos_formatado</b>, respeitando seus respectivos elementos:</p>
<p class="Texto_Justificado_Recuo_Primeira_Linha"><br></p>

<div>
<table border="2" cellpadding="0" style="border-collapse:collapse;border-color:#a3a3a3;border-style:solid;border-width:1px;margin-left:auto;margin-right:auto;" summary="" title="" valign="top">
    <thead>
        <tr>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; width: 1.5in; padding: 5px; text-align: center; background-color: rgb(221, 221, 221);">
                <p class="Tabela_Texto_Centralizado"><strong>Parcela</strong></p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; width: 1.8in; padding: 5px; text-align: center; background-color: rgb(221, 221, 221);">
                <p class="Tabela_Texto_Centralizado"><strong>3.3.50.39.53.23</strong></p>
                <p class="Tabela_Texto_Centralizado"><strong>(Outras Despesas)</strong></p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; width: 2.2in; padding: 5px; text-align: center; background-color: rgb(221, 221, 221);">
                <p class="Tabela_Texto_Centralizado"><strong>3.3.50.39.53.24</strong></p>
                <p class="Tabela_Texto_Centralizado"><strong>(Pessoal / Recursos Humanos)</strong></p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; width: 1.5in; padding: 5px; text-align: center; background-color: rgb(221, 221, 221);">
                <p class="Tabela_Texto_Centralizado"><strong>Total</strong></p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; width: 1.3in; padding: 5px; text-align: center; background-color: rgb(221, 221, 221);">
                <p class="Tabela_Texto_Centralizado"><strong>Início da</strong></p>
                <p class="Tabela_Texto_Centralizado"><strong>Parcela</strong></p>
            </td>
            <td style="border-width: 1px; border-style: solid; border-color: rgb(163, 163, 163); vertical-align: middle; width: 1.3in; padding: 5px; text-align: center; background-color: rgb(221, 221, 221);">
                <p class="Tabela_Texto_Centralizado"><strong>Final da</strong></p>
                <p class="Tabela_Texto_Centralizado"><strong>Parcela</strong></p>
            </td>
        </tr>
    </thead>
    <tbody>
<!-- LINHAS_TABELA_PARCELAS -->
    </tbody>
</table>
</div>

<p><br></p>

<div>
    <p class="Texto_Justificado_Recuo_Primeira_Linha" paraeid="{1085db72-107a-4c2f-acfc-41882b8d5536}{245}" paraid="1459007009">Informamos que foram encartadas as certidões que atestam a regularidade fiscal, trabalhista e tributária, em relevância à <strong>portaria_usuario</strong>, que estabeleceu novas normas de gestão de parcerias no âmbito da SMDHC, atribuindo à <strong>Pessoa Gestora</strong> a competência de <strong>acompanhar a entrega regular da prestação contas</strong> do referido Termo.</p>
    
    <p class="Texto_Justificado_Recuo_Primeira_Linha" paraeid="{1085db72-107a-4c2f-acfc-41882b8d5536}{255}" paraid="208766175">&nbsp;</p>
    
    <!-- CONDICIONAL_GLOSA_RETENCAO_INICIO -->
    <p class="Texto_Justificado_Recuo_Primeira_Linha" paraeid="{221ec6eb-cac4-42e6-a260-010369388ffa}{6}" paraid="1148630699">Orientamos que na eventual necessidade de incorrer <b>desconto relativos à glosa</b>, a mesma deverá informar a dedução com base nos valores acima apresentados para posterior envio do processo para a unidade <strong>SMDHC/CAF/DOF/DEOF</strong>.</p>
    
    <p class="Texto_Justificado_Recuo_Primeira_Linha" paraeid="{221ec6eb-cac4-42e6-a260-010369388ffa}{6}" paraid="1148630699"><br></p>
    
    <p class="Texto_Justificado_Recuo_Primeira_Linha" paraeid="{221ec6eb-cac4-42e6-a260-010369388ffa}{6}" paraid="1148630699">No caso de <b>retenção da parcela</b>, sugerimos que o processo permaneça custodiado na unidade da Pessoa Gestora para registro do motivo da retenção até a eventual regularização possibilitando o posterior envio à unidade <strong>SMDHC/CAF/DOF/DEOF</strong>.</p>
    <!-- CONDICIONAL_GLOSA_RETENCAO_FIM -->
    
    <p class="Texto_Justificado_Recuo_Primeira_Linha" paraeid="{221ec6eb-cac4-42e6-a260-010369388ffa}{6}" paraid="1148630699"><br></p>
    
    <p class="Texto_Justificado_Recuo_Primeira_Linha" paraeid="{221ec6eb-cac4-42e6-a260-010369388ffa}{6}" paraid="1148630699">Por fim, estando em total concordância dos valores [info_empenho_parcial_usuario: parciais] acima apresentados, solicitamos a formalização da anuência da Pessoa Gestora da parceria a ser encaminhada à unidade <strong>SMDHC/CAF/DOF/DEOF</strong>, para prosseguimento do fluxo de pagamento.</p>
</div>$$
WHERE id = 20;

-- Verificar se a atualização foi bem-sucedida
SELECT 
    CASE 
        WHEN modelo_texto LIKE '%LINHAS_TABELA_PARCELAS%' THEN 'Modelo atualizado com sucesso!'
        ELSE 'Erro: modelo não foi atualizado corretamente'
    END AS resultado
FROM categoricas.c_geral_modelo_textos
WHERE id = 20;
