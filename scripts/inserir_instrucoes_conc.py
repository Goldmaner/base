"""
Script para inserir modelos de texto de instruções de conciliação bancária
no banco de dados PostgreSQL
"""

import os
import sys
from pathlib import Path

# Adicionar diretório pai ao path para importar módulos do projeto
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from db import get_db, get_cursor

# Instruções completas em HTML
INSTRUCAO_PREENCHIMENTO = """
<div class="instrucao-content">
    <h5 class="text-primary mb-3">📊 Instrução: Preenchimento da Conciliação Bancária</h5>
    
    <div class="alert alert-info">
        <i class="bi bi-info-circle-fill me-2"></i>
        <strong>Objetivo:</strong> Esta instrução orienta o preenchimento correto dos dados bancários do termo de parceria no sistema de conciliação bancária.
    </div>

    <h6 class="mt-4 mb-3 text-primary">1. Acesso ao Módulo</h6>
    <ol>
        <li>Clique em <strong>"Construir e/ou consultar conciliações bancárias existentes"</strong></li>
        <li>Ou acesse diretamente: <strong>Menu Principal → Análises PC → Conciliação Bancária</strong></li>
        <li>Selecione o <strong>número do termo</strong> no dropdown</li>
    </ol>

    <h6 class="mt-4 mb-3 text-primary">2. Importação de Extratos Bancários</h6>
    <ol>
        <li><strong>Formato aceito:</strong> Arquivos Excel (.xlsx) ou CSV com as seguintes colunas:
            <ul type="circle">
                <li><code>Data</code> - Data da movimentação (formato: DD/MM/AAAA)</li>
                <li><code>Crédito</code> - Valores de entrada (formato: 10.000,00)</li>
                <li><code>Débito</code> - Valores de saída (formato: 10.000,00)</li>
                <li><code>Discriminação</code> - Descrição da transação</li>
                <li><code>Origem/Destino</code> - Beneficiário ou pagador (se disponível)</li>
            </ul>
        </li>
        <li>Clique em <strong>"📥 Importar Extrato"</strong></li>
        <li>Selecione o arquivo do extrato bancário</li>
        <li>Aguarde o processamento automático</li>
    </ol>

    <h6 class="mt-4 mb-3 text-primary">3. Preenchimento dos Campos</h6>
    
    <div class="table-responsive mt-3">
        <table class="table table-bordered">
            <thead class="table-primary">
                <tr>
                    <th style="width: 25%;">Campo</th>
                    <th style="width: 50%;">Descrição</th>
                    <th style="width: 25%;">Observação</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Índice</strong></td>
                    <td>Número sequencial da linha (gerado automaticamente)</td>
                    <td class="text-muted">Apenas visualização</td>
                </tr>
                <tr>
                    <td><strong>Data</strong></td>
                    <td>Data da movimentação bancária</td>
                    <td class="text-danger">Obrigatório</td>
                </tr>
                <tr>
                    <td><strong>Crédito</strong></td>
                    <td>Valores de entrada (depósitos, transferências recebidas)</td>
                    <td>Formato: 10.000,00</td>
                </tr>
                <tr>
                    <td><strong>Débito</strong></td>
                    <td>Valores de saída (pagamentos, transferências enviadas)</td>
                    <td>Formato: 10.000,00</td>
                </tr>
                <tr>
                    <td><strong>Discriminação</strong></td>
                    <td>Saldo/Valor da transação (calculado automaticamente)</td>
                    <td class="text-info">Auto-calculado</td>
                </tr>
                <tr>
                    <td><strong>Categoria de Transação</strong></td>
                    <td>Classificação da despesa ou receita<br>
                        <small>Ex: Destinatário Identificado, Taxas Bancárias, Rendimentos, etc.</small>
                    </td>
                    <td class="text-danger">Obrigatório para análise</td>
                </tr>
                <tr>
                    <td><strong>Competência</strong></td>
                    <td>Mês/Ano de competência da transação (MM/AAAA)<br>
                        <small>Ex: 01/2024 para despesas de janeiro/2024</small>
                    </td>
                    <td class="text-warning">Importante para relatórios</td>
                </tr>
                <tr>
                    <td><strong>Origem/Destino</strong></td>
                    <td>Nome do beneficiário (para débitos) ou do depositante (para créditos)</td>
                    <td>Essencial para rastreabilidade</td>
                </tr>
            </tbody>
        </table>
    </div>

    <h6 class="mt-4 mb-3 text-primary">4. Categorização Automática</h6>
    <div class="alert alert-success">
        <i class="bi bi-lightning-fill me-2"></i>
        <strong>Funcionalidade Inteligente:</strong> O sistema aplica categorização automática para débitos após a data de corte:
        <ul class="mt-2 mb-0">
            <li>Se <strong>Origem/Destino</strong> está preenchido → <code>Destinatário Identificado</code></li>
            <li>Se <strong>Origem/Destino</strong> está vazio → <code>Destinatário não Identificado</code></li>
        </ul>
    </div>

    <h6 class="mt-4 mb-3 text-primary">5. Mesclagem de Lançamentos</h6>
    <ol>
        <li>Para agrupar múltiplas linhas relacionadas, use o campo <strong>"Mesclar com"</strong></li>
        <li>Insira os <strong>IDs das linhas</strong> separados por vírgula (ex: 15,16,17)</li>
        <li>Linhas mescladas aparecem visualmente agrupadas na tabela</li>
        <li><strong>Utilidade:</strong> Agrupar parcelas, fracionamentos ou pagamentos relacionados</li>
    </ol>

    <h6 class="mt-4 mb-3 text-primary">6. Salvamento dos Dados</h6>
    <ol>
        <li>Preencha todos os campos obrigatórios (marcados em vermelho)</li>
        <li>Clique em <strong>"💾 Salvar Tudo"</strong> no topo da página</li>
        <li>Aguarde a confirmação de salvamento bem-sucedido</li>
        <li>Verifique se há mensagens de erro sobre campos faltantes</li>
    </ol>

    <h6 class="mt-4 mb-3 text-primary">7. Validações e Boas Práticas</h6>
    <div class="alert alert-warning">
        <i class="bi bi-exclamation-triangle-fill me-2"></i>
        <strong>Atenção aos seguintes pontos:</strong>
        <ul class="mt-2 mb-0">
            <li><strong>Data:</strong> Deve estar dentro do período de vigência do termo</li>
            <li><strong>Competência:</strong> Formato MM/AAAA (ex: 03/2024)</li>
            <li><strong>Valores monetários:</strong> Usar formato brasileiro (vírgula decimal)</li>
            <li><strong>Categorias:</strong> Preferencialmente usar categorias já cadastradas no orçamento</li>
            <li><strong>Origem/Destino:</strong> Preencher sempre que possível para rastreabilidade</li>
        </ul>
    </div>

    <h6 class="mt-4 mb-3 text-primary">8. Campos Especiais</h6>
    <ul>
        <li><strong>Avaliação Analista:</strong> Campo livre para observações do analista</li>
        <li><strong>Categoria de Avaliação:</strong> Será preenchido na etapa de avaliação (próxima instrução)</li>
        <li><strong>Mesclado com:</strong> IDs de linhas agrupadas (separados por vírgula)</li>
    </ul>

    <h6 class="mt-4 mb-3 text-primary">9. Dicas de Produtividade</h6>
    <ul>
        <li>Use <strong>Ctrl+C / Ctrl+V</strong> para copiar categorias entre linhas</li>
        <li>Ordene por data para facilitar o preenchimento cronológico</li>
        <li>Filtre por tipo (Crédito/Débito) para categorizar em lotes</li>
        <li>Salve periodicamente para não perder progresso</li>
    </ul>

    <div class="alert alert-info mt-4">
        <i class="bi bi-info-circle-fill me-2"></i>
        <strong>Próxima Etapa:</strong> Após o preenchimento completo, prossiga para a <strong>Avaliação dos Dados Bancários</strong>, onde você analisará a conformidade das transações.
    </div>
</div>
"""

