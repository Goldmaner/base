"""
RLS - analises_pc.conc_banco
Testa a substituição de Acesso_Total_PWA (anon/true) por
authenticated_acesso_total (authenticated/true).
"""
import psycopg2, os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    port=os.environ.get('DB_PORT', '5432'),
    database=os.environ.get('DB_DATABASE', 'projeto_parcerias'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', ''),
    sslmode=os.environ.get('DB_SSLMODE', 'prefer'),
)
cur = conn.cursor(cursor_factory=RealDictCursor)

TABLE = 'analises_pc.conc_banco'

# ── Antes ──────────────────────────────────────────────────────────────
cur.execute("""
    SELECT policyname, roles, cmd, qual
    FROM pg_policies
    WHERE schemaname = 'analises_pc' AND tablename = 'conc_banco'
    ORDER BY policyname
""")
print(f"=== POLICIES ANTES em {TABLE} ===")
for r in cur.fetchall():
    print(f"  [{r['policyname']}] roles={r['roles']} cmd={r['cmd']} USING={r['qual']}")

# ── Aplicar mudança ─────────────────────────────────────────────────────
print(f"\nAplicando mudança em {TABLE}...")

cur.execute('DROP POLICY IF EXISTS "Acesso_Total_PWA" ON analises_pc.conc_banco')
print("  DROP POLICY Acesso_Total_PWA → OK")

cur.execute("""
    CREATE POLICY "authenticated_acesso_total"
    ON analises_pc.conc_banco
    FOR ALL
    TO authenticated
    USING (true)
    WITH CHECK (true)
""")
print("  CREATE POLICY authenticated_acesso_total → OK")

conn.commit()
print("  Commit → OK")

# ── Depois ──────────────────────────────────────────────────────────────
cur.execute("""
    SELECT policyname, roles, cmd, qual
    FROM pg_policies
    WHERE schemaname = 'analises_pc' AND tablename = 'conc_banco'
    ORDER BY policyname
""")
print(f"\n=== POLICIES DEPOIS em {TABLE} ===")
for r in cur.fetchall():
    print(f"  [{r['policyname']}] roles={r['roles']} cmd={r['cmd']} USING={r['qual']}")

# ── Verificação: Flask (postgres) ainda lê normalmente ──────────────────
cur.execute("SELECT COUNT(*) AS total FROM analises_pc.conc_banco")
total = cur.fetchone()['total']
print(f"\n=== VERIFICAÇÃO FLASK (postgres/BYPASSRLS) ===")
print(f"  SELECT COUNT(*) em conc_banco = {total}  ✓")

conn.close()
print("\nConcluído.")
