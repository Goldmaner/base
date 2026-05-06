import sys
sys.path.insert(0, '.')
from app import app
with app.app_context():
    from db import get_cursor, get_db
    cur = get_cursor()
    try:
        # 1. Create c_alt_status_alteracao
        cur.execute("""
            CREATE TABLE IF NOT EXISTS categoricas.c_alt_status_alteracao (
                id SERIAL PRIMARY KEY,
                alt_status TEXT NOT NULL UNIQUE,
                alt_status_descricao TEXT,
                alt_ordem INTEGER NOT NULL DEFAULT 99,
                observacoes TEXT,
                criado_em TIMESTAMP DEFAULT NOW(),
                atualizado_em TIMESTAMP
            )
        """)
        print('[OK] Table c_alt_status_alteracao created/exists')

        # 2. Insert 14 status
        status_list = [
            ('Pendente - DGP/ADIT', 'Aguardando análise inicial da DGP/Aditamento', 1),
            ('Em análise - DGP/ADIT', 'Em análise pela equipe DGP/Aditamento', 2),
            ('Aguardando decisão externa - DP/UG/OSC', 'Aguardando retorno de DP, UG ou OSC', 3),
            ('Aguardando decisão externa - Conselho', 'Aguardando deliberação de Conselho', 4),
            ('Ateste de PC - DAC', 'Aguardando ateste da Divisão de Análise de Contas', 5),
            ('Aguardando reserva - DOF', 'Aguardando reserva orçamentária pelo DOF', 6),
            ('Aguardando parecer - AJ/AT', 'Aguardando parecer jurídico ou técnico', 7),
            ('Despacho Autorizatório - GAB', 'Aguardando despacho autorizatório do Gabinete', 8),
            ('Aguardando empenho - DEOF', 'Aguardando empenho pelo DEOF', 9),
            ('Aguardando assinatura TA - DP/UG/OSC', 'Aguardando assinatura do TA por DP/UG/OSC', 10),
            ('Aguardando assinatura TA - GAB', 'Aguardando assinatura do TA pelo Gabinete', 11),
            ('Publicação', 'Aguardando publicação no Diário Oficial', 12),
            ('Aguardando atualização da contratação - DEOF', 'Aguardando atualização pelo DEOF', 13),
            ('Concluído', 'Processo concluído', 14),
        ]
        for alt_status, desc, ordem in status_list:
            cur.execute("""
                INSERT INTO categoricas.c_alt_status_alteracao (alt_status, alt_status_descricao, alt_ordem)
                VALUES (%s, %s, %s)
                ON CONFLICT (alt_status) DO UPDATE SET alt_ordem = EXCLUDED.alt_ordem
            """, (alt_status, desc, ordem))
        print('[OK] 14 status inserted')

        # 3. Add columns to termos_alteracoes
        for col_def in [
            "ADD COLUMN IF NOT EXISTS alt_prioridade TEXT",
            "ADD COLUMN IF NOT EXISTS alt_data_inicio DATE DEFAULT CURRENT_DATE",
            "ADD COLUMN IF NOT EXISTS alt_data_conclusao DATE",
            "ADD COLUMN IF NOT EXISTS alt_oculto BOOLEAN DEFAULT FALSE",
            "ADD COLUMN IF NOT EXISTS alt_marcadores TEXT",
        ]:
            cur.execute(f"ALTER TABLE public.termos_alteracoes {col_def}")
        print('[OK] 5 columns added to termos_alteracoes')

        # 4. Migrate existing statuses
        cur.execute("UPDATE public.termos_alteracoes SET alt_status = 'Pendente - DGP/ADIT' WHERE alt_status = 'Em análise prévia'")
        n1 = cur.rowcount
        cur.execute("UPDATE public.termos_alteracoes SET alt_status = 'Em análise - DGP/ADIT' WHERE alt_status IN ('Iniciado', 'Em andamento')")
        n2 = cur.rowcount
        print(f'[OK] Migrated {n1} "Em análise prévia" -> "Pendente - DGP/ADIT"')
        print(f'[OK] Migrated {n2} "Iniciado"/"Em andamento" -> "Em análise - DGP/ADIT"')

        # 5. Create c_kanban_marcadores_cores
        cur.execute("""
            CREATE TABLE IF NOT EXISTS categoricas.c_kanban_marcadores_cores (
                id SERIAL PRIMARY KEY,
                marcador_nome TEXT NOT NULL UNIQUE,
                marcador_fonte TEXT,
                marcador_cor TEXT NOT NULL DEFAULT 'Cinza',
                criado_em TIMESTAMP DEFAULT NOW(),
                atualizado_em TIMESTAMP
            )
        """)
        print('[OK] Table c_kanban_marcadores_cores created/exists')

        get_db().commit()
        print('\n=== Migration completed successfully ===')

        # Verify
        cur.execute("SELECT COUNT(*) as n FROM categoricas.c_alt_status_alteracao")
        print(f'Status count: {cur.fetchone()["n"]}')
        cur.execute("SELECT COUNT(*) as n FROM public.termos_alteracoes WHERE alt_status NOT IN (SELECT alt_status FROM categoricas.c_alt_status_alteracao)")
        print(f'Records with unrecognized status: {cur.fetchone()["n"]}')

    except Exception as e:
        get_db().rollback()
        import traceback; traceback.print_exc()
    finally:
        cur.close()
