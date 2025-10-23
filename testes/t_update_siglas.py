import psycopg2
from psycopg2.extras import RealDictCursor
import sys
sys.path.insert(0, '..')
from config import DB_CONFIG

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=RealDictCursor)

# Verificar se coluna sigla existe
print("=== Verificando estrutura da tabela c_tipo_contrato ===")
cur.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'c_tipo_contrato'
    ORDER BY ordinal_position
""")
colunas = cur.fetchall()
print("Colunas existentes:")
for col in colunas:
    print(f"  - {col['column_name']}: {col['data_type']}")

tem_sigla = any(col['column_name'] == 'sigla' for col in colunas)

if not tem_sigla:
    print("\n❌ Coluna 'sigla' não existe. Adicionando...")
    cur.execute("ALTER TABLE c_tipo_contrato ADD COLUMN sigla VARCHAR(10)")
    conn.commit()
    print("✅ Coluna 'sigla' adicionada com sucesso!")
else:
    print("\n✅ Coluna 'sigla' já existe.")

# Verificar dados atuais
print("\n=== Dados atuais da tabela ===")
cur.execute("SELECT * FROM categoricas.c_tipo_contrato ORDER BY id")
rows = cur.fetchall()
for row in rows:
    print(f"ID: {row['id']}, Informação: {row['informacao']}, Sigla: {row.get('sigla', 'N/A')}")

# Atualizar siglas baseado na imagem fornecida
print("\n=== Atualizando siglas ===")
mapeamento = {
    'Acordo de Cooperação': 'ACP',
    'Colaboração': 'TCL',
    'Convênio': 'TCV',
    'Convênio de Cooperação': 'TCC',
    'Fomento': 'TFM',
    'Termo de Cooperação': 'TCP'
}

for informacao, sigla in mapeamento.items():
    cur.execute("""
        UPDATE categoricas.c_tipo_contrato 
        SET sigla = %s 
        WHERE informacao = %s
    """, (sigla, informacao))
    if cur.rowcount > 0:
        print(f"  ✅ {informacao} -> {sigla}")
    else:
        print(f"  ⚠️ '{informacao}' não encontrado na tabela")

conn.commit()

# Verificar resultado final
print("\n=== Dados finais da tabela ===")
cur.execute("SELECT * FROM categoricas.c_tipo_contrato ORDER BY sigla")
rows = cur.fetchall()
for row in rows:
    print(f"Sigla: {row.get('sigla', 'N/A'):5s} -> {row['informacao']}")

print("\n✅ Atualização concluída!")

cur.close()
conn.close()
