"""
Script para popular a tabela c_analistas_dgp com dados de exemplo
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG

def popular_agentes():
    """Insere agentes DGP de exemplo"""
    
    print("=" * 60)
    print("POPULANDO TABELA DE AGENTES DGP")
    print("=" * 60)
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Verificar se já existem registros
        cur.execute("SELECT COUNT(*) as total FROM categoricas.c_analistas_dgp")
        total_atual = cur.fetchone()['total']
        
        print(f"\n📊 Registros existentes: {total_atual}")
        
        if total_atual > 0:
            print("⚠️  Tabela já contém registros. Deseja continuar? (s/n)")
            resposta = input().strip().lower()
            if resposta != 's':
                print("❌ Operação cancelada.")
                return False
        
        # Dados de exemplo
        agentes = [
            {
                'nome_analista': 'João Silva Santos',
                'rf': '123456',
                'email': 'joao.silva@prefeitura.sp.gov.br',
                'status': True
            },
            {
                'nome_analista': 'Maria Oliveira Costa',
                'rf': '234567',
                'email': 'maria.oliveira@prefeitura.sp.gov.br',
                'status': True
            },
            {
                'nome_analista': 'Pedro Almeida Souza',
                'rf': '345678',
                'email': 'pedro.almeida@prefeitura.sp.gov.br',
                'status': True
            },
            {
                'nome_analista': 'Ana Paula Ferreira',
                'rf': '456789',
                'email': 'ana.ferreira@prefeitura.sp.gov.br',
                'status': False  # Inativo
            },
            {
                'nome_analista': 'Carlos Eduardo Lima',
                'rf': '567890',
                'email': 'carlos.lima@prefeitura.sp.gov.br',
                'status': True
            }
        ]
        
        print(f"\n📝 Inserindo {len(agentes)} agentes DGP...")
        
        for i, agente in enumerate(agentes, 1):
            cur.execute("""
                INSERT INTO categoricas.c_analistas_dgp 
                (nome_analista, rf, email, status)
                VALUES (%s, %s, %s, %s)
                RETURNING id
            """, (
                agente['nome_analista'],
                agente['rf'],
                agente['email'],
                agente['status']
            ))
            
            novo_id = cur.fetchone()['id']
            status_str = '✓ Ativo' if agente['status'] else '✗ Inativo'
            print(f"  [{i}/{len(agentes)}] {agente['nome_analista']} (RF: {agente['rf']}) - {status_str} [ID: {novo_id}]")
        
        conn.commit()
        
        print("\n" + "=" * 60)
        print("✅ AGENTES DGP INSERIDOS COM SUCESSO!")
        print("=" * 60)
        
        # Verificar total após inserção
        cur.execute("SELECT COUNT(*) as total FROM categoricas.c_analistas_dgp")
        total_final = cur.fetchone()['total']
        print(f"\n📊 Total de registros na tabela: {total_final}")
        
        # Mostrar estatísticas
        cur.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = true) as ativos,
                COUNT(*) FILTER (WHERE status = false) as inativos
            FROM categoricas.c_analistas_dgp
        """)
        stats = cur.fetchone()
        print(f"   • Ativos: {stats['ativos']}")
        print(f"   • Inativos: {stats['inativos']}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ ERRO ao inserir agentes: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cur.close()
        conn.close()
    
    return True

if __name__ == '__main__':
    sucesso = popular_agentes()
    sys.exit(0 if sucesso else 1)
