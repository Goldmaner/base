"""Executa o script de migração _migration_objetivos.sql diretamente."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DB_CONFIG
import psycopg2

sql_path = os.path.join(os.path.dirname(__file__), '_migration_objetivos.sql')
with open(sql_path, encoding='utf-8') as f:
    sql = f.read()

# psycopg2 executa BEGIN/COMMIT do script; desativa autocommit
conn = psycopg2.connect(**{k: v for k, v in DB_CONFIG.items()
                           if k in ('host','port','database','user','password','sslmode')})
conn.autocommit = False

try:
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    print("Migração concluída com sucesso!")
except Exception as e:
    conn.rollback()
    print(f"ERRO — rollback executado: {e}")
    sys.exit(1)
finally:
    conn.close()
