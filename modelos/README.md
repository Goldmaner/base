# 📁 Central de Modelos - Documentos Padrão

Esta pasta contém os modelos de documentos utilizados no sistema de Análise de Prestação de Contas.

## 📄 Arquivos Disponíveis

### Termos Contratuais
- **modelo_termo_celebrado.pdf** - Modelo de termo de colaboração/fomento/parceria
- **modelo_solicitacao_alteracao.pdf** - Documentos que registram pedidos de modificação em cláusulas, cronogramas, valores ou demais aspectos do termo celebrado
- **modelo_termo_aditamento.pdf** - Instrumentos formais utilizados para alterar, prorrogar ou suplementar cláusulas do termo celebrado original
- **modelo_termo_apostilamento.pdf** - Registros administrativos de ajustes que não modificam o objeto principal do termo

### Planejamento e Orçamento
- **modelo_manifestacao_plano.pdf** - Pareceres, comunicações ou documentos que resultem em mudanças relevantes no plano de trabalho
- **modelo_cronograma_desembolso.xlsx** - Documento que apresenta as datas e valores previstos para liberação dos recursos financeiros
- **modelo_plano_trabalho.pdf** - Documento detalhado das atividades, metas, prazos e responsabilidades para execução do termo
- **modelo_orcamento_anual.xlsx** - Relação detalhada dos recursos financeiros previstos para o exercício
- **modelo_memoria_calculo.xlsx** - Documento que detalha e justifica os cálculos realizados para apuração de valores

### Documentos Administrativos
- **modelo_facc.pdf** - Ficha de Atualização de Cadastro de Credores (FACC)

## 🔄 Versionamento

Todos os arquivos são versionados via Git para:
- ✅ Rastreabilidade de alterações
- ✅ Histórico completo de versões
- ✅ Sincronização entre ambientes
- ✅ Backup automático

## 📥 Como Acessar

1. **Via Interface Web:**
   - Acesse: Análise de Prestação de Contas → Ver Instrução → Acessar Central de Modelos
   - URL direta: `/analises_pc/central_modelos`

2. **Via Download Direto:**
   - Endpoint: `/analises_pc/download_modelo/<nome_arquivo>`
   - Exemplo: `/analises_pc/download_modelo/modelo_termo_celebrado.pdf`

## 🛡️ Segurança

- ✅ Lista branca de arquivos permitidos no backend
- ✅ Validação de extensões (.pdf, .xlsx)
- ✅ Caminho absoluto para evitar directory traversal
- ✅ Download via `send_from_directory()` do Flask

## 📝 Estrutura no Código

```python
# routes/analises_pc/routes.py
@analises_pc_bp.route('/download_modelo/<filename>')
def download_modelo(filename):
    modelos_dir = os.path.join(os.path.dirname(__file__), '../../modelos')
    # Validação + download seguro
```

## 🔧 Manutenção

Para adicionar novos modelos:

1. Adicione o arquivo nesta pasta
2. Atualize a lista em `routes/analises_pc/routes.py`:
   - Array `modelos` na função `central_modelos()`
   - Lista `arquivos_permitidos` na função `download_modelo()`
3. Faça commit no Git
4. Deploy da aplicação

---

**Última atualização:** 07/11/2025
