"""
Script de importação do CSV i_analises.csv para a tabela parcerias_analises
Importa para dois bancos de dados: local (localhost) e Railway
"""

import pandas as pd
import psycopg2
from datetime import datetime

# Configurações dos bancos de dados
DB_LOCAL = {
    'host': 'localhost',
    'port': '5432',
    'database': 'projeto_parcerias',
    'user': 'postgres',
    'password': 'Coração01'
}

DB_RAILWAY = {
    'host': 'shinkansen.proxy.rlwy.net',
    'port': '38157',
    'database': 'railway',
    'user': 'postgres',
    'password': 'sKOzVlsxAUcRIXXLynePvvHDQpXlmTVT'
}

CSV_PATH = r'C:\Users\d843702\i_analises.csv'


def parse_date(val):
    """
    Converte data do formato PT-BR (DD/MM/YYYY) para objeto date do Python
    Retorna None se o valor for vazio ou inválido
    """
    if pd.isnull(val) or str(val).strip() in ['', '-', 'nan']:
        return None
    try:
        val_str = str(val).strip()
        # Ignora datas inválidas como 00/01/1900
        if val_str.startswith('00/') or '/00/' in val_str:
            return None
        # Formato brasileiro: DD/MM/YYYY
        return datetime.strptime(val_str, '%d/%m/%Y').date()
    except Exception:
        # Retorna None silenciosamente para datas inválidas
        return None


def parse_float(val):
    """
    Converte valores numéricos do formato brasileiro para float
    Exemplo: 1.234,56 -> 1234.56 ou R$ 1.234,56 -> 1234.56
    Retorna None se vazio
    """
    if pd.isnull(val) or str(val).strip() in ['', '-', 'nan']:
        return None
    try:
        s = str(val).replace(' ', '').replace('\t', '').replace('\xa0', '').strip()
        # Remove R$ se existir
        s = s.replace('R$', '').strip()
        # Remove pontos de milhar e troca vírgula por ponto
        return float(s.replace('.', '').replace(',', '.'))
    except Exception as e:
        print(f"Erro ao converter número '{val}': {e}")
        return None


def parse_int(val):
    """
    Converte valores para inteiro
    Retorna None se vazio
    """
    if pd.isnull(val) or str(val).strip() in ['', '-', 'nan']:
        return None
    try:
        return int(float(str(val).strip()))
    except Exception as e:
        print(f"Erro ao converter inteiro '{val}': {e}")
        return None


def parse_boolean(val):
    """
    Converte valores para booleano
    Aceita: sim/não, s/n, true/false, 1/0, x/-
    Retorna False como padrão para NOT NULL
    """
    if pd.isnull(val) or str(val).strip() in ['', '-', 'nan']:
        return False
    
    val_str = str(val).strip().lower()
    
    # Valores verdadeiros
    if val_str in ['sim', 's', 'true', '1', 'x', 'yes', 'y']:
        return True
    
    # Valores falsos
    return False


def obter_lookups(conn):
    """
    Obtém os mapeamentos de nomes para IDs das tabelas categóricas
    """
    cursor = conn.cursor()
    
    # Lookup de responsabilidade_analise
    cursor.execute("SELECT id, nome_setor FROM categoricas.c_responsabilidade_analise")
    responsabilidade_map = {row[1].strip().lower(): row[0] for row in cursor.fetchall()}
    
    # Lookup de analistas
    cursor.execute("SELECT id, nome_analista FROM categoricas.c_analistas")
    analistas_map = {row[1].strip().lower(): row[0] for row in cursor.fetchall()}
    
    cursor.close()
    
    return {
        'responsabilidade': responsabilidade_map,
        'analistas': analistas_map
    }


def lookup_id(val, lookup_map, campo_nome):
    """
    Busca o ID correspondente ao valor no mapa de lookup
    Retorna None se não encontrar
    """
    if pd.isnull(val) or str(val).strip() in ['', '-', 'nan']:
        return None
    
    val_str = str(val).strip()
    
    # Se for um número, tenta usar diretamente como ID
    try:
        id_num = int(val_str)
        return id_num
    except ValueError:
        pass
    
    # Se não for número, busca pelo nome
    val_lower = val_str.lower()
    
    if val_lower in lookup_map:
        return lookup_map[val_lower]
    
    # Tenta busca parcial
    for key, id_val in lookup_map.items():
        if val_lower in key or key in val_lower:
            return id_val
    
    # Se não encontrou, não imprime aviso (para não poluir) e retorna None
    return None


