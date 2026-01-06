"""
Script para adicionar a coluna d_usuario (R.F.) na tabela categoricas.c_dac_analistas
Executa de forma segura, verificando se a coluna já existe
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config import DB_CONFIG

def adicionar_coluna_rf_analistas():
    """Adiciona a coluna d_usuario (R.F.) na tabela c_analistas"""
    
    print("=" * 70)
    print("📊 Adicionando coluna d_usuario (R.F.) em categoricas.c_dac_analistas")
    print("=" * 70)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Verificar se a coluna já existe
        print("\n🔍 Verificando se a coluna já existe...")
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'categoricas' 
              AND table_name = 'c_analistas' 
              AND column_name = 'd_usuario'
        """)
        
        if cur.fetchone():
            print("✅ Coluna 'd_usuario' já existe! Nada a fazer.")
            cur.close()
            conn.close()
            return
        
        # Adicionar a coluna
        print("\n⚙️  Adicionando coluna d_usuario (R.F.)...")
        cur.execute("""
            ALTER TABLE categoricas.c_dac_analistas 
            ADD COLUMN d_usuario VARCHAR(20);
        """)
        
        # Adicionar comentário
        cur.execute("""
            COMMENT ON COLUMN categoricas.c_dac_analistas.d_usuario 
            IS 'Registro Funcional (R.F.) do analista';
        """)
        
        conn.commit()
        
        # Verificar criação
        print("\n✓ Coluna criada com sucesso!")
        print("\n📋 Estrutura atualizada da tabela c_analistas:")
        print("-" * 70)
        
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'categoricas' 
              AND table_name = 'c_analistas'
            ORDER BY ordinal_position
        """)
        
        for row in cur.fetchall():
            col_name, data_type, max_len, nullable = row
            tipo = f"{data_type}"
            if max_len:
                tipo += f"({max_len})"
            null_info = "NULL" if nullable == 'YES' else "NOT NULL"
            
            # Destacar a nova coluna
            prefix = "  ✨ " if col_name == 'd_usuario' else "     "
            print(f"{prefix}{col_name:25} {tipo:20} {null_info}")
        
        print("\n" + "=" * 70)
        print("✅ Migração concluída!")
        print("=" * 70)
        print("\n📝 A coluna d_usuario (R.F.) foi adicionada:")
        print("   • Tipo: VARCHAR(20)")
        print("   • Permite NULL (campo opcional)")
        print("   • Já disponível em Listas Suspensas > Analistas")
        print()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"\n❌ Erro ao adicionar coluna: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    try:
        adicionar_coluna_rf_analistas()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação cancelada pelo usuário")
        sys.exit(0)
