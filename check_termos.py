import psycopg2
from config import DB_CONFIG

termos = [
    'TCV/002/2008/SMPP/CPLGBT',
    'TFM/087/2025/SMDHC/CPPI',
    'TFM/089/2025/SMDHC/CPM',
    'TFM/090/2025/SMDHC/FUMCAD'
]

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

for termo in termos:
    cur.execute("SELECT numero_termo FROM Parcerias WHERE numero_termo = %s", (termo,))
    result = cur.fetchone()
    if result:
        print(f"✗ {termo} - JÁ EXISTE")
    else:
        print(f"✓ {termo} - NÃO EXISTE (pode importar!)")

conn.close()
