"""
Script para buscar um número de termo específico em todas as tabelas do banco de dados
que possuem a coluna 'numero_termo'
"""

import sys
import os
import psycopg2
import psycopg2.extras

# Adicionar o diretório pai ao path para importar config
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import DB_CONFIG

def buscar_termo_em_todas_tabelas(numero_termo):
    """
    Busca um número de termo em todas as tabelas que possuem a coluna numero_termo
    """
    print("=" * 80)
    print(f"BUSCANDO TERMO: {numero_termo}")
    print("=" * 80)
    print()
    
    # Conectar ao banco de dados
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Primeiro, buscar todas as tabelas que têm a coluna 'numero_termo'
    print("📋 Identificando tabelas com coluna 'numero_termo'...")
    print()
    
    query_tabelas = """
        SELECT 
            table_schema,
            table_name
        FROM information_schema.columns
        WHERE column_name = 'numero_termo'
        AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name
    """
    
    cur.execute(query_tabelas)
    tabelas = cur.fetchall()
    
    if not tabelas:
        print("❌ Nenhuma tabela encontrada com a coluna 'numero_termo'")
        cur.close()
        return
    
    print(f"✅ Encontradas {len(tabelas)} tabelas com coluna 'numero_termo':")
    for tab in tabelas:
        print(f"   - {tab['table_schema']}.{tab['table_name']}")
    print()
    print("-" * 80)
    print()
    
    # Agora buscar o termo em cada tabela
    encontrados = []
    nao_encontrados = []
    
    for tabela in tabelas:
        schema = tabela['table_schema']
        nome_tabela = tabela['table_name']
        tabela_completa = f"{schema}.{nome_tabela}"
        
        try:
            # Buscar registros que contenham o termo
            query_busca = f"""
                SELECT COUNT(*) as total
                FROM {tabela_completa}
                WHERE numero_termo = %s
            """
            
            cur.execute(query_busca, (numero_termo,))
            resultado = cur.fetchone()
            total = resultado['total']
            
            if total > 0:
                # Buscar mais detalhes sobre os registros
                query_detalhes = f"""
                    SELECT *
                    FROM {tabela_completa}
                    WHERE numero_termo = %s
                    LIMIT 5
                """
                cur.execute(query_detalhes, (numero_termo,))
                registros = cur.fetchall()
                
                encontrados.append({
                    'tabela': tabela_completa,
                    'total': total,
                    'registros': registros
                })
            else:
                nao_encontrados.append(tabela_completa)
                
        except Exception as e:
            print(f"⚠️  Erro ao buscar em {tabela_completa}: {e}")
            print()
    
    # Exibir resultados
    print("=" * 80)
    print("RESULTADOS DA BUSCA")
    print("=" * 80)
    print()
    
    if encontrados:
        print(f"✅ TERMO ENCONTRADO EM {len(encontrados)} TABELA(S):")
        print()
        
        for item in encontrados:
            print(f"📊 {item['tabela']}")
            print(f"   Total de registros: {item['total']}")
            print()
            print("   Primeiros registros encontrados:")
            for i, reg in enumerate(item['registros'], 1):
                print(f"   [{i}] Colunas do registro:")
                for coluna, valor in reg.items():
                    # Limitar o tamanho de valores muito longos
                    if isinstance(valor, str) and len(valor) > 100:
                        valor = valor[:100] + "..."
                    print(f"       {coluna}: {valor}")
                print()
            print("-" * 80)
            print()
    else:
        print("❌ TERMO NÃO ENCONTRADO em nenhuma tabela")
        print()
    
    if nao_encontrados:
        print(f"ℹ️  Tabelas verificadas sem resultado ({len(nao_encontrados)}):")
        for tab in nao_encontrados:
            print(f"   - {tab}")
        print()
    
    cur.close()
    conn.close()
    
    print("=" * 80)
    print("BUSCA CONCLUÍDA")
    print("=" * 80)


if __name__ == "__main__":
    # Número do termo a buscar
    termo = "TFM/214/2024/SMDHC/CPCA"
    
    buscar_termo_em_todas_tabelas(termo)
