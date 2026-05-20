import os
from dotenv import load_dotenv
load_dotenv()
import psycopg2

conn = psycopg2.connect(
    host=os.environ['DB_HOST'],
    port=os.environ.get('DB_PORT', '5432'),
    database=os.environ['DB_DATABASE'],
    user=os.environ['DB_USER'],
    password=os.environ['DB_PASSWORD'],
    sslmode=os.environ.get('DB_SSLMODE', 'require')
)
cur = conn.cursor()
cur.execute(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema='analises_pc' AND table_name='conc_extrato' "
    "ORDER BY ordinal_position"
)
print([r[0] for r in cur.fetchall()])
cur.close()
conn.close()
