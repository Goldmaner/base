# -*- coding: utf-8 -*-
"""
Script para importar ultra liquidacoes do arquivo CSV

Arquivo: C:\\Users\\d843702\\Downloads\\ultra_liquidacoes.csv
Formato: UTF-8, delimitador TAB
Destino: gestao_financeira.ultra_liquidacoes

Uso:
    python scripts/importar_ultra_liquidacoes.py
"""

import csv
import sys
import os
from datetime import datetime

# Adicionar o diretorio raiz ao path para importar modulos do Flask
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from db import get_db, get_cursor

ARQUIVO_CSV = r"C:\Users\d843702\Downloads\ultra_liquidacoes.csv"
ARQUIVO_LOG = r"C:\Users\d843702\Downloads\importacao_ultra_liquidacoes_log.txt"

# Dicionario de conversao de status
CONVERSAO_STATUS = {
    'Pago': ('Pago', 'Integral'),
    'Pago Parcial': ('Pago', 'Parcial'),
    'Pago Parcial - Glosa': ('Pago', 'Glosa'),
    'Encaminhado p/ Pagamento': ('Encaminhado para Pagamento', None),
    'Nao Pago': ('Nao Pago', None),
    'Não Pago': ('Nao Pago', None),
    'Nao Pago - Rescisao': ('Nao Pago', 'Rescisao'),
    'Não Pago - Rescisão': ('Nao Pago', 'Rescisao'),
    'Nao Pago - Glosa': ('Nao Pago', 'Glosa'),
    'Não Pago - Glosa': ('Nao Pago', 'Glosa'),
    'Nao Pago - Antigos': ('Nao Pago', 'Antigos'),
    'Não Pago - Antigos': ('Nao Pago', 'Antigos'),
}

def converter_data(data_str):
    """Converte data de dd/mm/yyyy para yyyy-mm-dd"""
    if not data_str or not data_str.strip():
        return None
    try:
        # Tentar formato dd/mm/yyyy
        dt = datetime.strptime(data_str.strip(), '%d/%m/%Y')
        return dt.strftime('%Y-%m-%d')
    except:
        return None

def converter_numero(num_str):
    """Converte numero de formato brasileiro (virgula) para float"""
    if not num_str or not num_str.strip():
        return 0
    try:
        # Substituir virgula por ponto
        num_limpo = num_str.strip().replace(',', '.')
        return float(num_limpo)
    except:
        return 0

def converter_status(status_antigo):
    """Converte status antigo para os dois novos campos"""
    if not status_antigo or not status_antigo.strip():
        return (None, None)
    
    status_limpo = status_antigo.strip()
    
    # Buscar conversao
    if status_limpo in CONVERSAO_STATUS:
        return CONVERSAO_STATUS[status_limpo]
    
    # Se nao encontrar, retornar o proprio status como principal
    print(f"AVISO: Status nao mapeado: '{status_limpo}'")
    return (status_limpo, None)

