import sys
sys.path.insert(0, '.')

from app import app
with app.app_context():
    from db import get_cursor, get_db
    cur = get_cursor()
    try:
        with open('scripts/add_kanban_columns.sql', 'r', encoding='utf-8') as f:
            sql = f.read()
        
        # Execute each statement separately
        statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]
        
        for i, stmt in enumerate(statements):
            if not stmt:
                continue
            try:
                cur.execute(stmt)
                print(f'[OK] Statement {i+1}: {stmt[:60].replace(chr(10), " ")}...')
            except Exception as e:
                print(f'[ERR] Statement {i+1}: {e}')
                print(f'      SQL: {stmt[:100]}')
        
        get_db().commit()
        print('\nMigration completed successfully')
        
        # Verify
        cur.execute("SELECT alt_status, alt_ordem FROM categoricas.c_alt_status_alteracao ORDER BY alt_ordem")
        rows = cur.fetchall()
        print(f'\n{len(rows)} status inserted:')
        for r in rows:
            print(f'  {r["alt_ordem"]}. {r["alt_status"]}')
        
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'termos_alteracoes'
            AND column_name IN ('alt_prioridade','alt_data_inicio','alt_data_conclusao','alt_oculto','alt_marcadores','termo_sei_doc','data_assinatura')
            ORDER BY column_name
        """)
        cols = cur.fetchall()
        print(f'\nNew columns in termos_alteracoes:')
        for c in cols:
            print(f'  {c["column_name"]} ({c["data_type"]})')
        
        cur.execute("SELECT COUNT(*) as n FROM public.termos_alteracoes WHERE alt_status NOT IN (SELECT alt_status FROM categoricas.c_alt_status_alteracao)")
        bad = cur.fetchone()
        print(f'\nRecords with unrecognized status: {bad["n"]}')
        
    except Exception as e:
        get_db().rollback()
        import traceback
        traceback.print_exc()
    finally:
        cur.close()
