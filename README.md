# FAF - Sistema de Gestão de Orçamento e Parcerias

Este projeto é uma aplicação web desenvolvida em Flask para gestão de orçamento, parcerias e despesas, com integração ao PostgreSQL e interface moderna baseada em Bootstrap.

## Estrutura de Pastas

```
FAF/
│
├── app.py                # Arquivo principal da aplicação Flask
├── config.py             # Configurações do projeto (DB, variáveis)
├── db.py                 # Conexão e funções do banco de dados
├── utils.py              # Funções utilitárias
│
├── routes/               # Blueprints e rotas da aplicação
│   ├── __init__.py
│   ├── auth.py           # Autenticação de usuários
│   ├── despesas.py       # Rotas de despesas
│   ├── instrucoes.py     # Rotas de instruções
│   ├── main.py           # Rotas principais
│   ├── orcamento.py      # Rotas de orçamento e dicionário de categorias
│   └── parcerias.py      # Rotas de parcerias
│
├── templates/            # Templates HTML (Jinja2)
│   ├── instrucoes.html
│   ├── login.html
│   ├── orcamento_1.html  # Listagem de orçamento
│   ├── orcamento_2.html  # Edição de orçamento
│   ├── orcamento_3_dict.html # Dicionário de categorias de despesas
│   ├── parcerias_form.html
│   ├── parcerias.html
│   └── tela_inicial.html
│
├── outras coisas/        # Scripts auxiliares e documentação
│   ├── create_users.py
│   ├── debug_table.py
│   ├── ESTRUTURA_MODULAR.md
│   ├── fix_sequence.py
│   ├── import_2.py
│   ├── parcerias.csv
│   ├── parcerias_despesas.csv
│   ├── README.md         # (Este arquivo)
│   ├── test_flask_apis.py
│   ├── test_insert.py
│   ├── test_postgres_connection.py
│   └── ...
│
├── melhorias/            # Documentação de melhorias e changelogs
│   ├── CHANGELOG_AUTOSAVE_PAGINATION.md
│   ├── CORRECOES_FILTRO_FORMATACAO.md
│   └── MELHORIAS_UX_FORMULARIO.md
│
└── __pycache__/          # Arquivos temporários do Python
```

## Principais Funcionalidades

- **Gestão de Orçamento:** Cadastro, edição e visualização de despesas por mês, com filtros e paginação.
- **Dicionário de Categorias:** Padronização em massa de categorias de despesas, busca global, edição em lote e visualização de termos.
- **Parcerias:** Cadastro e acompanhamento de parcerias, integração com despesas.
- **Importação/Exportação:** Suporte a importação/exportação de dados via Excel/CSV.
- **Integração com PostgreSQL:** Persistência dos dados em banco relacional.
- **Interface Moderna:** Utilização de Bootstrap, modais, feedback visual e responsividade.

## Como Executar

1. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```

2. Configure o banco de dados em `config.py`.

3. Execute a aplicação:
   ```
   python app.py
   ```

4. Acesse via navegador: [http://localhost:5000](http://localhost:5000)

## Observações

- Scripts auxiliares e documentação estão em `outras coisas/` e `melhorias/`.
- Testes e backups não estão incluídos neste resumo.
- Para padronização de categorias, utilize o dicionário disponível em `orcamento_3_dict.html`.

---

Projeto desenvolvido para facilitar a gestão de orçamento e parcerias, com foco em usabilidade, padronização e integração de dados.
