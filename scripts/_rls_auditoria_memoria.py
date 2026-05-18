"""
RLS - auditoria_memoria (todas as tabelas)
Padrão: authenticated → ALL | anon → bloqueado
"""
import psycopg2, os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

SCHEMA = 'auditoria_memoria'
TABELAS = ['auditoria_enc_pagamento']

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    port=os.environ.get('DB_PORT', '5432'),
    database=os.environ.get('DB_DATABASE', 'projeto_parcerias'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', ''),
    sslmode=os.environ.get('DB_SSLMODE', 'prefer'),
)
cur = conn.cursor(cursor_factory=RealDictCursor)

ok = []
puladas = []
erros = []

for tabela in TABELAS:
    full = f'{SCHEMA}.{tabela}'
    try:
        cur.execute("""
            SELECT policyname FROM pg_policies
            WHERE schemaname = %s AND tablename = %s
        """, (SCHEMA, tabela))
        policies = [r['policyname'] for r in cur.fetchall()]

        if 'authenticated_acesso_total' in policies and 'Acesso_Total_PWA' not in policies:
            puladas.append(full)
            continue

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

print("=== RESULTADO ===")
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
for tabela in TABELAS:
    cur.execute(f"SELECT COUNT(*) AS n FROM {SCHEMA}.{tabela}")
    print(f"  {SCHEMA}.{tabela}: {cur.fetchone()['n']} registros  ✓")

conn.close()
print("\nConcluído.")
