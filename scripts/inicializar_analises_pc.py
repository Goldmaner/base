"""
Script de inicialização do módulo analises_pc
Cria índices e valida a estrutura do banco de dados
"""

import sys
import os

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from config import DB_CONFIG

def get_connection():
    """Cria uma conexão direta com o banco"""
    return psycopg2.connect(**DB_CONFIG)

def verificar_tabelas():
    """Verifica se as tabelas necessárias existem"""
    print("\n🔍 Verificando estrutura de tabelas...")
    
    conn = get_connection()
    cur = conn.cursor()
    
    tabelas_necessarias = [
        'analises_pc.checklist_termo',
        'analises_pc.checklist_analista',
        'analises_pc.checklist_recursos'
    ]
    
    tabelas_encontradas = []
    tabelas_faltando = []
    
    for tabela in tabelas_necessarias:
        schema, nome = tabela.split('.')
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = %s 
                AND table_name = %s
            )
        """, (schema, nome))
        
        existe = cur.fetchone()[0]
        if existe:
            tabelas_encontradas.append(tabela)
            print(f"   ✓ {tabela}")
        else:
            tabelas_faltando.append(tabela)
            print(f"   ✗ {tabela} - NÃO ENCONTRADA")
    
    cur.close()
    conn.close()
    
    if tabelas_faltando:
        print(f"\n❌ Erro: {len(tabelas_faltando)} tabela(s) faltando!")
        print("   Execute os scripts de criação das tabelas primeiro.")
        return False
    
    print(f"\n✓ Todas as {len(tabelas_encontradas)} tabelas encontradas!")
    return True

def criar_indices():
    """Cria os índices de performance"""
    print("\n📊 Criando índices de performance...")
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # Índices para checklist_termo
        indices = [
            ("idx_checklist_termo_numero_termo", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_termo_numero_termo ON analises_pc.checklist_termo(numero_termo)"),
            ("idx_checklist_termo_meses", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_termo_meses ON analises_pc.checklist_termo(meses_analisados)"),
            ("idx_checklist_termo_composto", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_termo_composto ON analises_pc.checklist_termo(numero_termo, meses_analisados)"),
            
            # Índices para checklist_analista
            ("idx_checklist_analista_numero_termo", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_analista_numero_termo ON analises_pc.checklist_analista(numero_termo)"),
            ("idx_checklist_analista_meses", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_analista_meses ON analises_pc.checklist_analista(meses_analisados)"),
            ("idx_checklist_analista_composto", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_analista_composto ON analises_pc.checklist_analista(numero_termo, meses_analisados)"),
            ("idx_checklist_analista_nome", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_analista_nome ON analises_pc.checklist_analista(nome_analista)"),
            
            # Índices para checklist_recursos
            ("idx_checklist_recursos_numero_termo", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_recursos_numero_termo ON analises_pc.checklist_recursos(numero_termo)"),
            ("idx_checklist_recursos_meses", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_recursos_meses ON analises_pc.checklist_recursos(meses_analisados)"),
            ("idx_checklist_recursos_composto", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_recursos_composto ON analises_pc.checklist_recursos(numero_termo, meses_analisados)"),
            ("idx_checklist_recursos_tipo", 
             "CREATE INDEX IF NOT EXISTS idx_checklist_recursos_tipo ON analises_pc.checklist_recursos(numero_termo, meses_analisados, tipo_recurso)"),
        ]
        
        for nome, sql in indices:
            cur.execute(sql)
            print(f"   ✓ {nome}")
        
        # Criar constraint UNIQUE
        print("\n🔒 Criando constraints...")
        try:
            cur.execute("""
                ALTER TABLE analises_pc.checklist_termo 
                ADD CONSTRAINT uk_checklist_termo_composto 
                UNIQUE (numero_termo, meses_analisados)
            """)
            print("   ✓ Constraint UNIQUE adicionada")
        except Exception:
            print("   ℹ Constraint UNIQUE já existe")
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"\n✓ {len(indices)} índices criados com sucesso!")
        return True
        
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        print(f"\n❌ Erro ao criar índices: {e}")
        return False

def verificar_dependencias():
    """Verifica se as tabelas de dependência existem"""
    print("\n🔗 Verificando dependências externas...")
    
    conn = get_connection()
    cur = conn.cursor()
    
    dependencias = [
        ('public', 'parcerias', 'numero_termo'),
        ('categoricas', 'c_analistas', 'nome_analista')
    ]
    
    todas_ok = True
    
    for schema, tabela, coluna in dependencias:
        # Verificar tabela
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = %s AND table_name = %s
            )
        """, (schema, tabela))
        
        if cur.fetchone()[0]:
            # Verificar coluna
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = %s AND column_name = %s
                )
            """, (schema, tabela, coluna))
            
            if cur.fetchone()[0]:
                print(f"   ✓ {schema}.{tabela}.{coluna}")
            else:
                print(f"   ✗ {schema}.{tabela}.{coluna} - COLUNA NÃO ENCONTRADA")
                todas_ok = False
        else:
            print(f"   ✗ {schema}.{tabela} - TABELA NÃO ENCONTRADA")
            todas_ok = False
    
    cur.close()
    conn.close()
    
    if not todas_ok:
        print("\n⚠️  Aviso: Algumas dependências não foram encontradas.")
        print("   O módulo pode não funcionar corretamente.")
    else:
        print("\n✓ Todas as dependências encontradas!")
    
    return todas_ok

def mostrar_estatisticas():
    """Mostra estatísticas das tabelas"""
    print("\n📈 Estatísticas das tabelas:")
    
    conn = get_connection()
    cur = conn.cursor()
    
    tabelas = [
        'analises_pc.checklist_termo',
        'analises_pc.checklist_analista',
        'analises_pc.checklist_recursos'
    ]
    
    for tabela in tabelas:
        cur.execute(f"SELECT COUNT(*) FROM {tabela}")
        count = cur.fetchone()[0]
        print(f"   {tabela}: {count} registro(s)")
    
    cur.close()
    conn.close()

def main():
    """Função principal"""
    print("=" * 70)
    print("🚀 Inicialização do Módulo analises_pc")
    print("=" * 70)
    
    # Verificar tabelas
    if not verificar_tabelas():
        print("\n❌ Inicialização interrompida: tabelas faltando")
        sys.exit(1)
    
    # Verificar dependências
    verificar_dependencias()
    
    # Criar índices
    if not criar_indices():
        print("\n❌ Erro ao criar índices")
        sys.exit(1)
    
    # Mostrar estatísticas
    mostrar_estatisticas()
    
    print("\n" + "=" * 70)
    print("✅ Módulo analises_pc inicializado com sucesso!")
    print("=" * 70)
    print("\n📝 Próximos passos:")
    print("   1. Inicie o servidor: python run_dev.py")
    print("   2. Acesse: http://localhost:5000/analises_pc/")
    print("   3. Ou via Instruções → 'Ir para o Formulário Inicial'")
    print("\n💡 Para testes: python testes/test_analises_pc_api.py")
    print()

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Operação cancelada pelo usuário")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")
        sys.exit(1)