def importar_ultra_liquidacoes():
    """Importa ultra liquidacoes do CSV para o banco de dados"""
    
    if not os.path.exists(ARQUIVO_CSV):
        print(f"Arquivo nao encontrado: {ARQUIVO_CSV}")
        return
    
    # Abrir arquivo de log
    log_file = open(ARQUIVO_LOG, 'w', encoding='utf-8')
    
    def log(msg):
        """Escreve no console e no arquivo"""
        print(msg)
        log_file.write(msg + '\n')
        log_file.flush()
    
    with app.app_context():
        conn = get_db()
        cur = get_cursor()
        
        try:
            # Ler CSV
            log(f"Lendo arquivo: {ARQUIVO_CSV}")
            with open(ARQUIVO_CSV, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=';')  # Ponto e virgula delimitado
                registros = list(reader)
            
            log(f"Total de registros no CSV: {len(registros)}")
            
            # Debug: mostrar colunas
            if registros:
                log(f"\nColunas encontradas: {list(registros[0].keys())}\n")
            
            # Contadores
            inseridos = 0
            erros = 0
            primeiro_erro = None
            
            # Processar cada registro
            for i, row in enumerate(registros, 1):
                numero_termo = row.get('numero_termo', '').strip()
                parcela_numero = row.get('parcela_numero', '').strip()
                
                if not numero_termo:
                    log(f"Linha {i}: Termo vazio, pulando...")
                    erros += 1
                    continue
                
                # Debug para primeiras linhas
                if i <= 3:
                    log(f"\nDEBUG Linha {i}:")
                    log(f"  Dados completos: {row}")
                
                # Converter status
                status_antigo = row.get('parcela_status', '').strip()
                status_novo, status_secundario_novo = converter_status(status_antigo)
                
                # Inserir novo registro
                try:
                    cur.execute("""
                        INSERT INTO gestao_financeira.ultra_liquidacoes (
                            vigencia_inicial,
                            vigencia_final,
                            numero_termo,
                            parcela_tipo,
                            parcela_numero,
                            valor_elemento_53_23,
                            valor_elemento_53_24,
                            valor_previsto,
                            valor_subtraido,
                            valor_encaminhado,
                            valor_pago,
                            parcela_status,
                            data_pagamento,
                            observacoes,
                            parcela_status_secundario,
                            created_em
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    """, (
                        converter_data(row.get('vigencia_inicial', '')),
                        converter_data(row.get('vigencia_final', '')),
                        numero_termo,
                        row.get('parcela_tipo', '').strip() or None,
                        parcela_numero or None,
                        converter_numero(row.get('valor_elemento_53_23', '')),
                        converter_numero(row.get('valor_elemento_53_24', '')),
                        converter_numero(row.get('valor_previsto', '')),
                        converter_numero(row.get('valor_subtraido', '')),
                        converter_numero(row.get('valor_encaminhado', '')),
                        converter_numero(row.get('valor_pago', '')),
                        status_novo,
                        converter_data(row.get('data_pagamento', '')),
                        row.get('observacoes', '').strip() or None,
                        status_secundario_novo
                    ))
                    
                    inseridos += 1
                    status_msg = f"{status_novo}" + (f" ({status_secundario_novo})" if status_secundario_novo else "")
                    if i <= 5 or inseridos % 100 == 0:  # Mostrar primeiros 5 e depois a cada 100
                        log(f"OK - Linha {i}: {numero_termo} - {parcela_numero} - Status: {status_msg}")
                    
                except Exception as e:
                    erros += 1
                    erro_msg = str(e)
                    
                    # Guardar primeiro erro com detalhes
                    if not primeiro_erro:
                        import traceback
                        primeiro_erro = {
                            'linha': i,
                            'termo': numero_termo,
                            'erro': erro_msg,
                            'traceback': traceback.format_exc()
                        }
                    
                    # Mostrar apenas primeiros 10 erros
                    if erros <= 10:
                        log(f"ERRO - Linha {i}: {numero_termo} - {erro_msg}")
            
            # Commit
            conn.commit()
            
            # Resumo
            log("\n" + "="*60)
            log("RESUMO DA IMPORTACAO")
            log("="*60)
            log(f"Registros inseridos: {inseridos}")
            log(f"Erros: {erros}")
            log(f"Total processado: {len(registros)}")
            log("="*60)
            
            # Mostrar primeiro erro detalhado
            if primeiro_erro:
                log("\nDETALHES DO PRIMEIRO ERRO:")
                log(f"Linha: {primeiro_erro['linha']}")
                log(f"Termo: {primeiro_erro['termo']}")
                log(f"Erro: {primeiro_erro['erro']}")
                log(f"\nTraceback completo:")
                log(primeiro_erro['traceback'])
            
            if inseridos > 0:
                log(f"\nImportacao concluida com sucesso!")
            else:
                log(f"\nNenhum registro foi inserido.")
                
        except Exception as e:
            conn.rollback()
            log(f"\nERRO GERAL: {str(e)}")
            import traceback
            log(traceback.format_exc())
        
        finally:
            cur.close()
            log_file.close()
            print(f"\nLog salvo em: {ARQUIVO_LOG}")

if __name__ == '__main__':
    print("="*60)
    print("IMPORTACAO DE ULTRA LIQUIDACOES")
    print("="*60)
    print(f"Origem: {ARQUIVO_CSV}")
    print(f"Destino: gestao_financeira.ultra_liquidacoes")
    print("="*60)
    
    resposta = input("\nDeseja continuar com a importacao? (S/N): ")
    
    if resposta.upper() == 'S':
        importar_ultra_liquidacoes()
    else:
        print("Importacao cancelada pelo usuario.")
