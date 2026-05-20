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

TERMO = 'TCL/001/2017/SMDHC/CPLGBTI'

# 1. Todas as linhas de setembro 2018
cur.execute("""
    SELECT id, indice, data, credito, debito, discriminacao, cat_transacao,
           competencia, origem_destino, cat_avaliacao, mesclado_com
    FROM analises_pc.conc_extrato
    WHERE numero_termo = %s
      AND data >= '2018-09-01' AND data <= '2018-09-30'
    ORDER BY indice, id
""", (TERMO,))

rows = cur.fetchall()
cols = [d[0] for d in cur.description]

print("=== LINHAS SETEMBRO 2018 ===")
header = " | ".join(f"{c:>14}" for c in cols)
print(header)
print("-" * len(header))
for r in rows:
    vals = [(str(v) if v is not None else "") for v in r]
    print(" | ".join(f"{v:>14}" for v in vals))
print(f"\nTotal setembro: {len(rows)} linhas\n")

# 2. Contagem por indice na faixa 1408-1418 - detecta duplicatas
cur.execute("""
    SELECT indice, COUNT(*) as qtd,
           array_agg(id ORDER BY id) as ids,
           array_agg(data::text ORDER BY id) as datas,
           array_agg(debito::text ORDER BY id) as debitos,
           array_agg(discriminacao ORDER BY id) as discriminacoes
    FROM analises_pc.conc_extrato
    WHERE numero_termo = %s
      AND indice BETWEEN 1408 AND 1418
    GROUP BY indice
    ORDER BY indice
""", (TERMO,))

print("=== CONTAGEM POR INDICE (faixa 1408-1418) ===")
for r in cur.fetchall():
    print(f"  indice={r[0]:5d}  qtd={r[1]}  ids={r[2]}")
    print(f"           datas={r[3]}")
    print(f"           debitos={r[4]}")
    print(f"           discr={r[5]}")

# 3. Linhas com mesclado_com em setembro 2018
cur.execute("""
    SELECT id, indice, data, debito, discriminacao, mesclado_com
    FROM analises_pc.conc_extrato
    WHERE numero_termo = %s
      AND mesclado_com IS NOT NULL
      AND data >= '2018-09-01' AND data <= '2018-09-30'
    ORDER BY indice, id
""", (TERMO,))
rows_mesc = cur.fetchall()
print(f"\n=== LINHAS COM MESCLADO_COM (set/2018) - {len(rows_mesc)} linhas ===")
for r in rows_mesc:
    print(f"  id={r[0]:8d}  indice={r[1]:5}  data={r[2]}  debito={r[3]}  discr={r[4]}  mesclado_com={r[5]}")

# 4. Contexto ampliado - 5 linhas antes e depois do bloco 1411-1413
cur.execute("""
    SELECT id, indice, data, credito, debito, discriminacao, cat_transacao, mesclado_com
    FROM analises_pc.conc_extrato
    WHERE numero_termo = %s
      AND indice BETWEEN 1406 AND 1416
    ORDER BY indice, id
""", (TERMO,))
print(f"\n=== CONTEXTO AMPLIADO (indice 1406-1416) ===")
cols2 = [d[0] for d in cur.description]
print(" | ".join(f"{c:>12}" for c in cols2))
print("-" * (15 * len(cols2)))
for r in cur.fetchall():
    vals = [(str(v) if v is not None else "") for v in r]
    print(" | ".join(f"{v:>12}" for v in vals))

cur.close()
conn.close()
