"""
Script para adicionar coluna numero_parcela na tabela temp_acomp_empenhos
Execute: python scripts/adicionar_coluna_numero_parcela.py
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def adicionar_coluna():
    """Adiciona coluna numero_parcela se não existir"""
    
    # Conexão com banco
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        port=os.getenv('DB_PORT', 5432),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        print("=" * 60)
        print("ADICIONANDO COLUNA numero_parcela")
        print("=" * 60)
        
        # Criar schema se não existir
        print("→ Verificando schema gestao_financeira...")
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS gestao_financeira
        """)
        conn.commit()
        print("✓ Schema gestao_financeira OK")
        
        # Verificar se coluna existe
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'gestao_financeira' 
            AND table_name = 'temp_acomp_empenhos' 
            AND column_name = 'numero_parcela'
        """)
        
        existe = cur.fetchone()
        
        if existe:
            print("✓ Coluna 'numero_parcela' já existe!")
        else:
            print("→ Adicionando coluna 'numero_parcela'...")
            
            cur.execute("""
                ALTER TABLE gestao_financeira.temp_acomp_empenhos 
                ADD COLUMN numero_parcela VARCHAR(10)
            """)
            
            conn.commit()
            print("✓ Coluna 'numero_parcela' adicionada com sucesso!")
        
        # Mostrar estrutura da tabela
        print("\n" + "=" * 60)
        print("ESTRUTURA DA TABELA temp_acomp_empenhos")
        print("=" * 60)
        
        cur.execute("""
            SELECT 
                column_name, 
                data_type, 
                character_maximum_length,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'gestao_financeira' 
            AND table_name = 'temp_acomp_empenhos'
            ORDER BY ordinal_position
        """)
        
        colunas = cur.fetchall()
        
        for col in colunas:
            tipo = col['data_type']
            if col['character_maximum_length']:
                tipo += f"({col['character_maximum_length']})"
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            print(f"  - {col['column_name']:25} {tipo:20} {nullable}")
        
        print("\n✓ Script concluído com sucesso!")
        
    except Exception as e:
        print(f"\n✗ ERRO: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    adicionar_coluna()
