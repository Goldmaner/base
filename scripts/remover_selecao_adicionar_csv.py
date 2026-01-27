# -*- coding: utf-8 -*-
"""
Script para remover funcionalidade de seleção de células 
e adicionar botão de exportação CSV
"""

# Ler arquivo
with open(r"c:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF\templates\gestao_financeira\ultra_liquidacoes.html", 'r', encoding='utf-8') as f:
    conteudo = f.read()

# Encontrar início e fim da seção de seleção
inicio_marcador = "<!-- ============================================================================ -->\n<!-- FUNCIONALIDADE: SELEÇÃO DE CÉLULAS COM SOMA -->"
fim_marcador = "</html>"

inicio_idx = conteudo.find(inicio_marcador)
fim_idx = conteudo.rfind(fim_marcador)

if inicio_idx == -1:
    print("❌ Marcador de início não encontrado")
    exit(1)

# Extrair partes
antes = conteudo[:inicio_idx]
depois = fim_marcador + "\n"

# Novo código
novo_codigo = """
<!-- ============================================================================ -->
<!-- FUNCIONALIDADE: EXPORTAÇÃO CSV EDIÇÃO COLETIVA -->
<!-- ============================================================================ -->
<script>
    // ============================================================================
    // EXPORTAÇÃO CSV DA EDIÇÃO COLETIVA
    // ============================================================================
    $(document).on('click', '#btnExportarCSVColetivo', function() {
        const termo = $('#coletivo_numero_termo_hidden').val();
        if (!termo) {
            toastr.error('Nenhum termo carregado para exportação');
            return;
        }
        
        // Coletar dados da tabela
        const linhas = [];
        const cabecalho = [
            'Vigência Inicial',
            'Vigência Final',
            'Tipo Parcela',
            'Nº Parcela',
            'Valor 53/23',
            'Valor 53/24',
            'Valor Previsto',
            'Subtraído',
            'Encaminhado',
            'Pago',
            'Status',
            'Status Sec.',
            'Data Pgto'
        ];
        linhas.push(cabecalho.join(';'));
        
        $('#corpoTabelaColetiva tr').each(function() {
            const colunas = [];
            $(this).find('td').each(function(idx) {
                const input = $(this).find('input, select');
                let valor = '';
                if (input.length > 0) {
                    valor = input.val() || '';
                } else {
                    valor = $(this).text().trim();
                }
                // Remover ponto e vírgula do valor para não quebrar CSV
                valor = valor.replace(/;/g, ',');
                colunas.push(valor);
            });
            linhas.push(colunas.join(';'));
        });
        
        // Gerar CSV com UTF-8 BOM
        const BOM = '\\uFEFF';
        const csvContent = BOM + linhas.join('\\r\\n');
        
        // Download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        link.setAttribute('href', url);
        link.setAttribute('download', `edicao_coletiva_${termo.replace(/\\//g, '_')}_${new Date().toISOString().split('T')[0]}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        toastr.success('CSV exportado com sucesso!');
    });
</script>

"""

# Juntar
novo_conteudo = antes + novo_codigo + depois

# Salvar
with open(r"c:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF\templates\gestao_financeira\ultra_liquidacoes.html", 'w', encoding='utf-8') as f:
    f.write(novo_conteudo)

print("✅ Arquivo atualizado com sucesso!")
print(f"   Removido: {len(conteudo) - len(novo_conteudo)} caracteres")
print(f"   Tamanho original: {len(conteudo)}")
print(f"   Tamanho novo: {len(novo_conteudo)}")
