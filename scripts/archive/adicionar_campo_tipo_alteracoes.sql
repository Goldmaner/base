-- =====================================================
-- Script: Adicionar tipo de campo às alterações
-- Objetivo: Adicionar colunas para configurar o tipo de campo dinâmico
--           de cada tipo de alteração (text, textarea, number, etc.)
-- Data: 2026-01-09
-- =====================================================

-- 1. Adicionar colunas à tabela c_alt_tipo
ALTER TABLE categoricas.c_alt_tipo 
ADD COLUMN IF NOT EXISTS alt_campo_tipo VARCHAR(50),
ADD COLUMN IF NOT EXISTS alt_campo_placeholder TEXT,
ADD COLUMN IF NOT EXISTS alt_campo_maxlength INTEGER,
ADD COLUMN IF NOT EXISTS alt_campo_min INTEGER;

-- 2. Popular os tipos de campo para cada tipo de alteração
UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'text',
  alt_campo_placeholder = 'Digite o novo nome do projeto'
WHERE alt_tipo = 'Nome do projeto';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'select_osc',
  alt_campo_placeholder = 'Selecione a OSC'
WHERE alt_tipo = 'Nome da organização';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'text',
  alt_campo_placeholder = 'XX.XXX.XXX/XXXX-XX',
  alt_campo_maxlength = 18
WHERE alt_tipo = 'CNPJ da organização';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'text',
  alt_campo_placeholder = 'Digite o nome do responsável legal',
  alt_campo_maxlength = 300
WHERE alt_tipo = 'Nome do responsável legal';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'select_pg',
  alt_campo_placeholder = 'Selecione a pessoa gestora'
WHERE alt_tipo = 'Pessoa gestora indicada pela administração pública';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'textarea',
  alt_campo_placeholder = 'Descreva o objeto da parceria'
WHERE alt_tipo = 'Objeto da parceria';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'number',
  alt_campo_placeholder = 'Quantidade',
  alt_campo_min = 0
WHERE alt_tipo = 'Quantidade de beneficiários diretos';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'textarea',
  alt_campo_placeholder = 'Descreva as cláusulas gerais'
WHERE alt_tipo = 'Cláusulas gerais';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'textarea',
  alt_campo_placeholder = 'Descreva a alteração da norma'
WHERE alt_tipo = 'Alteração de norma geral aplicável';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'money',
  alt_campo_placeholder = 'R$ 0,00'
WHERE alt_tipo = 'Aumento de valor total da parceria';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'money',
  alt_campo_placeholder = 'R$ 0,00'
WHERE alt_tipo = 'Redução de valor de valor total da parceria';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'text',
  alt_campo_placeholder = 'SEI do orçamento',
  alt_campo_maxlength = 12
WHERE alt_tipo = 'Remanejamentos sem alteração de valor de parcela';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'text',
  alt_campo_placeholder = 'SEI do orçamento',
  alt_campo_maxlength = 12
WHERE alt_tipo = 'Remanejamentos com alteração de valor de parcela';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'textarea',
  alt_campo_placeholder = 'Descreva as metas e cronograma'
WHERE alt_tipo = 'Metas e cronograma de execução';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'text',
  alt_campo_placeholder = '1511-x / 15138-9'
WHERE alt_tipo = 'FACC';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'date',
  alt_campo_placeholder = 'Nova data final'
WHERE alt_tipo = 'Prorrogação de vigência';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'date_range',
  alt_campo_placeholder = 'Novas datas de início e fim'
WHERE alt_tipo = 'Adequação de vigência';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'date',
  alt_campo_placeholder = 'Nova data final'
WHERE alt_tipo = 'Redução de vigência da parceria';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'date',
  alt_campo_placeholder = 'Data da suspensão'
WHERE alt_tipo = 'Suspensão de vigência da parceria';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'date',
  alt_campo_placeholder = 'Data da retomada'
WHERE alt_tipo = 'Retomada de vigência da parceria';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'textarea',
  alt_campo_placeholder = 'Justificativa do projeto'
WHERE alt_tipo = 'Justificativa do Projeto';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'text',
  alt_campo_placeholder = 'Abrangência geográfica do projeto'
WHERE alt_tipo = 'Abragência geográfica';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'text',
  alt_campo_placeholder = 'Localização do projeto'
WHERE alt_tipo = 'Localização do projeto';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'text',
  alt_campo_placeholder = 'Faixa etária dos beneficiários'
WHERE alt_tipo = 'Faixa etária de beneficiários';

UPDATE categoricas.c_alt_tipo SET 
  alt_campo_tipo = 'number',
  alt_campo_placeholder = 'Quantidade',
  alt_campo_min = 0
WHERE alt_tipo = 'Quantidade de beneficiários indiretos';

-- 3. Verificar resultado
SELECT 
  alt_tipo, 
  alt_instrumento,
  alt_campo_tipo, 
  alt_campo_placeholder,
  alt_campo_maxlength,
  alt_campo_min
FROM categoricas.c_alt_tipo
ORDER BY alt_tipo;

-- 4. COMMIT (apenas se estiver satisfeito com o resultado)
-- COMMIT;
