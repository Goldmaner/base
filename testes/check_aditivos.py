import psycopg2
from psycopg2.extras import RealDictCursor
import sys
sys.path.insert(0, '..')
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Verificar estrutura da tabela parcerias_despesas
print("=== Estrutura da tabela Parcerias_Despesas ===")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'parcerias_despesas'
    ORDER BY ordinal_position
""")
colunas = cur.fetchall()
for col in colunas:
    print(f"  - {col['column_name']}: {col['data_type']}")

# Verificar dados de exemplo
print("\n=== Exemplo de dados (primeiras 10 linhas) ===")
cur.execute("SELECT * FROM Parcerias_Despesas LIMIT 10")
rows = cur.fetchall()
if rows:
    print("Colunas:", rows[0].keys())
    for row in rows[:3]:
        print(f"Termo: {row['numero_termo']}, Valor: {row['valor']}, Aditivo: {row.get('aditivo', 'N/A')}")

# Verificar aditivos disponíveis para um termo específico
print("\n=== Aditivos para TFM/072/2022/SMDHC/CPM ===")
cur.execute("""
    SELECT DISTINCT aditivo 
    FROM Parcerias_Despesas 
    WHERE numero_termo = 'TFM/072/2022/SMDHC/CPM'
    ORDER BY aditivo
""")
aditivos = cur.fetchall()
for ad in aditivos:
    print(f"  Aditivo: {ad['aditivo']}")

# Testar soma total por termo e aditivo
print("\n=== Total por termo e aditivo ===")
cur.execute("""
    SELECT 
        numero_termo, 
        aditivo, 
        SUM(valor) as total,
        COUNT(*) as qtd_linhas
    FROM Parcerias_Despesas 
    WHERE numero_termo = 'TFM/072/2022/SMDHC/CPM'
    GROUP BY numero_termo, aditivo
    ORDER BY aditivo
""")
totais = cur.fetchall()
for t in totais:
    print(f"  Termo: {t['numero_termo']}, Aditivo: {t['aditivo']}, Total: R$ {t['total']:,.2f}, Linhas: {t['qtd_linhas']}")

cur.close()
conn.close()
