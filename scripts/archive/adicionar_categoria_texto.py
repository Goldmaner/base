"""
Script para adicionar coluna categoria_texto em categoricas.c_geral_legislacao
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import get_cursor, get_db
from app import app

def adicionar_coluna_categoria_texto():
    """Adiciona coluna categoria_texto se não existir"""
    try:
        cur = get_cursor()
        db = get_db()
        
        print("🔧 Adicionando coluna categoria_texto em categoricas.c_geral_legislacao...")
        
        # Adicionar coluna categoria_texto
        cur.execute("""
            ALTER TABLE categoricas.c_geral_legislacao 
            ADD COLUMN IF NOT EXISTS categoria_texto VARCHAR(255)
        """)
        
        # Criar índice para melhorar performance
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_c_geral_legislacao_categoria 
            ON categoricas.c_geral_legislacao(categoria_texto)
        """)
        
        db.commit()
        
        print("✅ Coluna categoria_texto adicionada com sucesso!")
        print("✅ Índice criado com sucesso!")
        
        # Verificar estrutura
        cur.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns 
            WHERE table_schema = 'categoricas' 
              AND table_name = 'c_geral_legislacao' 
            ORDER BY ordinal_position
        """)
        
        print("\n📋 Estrutura atual da tabela:")
        print("=" * 60)
        for row in cur.fetchall():
            col_name, data_type, max_length = row
            if max_length:
                print(f"  {col_name}: {data_type}({max_length})")
            else:
                print(f"  {col_name}: {data_type}")
        
        cur.close()
        
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        try:
            get_db().rollback()
        except:
            pass

if __name__ == '__main__':
    with app.app_context():
        adicionar_coluna_categoria_texto()
