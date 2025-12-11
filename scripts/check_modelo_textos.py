import psycopg2

conn = psycopg2.connect(
    host='200.144.197.137',
    dbname='smdhc_faf',
    user='faf_fmusp',
    password='w3i2o2m2',
    port=5432
)

cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type, character_maximum_length
    FROM information_schema.columns 
    WHERE table_schema = 'categoricas' 
      AND table_name = 'c_modelo_textos' 
    ORDER BY ordinal_position
""")

print("Estrutura da tabela categoricas.c_modelo_textos:")
print("=" * 60)
for row in cur.fetchall():
    col_name, data_type, max_length = row
    if max_length:
        print(f"{col_name}: {data_type}({max_length})")
    else:
        print(f"{col_name}: {data_type}")

cur.close()
conn.close()
