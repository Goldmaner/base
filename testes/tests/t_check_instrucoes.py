'''import sqlite3

def listar_instrucoes():
    try:
        conn = sqlite3.connect('meu_banco.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Configurar a conexão para usar UTF-8
        cursor.execute("PRAGMA encoding = 'UTF-8'")
        cursor.execute("SELECT * FROM Instrucoes")
        instrucoes = cursor.fetchall()
        
        print("\nInstruções salvas:".encode('utf-8').decode('utf-8'))
        print("-" * 50)
        for instrucao in instrucoes:
            print(f"ID: {instrucao['id']}")
            print(f"Título: {instrucao['titulo']}".encode('utf-8').decode('utf-8'))
            print(f"Categoria: {instrucao['categoria']}".encode('utf-8').decode('utf-8'))
            print(f"Texto: {instrucao['texto']}".encode('utf-8').decode('utf-8'))
            print(f"Data Criação: {instrucao['data_criacao']}")
            print("-" * 50)
            
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Erro SQLite: {e}")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    # Configurar a codificação do terminal
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    listar_instrucoes()'''

import sqlite3
from pathlib import Path
p = Path(r"c:\Users\d843702\OneDrive - rede.sp\Área de Trabalho\FAF\FAF\meu_banco.db")   # substitua pelo resolved do script
print("Arquivo:", p, "existe?", p.exists(), "tamanho:", p.stat().st_size if p.exists() else "N/A")
con = sqlite3.connect(p)
cur = con.cursor()
cur.execute("SELECT COUNT(*) FROM Parcerias")
print("COUNT(*) =", cur.fetchone()[0])
cur.execute("SELECT numero_termo, osc FROM Parcerias LIMIT 5")
for r in cur.fetchall():
    print(r)
con.close()
