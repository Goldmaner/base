"""
Script de importação de pesquisas de parcerias do CSV para o banco de dados
Tabela: public.o_pesquisa_parcerias

Autor: Sistema FAF
Data: Novembro 2025
"""

import csv
import psycopg2
from datetime import datetime
import os
import sys

# Adicionar o diretório raiz ao path para importar db
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from db import get_cursor, get_db


def limpar_cnpj(cnpj):
    """Remove formatação do CNPJ, mantendo apenas números"""
    return cnpj.replace('.', '').replace('/', '').replace('-', '').strip()


def formatar_cnpj(cnpj):
    """Formata CNPJ no padrão XX.XXX.XXX/XXXX-XX"""
    cnpj_limpo = limpar_cnpj(cnpj)
    if len(cnpj_limpo) != 14:
        return cnpj  # Retorna original se não tiver 14 dígitos
    return f"{cnpj_limpo[:2]}.{cnpj_limpo[2:5]}.{cnpj_limpo[5:8]}/{cnpj_limpo[8:12]}-{cnpj_limpo[12:]}"


def buscar_osc_por_cnpj(cnpj, cursor):
    """
    Busca o nome da OSC na tabela public.parcerias usando o CNPJ
    Retorna (nome_osc, encontrado)
    """
    try:
        # Tentar com CNPJ formatado
        cnpj_formatado = formatar_cnpj(cnpj)
        
        query = """
            SELECT DISTINCT osc 
            FROM public.parcerias 
            WHERE cnpj = %s
            LIMIT 1
        """
        
        cursor.execute(query, (cnpj_formatado,))
        resultado = cursor.fetchone()
        
        if resultado and resultado['osc']:
            return resultado['osc'], True
        
        # Tentar com CNPJ sem formatação
        cnpj_limpo = limpar_cnpj(cnpj)
        cursor.execute(query, (cnpj_limpo,))
        resultado = cursor.fetchone()
        
        if resultado and resultado['osc']:
            return resultado['osc'], True
        
        return None, False
        
    except Exception as e:
        print(f"[ERRO] Erro ao buscar OSC para CNPJ {cnpj}: {str(e)}")
        return None, False


def determinar_emissor(numero_pesquisa):
    """
    Determina o emissor baseado no número da pesquisa
    1-44: Thays Rocha
    45-69: Maira Mihara
    """
    if numero_pesquisa <= 44:
        return "Thays Rocha"
    else:
        return "Maira Mihara"


def converter_data(data_str):
    """
    Converte data de DD/MM/YYYY para datetime
    """
    try:
        return datetime.strptime(data_str, '%d/%m/%Y')
    except Exception as e:
        print(f"[ERRO] Erro ao converter data '{data_str}': {str(e)}")
        return None


def importar_pesquisas(arquivo_csv):
    """
    Importa pesquisas do CSV para o banco de dados
    """
    print("=" * 80)
    print("IMPORTAÇÃO DE PESQUISAS DE PARCERIAS")
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
        with open(arquivo_csv, 'r', encoding='utf-8-sig') as f:  # utf-8-sig remove o BOM
            # Ler com separador ponto-e-vírgula
            reader = csv.DictReader(f, delimiter=';')
            
            pesquisas = list(reader)
            total = len(pesquisas)
            
            print(f"[INFO] Arquivo CSV lido: {total} registro(s) encontrado(s)")
            print()
            
    except Exception as e:
        print(f"[ERRO] Erro ao ler arquivo CSV: {str(e)}")
        return False
    
    # Processar cada registro
    importadas = 0
    erros = 0
    
    for idx, row in enumerate(pesquisas, start=1):
        try:
            numero_pesquisa = int(row['numero_pesquisa'])
            cnpj = row['cnpj'].strip()
            data_str = row['criado_em'].strip()
            
            # Converter data
            criado_em = converter_data(data_str)
            if not criado_em:
                print(f"[ERRO] Linha {idx}: Data inválida '{data_str}'")
                erros += 1
                continue
            
            # Buscar OSC
            nome_osc, osc_identificada = buscar_osc_por_cnpj(cnpj, cur)
            
            if not osc_identificada:
                print(f"[AVISO] Pesquisa {numero_pesquisa}: CNPJ {cnpj} não encontrado na base")
                nome_osc = None  # Será NULL no banco
            
            # Determinar emissor
            nome_emissor = determinar_emissor(numero_pesquisa)
            
            # Formatar CNPJ para inserção
            cnpj_formatado = formatar_cnpj(cnpj)
            
            # Inserir no banco
            query = """
                INSERT INTO public.o_pesquisa_parcerias 
                (numero_pesquisa, sei_informado, nome_osc, nome_emissor, criado_em, 
                 osc_identificada, cnpj, respondido, obs)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
            """
            
            cur.execute(query, (
                numero_pesquisa,
                None,  # sei_informado (NULL por enquanto)
                nome_osc,
                nome_emissor,
                criado_em,
                osc_identificada,
                cnpj_formatado,
                None,  # respondido (NULL por enquanto)
                None   # obs (NULL por enquanto)
            ))
            
            importadas += 1
            
            # Log de progresso
            status = "✓ ENCONTRADA" if osc_identificada else "✗ NÃO ENCONTRADA"
            print(f"[{idx}/{total}] Pesquisa {numero_pesquisa} | {nome_emissor} | {cnpj_formatado} | {status}")
            if osc_identificada and nome_osc:
                print(f"        OSC: {nome_osc}")
            
        except Exception as e:
            print(f"[ERRO] Linha {idx}: {str(e)}")
            erros += 1
            continue
    
    # Commit das alterações
    try:
        get_db().commit()
        print()
        print("=" * 80)
        print(f"[SUCESSO] Importação concluída!")
        print(f"[INFO] Total de registros: {total}")
        print(f"[INFO] Importadas com sucesso: {importadas}")
        print(f"[INFO] Erros: {erros}")
        print("=" * 80)
        
        # Estatísticas
        cur.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN osc_identificada = true THEN 1 END) as encontradas,
                COUNT(CASE WHEN osc_identificada = false THEN 1 END) as nao_encontradas
            FROM public.o_pesquisa_parcerias
        """)
        stats = cur.fetchone()
        
        print()
        print("ESTATÍSTICAS DA TABELA:")
        print(f"- Total de pesquisas: {stats['total']}")
        print(f"- OSCs encontradas: {stats['encontradas']}")
        print(f"- OSCs não encontradas: {stats['nao_encontradas']}")
        
        cur.close()
        return True
        
    except Exception as e:
        print(f"[ERRO] Erro ao fazer commit: {str(e)}")
        get_db().rollback()
        return False


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
        'import_pesquisas.csv'
    )
    
    if not os.path.exists(arquivo_csv):
        print(f"[ERRO] Arquivo não encontrado: {arquivo_csv}")
        return
    
    print(f"[INFO] Arquivo CSV: {arquivo_csv}")
    print()
    
    # Confirmar importação
    resposta = input("Deseja prosseguir com a importação? (s/n): ")
    if resposta.lower() != 's':
        print("[INFO] Importação cancelada pelo usuário")
        return
    
    print()
    
    # Executar importação dentro do contexto Flask
    with app.app_context():
        sucesso = importar_pesquisas(arquivo_csv)
    
    if sucesso:
        print()
        print("[OK] Importação finalizada com sucesso!")
    else:
        print()
        print("[ERRO] Importação finalizada com erros")


if __name__ == '__main__':
    main()
