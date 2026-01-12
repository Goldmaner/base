"""
Script para adicionar coluna doc_respondido na tabela parcerias_notificacoes
"""

import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from config import DB_CONFIG


def adicionar_coluna_doc_respondido():
    """
    Adiciona coluna doc_respondido (BOOLEAN) na tabela parcerias_notificacoes
    """
    conn = None
    try:
        print("="*70)
        print("ADICIONANDO COLUNA doc_respondido")
        print("="*70)
        
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Verificar se coluna já existe
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = 'parcerias_notificacoes' 
            AND column_name = 'doc_respondido'
        """)
        
        if cur.fetchone():
            print("[INFO] Coluna 'doc_respondido' já existe!")
            return True
        
        # Adicionar coluna
        print("[INFO] Adicionando coluna 'doc_respondido' (BOOLEAN DEFAULT FALSE)...")
        cur.execute("""
            ALTER TABLE parcerias_notificacoes
            ADD COLUMN doc_respondido BOOLEAN DEFAULT FALSE
        """)
        
        conn.commit()
        print("✅ Coluna adicionada com sucesso!")
        
        # Verificar
        cur.execute("SELECT COUNT(*) FROM parcerias_notificacoes WHERE doc_respondido IS NOT NULL")
        total = cur.fetchone()[0]
        print(f"[INFO] Total de registros: {total}")
        
        cur.close()
        return True
        
    except Exception as e:
        print(f"[ERRO] {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    sucesso = adicionar_coluna_doc_respondido()
    
    if sucesso:
        print("\n✅ Script executado com sucesso!\n")
    else:
        print("\n❌ Falha na execução!\n")
        sys.exit(1)
