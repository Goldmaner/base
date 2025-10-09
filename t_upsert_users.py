# upsert_users.py
import sqlite3
from werkzeug.security import generate_password_hash
from pathlib import Path

# coloque aqui o caminho exato do seu DB (troque se for outro)
DB = r"C:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF\meu_banco.db"

users = [
    ("jeffersonluiz@prefeitura.sp.gov.br", "admin", "Agente Público"),
    ("mmteixeira@prefeitura.sp.gov.br", "maira", "OSC"),
]

def normalize(email: str) -> str:
    return email.strip().lower()

p = Path(DB)
if not p.exists():
    print("Arquivo DB não encontrado em:", DB)
    raise SystemExit(1)

conn = sqlite3.connect(DB)
c = conn.cursor()

for email, senha, tipo in users:
    email_n = normalize(email)
    hashed = generate_password_hash(senha)

    # Tenta atualizar; se nenhuma linha atualizada, insere
    c.execute("""
        UPDATE usuarios
        SET senha = ?, tipo_usuario = ?
        WHERE lower(email) = ?
    """, (hashed, tipo, email_n))
    if c.rowcount == 0:
        try:
            c.execute("""
                INSERT INTO usuarios (email, senha, tipo_usuario)
                VALUES (?, ?, ?)
            """, (email_n, hashed, tipo))
            print("Inserido:", email_n)
        except sqlite3.IntegrityError as e:
            print("Falha ao inserir (unique?):", email_n, e)
    else:
        print("Atualizado senha/tipo para:", email_n)

conn.commit()
conn.close()
print("Pronto.")
