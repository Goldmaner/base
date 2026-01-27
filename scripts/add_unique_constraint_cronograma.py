"""
Script para adicionar UNIQUE constraint em ultra_liquidacoes_cronograma
para permitir ON CONFLICT DO NOTHING ao adicionar parcelas projetadas
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config import DB_CONFIG

def main():
    print("🔧 Adicionando UNIQUE constraint em ultra_liquidacoes_cronograma...")
    
    try:
        # Conectar ao banco
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        cur = conn.cursor()
        
        # Verificar se a constraint já existe
        cur.execute("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_schema = 'gestao_financeira' 
            AND table_name = 'ultra_liquidacoes_cronograma' 
            AND constraint_type = 'UNIQUE'
            AND constraint_name = 'uq_cronograma_termo_info_mes'
        """)
        
        if cur.fetchone():
            print("✅ Constraint já existe!")
            conn.close()
            return
        
        # Verificar se há duplicatas
        print("\n🔍 Verificando duplicatas...")
        cur.execute("""
            SELECT numero_termo, info_alteracao, nome_mes, COUNT(*) as total
            FROM gestao_financeira.ultra_liquidacoes_cronograma
            GROUP BY numero_termo, info_alteracao, nome_mes
            HAVING COUNT(*) > 1
        """)
        
        duplicatas = cur.fetchall()
        
        if duplicatas:
            print(f"\n⚠️ ATENÇÃO: {len(duplicatas)} duplicatas encontradas:")
            for dup in duplicatas[:5]:  # Mostrar apenas 5 primeiras
                print(f"  - Termo: {dup[0]}, Info: {dup[1]}, Mês: {dup[2]}, Total: {dup[3]}")
            
            if len(duplicatas) > 5:
                print(f"  ... e mais {len(duplicatas) - 5} duplicatas")
            
            resposta = input("\n🤔 Deseja remover as duplicatas automaticamente? (s/N): ")
            
            if resposta.lower() == 's':
                print("\n🗑️ Removendo duplicatas (mantendo o mais recente)...")
                cur.execute("""
                    DELETE FROM gestao_financeira.ultra_liquidacoes_cronograma a
                    USING gestao_financeira.ultra_liquidacoes_cronograma b
                    WHERE a.id < b.id
                    AND a.numero_termo = b.numero_termo
                    AND a.info_alteracao = b.info_alteracao
                    AND a.nome_mes = b.nome_mes
                """)
                print(f"✅ {cur.rowcount} registros duplicados removidos")
                conn.commit()
            else:
                print("❌ Operação cancelada. Resolva as duplicatas manualmente antes de continuar.")
                conn.close()
                return
        else:
            print("✅ Nenhuma duplicata encontrada")
        
        # Adicionar constraint
        print("\n➕ Adicionando UNIQUE constraint...")
        cur.execute("""
            ALTER TABLE gestao_financeira.ultra_liquidacoes_cronograma
            ADD CONSTRAINT uq_cronograma_termo_info_mes 
            UNIQUE (numero_termo, info_alteracao, nome_mes)
        """)
        
        conn.commit()
        print("✅ Constraint adicionada com sucesso!")
        print("\n📝 Constraint criada: uq_cronograma_termo_info_mes")
        print("   Garante unicidade em: (numero_termo, info_alteracao, nome_mes)")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        if conn:
            conn.rollback()
            conn.close()

if __name__ == '__main__':
    main()
