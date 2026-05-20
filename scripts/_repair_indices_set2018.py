"""
Reparo de índices para TCL/001/2017/SMDHC/CPLGBTI.

O que aconteceu:
  - 2 linhas foram inseridas acima do índice 1412 (ids 15380 e 15381)
  - recalcularIndices() atualizou os índices em memória corretamente
  - Mas o save-sujo NÃO salvou as linhas antigas (não dirty)
  - Resultado: ids 2048, 2049 e todos os subsequentes ficaram com
    índices defasados no banco (1 a menos do correto)

Correção:
  - Todos os registros com id < 15380 E indice >= 1412 devem ter
    indice += 2 (deslocamento causado pela inserção de 2 linhas)
"""

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

# 1. Verificar quais linhas serão afetadas (simulação antes de alterar)
cur.execute("""
    SELECT COUNT(*), MIN(indice), MAX(indice), MIN(id), MAX(id)
    FROM analises_pc.conc_extrato
    WHERE numero_termo = %s
      AND id < 15380
      AND indice >= 1412
""", (TERMO,))
row = cur.fetchone()
print("=== SIMULAÇÃO: linhas afetadas ===")
print(f"  Qtd: {row[0]}  indice_min={row[1]}  indice_max={row[2]}  id_min={row[3]}  id_max={row[4]}")

# 2. Confirmar as primeiras 10 afetadas para checar
cur.execute("""
    SELECT id, indice, data, debito, credito, discriminacao, cat_transacao
    FROM analises_pc.conc_extrato
    WHERE numero_termo = %s
      AND id < 15380
      AND indice >= 1412
    ORDER BY indice, id
    LIMIT 10
""", (TERMO,))
print("\nPrimeiras 10 linhas a corrigir:")
for r in cur.fetchall():
    print(f"  id={r[0]:8d}  indice={r[1]:5d} → {r[1]+2:5d}  data={r[2]}  debito={r[3]}  credito={r[4]}  discr={r[5]}  cat={r[6]}")

resposta = input("\nConfirma o UPDATE (shift +2 nesses registros)? [s/N] ").strip().lower()
if resposta != 's':
    print("Cancelado.")
    cur.close(); conn.close()
    exit()

# 3. Executar o UPDATE (PostgreSQL não suporta ORDER BY em UPDATE,
#    mas como não há constraint unique em (numero_termo, indice), é seguro)
cur.execute("""
    UPDATE analises_pc.conc_extrato
    SET indice = indice + 2
    WHERE numero_termo = %s
      AND id < 15380
      AND indice >= 1412
""", (TERMO,))
affected = cur.rowcount
conn.commit()
print(f"\nAtualizado: {affected} linha(s). Commit realizado.")

# 4. Verificar estado final ao redor dos índices 1411-1416
cur.execute("""
    SELECT id, indice, data, debito, credito, discriminacao, cat_transacao
    FROM analises_pc.conc_extrato
    WHERE numero_termo = %s
      AND indice BETWEEN 1410 AND 1420
    ORDER BY indice, id
""", (TERMO,))
print("\n=== ESTADO FINAL (índices 1410-1420) ===")
for r in cur.fetchall():
    print(f"  id={r[0]:8d}  indice={r[1]:5d}  data={r[2]}  debito={r[3]}  credito={r[4]}  discr={r[5]}  cat={r[6]}")

cur.close()
conn.close()
