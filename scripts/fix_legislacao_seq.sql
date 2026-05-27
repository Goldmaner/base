-- Fix: cria sequência para id e adiciona UNIQUE em lei
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_sequences
    WHERE schemaname='categoricas' AND sequencename='c_geral_legislacao_id_seq'
  ) THEN
    CREATE SEQUENCE categoricas.c_geral_legislacao_id_seq;
  END IF;

  PERFORM setval(
    'categoricas.c_geral_legislacao_id_seq',
    COALESCE((SELECT MAX(id) FROM categoricas.c_geral_legislacao), 0) + 1,
    false
  );

  ALTER TABLE categoricas.c_geral_legislacao
    ALTER COLUMN id SET DEFAULT nextval('categoricas.c_geral_legislacao_id_seq');

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'categoricas.c_geral_legislacao'::regclass
      AND contype = 'u'
      AND conname = 'c_geral_legislacao_lei_key'
  ) THEN
    ALTER TABLE categoricas.c_geral_legislacao
      ADD CONSTRAINT c_geral_legislacao_lei_key UNIQUE (lei);
  END IF;
END $$;
