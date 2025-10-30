import sqlite3

def check_database():
    try:
        # Conectar ao banco de dados
        conn = sqlite3.connect('meu_banco.db')
        cursor = conn.cursor()
        
        # Verificar se a tabela existe
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='Instrucoes';
        """)
        
        if cursor.fetchone() is None:
            # Criar a tabela se não existir
            cursor.execute("""
            CREATE TABLE Instrucoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                texto TEXT NOT NULL,
                data_criacao TEXT DEFAULT (datetime('now','localtime')),
                categoria TEXT
            )
            """)
            conn.commit()
            print("Tabela Instrucoes criada com sucesso!")
        else:
            print("Tabela Instrucoes já existe!")
            
            # Mostrar estrutura da tabela
            cursor.execute("PRAGMA table_info(Instrucoes)")
            columns = cursor.fetchall()
            print("\nEstrutura da tabela:")
            for col in columns:
                print(f"Coluna: {col[1]}, Tipo: {col[2]}, NotNull: {col[3]}")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Erro SQLite: {e}")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    check_database()