"""
Script para criar índices de performance em numero_termo
Melhora a velocidade de autocomplete e buscas
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_CONFIG

def criar_indices():
    """Cria índices para melhorar performance de buscas"""
    
    print("=" * 60)
    print("CRIANDO ÍNDICES DE PERFORMANCE")
    print("=" * 60)
    
    # Conectar diretamente ao banco
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Ler o arquivo SQL
        sql_file = os.path.join(os.path.dirname(__file__), 'create_index_numero_termo.sql')
        
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        print("\n📊 Executando comandos SQL...")
        
        # Executar cada comando separadamente
        comandos = [cmd.strip() for cmd in sql.split(';') if cmd.strip() and not cmd.strip().startswith('--')]
        
        for i, comando in enumerate(comandos, 1):
            if comando:
                print(f"\n[{i}/{len(comandos)}] Executando: {comando[:80]}...")
                cur.execute(comando)
                print(f"✅ Comando {i} executado com sucesso!")
        
        conn.commit()
        print("\n" + "=" * 60)
        print("✅ ÍNDICES CRIADOS COM SUCESSO!")
        print("=" * 60)
        
        # Verificar índices criados
        print("\n📋 Verificando índices criados:")
        cur.execute("""
            SELECT 
                indexname, 
                tablename,
                indexdef
            FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND (indexname LIKE '%numero_termo%' OR indexname LIKE 'idx_%')
            AND (tablename = 'parcerias' OR tablename = 'termos_rescisao')
            ORDER BY tablename, indexname
        """)
        
        indices = cur.fetchall()
        for idx in indices:
            print(f"\n✓ {idx['indexname']}")
            print(f"  Tabela: {idx['tablename']}")
            print(f"  Definição: {idx['indexdef']}")
        
        print(f"\n📊 Total de índices criados: {len(indices)}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERRO ao criar índices: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cur.close()
        conn.close()
    
    return True

if __name__ == '__main__':
    sucesso = criar_indices()
    sys.exit(0 if sucesso else 1)
