"""
Script para importar SEI das pesquisas de parcerias
Atualiza a coluna psei_pesquisa na tabela public.o_pesquisa_parcerias
usando numero_pesquisa como chave
"""

import os
import sys
import csv

# Adicionar diretório pai ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db import get_cursor


def importar_sei_pesquisas(arquivo_csv):
    """
    Importa os números SEI das pesquisas do arquivo CSV
    
    Args:
        arquivo_csv: Caminho do arquivo CSV com colunas numero_pesquisa e SEI_pesquisa
    
    Returns:
        bool: True se sucesso, False se erro
    """
    print()
    print("=" * 80)
    print("ATUALIZAÇÃO DE SEI DAS PESQUISAS DE PARCERIAS")
    print("=" * 80)
    print()
    
    # Conectar ao banco
    try:
        cur = get_cursor()
        if not cur:
            print("[ERRO] Não foi possível conectar ao banco de dados")
            return False
        
        print("[OK] Conectado ao banco de dados")
        print()
        
    except Exception as e:
        print(f"[ERRO] Erro ao conectar: {str(e)}")
        return False
    
    # Ler arquivo CSV
    try:
        with open(arquivo_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')
            
            registros = list(reader)
            total = len(registros)
            
            print(f"[INFO] Arquivo CSV lido: {total} registro(s) encontrado(s)")
            print()
            
    except Exception as e:
        print(f"[ERRO] Erro ao ler arquivo CSV: {str(e)}")
        return False
    
    # Processar cada registro
    atualizados = 0
    nao_encontrados = 0
    erros = 0
    
    for idx, row in enumerate(registros, start=1):
        try:
            numero_pesquisa = int(row['numero_pesquisa'])
            sei_pesquisa = row['SEI_pesquisa'].strip()
            
            # Verificar se a pesquisa existe
            query_check = """
                SELECT numero_pesquisa 
                FROM public.o_pesquisa_parcerias 
                WHERE numero_pesquisa = %s
            """
            cur.execute(query_check, (numero_pesquisa,))
            existe = cur.fetchone()
            
            if not existe:
                print(f"[AVISO] Pesquisa {numero_pesquisa} não existe na base")
                nao_encontrados += 1
                continue
            
            # Atualizar o SEI
            query_update = """
                UPDATE public.o_pesquisa_parcerias
                SET psei_pesquisa = %s
                WHERE numero_pesquisa = %s
            """
            
            cur.execute(query_update, (sei_pesquisa, numero_pesquisa))
            cur.connection.commit()
            
            atualizados += 1
            print(f"[{idx}/{total}] Pesquisa {numero_pesquisa} | SEI: {sei_pesquisa} | ✓ ATUALIZADA")
            
        except KeyError as e:
            print(f"[ERRO] Linha {idx}: Coluna não encontrada - {str(e)}")
            erros += 1
            continue
            
        except ValueError as e:
            print(f"[ERRO] Linha {idx}: Valor inválido - {str(e)}")
            erros += 1
            continue
            
        except Exception as e:
            print(f"[ERRO] Linha {idx}: {str(e)}")
            erros += 1
            continue
    
    # Fechar cursor
    cur.close()
    
    # Exibir resumo
    print()
    print("=" * 80)
    print("[SUCESSO] Atualização concluída!")
    print(f"[INFO] Total de registros no CSV: {total}")
    print(f"[INFO] Atualizados com sucesso: {atualizados}")
    print(f"[INFO] Não encontrados: {nao_encontrados}")
    print(f"[INFO] Erros: {erros}")
    print("=" * 80)
    print()
    
    return erros == 0


def main():
    """Função principal"""
    # Adicionar diretório pai ao path para importar módulos
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    
    # Importar app Flask para ter contexto
    from app import app
    
    # Caminho do arquivo CSV
    arquivo_csv = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'testes', 
        'import_pesquisa_2.csv'
    )
    
    if not os.path.exists(arquivo_csv):
        print(f"[ERRO] Arquivo não encontrado: {arquivo_csv}")
        return
    
    print(f"[INFO] Arquivo CSV: {arquivo_csv}")
    print()
    
    # Confirmar atualização
    resposta = input("Deseja prosseguir com a atualização dos SEI? (s/n): ")
    if resposta.lower() != 's':
        print("[INFO] Atualização cancelada pelo usuário")
        return
    
    print()
    
    # Executar atualização dentro do contexto Flask
    with app.app_context():
        sucesso = importar_sei_pesquisas(arquivo_csv)
    
    if sucesso:
        print()
        print("[OK] Atualização finalizada com sucesso!")
    else:
        print()
        print("[ERRO] Atualização finalizada com erros")


if __name__ == '__main__':
    main()
