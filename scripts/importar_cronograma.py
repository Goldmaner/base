# -*- coding: utf-8 -*-
"""
Script para importar cronograma de ultra_liquidacoes do CSV para a tabela
gestao_financeira.ultra_liquidacoes_cronograma

Transforma formato horizontal (12 colunas de meses) em formato vertical (uma linha por mês)
"""

import os
import sys
import csv
from datetime import datetime, date
from decimal import Decimal

# Adicionar o diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from db import get_db, get_cursor

# Arquivo CSV de origem
ARQUIVO_CSV = r"C:\Users\d843702\Downloads\cronograma.csv"

# Arquivo de log
ARQUIVO_LOG = r"C:\Users\d843702\Downloads\importacao_cronograma_log.txt"

# Mapeamento dos meses para números
MESES = {
    'janeiro': 1,
    'fevereiro': 2,
    'março': 3,
    'abril': 4,
    'maio': 5,
    'junho': 6,
    'julho': 7,
    'agosto': 8,
    'setembro': 9,
    'outubro': 10,
    'novembro': 11,
    'dezembro': 12
}

# Lista ordenada dos meses (para iterar)
MESES_ORDEM = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 
               'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']


def converter_valor(valor_str):
    """
    Converte valor do formato brasileiro (1.234,56) para Decimal
    Retorna Decimal('0') se for zero ou vazio
    """
    if not valor_str or valor_str.strip() == '':
        return Decimal('0')
    
    # Remove espaços
    valor_limpo = valor_str.strip()
    
    # Remove pontos de milhar e troca vírgula por ponto
    valor_limpo = valor_limpo.replace('.', '').replace(',', '.')
    
    try:
        return Decimal(valor_limpo)
    except:
        return Decimal('0')


def construir_data(ano, numero_mes):
    """
    Constrói objeto date a partir do ano e número do mês
    Sempre usa dia 01
    """
    return date(int(ano), numero_mes, 1)


def processar_info_alteracao(aditivo_str):
    """
    Converte coluna aditivo em info_alteracao
    "-" → "Base"
    Número → "Aditamento N"
    """
    if not aditivo_str or aditivo_str.strip() == '-':
        return 'Base'
    
    aditivo_limpo = aditivo_str.strip()
    
    # Se for um número
    if aditivo_limpo.isdigit():
        return f'Aditamento {aditivo_limpo}'
    
    # Caso contrário, retorna como está
    return aditivo_limpo


def processar_linha_csv(linha):
    """
    Processa uma linha do CSV e retorna lista de registros para inserir
    Cada registro é um dicionário com os campos da tabela
    
    Ignora zeros externos (antes do primeiro valor e depois do último),
    mas mantém zeros internos (entre valores)
    """
    registros = []
    
    aditivo = linha['aditivo']
    numero_termo = linha['numero_termo'].strip()
    ano = linha['ano'].strip()
    parcela_numero = linha['parcela_numero'].strip()
    
    info_alteracao = processar_info_alteracao(aditivo)
    
    # Extrair valores dos 12 meses
    valores_meses = []
    for mes in MESES_ORDEM:
        valor = converter_valor(linha[mes])
        valores_meses.append((mes, valor))
    
    # Encontrar índices do primeiro e último valor não-zero
    indices_nao_zero = [i for i, (mes, valor) in enumerate(valores_meses) if valor != 0]
    
    if not indices_nao_zero:
        # Todos os valores são zero, não há nada para importar
        return []
    
    primeiro_idx = indices_nao_zero[0]
    ultimo_idx = indices_nao_zero[-1]
    
    # Iterar apenas do primeiro ao último valor não-zero (inclusive)
    # Isso mantém zeros internos mas ignora zeros externos
    for i in range(primeiro_idx, ultimo_idx + 1):
        mes, valor = valores_meses[i]
        numero_mes = MESES[mes]
        nome_mes = construir_data(ano, numero_mes)
        
        registro = {
            'info_alteracao': info_alteracao,
            'numero_termo': numero_termo,
            'nome_mes': nome_mes,
            'valor_mes': valor,
            'parcela_numero': parcela_numero,
            'created_por': 'Script de Importação',
            'created_em': datetime.now(),
            'atualizado_por': None,
            'atualizado_em': None
        }
        
        registros.append(registro)
    
    return registros


