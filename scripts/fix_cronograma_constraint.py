"""
Script para adicionar a constraint UNIQUE que está faltando na tabela ultra_liquidacoes_cronograma
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DB_CONFIG

def adicionar_constraint():
    # Conectar diretamente ao banco
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        print("=" * 80)
        print("🔍 Verificando constraints existentes...")
        print("=" * 80)
        
        # Verificar constraints atuais
        cur.execute("""
            SELECT conname, pg_get_constraintdef(oid) as constraintdef
            FROM pg_constraint 
            WHERE conrelid = 'gestao_financeira.ultra_liquidacoes_cronograma'::regclass
        """)
        
        constraints = cur.fetchall()
        print(f"\n📋 Constraints encontradas: {len(constraints)}")
        for constraint in constraints:
            print(f"  - {constraint['conname']}: {constraint['constraintdef']}")
        
        # Verificar se a constraint que precisamos já existe
        cur.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_schema = 'gestao_financeira' 
            AND table_name = 'ultra_liquidacoes_cronograma'
            AND constraint_type = 'UNIQUE'
            AND constraint_name = 'ultra_liquidacoes_cronograma_numero_termo_info_alteracao_nome_mes_key'
        """)
        
        existe = cur.fetchone()
        
        if existe:
            print("\n✅ Constraint UNIQUE já existe!")
            return True
        
        print("\n⚠️  Constraint UNIQUE não encontrada.")
        
        # Primeiro, verificar se há duplicatas
        print("\n🔍 Verificando duplicatas existentes...")
        cur.execute("""
            SELECT numero_termo, info_alteracao, nome_mes, COUNT(*) as total
            FROM gestao_financeira.ultra_liquidacoes_cronograma
            GROUP BY numero_termo, info_alteracao, nome_mes
            HAVING COUNT(*) > 1
            ORDER BY total DESC, numero_termo, nome_mes
        """)
        
        duplicatas = cur.fetchall()
        
        if duplicatas:
            print(f"\n⚠️  Encontradas {len(duplicatas)} combinações duplicadas!")
            print("\nExemplos:")
            for i, dup in enumerate(duplicatas[:5], 1):
                print(f"  {i}. {dup['numero_termo']} | {dup['info_alteracao']} | {dup['nome_mes']} ({dup['total']} registros)")
            
            if len(duplicatas) > 5:
                print(f"  ... e mais {len(duplicatas) - 5} combinações")
            
            print("\n⚙️  Removendo duplicatas (mantendo apenas o mais recente)...")
            
            # Para cada duplicata, manter apenas o registro com maior ID (mais recente)
            for dup in duplicatas:
                cur.execute("""
                    DELETE FROM gestao_financeira.ultra_liquidacoes_cronograma
                    WHERE numero_termo = %s 
                    AND info_alteracao = %s 
                    AND nome_mes = %s
                    AND id NOT IN (
                        SELECT MAX(id)
                        FROM gestao_financeira.ultra_liquidacoes_cronograma
                        WHERE numero_termo = %s 
                        AND info_alteracao = %s 
                        AND nome_mes = %s
                    )
                """, [
                    dup['numero_termo'], dup['info_alteracao'], dup['nome_mes'],
                    dup['numero_termo'], dup['info_alteracao'], dup['nome_mes']
                ])
                
                if cur.rowcount > 0:
                    print(f"  ✅ Removidos {cur.rowcount} duplicados de {dup['numero_termo']} | {dup['nome_mes']}")
            
            conn.commit()
            print("\n✅ Duplicatas removidas!")
        else:
            print("✅ Nenhuma duplicata encontrada!")
        
        print("\n⚙️  Criando constraint UNIQUE...")
        
        # Criar a constraint
        cur.execute("""
            ALTER TABLE gestao_financeira.ultra_liquidacoes_cronograma
            ADD CONSTRAINT ultra_liquidacoes_cronograma_numero_termo_info_alteracao_nome_mes_key 
            UNIQUE (numero_termo, info_alteracao, nome_mes)
        """)
        
        conn.commit()
        
        print("✅ Constraint UNIQUE criada com sucesso!")
        print("\n📋 Nome da constraint:")
        print("  ultra_liquidacoes_cronograma_numero_termo_info_alteracao_nome_mes_key")
        print("\n🔑 Colunas:")
        print("  - numero_termo")
        print("  - info_alteracao")
        print("  - nome_mes")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Erro ao criar constraint: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cur.close()
    
    return True

if __name__ == '__main__':
    print("\n" + "=" * 80)
    print("ADICIONAR CONSTRAINT UNIQUE - ultra_liquidacoes_cronograma")
    print("=" * 80)
    
    sucesso = adicionar_constraint()
    
    if sucesso:
        print("\n" + "=" * 80)
        print("✅ OPERAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("❌ OPERAÇÃO FALHOU")
        print("=" * 80)
        sys.exit(1)
