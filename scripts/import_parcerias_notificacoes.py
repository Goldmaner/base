"""
Script para importar dados do CSV parcerias_notificacoes.csv para a tabela parcerias_notificacoes
Autor: Sistema FAF
Data: 2025-11-17
"""

import csv
import sys
import os
from datetime import datetime
import psycopg2

# Adicionar o diretório pai ao path para importar os módulos do projeto
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import DB_CONFIG

def converter_data(data_str):
    """
    Converte string de data no formato DD/MM/YYYY para formato ISO (YYYY-MM-DD)
    Retorna None se a string estiver vazia ou for '-'
    """
    if not data_str or data_str.strip() == '' or data_str.strip() == '-':
        return None
    
    try:
        # Formato esperado: DD/MM/YYYY
        data_obj = datetime.strptime(data_str.strip(), '%d/%m/%Y')
        return data_obj.strftime('%Y-%m-%d')
    except ValueError as e:
        print(f"[AVISO] Erro ao converter data '{data_str}': {e}")
        return None

def converter_timestamp(timestamp_str):
    """
    Converte string de timestamp para formato ISO
    Retorna None se a string estiver vazia ou for '-'
    Aceita vários formatos: DD/MM/YYYY HH:MM:SS, DD/MM/YYYY HH:MM, etc.
    """
    if not timestamp_str or timestamp_str.strip() == '' or timestamp_str.strip() == '-':
        return None
    
    timestamp_str = timestamp_str.strip()
    
    # Tentar vários formatos
    formatos = [
        '%d/%m/%Y %H:%M:%S',
        '%d/%m/%Y %H:%M',
        '%d/%m/%Y',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M'
    ]
    
    for formato in formatos:
        try:
            data_obj = datetime.strptime(timestamp_str, formato)
            return data_obj.strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    
    print(f"[AVISO] Erro ao converter timestamp '{timestamp_str}': formato nao reconhecido")
    return None

def converter_boolean(bool_str):
    """
    Converte string para boolean
    Aceita: true, false, 1, 0, sim, não
    Retorna False como padrão
    """
    if not bool_str or bool_str.strip() == '':
        return False
    
    valor = bool_str.strip().lower()
    return valor in ['true', '1', 'sim', 's', 'yes', 'y']

def converter_inteiro(int_str, default=0):
    """
    Converte string para inteiro
    Retorna o valor default se a conversão falhar
    """
    if not int_str or int_str.strip() == '' or int_str.strip() == '-':
        return default
    
    try:
        return int(int_str.strip())
    except ValueError:
        return default

def tratar_string(s):
    """
    Trata string vazias ou com '-' como None
    Remove espaços em branco extras
    """
    if not s or s.strip() == '' or s.strip() == '-':
        return None
    return s.strip()

def importar_notificacoes():
    """
    Importa os dados do CSV para a tabela parcerias_notificacoes
    """
    csv_path = os.path.join(os.path.dirname(__file__), '..', 'docs', 'parcerias_notificacoes.csv')
    
    if not os.path.exists(csv_path):
        print(f"[ERRO] Arquivo nao encontrado: {csv_path}")
        return
    
    print(f"[INFO] Lendo arquivo: {csv_path}")
    
    conn = None
    cursor = None
    
    try:
        # Conectar ao banco usando DB_CONFIG diretamente
        print(f"[INFO] Conectando ao banco: {DB_CONFIG.get('host')}:{DB_CONFIG.get('port')}/{DB_CONFIG.get('database')}")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        print("[OK] Conexao com banco de dados estabelecida")
        
        # Ler o CSV
        registros_importados = 0
        registros_com_erro = 0
        
        with open(csv_path, 'r', encoding='utf-8-sig') as csvfile:  # utf-8-sig remove o BOM automaticamente
            # Usar ponto-e-vírgula como delimitador
            reader = csv.DictReader(csvfile, delimiter=';')
            
            print(f"[INFO] Colunas encontradas no CSV: {reader.fieldnames}\n")
            
            # SQL de inserção
            insert_sql = """
                INSERT INTO parcerias_notificacoes (
                    tipo_doc, ano_doc, numero_doc, numero_termo, nome_responsavel,
                    data_doc, data_pub, data_email_ar, dilacao, dilacao_dias,
                    sei_doc, observacoes
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
            """
            
            for i, row in enumerate(reader, start=1):
                try:
                    # Preparar dados
                    dados = (
                        tratar_string(row.get('tipo_doc')),           # tipo_doc
                        converter_inteiro(row.get('ano_doc')),        # ano_doc
                        converter_inteiro(row.get('numero_doc')),     # numero_doc
                        tratar_string(row.get('numero_termo')),       # numero_termo
                        tratar_string(row.get('nome_responsavel')),   # nome_responsavel
                        converter_data(row.get('data_doc')),          # data_doc
                        converter_data(row.get('data_pub')),          # data_pub
                        converter_timestamp(row.get('data_email_ar')),# data_email_ar
                        converter_boolean(row.get('dilacao')),        # dilacao
                        converter_inteiro(row.get('dilacao_dias'), 0),# dilacao_dias
                        tratar_string(row.get('sei_doc')),            # sei_doc
                        tratar_string(row.get('observacoes'))         # observacoes
                    )
                    
                    # Inserir no banco
                    cursor.execute(insert_sql, dados)
                    conn.commit()  # Commit imediatamente após cada inserção
                    registros_importados += 1
                    
                    print(f"[OK] Linha {i}: {row.get('tipo_doc')} {row.get('ano_doc')}/{row.get('numero_doc')} - Termo: {row.get('numero_termo') or '(sem termo)'}")
                    
                except Exception as e:
                    conn.rollback()  # Rollback apenas da transação atual
                    registros_com_erro += 1
                    print(f"[ERRO] Erro na linha {i}: {e}")
                    print(f"       Dados preparados: {dados if 'dados' in locals() else 'N/A'}")
                    print(f"       Dados originais: {row}")
                    # Continuar com o próximo registro
                    continue
        
        # Não precisa fazer commit aqui pois já fizemos após cada inserção
        
        print(f"\n{'='*60}")
        print(f"[OK] Importacao concluida!")
        print(f"     Registros importados: {registros_importados}")
        if registros_com_erro > 0:
            print(f"     Registros com erro: {registros_com_erro}")
        print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"\n[ERRO] Erro durante a importacao: {e}")
        if conn:
            conn.rollback()
            print("[INFO] Rollback realizado")
        raise
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
            print("[INFO] Conexao com banco de dados fechada")

if __name__ == '__main__':
    print("="*60)
    print("IMPORTACAO DE NOTIFICACOES DE PARCERIAS")
    print("="*60)
    print()
    
    try:
        importar_notificacoes()
    except KeyboardInterrupt:
        print("\n\n[AVISO] Importacao cancelada pelo usuario")
    except Exception as e:
        print(f"\n[ERRO] Erro fatal: {e}")
        sys.exit(1)