INSTRUCAO_AVALIACAO = """
<div class="instrucao-content">
    <h5 class="text-warning mb-3">🔍 Instrução: Avaliação dos Dados Bancários</h5>
    
    <div class="alert alert-warning">
        <i class="bi bi-search me-2"></i>
        <strong>Objetivo:</strong> Esta instrução orienta a análise crítica dos dados bancários preenchidos, verificando conformidade, identificando inconsistências e aplicando avaliações.
    </div>

    <h6 class="mt-4 mb-3 text-warning">1. Acesso ao Relatório de Conciliação</h6>
    <ol>
        <li>Após preencher os dados bancários, acesse <strong>Relatório de Conciliação</strong></li>
        <li>Ou clique em <strong>"Abrir Relatório de Conciliação"</strong> no rodapé desta instrução</li>
        <li>Selecione o <strong>termo</strong> e os <strong>períodos</strong> a analisar</li>
    </ol>

    <h6 class="mt-4 mb-3 text-warning">2. Verificações Preliminares</h6>
    
    <div class="card mb-3">
        <div class="card-header bg-warning text-dark fw-bold">
            Checklist de Verificação
        </div>
        <div class="card-body">
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    Todos os lançamentos possuem <strong>categoria de transação</strong> preenchida
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    Competências estão no formato correto (MM/AAAA)
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    Valores conferem com extratos bancários físicos
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    Datas estão dentro do período de vigência do termo
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    Origem/Destino preenchido para pagamentos relevantes
                </label>
            </div>
        </div>
    </div>

    <h6 class="mt-4 mb-3 text-warning">3. Categorias de Avaliação</h6>
    
    <div class="table-responsive">
        <table class="table table-bordered">
            <thead class="table-warning">
                <tr>
                    <th style="width: 25%;">Categoria</th>
                    <th style="width: 50%;">Quando Aplicar</th>
                    <th style="width: 25%;">Cor no Sistema</th>
                </tr>
            </thead>
            <tbody>
                <tr class="table-success">
                    <td><strong>Avaliado</strong></td>
                    <td>Lançamento está correto, completo e conforme documentação</td>
                    <td><span class="badge bg-success">Verde</span></td>
                </tr>
                <tr class="table-light">
                    <td><strong>Aguardando</strong></td>
                    <td>Pendente de informações adicionais ou documentos</td>
                    <td><span class="badge bg-secondary">Cinza</span></td>
                </tr>
                <tr class="table-info">
                    <td><strong>Pessoa Gestora</strong></td>
                    <td>Análise delegada à pessoa gestora responsável</td>
                    <td><span class="badge bg-info">Azul</span></td>
                </tr>
                <tr class="table-danger">
                    <td><strong>Glosar</strong></td>
                    <td>Despesa improcedente ou sem comprovação adequada</td>
                    <td><span class="badge bg-danger">Vermelho</span></td>
                </tr>
            </tbody>
        </table>
    </div>

    <h6 class="mt-4 mb-3 text-warning">4. Análise de Conformidade</h6>
    
    <h6 class="mt-3 fw-bold">4.1. Despesas Identificadas</h6>
    <ul>
        <li>Verifique se <strong>categoria da transação</strong> corresponde ao <strong>orçamento aprovado</strong></li>
        <li>Confira se o <strong>beneficiário</strong> (Origem/Destino) está nos documentos da PC</li>
        <li>Compare valores com <strong>notas fiscais</strong> e recibos apresentados</li>
        <li>Valide se a competência está dentro do <strong>período de execução</strong></li>
    </ul>

    <h6 class="mt-3 fw-bold">4.2. Despesas não Identificadas</h6>
    <div class="alert alert-danger">
        <i class="bi bi-exclamation-octagon-fill me-2"></i>
        <strong>Atenção Especial:</strong> Lançamentos sem Origem/Destino requerem análise criteriosa:
        <ul class="mt-2 mb-0">
            <li>Solicitar <strong>esclarecimentos à OSC</strong></li>
            <li>Verificar se há documentação que identifique o pagamento</li>
            <li>Avaliar possibilidade de <strong>glosa</strong> se não comprovado</li>
        </ul>
    </div>

    <h6 class="mt-3 fw-bold">4.3. Taxas Bancárias</h6>
    <ul>
        <li>Verificar se taxas são <strong>inerentes à manutenção da conta</strong></li>
        <li>Comparar com tabela de tarifas do banco</li>
        <li>Identificar <strong>Devoluções de Taxas</strong> (créditos)</li>
    </ul>

    <h6 class="mt-3 fw-bold">4.4. Rendimentos de Aplicação</h6>
    <ul>
        <li>Confirmar se aplicação está em <strong>caderneta de poupança</strong> ou equivalente</li>
        <li>Verificar se rendimentos foram <strong>revertidos à parceria</strong></li>
        <li>Calcular se o percentual está compatível com a taxa vigente</li>
    </ul>

    <h6 class="mt-4 mb-3 text-warning">5. Cruzamento com Orçamento</h6>
    <ol>
        <li>Acesse o <strong>Orçamento Anual</strong> do termo</li>
        <li>Compare <strong>categorias de transação</strong> com <strong>categorias de despesa</strong></li>
        <li>Verifique se valores executados estão dentro do <strong>previsto</strong></li>
        <li>Identifique despesas <strong>fora do orçamento</strong> (exigem justificativa)</li>
    </ol>

    <div class="alert alert-success mt-3">
        <i class="bi bi-check-circle-fill me-2"></i>
        <strong>Sincronização Automática:</strong> O sistema mantém sincronizadas as categorias entre:
        <ul class="mt-2 mb-0">
            <li><code>parcerias_despesas.categoria_despesa</code></li>
            <li><code>conc_extrato.cat_transacao</code></li>
        </ul>
        Alterações em uma refletem na outra automaticamente.
    </div>

    <h6 class="mt-4 mb-3 text-warning">6. Aplicação das Avaliações</h6>
    <ol>
        <li>Retorne à tela de <strong>Conciliação Bancária</strong></li>
        <li>Para cada lançamento, selecione a <strong>Categoria de Avaliação</strong> apropriada:
            <ul type="circle">
                <li><code>Avaliado</code> - Aprovado e conforme</li>
                <li><code>Aguardando</code> - Pendente de informações</li>
                <li><code>Pessoa Gestora</code> - Delegar análise</li>
                <li><code>Glosar</code> - Rejeitar despesa</li>
            </ul>
        </li>
        <li>Preencha o campo <strong>"Avaliação Analista"</strong> com observações detalhadas</li>
        <li>Salve as alterações</li>
    </ol>

    <h6 class="mt-4 mb-3 text-warning">7. Documentação de Glosas</h6>
    <div class="card border-danger">
        <div class="card-header bg-danger text-white fw-bold">
            Procedimento para Glosas
        </div>
        <div class="card-body">
            <ol class="mb-0">
                <li>Identifique claramente o <strong>motivo da glosa</strong></li>
                <li>Documente no campo <strong>"Avaliação Analista"</strong>:
                    <ul type="circle">
                        <li>Valor glosado</li>
                        <li>Justificativa técnica</li>
                        <li>Normativo descumprido (se aplicável)</li>
                    </ul>
                </li>
                <li>Marque a categoria como <strong>"Glosar"</strong></li>
                <li>Informe à OSC via <strong>ofício de inconsistências</strong></li>
                <li>Aguarde resposta dentro do prazo regulamentar</li>
            </ol>
        </div>
    </div>

    <h6 class="mt-4 mb-3 text-warning">8. Geração do Relatório Final</h6>
    <ol>
        <li>Após avaliar todos os lançamentos, acesse <strong>Relatório de Conciliação</strong></li>
        <li>Selecione os <strong>períodos analisados</strong></li>
        <li>Clique em <strong>"Gerar Relatório"</strong></li>
        <li>O relatório apresentará:
            <ul type="circle">
                <li>Valor total executado</li>
                <li>Valor aprovado</li>
                <li>Glosas e pendências</li>
                <li>Rendimentos e taxas</li>
                <li>Saldos por categoria</li>
            </ul>
        </li>
        <li>Exporte para <strong>PDF</strong> ou <strong>Excel</strong> conforme necessidade</li>
    </ol>

    <h6 class="mt-4 mb-3 text-warning">9. Comunicação com a OSC</h6>
    <div class="alert alert-info">
        <i class="bi bi-envelope-fill me-2"></i>
        <strong>Se houver inconsistências:</strong>
        <ul class="mt-2 mb-0">
            <li>Utilize a <strong>Central de Modelos</strong> para gerar ofícios padronizados</li>
            <li>Especifique claramente cada <strong>inconsistência identificada</strong></li>
            <li>Estabeleça <strong>prazo para resposta</strong> (conforme normativo)</li>
            <li>Registre a notificação no <strong>sistema</strong></li>
        </ul>
    </div>

    <h6 class="mt-4 mb-3 text-warning">10. Checklist Final</h6>
    <div class="card">
        <div class="card-header bg-success text-white fw-bold">
            Antes de Finalizar a Avaliação
        </div>
        <div class="card-body">
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    Todos os lançamentos possuem categoria de avaliação
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    Glosas estão devidamente justificadas
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    Relatório de conciliação foi gerado e revisado
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    Documentação está anexada ao processo SEI
                </label>
            </div>
            <div class="form-check">
                <input class="form-check-input" type="checkbox" disabled>
                <label class="form-check-label">
                    OSC foi notificada sobre pendências (se houver)
                </label>
            </div>
        </div>
    </div>

    <div class="alert alert-success mt-4">
        <i class="bi bi-check2-circle me-2"></i>
        <strong>Conclusão:</strong> Com a avaliação completa, você estará apto a emitir parecer técnico fundamentado sobre a prestação de contas, garantindo conformidade e transparência no uso dos recursos públicos.
    </div>
</div>
"""

