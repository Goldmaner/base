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
    
    print("Testando insercao com termo existente...")
    
    # Buscar um termo que existe
    cur.execute("SELECT numero_termo FROM parcerias LIMIT 1;")
    termo_existente = cur.fetchone()['numero_termo']
    print(f"Usando termo existente: {termo_existente}")
    
    # Testar inserção com termo válido
    test_data = {
        'numero_termo': termo_existente,
        'rubrica': 'Teste Rubrica',
        'quantidade': 1,
        'categoria_despesa': 'Teste Categoria',
        'valor': 100.50,
        'mes': 12  # Usar mês 12 para não conflitar
    }
    
    cur.execute("""
        INSERT INTO Parcerias_Despesas 
        (numero_termo, rubrica, quantidade, categoria_despesa, valor, mes)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (
        test_data['numero_termo'],
        test_data['rubrica'],
        test_data['quantidade'], 
        test_data['categoria_despesa'],
        test_data['valor'],
        test_data['mes']
    ))
    
    new_id = cur.fetchone()['id']
    print(f"Registro inserido com sucesso! ID: {new_id}")
    
    # Verificar o registro inserido
    cur.execute("SELECT * FROM parcerias_despesas WHERE id = %s", (new_id,))
    registro = cur.fetchone()
    print(f"Registro encontrado: {dict(registro)}")
    
    # Limpar teste (deletar o registro)
    cur.execute("DELETE FROM parcerias_despesas WHERE id = %s", (new_id,))
    print("Registro de teste removido")
    
    conn.commit()
    cur.close()
    conn.close()
    
    print("Teste de insercao concluido com sucesso!")
    
except Exception as e:
    print(f"Erro: {e}")
    if 'conn' in locals():
        conn.rollback()