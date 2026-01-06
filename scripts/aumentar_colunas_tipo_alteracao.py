"""
Script para aumentar tamanho das colunas da tabela c_tipo_alteracao
que armazenam múltiplas seleções (checkbox_multiple)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from db import execute_query

def aumentar_colunas():
    """Aumenta o tamanho das colunas que armazenam múltiplas seleções"""
    
    with app.app_context():
        print("Aumentando tamanho das colunas de c_tipo_alteracao...")
        
        # Colunas que precisam ser maiores para armazenar múltiplas seleções
        alteracoes = [
            "ALTER TABLE categoricas.c_tipo_alteracao ALTER COLUMN alt_modalidade TYPE VARCHAR(500)",
            "ALTER TABLE categoricas.c_tipo_alteracao ALTER COLUMN alt_campo TYPE VARCHAR(500)",
            "ALTER TABLE categoricas.c_tipo_alteracao ALTER COLUMN alt_fonte_recursos TYPE VARCHAR(500)",
            "ALTER TABLE categoricas.c_tipo_alteracao ALTER COLUMN alt_instrumento TYPE VARCHAR(500)"
        ]
        
        for query in alteracoes:
            print(f"\nExecutando: {query}")
            resultado = execute_query(query)
            
            if resultado:
                print("✓ Sucesso")
            else:
                print("✗ Erro ao executar")
                return False
        
        print("\n✓ Todas as colunas foram aumentadas com sucesso!")
        print("  - alt_modalidade: VARCHAR(80) → VARCHAR(500)")
        print("  - alt_campo: VARCHAR(80) → VARCHAR(500)")
        print("  - alt_fonte_recursos: VARCHAR(80) → VARCHAR(500)")
        print("  - alt_instrumento: VARCHAR(80) → VARCHAR(500)")
        
        return True

if __name__ == '__main__':
    aumentar_colunas()
