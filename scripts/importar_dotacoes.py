# -*- coding: utf-8 -*-
"""
Script para importar dotacoes orcamentarias do arquivo CSV

Arquivo: C:\\Users\\d843702\\Downloads\\dotacao_importacao.csv
Formato: UTF-8, delimitador ;
Destino: categoricas.c_geral_dotacoes

Uso:
    python scripts/importar_dotacoes.py
"""

import csv
import sys
import os

# Adicionar o diretorio raiz ao path para importar modulos do Flask
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from db import get_db, get_cursor

ARQUIVO_CSV = r"C:\Users\d843702\Downloads\dotacao_importacao.csv"

def importar_dotacoes():
    """Importa dotacoes do CSV para o banco de dados"""
    
    if not os.path.exists(ARQUIVO_CSV):
        print(f"Arquivo nao encontrado: {ARQUIVO_CSV}")
        return
    
    with app.app_context():
        conn = get_db()
        cur = get_cursor()
        
        try:
            # Ler CSV
            print(f"Lendo arquivo: {ARQUIVO_CSV}")
            with open(ARQUIVO_CSV, 'r', encoding='utf-8-sig') as f:  # utf-8-sig remove BOM
                reader = csv.DictReader(f, delimiter=';')
                registros = list(reader)
            
            print(f"Total de registros no CSV: {len(registros)}")
            
            # Debug: mostrar colunas e primeira linha
            if registros:
                print(f"\nColunas encontradas no CSV: {list(registros[0].keys())}")
                print(f"Primeira linha de exemplo: {registros[0]}\n")
            
            # Verificar registros existentes
            cur.execute("SELECT dotacao_numero FROM categoricas.c_geral_dotacoes")
            dotacoes_existentes = {row[0] for row in cur.fetchall()}
            print(f"Dotacoes ja cadastradas: {len(dotacoes_existentes)}")
            
            # Contadores
            inseridos = 0
            duplicados = 0
            erros = 0
            
            # Processar cada registro
            for i, row in enumerate(registros, 1):
                dotacao_numero = row.get('dotacao_numero', '').strip()
                
                if not dotacao_numero:
                    print(f"Linha {i}: Dotacao vazia, pulando...")
                    erros += 1
                    continue
                
                # Verificar se ja existe
                if dotacao_numero in dotacoes_existentes:
                    print(f"Linha {i}: Dotacao {dotacao_numero} ja existe")
                    duplicados += 1
                    continue
                
                # Inserir novo registro
                try:
                    cur.execute("""
                        INSERT INTO categoricas.c_geral_dotacoes (
                            dotacao_numero,
                            programa_aplicacao,
                            coordenacao,
                            condicoes_termo,
                            condicoes_unidade,
                            condicoes_osc
                        ) VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        dotacao_numero,
                        row.get('programa_aplicacao', '').strip() or None,
                        row.get('coordenacao', '').strip() or None,
                        row.get('condicoes_termo', '').strip() or None,
                        row.get('condicoes_unidade', '').strip() or None,
                        row.get('condicoes_osc', '').strip() or None
                    ))
                    
                    inseridos += 1
                    print(f"OK - Linha {i}: Dotacao {dotacao_numero} inserida")
                    
                except Exception as e:
                    print(f"ERRO - Linha {i}: Erro ao inserir {dotacao_numero}: {str(e)}")
                    erros += 1
            
            # Commit
            conn.commit()
            
            # Resumo
            print("\n" + "="*60)
            print("RESUMO DA IMPORTACAO")
            print("="*60)
            print(f"Registros inseridos: {inseridos}")
            print(f"Registros duplicados: {duplicados}")
            print(f"Erros: {erros}")
            print(f"Total processado: {len(registros)}")
            print("="*60)
            
            if inseridos > 0:
                print(f"\nImportacao concluida com sucesso!")
            else:
                print(f"\nNenhum registro novo foi inserido.")
                
        except Exception as e:
            conn.rollback()
            print(f"\nERRO GERAL: {str(e)}")
            import traceback
            traceback.print_exc()
        
        finally:
            cur.close()

if __name__ == '__main__':
    print("="*60)
    print("IMPORTACAO DE DOTACOES ORCAMENTARIAS")
    print("="*60)
    print(f"Origem: {ARQUIVO_CSV}")
    print(f"Destino: categoricas.c_geral_dotacoes")
    print("="*60)
    
    resposta = input("\nDeseja continuar com a importacao? (S/N): ")
    
    if resposta.upper() == 'S':
        importar_dotacoes()
    else:
        print("Importacao cancelada pelo usuario.")
