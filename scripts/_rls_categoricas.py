"""
RLS - categoricas (todas as tabelas)
Padrão: authenticated → ALL | anon → bloqueado
Habilita RLS nas tabelas que ainda não têm e aplica authenticated_acesso_total.
"""
import psycopg2, os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

SCHEMA = 'categoricas'

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    port=os.environ.get('DB_PORT', '5432'),
    database=os.environ.get('DB_DATABASE', 'projeto_parcerias'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', ''),
    sslmode=os.environ.get('DB_SSLMODE', 'prefer'),
)
cur = conn.cursor(cursor_factory=RealDictCursor)

cur.execute("""
    SELECT t.tablename, t.rowsecurity,
           array_agg(p.policyname ORDER BY p.policyname)
               FILTER (WHERE p.policyname IS NOT NULL) AS policies
    FROM pg_tables t
    LEFT JOIN pg_policies p
           ON p.schemaname = t.schemaname AND p.tablename = t.tablename
    WHERE t.schemaname = %s
    GROUP BY t.tablename, t.rowsecurity
    ORDER BY t.tablename
""", (SCHEMA,))
tabelas_info = cur.fetchall()

print(f"=== INVENTÁRIO {SCHEMA} ({len(tabelas_info)} tabelas) ===")
for r in tabelas_info:
    print(f"  {r['tablename']} | rls={r['rowsecurity']} | policies={r['policies']}")

ok = []
puladas = []
erros = []

for r in tabelas_info:
    tabela = r['tablename']
    full = f'{SCHEMA}.{tabela}'
    policies = r['policies'] or []

    try:
        if 'authenticated_acesso_total' in policies and 'Acesso_Total_PWA' not in policies:
            puladas.append(full)
            continue

        if not r['rowsecurity']:
            cur.execute(f'ALTER TABLE {full} ENABLE ROW LEVEL SECURITY')

        cur.execute(f'DROP POLICY IF EXISTS "Acesso_Total_PWA" ON {full}')
        cur.execute(f"""
            CREATE POLICY "authenticated_acesso_total"
            ON {full}
            FOR ALL
            TO authenticated
            USING (true)
            WITH CHECK (true)
        """)
        ok.append(full)
    except Exception as e:
        conn.rollback()
        erros.append((full, str(e)))

conn.commit()

print(f"\n=== RESULTADO ===")
print(f"\n✓ Aplicadas ({len(ok)}):")
for t in ok:
    print(f"  {t}")
if puladas:
    print(f"\n— Já corretas / puladas ({len(puladas)}):")
    for t in puladas:
        print(f"  {t}")
if erros:
    print(f"\n✗ Erros ({len(erros)}):")
    for t, e in erros:
        print(f"  {t}: {e}")

print(f"\n=== VERIFICAÇÃO (postgres/BYPASSRLS) ===")
for r in tabelas_info:
    cur.execute(f"SELECT COUNT(*) AS n FROM {SCHEMA}.{r['tablename']}")
    print(f"  {SCHEMA}.{r['tablename']}: {cur.fetchone()['n']} registros  ✓")

conn.close()
print("\nConcluído.")
