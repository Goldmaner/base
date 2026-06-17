"""
Script de migração: cria e popula a tabela sistema.mapa_paginas

Uso:
    python scripts/criar_mapa_paginas.py

A tabela alimenta a Central de Páginas (/central-paginas).
parent_id permite declarar subpáginas de uma página principal.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db import get_db

SQL_SCHEMA = "CREATE SCHEMA IF NOT EXISTS sistema;"

SQL_TABELA = """
CREATE TABLE IF NOT EXISTS sistema.mapa_paginas (
    id          SERIAL  PRIMARY KEY,
    nome_pagina TEXT    NOT NULL,
    rota        TEXT,
    area        TEXT,
    descricao   TEXT,
    responsavel TEXT,
    icone       TEXT,
    ordem       INTEGER DEFAULT 0,
    ativo       BOOLEAN DEFAULT TRUE,
    parent_id   INTEGER REFERENCES sistema.mapa_paginas(id),
    CONSTRAINT mapa_paginas_nome_parent_uq
        UNIQUE NULLS NOT DISTINCT (nome_pagina, parent_id)
);
"""

SQL_PARENT_ID_COLUMN = """
ALTER TABLE sistema.mapa_paginas
    ADD COLUMN IF NOT EXISTS parent_id INTEGER REFERENCES sistema.mapa_paginas(id);

ALTER TABLE sistema.mapa_paginas
    DROP CONSTRAINT IF EXISTS mapa_paginas_nome_parent_uq;

ALTER TABLE sistema.mapa_paginas
    ADD CONSTRAINT mapa_paginas_nome_parent_uq
    UNIQUE NULLS NOT DISTINCT (nome_pagina, parent_id);
"""

# ── Páginas raiz (parent_id = NULL) ──────────────────────────────────────
SQL_PAGINAS_RAIZ = """
INSERT INTO sistema.mapa_paginas
    (nome_pagina, rota, area, descricao, responsavel, icone, ordem)
VALUES
  -- Gestão de Parcerias
  ('Parcerias',
   '/parcerias', 'Gestão de Parcerias',
   'Cadastro, consulta e edição de termos e informações principais das parcerias.',
   'DGP', 'bi-file-text', 1),

  ('Pesquisa de Parcerias',
   '/pesquisa-parcerias', 'Gestão de Parcerias',
   'Busca avançada de parcerias com múltiplos filtros: OSC, SEI, situação, período e mais.',
   'DGP', 'bi-search', 2),

  ('Editais',
   '/editais', 'Gestão de Parcerias',
   'Gerenciamento de editais de chamamento público e convocatórias.',
   'DGP', 'bi-megaphone', 3),

  ('Certidões',
   '/certidoes', 'Gestão de Parcerias',
   'Consulta e organização das certidões obrigatórias das OSCs.',
   'DAC', 'bi-patch-check', 4),

  -- Gestão Financeira
  ('Gestão Financeira',
   '/gestao_financeira', 'Gestão Financeira',
   'Visão geral da gestão financeira das parcerias: repasses, saldos e pendências.',
   'DAC', 'bi-wallet2', 1),

  ('Ultra Liquidações',
   '/gestao_financeira/ultra-liquidacoes', 'Gestão Financeira',
   'Acompanhamento de parcelas, cronogramas e liquidações financeiras das parcerias.',
   'DAC', 'bi-cash-coin', 2),

  ('Dotações e Empenhos',
   '/gestao_orcamentaria', 'Gestão Financeira',
   'Controle de dotações orçamentárias, empenhos e créditos disponíveis.',
   'DAC', 'bi-layers', 3),

  ('SOF API',
   '/gestao_orcamentaria/sof-api', 'Gestão Financeira',
   'Consulta de dados orçamentários via integração com o SOF da Prefeitura de São Paulo.',
   'DAC', 'bi-cloud-download', 4),

  -- Análises
  ('Análises',
   '/analises', 'Análises',
   'Painéis analíticos e indicadores das parcerias da SMDHC.',
   'DAC', 'bi-bar-chart-line', 1),

  ('Conciliação Bancária',
   '/conc_banc', 'Análises',
   'Conciliação de extratos bancários e lançamentos financeiros das parcerias.',
   'DAC', 'bi-bank', 2),

  -- Administração
  ('Usuários',
   '/gestao_pessoas', 'Administração',
   'Gerenciamento de usuários, perfis de acesso e permissões do sistema.',
   'Admin', 'bi-people', 1),

  ('Férias',
   '/ferias', 'Administração',
   'Controle e acompanhamento de férias e ausências dos servidores.',
   'DP', 'bi-calendar-event', 2),

  -- Apoio / Outros
  ('Instruções',
   '/instrucoes', 'Apoio / Outros',
   'Consulta de instruções de serviço, normativas e orientações internas.',
   'DGP', 'bi-book', 1),

  ('Listas',
   '/listas', 'Apoio / Outros',
   'Tabelas de referência do sistema: analistas, status, tipos, glosas e outros dados auxiliares.',
   'DGP', 'bi-list-ul', 2),

  ('Manuais',
   '/manuais', 'Apoio / Outros',
   'Manuais e guias de uso do sistema FParcerias para servidores e parceiros.',
   'Admin', 'bi-journal-text', 3)

