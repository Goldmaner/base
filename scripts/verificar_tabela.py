import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from db import get_db, get_cursor

with app.app_context():
    cur = get_cursor()
    
    # Verificar estrutura da tabela
    cur.execute("""
        SELECT column_name, data_type, is_nullable 
        FROM information_schema.columns 
        WHERE table_schema = 'categoricas' 
        AND table_name = 'c_modelo_textos' 
        ORDER BY ordinal_position
    """)
    
    print("📋 Estrutura da tabela categoricas.c_modelo_textos:")
    print("-" * 60)
    cols = cur.fetchall()
    for col in cols:
        print(f"{col['column_name']:20} {col['data_type']:20} nullable={col['is_nullable']}")
    
    # Verificar constraints
    cur.execute("""
        SELECT constraint_name, constraint_type 
        FROM information_schema.table_constraints 
        WHERE table_schema = 'categoricas' 
        AND table_name = 'c_modelo_textos'
    """)
    
    print("\n🔒 Constraints:")
    print("-" * 60)
    consts = cur.fetchall()
    for const in consts:
        print(f"{const['constraint_name']:40} {const['constraint_type']}")
