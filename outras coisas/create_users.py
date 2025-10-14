# create_users.py
import sqlite3
from werkzeug.security import generate_password_hash

DB = "meu_banco.db"

users = [
    ("jeffersonluiz@prefeitura.sp.gov.br", "admin", "Agente Público"),
    ("mmteixeira@prefeitura.sp.gov.br", "maira", "Agente Público"),
]

def normalize_email(email):
    return email.strip().lower()

conn = sqlite3.connect(DB)
c = conn.cursor()

for email, senha, tipo in users:
    email_n = normalize_email(email)
    hashed = generate_password_hash(senha)  # werkzeug generate (pbkdf2:sha256)
    try:
        c.execute("""
            INSERT INTO usuarios (email, senha, tipo_usuario)
            VALUES (?, ?, ?)
        """, (email_n, hashed, tipo))
        print("Inserido:", email_n)
    except sqlite3.IntegrityError as e:
        print("Já existe ou erro:", email_n, e)

conn.commit()
conn.close()
