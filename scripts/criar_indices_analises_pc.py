"""
Script para criar índices de performance no schema analises_pc
Executar após a criação das tabelas do módulo
"""

import sys
import os

# Adicionar o diretório raiz ao path para importar db.py
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_db_connection

def criar_indices():
    """Cria os índices de performance para o schema analises_pc"""
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        print("📊 Criando índices para analises_pc...")
        
        # Ler arquivo SQL
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'criar_indices_analises_pc.sql'
        )
        
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Executar script
        cur.execute(sql_script)
        conn.commit()
        
        # Verificar índices criados
        cur.execute("""
            SELECT 
                tablename,
                indexname
            FROM pg_indexes
            WHERE schemaname = 'analises_pc'
            ORDER BY tablename, indexname
        """)
        
        indices = cur.fetchall()
        
        print("\n✓ Índices criados com sucesso!\n")
        print("Índices encontrados:")
        print("-" * 60)
        
        tabela_atual = None
        for tabela, indice in indices:
            if tabela != tabela_atual:
                print(f"\n📋 Tabela: {tabela}")
                tabela_atual = tabela
            print(f"   └─ {indice}")
        
        print("\n" + "-" * 60)
        print(f"Total: {len(indices)} índices")
        
        cur.close()
        conn.close()
        
        print("\n✓ Script executado com sucesso!")
        
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"\n❌ Erro ao criar índices: {e}")
        sys.exit(1)

if __name__ == '__main__':
    criar_indices()
