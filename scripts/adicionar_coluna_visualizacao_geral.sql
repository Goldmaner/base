-- Adicionar coluna visualizacao_geral à tabela c_dgp_analistas
-- Controla se o analista DGP pode ver TODOS os registros de Celebração de Parcerias
-- FALSE (padrão): vê apenas os registros onde é responsável
-- TRUE: vê todos os registros

ALTER TABLE categoricas.c_dgp_analistas
ADD COLUMN IF NOT EXISTS visualizacao_geral BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN categoricas.c_dgp_analistas.visualizacao_geral
IS 'Se TRUE, o analista pode ver todos os registros de Celebração de Parcerias';
