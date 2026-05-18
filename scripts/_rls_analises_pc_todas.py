"""
RLS - analises_pc (todas as tabelas restantes)
Substitui Acesso_Total_PWA (anon/true) por authenticated_acesso_total (authenticated/true).
conc_banco já foi feita anteriormente — pulada se já estiver correta.
"""
import psycopg2, os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

TABELAS = [
    'checklist_analista',
    'checklist_change_log',
    'checklist_recursos',
    'checklist_termo',
    'conc_analise',
    'conc_banco',              # já feita — script verifica e pula se OK
    'conc_contrapartida',
    'conc_extrato',
    'conc_extrato_inconsistencia_recursos',
    'conc_extrato_notas_fiscais',
    'conc_rendimentos',
    'lista_inconsistencias',
    'lista_inconsistencias_agregadas',
    'lista_inconsistencias_globais',
]

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
    full = f'analises_pc.{tabela}'
    try:
        # Verifica se já tem a policy correta
        cur.execute("""
            SELECT policyname, roles FROM pg_policies
            WHERE schemaname = 'analises_pc' AND tablename = %s
        """, (tabela,))
        policies = {r['policyname']: r['roles'] for r in cur.fetchall()}

        if 'authenticated_acesso_total' in policies and 'Acesso_Total_PWA' not in policies:
            puladas.append(full)
            continue

        cur.execute(
            f'DROP POLICY IF EXISTS "Acesso_Total_PWA" ON {full}'
        )
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
        continue

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

# Verificação final
print("\n=== VERIFICAÇÃO FINAL (postgres/BYPASSRLS) ===")
for tabela in TABELAS:
    cur.execute(f"SELECT COUNT(*) AS n FROM analises_pc.{tabela}")
    n = cur.fetchone()['n']
    print(f"  analises_pc.{tabela}: {n} registros  ✓")

conn.close()
print("\nConcluído.")
