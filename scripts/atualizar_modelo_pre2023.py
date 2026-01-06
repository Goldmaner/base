"""
Script para atualizar o modelo de texto "Pesquisa de Parcerias: Parcerias pré-2023"
para usar a nova função criar_tabela_pre2023() que filtra corretamente
termos com responsabilidade DP (1)
"""

import sys
import os

# Adicionar o diretório pai ao path para importar app e db
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from db import get_cursor

def atualizar_modelo_pre2023():
    """
    Atualiza o modelo "Pesquisa de Parcerias: Parcerias pré-2023" 
    substituindo criar_tabela_informado_usuario por criar_tabela_pre2023
    """
    try:
        # Usar contexto da aplicação Flask
        with app.app_context():
            # Query para buscar o modelo atual
            query_buscar = """
                SELECT id, titulo_texto, modelo_texto
                FROM categoricas.c_geral_legislacao
                WHERE titulo_texto = 'Pesquisa de Parcerias: Parcerias pré-2023'
            """
            
            cur = get_cursor()
            if not cur:
                print("❌ Erro ao conectar com o banco de dados")
                return False
            
            cur.execute(query_buscar)
            resultado = cur.fetchone()
            
            if not resultado:
                print("❌ Modelo 'Pesquisa de Parcerias: Parcerias pré-2023' não encontrado")
                cur.close()
                return False
            
            modelo_id = resultado['id']
            texto_original = resultado['modelo_texto']
            
            print(f"✅ Modelo encontrado (ID: {modelo_id})")
            print(f"📄 Texto original (primeiros 200 chars):\n{texto_original[:200]}...\n")
            
            # Substituir criar_tabela_informado_usuario por criar_tabela_pre2023
            texto_atualizado = texto_original.replace(
                'criar_tabela_informado_usuario',
                'criar_tabela_pre2023'
            )
            
            if texto_atualizado == texto_original:
                print("ℹ️  Nenhuma alteração necessária (função já está atualizada)")
                cur.close()
                return True
            
            # Atualizar no banco
            query_update = """
                UPDATE categoricas.c_geral_legislacao
                SET modelo_texto = %s
                WHERE id = %s
            """
            
            cur.execute(query_update, (texto_atualizado, modelo_id))
            cur.connection.commit()
            cur.close()
            
            print(f"✅ Modelo atualizado com sucesso!")
            print(f"📝 Substituição: criar_tabela_informado_usuario → criar_tabela_pre2023")
            print(f"📄 Texto atualizado (primeiros 200 chars):\n{texto_atualizado[:200]}...\n")
            
            return True
        
    except Exception as e:
        print(f"❌ Erro ao atualizar modelo: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("ATUALIZAÇÃO DO MODELO PRÉ-2023")
    print("=" * 60)
    print()
    
    sucesso = atualizar_modelo_pre2023()
    
    print()
    print("=" * 60)
    if sucesso:
        print("✅ SCRIPT EXECUTADO COM SUCESSO!")
    else:
        print("❌ SCRIPT FALHOU - Verifique os erros acima")
    print("=" * 60)
