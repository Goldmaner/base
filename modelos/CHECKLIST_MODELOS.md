# 📋 Checklist de Modelos para Upload

## ✅ Modelos já Presentes

- [x] modelo_termo_celebrado.pdf
- [x] modelo_termo_aditamento.pdf  
- [x] modelo_plano_trabalho.pdf
- [x] modelo_memoria_calculo.xlsx

## ⏳ Modelos Pendentes

Adicione os seguintes arquivos nesta pasta:

- [ ] **modelo_solicitacao_alteracao.pdf**
  - Descrição: Documentos que registram pedidos de modificação em cláusulas, cronogramas, valores ou demais aspectos do termo celebrado

- [ ] **modelo_termo_apostilamento.pdf**
  - Descrição: Registros administrativos de ajustes que não modificam o objeto principal do termo, como correções de dados ou atualizações cadastrais

- [ ] **modelo_manifestacao_plano.pdf**
  - Descrição: Pareceres, comunicações ou documentos que resultem em mudanças relevantes no cronograma, atividades ou objetivos do plano de trabalho

- [ ] **modelo_cronograma_desembolso.xlsx**
  - Descrição: Documento que apresenta as datas e valores previstos para liberação dos recursos financeiros ao longo da execução do termo

- [ ] **modelo_orcamento_anual.xlsx**
  - Descrição: Relação detalhada dos recursos financeiros previstos para o exercício, com a discriminação das fontes e aplicações

- [ ] **modelo_facc.pdf**
  - Descrição: Ficha de Atualização de Cadastro de Credores - Formulário utilizado para atualizar ou confirmar os dados cadastrais dos credores envolvidos no processo

## 🔄 Após Adicionar os Arquivos

1. Marque o checkbox acima
2. Execute: `git add modelos/`
3. Execute: `git commit -m "Adiciona modelo [nome_arquivo]"`
4. Execute: `git push`

## ℹ️ Observações

- Todos os arquivos devem estar em formato final (PDF ou XLSX)
- Certifique-se de que os nomes dos arquivos estão EXATAMENTE como listado acima
- Caso altere o nome, atualize também em:
  - `routes/analises_pc/routes.py` (função `central_modelos()`)
  - `routes/analises_pc/routes.py` (função `download_modelo()` - lista `arquivos_permitidos`)

---

**Status Atual:** 4 de 10 modelos (40% completo)
