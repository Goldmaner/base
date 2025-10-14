#!/usr/bin/env python3
"""
Script de teste para verificar conectividade com PostgreSQL
e estrutura das tabelas necessárias para o projeto FAF.
"""

import psycopg2
from psycopg2.extras import RealDictCursor

# Configuração do banco PostgreSQL
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'projeto_parcerias',
    'user': 'postgres',
    'password': 'Coração01'
}

def test_connection():
    """Testa conexão básica com o PostgreSQL."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        print("✅ Conexão com PostgreSQL estabelecida com sucesso!")
        
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Testar versão do PostgreSQL
        cur.execute("SELECT version();")
        version = cur.fetchone()
        print(f"🐘 Versão do PostgreSQL: {version['version']}")
        
        cur.close()
        conn.close()
        return True
        
    except psycopg2.Error as e:
        print(f"❌ Erro na conexão com PostgreSQL: {e}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return False

def test_tables():
    """Verifica se as tabelas necessárias existem no banco."""
    required_tables = ['usuarios', 'Parcerias', 'Parcerias_Despesas', 'Instrucoes']
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n📋 Verificando tabelas necessárias:")
        
        for table in required_tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = %s
                );
            """, (table.lower(),))
            
            exists = cur.fetchone()['exists']
            status = "✅" if exists else "❌"
            print(f"{status} Tabela '{table}': {'Existe' if exists else 'Não encontrada'}")
            
            if exists:
                # Contar registros na tabela
                cur.execute(f"SELECT COUNT(*) as count FROM {table};")
                count = cur.fetchone()['count']
                print(f"   📊 Registros: {count}")
        
        cur.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Erro ao verificar tabelas: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")

def test_sample_queries():
    """Testa algumas queries de exemplo."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        print("\n🔍 Testando queries de exemplo:")
        
        # Testar query dos usuários
        cur.execute("SELECT COUNT(*) as count FROM usuarios;")
        user_count = cur.fetchone()['count']
        print(f"✅ Usuários cadastrados: {user_count}")
        
        # Testar query das parcerias (principal)
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM Parcerias 
            WHERE tipo_termo NOT IN ('Convênio de Cooperação', 'Convênio', 'Convênio - Passivo', 'Acordo de Cooperação')
        """)
        parcerias_count = cur.fetchone()['count']
        print(f"✅ Parcerias válidas para orçamento: {parcerias_count}")
        
        # Testar query das despesas
        cur.execute("SELECT COUNT(*) as count FROM Parcerias_Despesas;")
        despesas_count = cur.fetchone()['count']
        print(f"✅ Despesas cadastradas: {despesas_count}")
        
        cur.close()
        conn.close()
        
    except psycopg2.Error as e:
        print(f"❌ Erro ao executar queries de teste: {e}")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")

def main():
    """Executa todos os testes."""
    print("🚀 Iniciando testes de conectividade PostgreSQL...\n")
    
    if test_connection():
        test_tables()
        test_sample_queries()
        print("\n🎉 Testes concluídos!")
    else:
        print("\n💥 Falha na conexão - verifique as configurações do PostgreSQL")

if __name__ == "__main__":
    main()