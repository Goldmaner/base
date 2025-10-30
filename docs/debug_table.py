import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'projeto_parcerias',
    'user': 'postgres',
    'password': 'Coração01'
}

try:
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    print("Investigando estrutura da tabela Parcerias_Despesas:")
    
    # Verificar estrutura da tabela
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'parcerias_despesas' 
        ORDER BY ordinal_position;
    """)
    
    columns = cur.fetchall()
    print("\nColunas da tabela:")
    for col in columns:
        print(f"  - {col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']})")
    
    # Verificar chave primária
    cur.execute("""
        SELECT a.attname
        FROM pg_index i
        JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
        WHERE i.indrelid = 'parcerias_despesas'::regclass AND i.indisprimary;
    """)
    
    pk_columns = cur.fetchall()
    print(f"\nChave primaria: {[col['attname'] for col in pk_columns]}")
    
    # Ver alguns registros existentes
    cur.execute("SELECT * FROM parcerias_despesas LIMIT 5;")
    registros = cur.fetchall()
    print(f"\nPrimeiros 5 registros:")
    for i, reg in enumerate(registros, 1):
        print(f"  {i}. {dict(reg)}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Erro: {e}")