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
    
    # Verificar se a coluna id tem default (sequencia)
    cur.execute("""
        SELECT column_default 
        FROM information_schema.columns 
        WHERE table_name = 'parcerias_despesas' AND column_name = 'id';
    """)
    default_val = cur.fetchone()
    print(f"Valor default para coluna id: {default_val['column_default'] if default_val else 'Nenhum'}")
    
    # Verificar sequências relacionadas
    cur.execute("""
        SELECT sequence_name 
        FROM information_schema.sequences 
        WHERE sequence_name LIKE '%parcerias_despesas%';
    """)
    sequences = cur.fetchall()
    print(f"Sequencias relacionadas: {[seq['sequence_name'] for seq in sequences]}")
    
    # Verificar o maior ID atual
    cur.execute("SELECT MAX(id) as max_id FROM parcerias_despesas;")
    max_id = cur.fetchone()
    print(f"Maior ID atual: {max_id['max_id']}")
    
    # Se existir uma sequencia, verificar o próximo valor
    if sequences:
        seq_name = sequences[0]['sequence_name']
        cur.execute(f"SELECT nextval('{seq_name}') as next_val;")
        next_val = cur.fetchone()
        print(f"Proximo valor da sequencia: {next_val['next_val']}")
        
        # Resetar a sequencia para o valor correto
        cur.execute(f"SELECT setval('{seq_name}', {max_id['max_id']}, true);")
        conn.commit()
        print(f"Sequencia resetada para: {max_id['max_id']}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"Erro: {e}")