"""
Script para criar a tabela de auditoria do módulo analises_pc
Executa o SQL de criação da tabela checklist_change_log
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config import DB_CONFIG

def criar_tabela_auditoria():
    """Cria a tabela de auditoria e seus índices"""
    
    print("=" * 70)
    print("📊 Criando Tabela de Auditoria - analises_pc.checklist_change_log")
    print("=" * 70)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # Ler arquivo SQL
        script_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            'create_audit_log.sql'
        )
        
        print(f"\n📄 Lendo script: {script_path}")
        
        with open(script_path, 'r', encoding='utf-8') as f:
            sql_script = f.read()
        
        # Executar script
        print("\n⚙️  Executando SQL...")
        cur.execute(sql_script)
        conn.commit()
        
        # Verificar criação
        print("\n✓ Tabela criada com sucesso!")
        print("\n📋 Estrutura da tabela:")
        print("-" * 70)
        
        cur.execute("""
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'analises_pc' 
              AND table_name = 'checklist_change_log'
            ORDER BY ordinal_position
        """)
        
        for row in cur.fetchall():
            col_name, data_type, max_len, nullable = row
            tipo = f"{data_type}"
            if max_len:
                tipo += f"({max_len})"
            null_info = "NULL" if nullable == 'YES' else "NOT NULL"
            print(f"  • {col_name:25} {tipo:20} {null_info}")
        
        # Verificar índices
        print("\n📊 Índices criados:")
        print("-" * 70)
        
        cur.execute("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'analises_pc'
              AND tablename = 'checklist_change_log'
            ORDER BY indexname
        """)
        
        indices = cur.fetchall()
        for idx_name, idx_def in indices:
            print(f"  ✓ {idx_name}")
        
        print("\n" + "=" * 70)
        print(f"✅ Auditoria configurada! Total de {len(indices)} índices criados.")
        print("=" * 70)
        
        print("\n📝 Próximos passos:")
        print("   1. A auditoria está ATIVA por padrão")
        print("   2. Para desabilitar: edite audit_log.py → AUDIT_ENABLED = False")
        print("   3. Todas as alterações nos checklists serão registradas")
        print("   4. Use /analises_pc/api/historico_auditoria para consultar logs")
        print()
        
        cur.close()
        conn.close()
        
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"\n❌ Erro ao criar tabela: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    try:
        criar_tabela_auditoria()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação cancelada pelo usuário")
        sys.exit(0)