def criar_tabela_se_nao_existir(conn):
    """
    Cria a tabela parcerias_analises se ela não existir
    """
    cursor = conn.cursor()
    
    # Remove a coluna origem_recurso se ela existir
    try:
        cursor.execute("""
            ALTER TABLE parcerias_analises 
            DROP COLUMN IF EXISTS origem_recurso
        """)
        conn.commit()
        print("Coluna origem_recurso removida (se existia)")
    except:
        pass
    
    # Cria a tabela se não existir
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parcerias_analises (
            id SERIAL PRIMARY KEY,
            tipo_prestacao VARCHAR(20) NOT NULL,
            numero_prestacao INTEGER NOT NULL,
            vigencia_inicial DATE NOT NULL,
            vigencia_final DATE NOT NULL,
            numero_termo VARCHAR(100),
            responsabilidade_analise INTEGER REFERENCES categoricas.c_responsabilidade_analise(id),
            entregue BOOLEAN NOT NULL,
            cobrado BOOLEAN NOT NULL,
            e_notificacao BOOLEAN NOT NULL,
            e_parecer BOOLEAN NOT NULL,
            e_fase_recursal BOOLEAN NOT NULL,
            e_encerramento BOOLEAN NOT NULL,
            data_parecer_dp DATE,
            valor_devolucao NUMERIC(15,2),
            valor_devolvido NUMERIC(15,2),
            responsavel_dp INTEGER REFERENCES categoricas.c_analistas(id),
            data_parecer_pg DATE,
            responsavel_pg VARCHAR(100),
            observacoes TEXT
        )
    """)
    
    conn.commit()
    cursor.close()
    print("Tabela verificada/criada com sucesso")


def limpar_tabela(conn):
    """
    Limpa todos os registros da tabela antes de importar
    """
    cursor = conn.cursor()
    cursor.execute("DELETE FROM parcerias_analises")
    conn.commit()
    cursor.close()
    print("Tabela limpa")


def importar_dados(conn, linhas, lookups):
    """
    Importa as linhas para o banco de dados
    """
    cursor = conn.cursor()
    sucesso = 0
    erros = 0
    
    for idx, linha in enumerate(linhas, 1):
        try:
            cursor.execute("""
                INSERT INTO parcerias_analises (
                    tipo_prestacao, numero_prestacao, vigencia_inicial, vigencia_final,
                    numero_termo, responsabilidade_analise, entregue, cobrado,
                    e_notificacao, e_parecer, e_fase_recursal, e_encerramento,
                    data_parecer_dp, valor_devolucao, valor_devolvido, responsavel_dp,
                    data_parecer_pg, responsavel_pg, observacoes
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                linha['tipo_prestacao'],
                linha['numero_prestacao'],
                linha['vigencia_inicial'],
                linha['vigencia_final'],
                linha['numero_termo'],
                linha['responsabilidade_analise'],
                linha['entregue'],
                linha['cobrado'],
                linha['e_notificacao'],
                linha['e_parecer'],
                linha['e_fase_recursal'],
                linha['e_encerramento'],
                linha['data_parecer_dp'],
                linha['valor_devolucao'],
                linha['valor_devolvido'],
                linha['responsavel_dp'],
                linha['data_parecer_pg'],
                linha['responsavel_pg'],
                linha['observacoes']
            ))
            sucesso += 1
        except Exception as e:
            conn.rollback()
            print(f"Erro ao inserir linha {idx}: {e}")
            print(f"  Dados: {linha}")
            erros += 1
            continue
    
    conn.commit()
    cursor.close()
    print(f"{sucesso} linhas importadas com sucesso")
    if erros > 0:
        print(f"{erros} linhas com erro")