def inserir_modelos():
    """Insere os modelos de texto no banco de dados"""
    db = None
    try:
        with app.app_context():
            db = get_db()
            cur = get_cursor()
            
            print("🔄 Inserindo modelos de texto de instruções de conciliação...")
            
            # Verificar se já existem
            cur.execute("""
                SELECT id FROM categoricas.c_geral_modelo_textos
                WHERE titulo_texto = %s
            """, ("Instrução: Preenchimento da Conciliação Bancária",))
            
            if cur.fetchone():
                # Atualizar modelo 1
                cur.execute("""
                    UPDATE categoricas.c_geral_modelo_textos
                    SET modelo_texto = %s, oculto = %s
                    WHERE titulo_texto = %s
                """, (
                    INSTRUCAO_PREENCHIMENTO,
                    False,
                    "Instrução: Preenchimento da Conciliação Bancária"
                ))
                print("✅ Modelo 1 atualizado: Preenchimento da Conciliação Bancária")
            else:
                # Inserir modelo 1
                cur.execute("""
                    INSERT INTO categoricas.c_geral_modelo_textos (titulo_texto, modelo_texto, oculto)
                    VALUES (%s, %s, %s)
                """, (
                    "Instrução: Preenchimento da Conciliação Bancária",
                    INSTRUCAO_PREENCHIMENTO,
                    False
                ))
                print("✅ Modelo 1 inserido: Preenchimento da Conciliação Bancária")
            
            # Verificar modelo 2
            cur.execute("""
                SELECT id FROM categoricas.c_geral_modelo_textos
                WHERE titulo_texto = %s
            """, ("Instrução: Avaliação dos Dados Bancários",))
            
            if cur.fetchone():
                # Atualizar modelo 2
                cur.execute("""
                    UPDATE categoricas.c_geral_modelo_textos
                    SET modelo_texto = %s, oculto = %s
                    WHERE titulo_texto = %s
                """, (
                    INSTRUCAO_AVALIACAO,
                    False,
                    "Instrução: Avaliação dos Dados Bancários"
                ))
                print("✅ Modelo 2 atualizado: Avaliação dos Dados Bancários")
            else:
                # Inserir modelo 2
                cur.execute("""
                    INSERT INTO categoricas.c_geral_modelo_textos (titulo_texto, modelo_texto, oculto)
                    VALUES (%s, %s, %s)
                """, (
                    "Instrução: Avaliação dos Dados Bancários",
                    INSTRUCAO_AVALIACAO,
                    False
                ))
                print("✅ Modelo 2 inserido: Avaliação dos Dados Bancários")
            
            db.commit()
            print("\n✅ Todos os modelos de texto foram inseridos com sucesso!")
            print("\n📋 Próximos passos:")
            print("1. Testar os badges 'Ver Instrução' nos itens 5 e 6 do checklist")
            print("2. Verificar se os modals abrem corretamente")
        
    except Exception as e:
        print(f"\n❌ Erro ao inserir modelos: {e}")
        import traceback
        traceback.print_exc()
        if db:
            db.rollback()
        raise

if __name__ == "__main__":
    inserir_modelos()
