"""
Passo 0 - Popula auth_user_id em gestao_pessoas.usuarios:
  - id = 1 (admin)    → ffdc0ca5-3e9d-4a97-abc5-a0f08cb42cfb
  - demais (usuarios) → 8493b623-7de1-47a5-99c0-2284da326e51
"""
import psycopg2, os
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

ADMIN_UID   = 'ffdc0ca5-3e9d-4a97-abc5-a0f08cb42cfb'
USERS_UID   = '8493b623-7de1-47a5-99c0-2284da326e51'

conn = psycopg2.connect(
    host=os.environ.get('DB_HOST', 'localhost'),
    port=os.environ.get('DB_PORT', '5432'),
    database=os.environ.get('DB_DATABASE', 'projeto_parcerias'),
    user=os.environ.get('DB_USER', 'postgres'),
    password=os.environ.get('DB_PASSWORD', ''),
    sslmode=os.environ.get('DB_SSLMODE', 'prefer'),
)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Admin
cur.execute(
    "UPDATE gestao_pessoas.usuarios SET auth_user_id = %s WHERE id = 1",
    (ADMIN_UID,)
)
print(f"Admin (id=1): {cur.rowcount} linha(s) atualizada(s) → {ADMIN_UID}")

# Demais usuários
cur.execute(
    "UPDATE gestao_pessoas.usuarios SET auth_user_id = %s WHERE id != 1",
    (USERS_UID,)
)
print(f"Usuários (id != 1): {cur.rowcount} linha(s) atualizada(s) → {USERS_UID}")

conn.commit()
print("\n✓ Commit realizado.")

# Confirmação
cur.execute("SELECT id, email, auth_user_id FROM gestao_pessoas.usuarios ORDER BY id")
rows = cur.fetchall()
print("\n=== RESULTADO FINAL ===")
for r in rows:
    tag = "ADMIN  " if str(r['auth_user_id']) == ADMIN_UID else "USUARIO"
    print(f"  [{tag}] id={r['id']:>2}  {r['email']}")

conn.close()
