# Script para importar dados de documentos SEI do CSV para a tabela parcerias_sei
# Tabela: public.parcerias_sei
# CSV: C:/Users/d843702/Downloads/documentos_sei.csv
# Formato: UTF-8, separado por ponto-e-vírgula (;)
# 
# Mapeamento de colunas:
# - Termos → numero_termo
# - SEI do Documento → termo_sei_doc
# - Nº do Aditamento → aditamento
# - Nº do Apostilamento → apostilamento

import csv
import sys
import os
from pathlib import Path

# Adicionar o diretório raiz ao path para importar config
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from config import DB_CONFIG


def get_connection():
    """
    Cria conexão direta com PostgreSQL usando psycopg2
    """
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        print(f"✓ Conectado ao banco: {DB_CONFIG['database']}")
        return conn
    except Exception as e:
        print(f"✗ Erro ao conectar ao banco: {e}")
        sys.exit(1)


def limpar_tabela(conn):
    """
    Limpa a tabela parcerias_sei antes da importação
    """
    try:
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE public.parcerias_sei RESTART IDENTITY CASCADE;")
        conn.commit()
        print("✓ Tabela parcerias_sei limpa com sucesso")
    except Exception as e:
        print(f"✗ Erro ao limpar tabela: {e}")
        conn.rollback()
        raise


def importar_csv(caminho_csv):
    """
    Importa dados do CSV para a tabela parcerias_sei
    
    Args:
        caminho_csv: Caminho completo do arquivo CSV
    """
    if not os.path.exists(caminho_csv):
        print(f"✗ Arquivo não encontrado: {caminho_csv}")
        sys.exit(1)
    
    print(f"\n📂 Arquivo: {caminho_csv}")
    
    # Conectar ao banco
    conn = get_connection()
    
    # Limpar tabela antes de importar
    limpar_tabela(conn)
    
    # Contadores
    total_linhas = 0
    importadas = 0
    erros = 0
    
    try:
        # Detectar encoding (tentar UTF-8 com BOM primeiro, depois UTF-8 puro)
        encodings = ['utf-8-sig', 'utf-8', 'latin-1', 'cp1252']
        file_content = None
        encoding_usado = None
        
        for enc in encodings:
            try:
                with open(caminho_csv, 'r', encoding=enc) as test_file:
                    file_content = test_file.read()
                    encoding_usado = enc
                    print(f"✓ Encoding detectado: {enc}")
                    break
            except UnicodeDecodeError:
                continue
        
        if not file_content:
            print("✗ Não foi possível detectar o encoding do arquivo")
            sys.exit(1)
        
        # Processar CSV
        from io import StringIO
        csv_reader = csv.DictReader(StringIO(file_content), delimiter=';')
        
        cursor = conn.cursor()
        
        # Mapeamento de colunas do CSV para banco
        # CSV: Termos, SEI do Documento, Nº do Aditamento, Nº do Apostilamento
        # Banco: numero_termo, termo_sei_doc, aditamento, apostilamento
        
        print("\n🔄 Iniciando importação...")
        print("-" * 80)
        
        for idx, row in enumerate(csv_reader, start=1):
            total_linhas += 1
            
            try:
                # Limpar chaves do BOM character se presente
                clean_row = {}
                for key, value in row.items():
                    clean_key = key.replace('\ufeff', '').strip()
                    # Tratar None e valores vazios
                    if value is None or (isinstance(value, str) and value.strip() == ''):
                        clean_row[clean_key] = '-'
                    else:
                        clean_row[clean_key] = value.strip()
                
                # Extrair dados do CSV
                numero_termo = clean_row.get('Termos', '-')
                termo_sei_doc = clean_row.get('SEI do Documento', '-')
                aditamento = clean_row.get('Nº do Aditamento', '-')
                apostilamento = clean_row.get('Nº do Apostilamento', '-')
                
                # Converter "-" para None se preferir NULL no banco, ou manter "-"
                # Aqui vou manter "-" conforme solicitado
                
                # Validação básica - ao menos numero_termo deve existir e não ser só "-"
                if not numero_termo or numero_termo == '-':
                    print(f"⚠ Linha {idx}: Termo vazio ou inválido, pulando...")
                    erros += 1
                    continue
                
                # Truncar valores se necessário para caber nos VARCHAR
                if termo_sei_doc and len(termo_sei_doc) > 12:
                    print(f"⚠ Linha {idx}: SEI truncado de {len(termo_sei_doc)} para 12 caracteres")
                    termo_sei_doc = termo_sei_doc[:12]
                
                if aditamento and len(aditamento) > 2:
                    print(f"⚠ Linha {idx}: Aditamento truncado de {len(aditamento)} para 2 caracteres")
                    aditamento = aditamento[:2]
                
                if apostilamento and len(apostilamento) > 2:
                    print(f"⚠ Linha {idx}: Apostilamento truncado de {len(apostilamento)} para 2 caracteres")
                    apostilamento = apostilamento[:2]
                
                if numero_termo and len(numero_termo) > 80:
                    print(f"⚠ Linha {idx}: Número do termo truncado de {len(numero_termo)} para 80 caracteres")
                    numero_termo = numero_termo[:80]
                
                # Inserir no banco
                sql = """
                    INSERT INTO public.parcerias_sei 
                    (numero_termo, termo_sei_doc, aditamento, apostilamento)
                    VALUES (%s, %s, %s, %s)
                """
                
                cursor.execute(sql, (
                    numero_termo,
                    termo_sei_doc,
                    aditamento,
                    apostilamento
                ))
                
                importadas += 1
                
                # Log a cada 10 registros
                if importadas % 10 == 0:
                    print(f"✓ Importados: {importadas} registros...")
                
            except Exception as e:
                erros += 1
                print(f"✗ Erro na linha {idx}: {e}")
                print(f"   Dados: {clean_row}")
                conn.rollback()
                continue
        
        # Commit final
        conn.commit()
        
        print("-" * 80)
        print(f"\n📊 Resumo da Importação:")
        print(f"   Total de linhas processadas: {total_linhas}")
        print(f"   ✓ Importadas com sucesso: {importadas}")
        print(f"   ✗ Erros: {erros}")
        print(f"   Taxa de sucesso: {(importadas/total_linhas*100) if total_linhas > 0 else 0:.1f}%")
        
    except Exception as e:
        print(f"\n✗ Erro geral durante importação: {e}")
        conn.rollback()
        raise
    
    finally:
        cursor.close()
        conn.close()
        print("\n✓ Conexão com banco encerrada")


if __name__ == '__main__':
    print("=" * 80)
    print("IMPORTAÇÃO DE DOCUMENTOS SEI")
    print("=" * 80)
    
    # Caminho do CSV
    caminho_csv = r"C:\Users\d843702\Downloads\documentos_sei.csv"
    
    try:
        importar_csv(caminho_csv)
        print("\n✅ Importação concluída com sucesso!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Falha na importação: {e}")
        sys.exit(1)
