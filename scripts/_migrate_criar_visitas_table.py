"""
Migração: cria public.parcerias_monit_visitas e importa dados existentes de parcerias_monit.
Execute uma única vez: python scripts/_migrate_criar_visitas_table.py

Após validar os dados, os campos visita_* podem ser removidos de parcerias_monit
com: ALTER TABLE public.parcerias_monit DROP COLUMN visita_status, DROP COLUMN visita_data, ...
(NÃO executado por este script — aguardar validação)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
conn.autocommit = False
cur = conn.cursor()

try:
    # 1. Criar tabela
    cur.execute("""
        CREATE TABLE IF NOT EXISTS public.parcerias_monit_visitas (
            id               SERIAL PRIMARY KEY,
            numero_termo     VARCHAR(30)  NOT NULL,
            tipo_prestacao   VARCHAR(50)  NOT NULL,
            numero_prestacao INTEGER      NOT NULL,
            visita_status    VARCHAR(100),
            visita_data      DATE,
            visita_horario   TIME,
            visita_responsavel TEXT[],
            visita_avaliacao VARCHAR(100),
            observacoes      TEXT,
            criado_em        TIMESTAMPTZ DEFAULT NOW(),
            atualizado_em    TIMESTAMPTZ DEFAULT NOW(),
            FOREIGN KEY (numero_termo, tipo_prestacao, numero_prestacao)
                REFERENCES public.parcerias_monit(numero_termo, tipo_prestacao, numero_prestacao)
                ON DELETE CASCADE
        )
    """)
    print("Tabela parcerias_monit_visitas criada (ou já existia).")

    # 2. Importar registros que têm ao menos um campo de visita preenchido
    cur.execute("""
        INSERT INTO public.parcerias_monit_visitas
            (numero_termo, tipo_prestacao, numero_prestacao,
             visita_status, visita_data, visita_horario,
             visita_responsavel, visita_avaliacao)
        SELECT
            numero_termo, tipo_prestacao, numero_prestacao,
            visita_status, visita_data, visita_horario,
            visita_responsavel, visita_avaliacao
        FROM public.parcerias_monit
        WHERE visita_status     IS NOT NULL
           OR visita_data       IS NOT NULL
           OR visita_responsavel IS NOT NULL
           OR visita_avaliacao  IS NOT NULL
        ON CONFLICT DO NOTHING
    """)
    importados = cur.rowcount
    print(f"{importados} registro(s) importado(s) de parcerias_monit → parcerias_monit_visitas.")

    conn.commit()
    print("Migração concluída com sucesso.")
    print()
    print("PRÓXIMO PASSO (quando validado):")
    print("  ALTER TABLE public.parcerias_monit")
    print("    DROP COLUMN visita_status,")
    print("    DROP COLUMN visita_data,")
    print("    DROP COLUMN visita_horario,")
    print("    DROP COLUMN visita_responsavel,")
    print("    DROP COLUMN visita_avaliacao;")

except Exception as e:
    conn.rollback()
    print(f"Erro: {e}")
finally:
    cur.close()
    conn.close()
