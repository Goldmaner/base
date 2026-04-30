"""Executa a migration: move as 3 tabelas de public para calendario."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import psycopg2, psycopg2.extras
from config import DB_CONFIG

_cfg = {k: v for k, v in DB_CONFIG.items()
        if k not in ('keepalives', 'keepalives_idle', 'keepalives_interval',
                     'keepalives_count', 'connect_timeout')}
conn = psycopg2.connect(**_cfg, cursor_factory=psycopg2.extras.RealDictCursor)
conn.autocommit = False
cur = conn.cursor()

try:
    # 1. Criar schema
    cur.execute("CREATE SCHEMA IF NOT EXISTS calendario")
    print("Schema 'calendario' pronto.")

    # 2. Mover tabelas
    # Responsaveis primeiro (tem FK para datas_eventos, ambas vão para mesmo destino)
    cur.execute("ALTER TABLE public.datas_eventos_responsaveis SET SCHEMA calendario")
    print("  public.datas_eventos_responsaveis -> calendario.datas_eventos_responsaveis")

    cur.execute("ALTER TABLE public.datas_eventos SET SCHEMA calendario")
    print("  public.datas_eventos -> calendario.datas_eventos")

    cur.execute("ALTER TABLE public.datas_importantes SET SCHEMA calendario")
    print("  public.datas_importantes -> calendario.datas_importantes")

    # 3. Verificar resultado
    cur.execute("""
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE tablename IN ('datas_importantes', 'datas_eventos', 'datas_eventos_responsaveis')
        ORDER BY tablename
    """)
    rows = cur.fetchall()
    print("\nVerificacao pos-migration:")
    for r in rows:
        cur.execute(f"SELECT COUNT(*) AS n FROM {r['schemaname']}.{r['tablename']}")
        n = cur.fetchone()['n']
        print(f"  {r['schemaname']}.{r['tablename']}: {n} linhas")

    # 4. Verificar FK
    cur.execute("""
        SELECT conname, contype
        FROM pg_constraint
        WHERE conname LIKE '%datas_eventos%'
    """)
    fks = cur.fetchall()
    print("\nConstraints preservadas:")
    for fk in fks:
        print(f"  {fk['conname']} ({fk['contype']})")

    conn.commit()
    print("\nMigration concluida com sucesso!")

except Exception as e:
    conn.rollback()
    print(f"ERRO — rollback executado: {e}")
    raise
finally:
    cur.close()
    conn.close()
