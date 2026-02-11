import psycopg2
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

cur.execute("""
    SELECT id, vigencia_inicial, vigencia_final, parcela_status, parcela_status_secundario, 
           valor_previsto, valor_elemento_53_23, valor_elemento_53_24
    FROM gestao_financeira.ultra_liquidacoes 
    WHERE numero_termo = 'TCL/024/2023/SMDHC/SESANA' 
    ORDER BY vigencia_inicial
""")

rows = cur.fetchall()

print('\n=== Parcelas TCL/024/2023/SMDHC/SESANA ===\n')
for r in rows:
    print(f"ID: {r[0]}")
    print(f"  Vigência: {r[1]} a {r[2]}")
    print(f"  Status: '{r[3]}'")
    print(f"  Status Secundário: '{r[4]}'")
    print(f"  Previsto: {r[5]}")
    print(f"  Elem 23: {r[6]}")
    print(f"  Elem 24: {r[7]}")
    print()

conn.close()
