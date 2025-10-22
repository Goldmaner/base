"""
Script para verificar e limpar duplicatas na tabela Parcerias_Despesas
Execute este script para ver se há dados salvos em múltiplos aditivos
"""

import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Conectar ao banco LOCAL
conn = psycopg2.connect(
    host=os.getenv('DB_LOCAL_HOST'),
    database=os.getenv('DB_LOCAL_NAME'),
    user=os.getenv('DB_LOCAL_USER'),
    password=os.getenv('DB_LOCAL_PASSWORD'),
    port=os.getenv('DB_LOCAL_PORT', 5432)
)

cur = conn.cursor()

print("=" * 80)
print("VERIFICAÇÃO DE DESPESAS POR ADITIVO")
print("=" * 80)

# Verificar termo específico
termo = "TFM/016/2018/SMDHC/FUMCAD"

cur.execute("""
    SELECT 
        COALESCE(aditivo, 0) as aditivo,
        COUNT(*) as registros,
        SUM(valor) as total
    FROM Parcerias_Despesas
    WHERE numero_termo = %s
    GROUP BY COALESCE(aditivo, 0)
    ORDER BY aditivo
""", (termo,))

resultados = cur.fetchall()

print(f"\nTermo: {termo}")
print("-" * 80)

total_geral = 0
for aditivo, registros, total in resultados:
    print(f"Aditivo {aditivo}: {registros} registros | Total: R$ {total:,.2f}")
    total_geral += total

print("-" * 80)
print(f"TOTAL GERAL (todos aditivos): R$ {total_geral:,.2f}")

# Buscar total previsto
cur.execute("SELECT total_previsto FROM Parcerias WHERE numero_termo = %s", (termo,))
row = cur.fetchone()
total_previsto = row[0] if row else 0

print(f"Total Previsto (tabela Parcerias): R$ {total_previsto:,.2f}")
print(f"Diferença: R$ {abs(total_geral - total_previsto):,.2f}")

print("\n" + "=" * 80)
print("AÇÕES SUGERIDAS:")
print("=" * 80)

if len(resultados) > 1:
    print("⚠️  ATENÇÃO: Há dados em múltiplos aditivos!")
    print("\nPara limpar apenas um aditivo específico, use:")
    print(f"  DELETE FROM Parcerias_Despesas WHERE numero_termo = '{termo}' AND COALESCE(aditivo, 0) = X;")
    print("\nPara limpar TUDO e começar do zero:")
    print(f"  DELETE FROM Parcerias_Despesas WHERE numero_termo = '{termo}';")
    print("\nOu use o botão 'Limpar Tudo' na interface!")
else:
    print("✅ Há dados em apenas 1 aditivo. Tudo OK!")

# Fechar conexão
cur.close()
conn.close()

print("\n" + "=" * 80)