def main():
    print("=" * 70)
    print("IMPORTAÇÃO DE ANÁLISES DE PRESTAÇÃO DE CONTAS")
    print("=" * 70)
    
    # Lê o CSV
    print(f"\nLendo CSV: {CSV_PATH}")
    try:
        df = pd.read_csv(CSV_PATH, encoding='utf-8', sep=';', dtype=str)
        print(f"CSV carregado: {len(df)} linhas encontradas")
        print(f"Colunas: {', '.join(df.columns)}")
    except Exception as e:
        print(f"Erro ao ler CSV: {e}")
        return
    
    # Conecta ao banco LOCAL para obter lookups
    print("\nObtendo tabelas de referência...")
    try:
        conn_temp = psycopg2.connect(**DB_LOCAL)
        lookups = obter_lookups(conn_temp)
        conn_temp.close()
        print(f"Responsabilidades: {len(lookups['responsabilidade'])} registros")
        print(f"Analistas: {len(lookups['analistas'])} registros")
    except Exception as e:
        print(f"Erro ao obter lookups: {e}")
        print("Continuando sem lookups (IDs de referência serão None)")
        lookups = {'responsabilidade': {}, 'analistas': {}}
    
    # Processa as linhas
    print("\nProcessando dados...")
    linhas = []
    erros = 0
    
    for idx, row in df.iterrows():
        try:
            # Processa responsabilidade_analise como ID
            responsabilidade_texto = row.get('responsabilidade_analise', '')
            responsabilidade_id = lookup_id(responsabilidade_texto, lookups['responsabilidade'], 'responsabilidade_analise')
            
            # Processa responsavel_dp como ID (analista)
            responsavel_dp_texto = row.get('responsavel_dp', '')
            responsavel_dp_id = lookup_id(responsavel_dp_texto, lookups['analistas'], 'responsavel_dp')
            
            linha = {
                'tipo_prestacao': str(row['tipo_prestacao']).strip() if not pd.isnull(row['tipo_prestacao']) else 'PC',
                'numero_prestacao': parse_int(row['numero_prestacao']),
                'vigencia_inicial': parse_date(row['vigencia_inicial']),
                'vigencia_final': parse_date(row['vigencia_final']),
                'numero_termo': str(row['numero_termo']).strip() if not pd.isnull(row['numero_termo']) else None,
                'responsabilidade_analise': responsabilidade_id,
                'entregue': parse_boolean(row['entregue']),
                'cobrado': parse_boolean(row['cobrado']),
                'e_notificacao': parse_boolean(row['e_notificacao']),
                'e_parecer': parse_boolean(row['e_parecer']),
                'e_fase_recursal': parse_boolean(row['e_fase_recursal']),
                'e_encerramento': parse_boolean(row['e_encerramento']),
                'data_parecer_dp': parse_date(row['data_parecer_dp']),
                'valor_devolucao': parse_float(row['valor_devolucao']),
                'valor_devolvido': parse_float(row['valor_devolvido']),
                'responsavel_dp': responsavel_dp_id,
                'data_parecer_pg': parse_date(row['data_parecer_pg']),
                'responsavel_pg': str(row['responsavel_pg']).strip() if not pd.isnull(row['responsavel_pg']) else None,
                'observacoes': str(row['observacoes']).strip() if not pd.isnull(row['observacoes']) else None
            }
            
            # Validação: campos NOT NULL
            if linha['numero_prestacao'] is None:
                print(f"Linha {idx + 2}: numero_prestacao é obrigatório, pulando...")
                erros += 1
                continue
            if linha['vigencia_inicial'] is None or linha['vigencia_final'] is None:
                print(f"Linha {idx + 2}: vigencia_inicial e vigencia_final são obrigatórias, pulando...")
                erros += 1
                continue
            
            linhas.append(linha)
        except Exception as e:
            print(f"Erro ao processar linha {idx + 2}: {e}")
            erros += 1
    
    print(f"{len(linhas)} linhas processadas com sucesso")
    if erros > 0:
        print(f"{erros} linhas com erro")
    
    if len(linhas) == 0:
        print("Nenhuma linha válida para importar!")
        return
    
    # Importa para o banco LOCAL - COMENTADO (já importado)
    # print("\n" + "=" * 70)
    # print("IMPORTANDO PARA BANCO LOCAL (localhost)")
    # print("=" * 70)
    # try:
    #     conn_local = psycopg2.connect(**DB_LOCAL)
    #     print("Conectado ao banco local")
    #     criar_tabela_se_nao_existir(conn_local)
    #     limpar_tabela(conn_local)
    #     importar_dados(conn_local, linhas, lookups)
    #     conn_local.close()
    #     print("Importação local concluída!")
    # except Exception as e:
    #     print(f"Erro na importação local: {e}")
    #     import traceback
    #     traceback.print_exc()
    
    # Importa para o banco RAILWAY
    print("\n" + "=" * 70)
    print("IMPORTANDO PARA BANCO RAILWAY")
    print("=" * 70)
    try:
        conn_railway = psycopg2.connect(**DB_RAILWAY)
        print("Conectado ao banco Railway")
        # Obtém lookups do Railway também
        lookups_railway = obter_lookups(conn_railway)
        criar_tabela_se_nao_existir(conn_railway)
        limpar_tabela(conn_railway)
        importar_dados(conn_railway, linhas, lookups_railway)
        conn_railway.close()
        print("Importação Railway concluída!")
    except Exception as e:
        print(f"Erro na importação Railway: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("IMPORTAÇÃO FINALIZADA!")
    print("=" * 70)


if __name__ == "__main__":
    main()
