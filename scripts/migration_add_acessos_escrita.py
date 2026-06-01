"""
Migração: adiciona coluna acessos_escrita à tabela gestao_pessoas.usuarios

Executar uma vez:
    python scripts/migration_add_acessos_escrita.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_CONFIG
import psycopg2
import psycopg2.extras

def run():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.execute("""
            ALTER TABLE gestao_pessoas.usuarios
            ADD COLUMN IF NOT EXISTS acessos_escrita TEXT NOT NULL DEFAULT '';
        """)
        conn.commit()
        print("[OK] Coluna acessos_escrita adicionada (ou já existia).")
    except Exception as e:
        conn.rollback()
        print(f"[ERRO] {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    run()
