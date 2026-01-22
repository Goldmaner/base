import psycopg2

conn = psycopg2.connect(
    dbname='postgres',
    user='postgres',
    password='postgres',
    host='localhost'
)
cur = conn.cursor()

cur.execute("""
    SELECT column_name, data_type, is_nullable 
    FROM information_schema.columns 
    WHERE table_schema = 'gestao_financeira' 
    AND table_name = 'back_empenhos' 
    ORDER BY ordinal_position
""")

cols = cur.fetchall()
print("\n=== ÚLTIMAS 10 COLUNAS ===")
for col in cols[-10:]:
    print(f"{col[0]:30} | {col[1]:20} | Nullable: {col[2]}")

cur.close()
conn.close()
