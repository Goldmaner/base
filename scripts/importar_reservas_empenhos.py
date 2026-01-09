"""
Script para importar dados de reservas e empenhos de CSV para o banco de dados.
Apaga todos os dados existentes e reimporta do arquivo CSV.

Uso: python scripts/importar_reservas_empenhos.py
"""

import csv
import sys
import os
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

# Adicionar o diretório raiz ao path para importar módulos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import DB_CONFIG

# Caminho do arquivo CSV
CSV_FILE = r"C:\Users\d843702\Downloads\reservas_empenhos.csv"

def converter_data(data_str):
    """
    Converte data do formato pt-BR (dd/mm/yy ou dd/mm/yyyy) para objeto date.
    Retorna None se a string estiver vazia ou inválida.
    """
    if not data_str or data_str.strip() == '':
        return None
    
    try:
        # Remover espaços
        data_str = data_str.strip()
        
        # Tentar formato dd/mm/yyyy
        if len(data_str.split('/')[-1]) == 4:
            return datetime.strptime(data_str, '%d/%m/%Y').date()
        else:
            # Formato dd/mm/yy
            return datetime.strptime(data_str, '%d/%m/%y').date()
    except Exception as e:
        print(f"⚠️  Erro ao converter data '{data_str}': {e}")
        return None

def converter_numero(numero_str):
    """
    Converte número do formato pt-BR (1.234,56) para float.
    Retorna None se a string estiver vazia ou inválida.
    """
    if not numero_str or numero_str.strip() == '':
        return None
    
    try:
        # Remover espaços e substituir separadores
        numero_str = numero_str.strip()
        numero_str = numero_str.replace('.', '')  # Remover separador de milhares
        numero_str = numero_str.replace(',', '.')  # Trocar vírgula decimal por ponto
        return float(numero_str)
    except Exception as e:
        print(f"⚠️  Erro ao converter número '{numero_str}': {e}")
        return None

def get_connection():
    """Cria conexão direta com o banco de dados."""
    return psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        database=DB_CONFIG['database'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password']
    )

def limpar_tabela(cur):
    """Apaga todos os dados da tabela antes de importar."""
    print("🗑️  Limpando dados existentes...")
    cur.execute("TRUNCATE TABLE gestao_financeira.temp_reservas_empenhos RESTART IDENTITY CASCADE;")
    print("✅ Tabela limpa com sucesso!")

def importar_csv():
    """Função principal de importação."""
    print("=" * 70)
    print("📊 IMPORTAÇÃO DE RESERVAS E EMPENHOS")
    print("=" * 70)
    
    # Verificar se o arquivo existe
    if not os.path.exists(CSV_FILE):
        print(f"❌ Erro: Arquivo não encontrado: {CSV_FILE}")
        return False
    
    print(f"📁 Arquivo: {CSV_FILE}")
    
    conn = None
    try:
        # Conectar ao banco de dados
        conn = get_connection()
        cur = conn.cursor()
        
        # Limpar tabela existente
        limpar_tabela(cur)
        
        # Abrir CSV com encoding adequado
        encodings = ['utf-8', 'cp1252', 'latin-1', 'iso-8859-1']
        csv_data = None
        
        for encoding in encodings:
            try:
                with open(CSV_FILE, 'r', encoding=encoding) as f:
                    csv_data = f.read()
                print(f"✅ Arquivo lido com encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue
        
        if csv_data is None:
            print("❌ Erro: Não foi possível ler o arquivo com nenhum encoding conhecido")
            return False
        
        # Processar CSV
        linhas = csv_data.split('\n')
        reader = csv.DictReader(linhas, delimiter=';')
        
        # Verificar cabeçalho
        print(f"\n📋 Colunas encontradas: {reader.fieldnames}")
        
        registros_inseridos = 0
        registros_erro = 0
        
        # Query de inserção
        insert_query = """
            INSERT INTO gestao_financeira.temp_reservas_empenhos 
            (numero_termo, vigencia_inicial, vigencia_final, aditivo, numero_parcela, 
             tipo_parcela, elemento_23, elemento_24, parcela_total_previsto, observacao)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        print("\n📥 Importando registros...")
        
        for idx, row in enumerate(reader, start=2):  # Linha 2 pois linha 1 é cabeçalho
            try:
                # Limpar BOM character se presente nas chaves
                row_clean = {}
                for key, value in row.items():
                    clean_key = key.replace('\ufeff', '').strip() if key else key
                    row_clean[clean_key] = value
                
                # Extrair e converter dados
                vigencia_inicial = converter_data(row_clean.get('Vigência Inicial', ''))
                vigencia_final = converter_data(row_clean.get('Vigência Final', ''))
                aditivo = row_clean.get('Aditivo', '').strip() or None
                numero_termo = row_clean.get('Termos', '').strip() or None
                tipo_parcela = row_clean.get('Tipo de Parcela', '').strip() or None
                numero_parcela = row_clean.get('Número da Parcela', '').strip() or None
                
                # Converter valo_clean.get('Observação', '') or row_clean
                elemento_23 = converter_numero(row_clean.get('53.23 (Outras Despesas)', ''))
                elemento_24 = converter_numero(row_clean.get('53.24 (Pessoal / Recursos Humanos)', ''))
                parcela_total = converter_numero(row_clean.get('Valor Previsto', ''))
                
                # Observação (se existir coluna)
                observacao = row.get('Observação', '') or row.get('Observacao', '') or None
                
                # Pular linhas vazias
                if not numero_termo and not numero_parcela:
                    continue
                
                # Inserir no banco
                cur.execute(insert_query, (
                    numero_termo,
                    vigencia_inicial,
                    vigencia_final,
                    aditivo,
                    numero_parcela,
                    tipo_parcela,
                    elemento_23,
                    elemento_24,
                    parcela_total,
                    observacao
                ))
                
                registros_inseridos += 1
                
                # Mostrar progresso a cada 10 registros
                if registros_inseridos % 10 == 0:
                    print(f"  ✓ {registros_inseridos} registros importados...")
            
            except Exception as e:
                registros_erro += 1
                print(f"  ❌ Erro na linha {idx}: {e}")
                print(f"     Dados: {row}")
        
        # Commit das transações
        conn.commit()
        
        # Resumo
        print("\n" + "=" * 70)
        print("📊 RESUMO DA IMPORTAÇÃO")
        print("=" * 70)
        print(f"✅ Registros importados com sucesso: {registros_inseridos}")
        if registros_erro > 0:
            print(f"⚠️  Registros com erro: {registros_erro}")
        print("=" * 70)
        
        return True
    
    except Exception as e:
        print(f"\n❌ Erro durante importação: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        return False
    
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == '__main__':
    print("\n🚀 Iniciando importação...\n")
    sucesso = importar_csv()
    
    if sucesso:
        print("\n✅ Importação concluída com sucesso!\n")
        sys.exit(0)
    else:
        print("\n❌ Importação falhou. Verifique os erros acima.\n")
        sys.exit(1)