ON CONFLICT ON CONSTRAINT mapa_paginas_nome_parent_uq DO NOTHING
RETURNING id, nome_pagina;
"""

# ── Subpáginas de Listas (parent_id = id da linha "Listas") ──────────────
SQL_FILHOS_LISTAS = """
WITH pai AS (
    SELECT id FROM sistema.mapa_paginas
    WHERE nome_pagina = 'Listas' AND parent_id IS NULL
    LIMIT 1
)
INSERT INTO sistema.mapa_paginas
    (nome_pagina, rota, area, descricao, responsavel, icone, ordem, parent_id)
SELECT nome_pagina, rota, area, descricao, responsavel, icone, ordem, pai.id
FROM pai, (VALUES
    ('DAC: Analistas',
     '/listas?tabela=c_dac_analistas', 'Apoio / Outros',
     'Lista de analistas da Divisão de Análise de Contas.',
     'DAC', 'bi-person-badge', 1),

    ('DAC: Despesas de Análise',
     '/listas?tabela=c_dac_despesas_analise', 'Apoio / Outros',
     'Categorias e tipos de despesas utilizados na análise de prestação de contas.',
     'DAC', 'bi-receipt', 2),

    ('DAC: Tipos de Glosa',
     '/listas?tabela=c_dac_glosas', 'Apoio / Outros',
     'Tipos e modelos de glosa utilizados nas análises e conciliações da DAC.',
     'DAC', 'bi-x-octagon', 3),

    ('DAC: Modelos de Inconsistências',
     '/listas?tabela=c_dac_modelo_textos_inconsistencias', 'Apoio / Outros',
     'Modelos de textos para apontamentos de inconsistências em prestações de contas.',
     'DAC', 'bi-exclamation-triangle', 4),

    ('DGP: Agentes DGP',
     '/listas?tabela=c_dgp_analistas', 'Apoio / Outros',
     'Lista de agentes da Divisão de Gestão de Parcerias.',
     'DGP', 'bi-person-check', 5),

    ('DGP: Status de CENTS',
     '/listas?tabela=c_dgp_cents_status', 'Apoio / Outros',
     'Status utilizados no acompanhamento de CENTS (Certificados de Entidades).',
     'DGP', 'bi-toggle-on', 6),

    ('DGP: Status de Celebração',
     '/listas?tabela=c_dgp_celebracao_status', 'Apoio / Outros',
     'Status do fluxo de celebração de parcerias.',
     'DGP', 'bi-flag', 7)
) AS sub(nome_pagina, rota, area, descricao, responsavel, icone, ordem)
ON CONFLICT ON CONSTRAINT mapa_paginas_nome_parent_uq DO NOTHING;
"""


def main():
    print("─" * 58)
    print("  Migração: sistema.mapa_paginas")
    print("─" * 58)

    from flask import Flask
    from config import SECRET_KEY

    app = Flask(__name__)
    app.secret_key = SECRET_KEY

    with app.app_context():
        conn = get_db()
        cur  = conn.cursor()

        print("→ Criando schema sistema...")
        cur.execute(SQL_SCHEMA)

        print("→ Criando tabela mapa_paginas...")
        cur.execute(SQL_TABELA)

        print("→ Garantindo coluna parent_id (caso tabela já exista)...")
        cur.execute(SQL_PARENT_ID_COLUMN)

        print("→ Inserindo páginas raiz...")
        cur.execute(SQL_PAGINAS_RAIZ)

        print("→ Inserindo subpáginas de Listas...")
        cur.execute(SQL_FILHOS_LISTAS)

        conn.commit()
        cur.close()

    print("✓ Concluído.")
    print("  Acesse /central-paginas para visualizar.")
    print("─" * 58)


if __name__ == '__main__':
    main()