def calcular_soma_csv(linhas_csv):
    """
    Calcula soma total por numero_termo do CSV
    Retorna dicionário {numero_termo: total}
    """
    somas = {}
    
    for linha in linhas_csv:
        numero_termo = linha['numero_termo'].strip()
        
        total = Decimal('0')
        for mes in MESES_ORDEM:
            valor = converter_valor(linha[mes])
            total += valor
        
        if numero_termo in somas:
            somas[numero_termo] += total
        else:
            somas[numero_termo] = total
    
    return somas


def calcular_soma_importados(registros):
    """
    Calcula soma total por numero_termo dos registros a importar
    Retorna dicionário {numero_termo: total}
    """
    somas = {}
    
    for registro in registros:
        numero_termo = registro['numero_termo']
        valor = registro['valor_mes']
        
        if numero_termo in somas:
            somas[numero_termo] += valor
        else:
            somas[numero_termo] = valor
    
    return somas


def main():
    # Abrir arquivo de log
    log_file = open(ARQUIVO_LOG, 'w', encoding='utf-8')
    
    def log(msg, console=True):
        """Log com opção de ocultar do console"""
        if console:
            print(msg)
        log_file.write(msg + '\n')
        log_file.flush()
    
    log("=" * 80)
    log("SCRIPT DE IMPORTAÇÃO - CRONOGRAMA DE ULTRA LIQUIDAÇÕES")
    log("=" * 80)
    log(f"Data/Hora: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
    log(f"Arquivo CSV: {ARQUIVO_CSV}")
    log("")
    
    # Verificar se arquivo existe
    if not os.path.exists(ARQUIVO_CSV):
        log(f"❌ ERRO: Arquivo não encontrado: {ARQUIVO_CSV}")
        log_file.close()
        return
    
    # Criar aplicação Flask
    app = create_app()
    
    with app.app_context():
        conn = get_db()
        cur = get_cursor()
        
        try:
            # Ler CSV
            log("📖 Lendo arquivo CSV...")
            
            with open(ARQUIVO_CSV, 'r', encoding='utf-8-sig') as f:
                # Detectar delimitador (testar ; e \t)
                primeira_linha = f.readline()
                f.seek(0)
                
                if ';' in primeira_linha:
                    delimiter = ';'
                elif '\t' in primeira_linha:
                    delimiter = '\t'
                else:
                    delimiter = ','
                
                log(f"   Delimitador detectado: '{delimiter}'")
                
                reader = csv.DictReader(f, delimiter=delimiter)
                linhas_csv = list(reader)
            
            log(f"   ✅ {len(linhas_csv)} linhas lidas do CSV")
            log("")
            
            # Calcular soma total do CSV por numero_termo
            log("🧮 Calculando totais do CSV por termo...")
            somas_csv = calcular_soma_csv(linhas_csv)
            
            for termo, total in sorted(somas_csv.items()):
                log(f"   {termo}: R$ {total:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'), console=False)
            log("")
            
            # Processar linhas e gerar registros
            log("🔄 Processando linhas do CSV...")
            
            todos_registros = []
            
            for idx, linha in enumerate(linhas_csv, 1):
                registros_linha = processar_linha_csv(linha)
                
                if registros_linha:
                    todos_registros.extend(registros_linha)
                    log(f"   Linha {idx}/{len(linhas_csv)}: {linha['numero_termo']} - {linha['parcela_numero']} → {len(registros_linha)} registros", console=False)
            
            log("")
            log(f"   ✅ Total de registros a inserir: {len(todos_registros)}")
            log("")
            
            # Calcular soma dos registros a importar
            log("🧮 Calculando totais dos registros a importar...")
            somas_importados = calcular_soma_importados(todos_registros)
            
            for termo, total in sorted(somas_importados.items()):
                log(f"   {termo}: R$ {total:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'), console=False)
            log("")
            
            # Comparar somas (conferência)
            log("✅ CONFERÊNCIA DE SOMAS:")
            log("-" * 80)
            
            todos_termos = set(list(somas_csv.keys()) + list(somas_importados.keys()))
            diferencas_encontradas = False
            
            print("\n⚠️ MOSTRANDO APENAS DIVERGÊNCIAS NO CONSOLE (log completo em arquivo):\n")
            
            for termo in sorted(todos_termos):
                total_csv = somas_csv.get(termo, Decimal('0'))
                total_importado = somas_importados.get(termo, Decimal('0'))
                diferenca = total_csv - total_importado
                
                if diferenca == 0:
                    status = "✅ OK"
                    # Só registra no arquivo, não mostra no console
                    log(f"{status} | {termo}", console=False)
                    log(f"         CSV: R$ {total_csv:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'), console=False)
                    log(f"   Importado: R$ {total_importado:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'), console=False)
                    log("", console=False)
                else:
                    status = "⚠️ DIFERENÇA"
                    diferencas_encontradas = True
                    # Mostra no console E no arquivo
                    log(f"{status} | {termo}")
                    log(f"         CSV: R$ {total_csv:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
                    log(f"   Importado: R$ {total_importado:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
                    log(f"    Diferença: R$ {diferenca:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
                    log("")
            
            if diferencas_encontradas:
                log("⚠️ ATENÇÃO: Diferenças encontradas! Revise antes de prosseguir.")
                log("")
            else:
                print("✅ Nenhuma divergência encontrada! Todas as somas conferem.\n")
            
            # Confirmar importação
            log("=" * 80)
            resposta = input("\n⚠️ Deseja prosseguir com a importação? (S/N): ")
            
            if resposta.strip().upper() != 'S':
                log("❌ Importação cancelada pelo usuário")
                log_file.close()
                return
            
            log("\n🚀 Iniciando importação...")
            log("")
            
            # Inserir registros
            query_insert = """
                INSERT INTO gestao_financeira.ultra_liquidacoes_cronograma
                (info_alteracao, numero_termo, nome_mes, valor_mes, parcela_numero,
                 created_por, created_em, atualizado_por, atualizado_em)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (numero_termo, info_alteracao, nome_mes) DO NOTHING
            """
            
            registros_inseridos = 0
            registros_ignorados = 0
            
            for registro in todos_registros:
                cur.execute(query_insert, (
                    registro['info_alteracao'],
                    registro['numero_termo'],
                    registro['nome_mes'],
                    registro['valor_mes'],
                    registro['parcela_numero'],
                    registro['created_por'],
                    registro['created_em'],
                    registro['atualizado_por'],
                    registro['atualizado_em']
                ))
                
                if cur.rowcount == 1:
                    registros_inseridos += 1
                else:
                    registros_ignorados += 1
            
            # Commit
            conn.commit()
            
            log(f"✅ {registros_inseridos} registros inseridos com sucesso!")
            if registros_ignorados > 0:
                log(f"⏭️  {registros_ignorados} registros já existiam (mantidos sem alteração)")
            log("")
            log("=" * 80)
            log("IMPORTAÇÃO CONCLUÍDA COM SUCESSO!")
            log("=" * 80)
            log(f"Log salvo em: {ARQUIVO_LOG}")
            
        except Exception as e:
            conn.rollback()
            log(f"\n❌ ERRO durante a importação: {str(e)}")
            import traceback
            log("\nTraceback completo:")
            log(traceback.format_exc())
        
        finally:
            cur.close()
            conn.close()
            log_file.close()


if __name__ == '__main__':
    main()
