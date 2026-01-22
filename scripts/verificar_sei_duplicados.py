"""
Script para identificar SEI duplicados em public.parcerias_sei
Gera CSV com todos os registros que possuem termo_sei_doc duplicado
"""

import psycopg2
import psycopg2.extras
import csv
from datetime import datetime
import sys
import os

# Adicionar diretório pai ao path para importar config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_CONFIG


def verificar_sei_duplicados():
    """
    Identifica termo_sei_doc duplicados e exporta para CSV
    Também gera query DELETE para duplicatas exatas (todos os campos iguais)
    """
    try:
        # Conectar ao banco
        print("Conectando ao banco de dados...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # === PARTE 1: DUPLICATAS EXATAS (todos os campos iguais) ===
        print("\n" + "="*80)
        print("PARTE 1: BUSCANDO DUPLICATAS EXATAS (todos os campos iguais)...")
        print("="*80)
        
        cur.execute("""
            WITH duplicatas AS (
                SELECT 
                    numero_termo,
                    termo_sei_doc,
                    data_assinatura,
                    aditamento,
                    apostilamento,
                    COUNT(*) as total,
                    ARRAY_AGG(id ORDER BY id) as ids
                FROM public.parcerias_sei
                GROUP BY numero_termo, termo_sei_doc, data_assinatura, aditamento, apostilamento
                HAVING COUNT(*) > 1
            )
            SELECT * FROM duplicatas
            ORDER BY total DESC
        """)
        
        duplicatas_exatas = cur.fetchall()
        
        if duplicatas_exatas:
            # Gerar arquivo SQL com comandos DELETE
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            arquivo_sql = f"delete_duplicatas_exatas_{timestamp}.sql"
            
            total_ids_para_excluir = 0
            ids_para_excluir = []
            
            with open(arquivo_sql, 'w', encoding='utf-8') as sqlfile:
                sqlfile.write("-- Script de exclusão de duplicatas exatas em public.parcerias_sei\n")
                sqlfile.write(f"-- Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
                sqlfile.write("-- ATENÇÃO: Mantém o registro com menor ID, exclui os demais\n\n")
                sqlfile.write("BEGIN;\n\n")
                
                for dup in duplicatas_exatas:
                    ids_list = dup['ids']
                    # Manter o primeiro ID (menor), excluir os demais
                    ids_excluir = ids_list[1:]
                    ids_para_excluir.extend(ids_excluir)
                    total_ids_para_excluir += len(ids_excluir)
                    
                    sqlfile.write(f"-- Duplicata: Termo={dup['numero_termo']}, SEI={dup['termo_sei_doc']}, Aditamento={dup['aditamento']}\n")
                    sqlfile.write(f"-- Total de registros: {dup['total']} | Mantendo ID {ids_list[0]}, excluindo IDs: {ids_excluir}\n")
                    
                    if ids_excluir:
                        ids_str = ','.join(map(str, ids_excluir))
                        sqlfile.write(f"DELETE FROM public.parcerias_sei WHERE id IN ({ids_str});\n\n")
                
                sqlfile.write("COMMIT;\n")
                sqlfile.write(f"\n-- Total de registros a excluir: {total_ids_para_excluir}\n")
            
            print(f"\n📄 DUPLICATAS EXATAS ENCONTRADAS:")
            print(f"   Total de grupos duplicados: {len(duplicatas_exatas)}")
            print(f"   Total de registros a excluir: {total_ids_para_excluir}")
            print(f"   ✅ Arquivo SQL gerado: {arquivo_sql}")
            print(f"\n⚠️  IMPORTANTE: Revise o arquivo SQL antes de executar!")
            
        else:
            print("\n✅ Nenhuma duplicata exata encontrada!")
        
        # === PARTE 2: DUPLICATAS EM TERMOS DIFERENTES ===
        print("\n" + "="*80)
        print("PARTE 2: BUSCANDO SEI DUPLICADOS EM TERMOS DIFERENTES...")
        print("="*80)
        
        # Query para encontrar SEI duplicados EM TERMOS DIFERENTES
        print("\nBuscando termo_sei_doc duplicados em termos diferentes...")
        cur.execute("""
            SELECT 
                ps.*,
                dup.total_duplicatas,
                dup.total_termos_diferentes,
                dup.termos_afetados
            FROM public.parcerias_sei ps
            INNER JOIN (
                SELECT 
                    termo_sei_doc,
                    COUNT(*) as total_duplicatas,
                    COUNT(DISTINCT numero_termo) as total_termos_diferentes,
                    STRING_AGG(DISTINCT numero_termo, ', ' ORDER BY numero_termo) as termos_afetados
                FROM public.parcerias_sei
                WHERE termo_sei_doc IS NOT NULL 
                  AND termo_sei_doc != '' 
                  AND termo_sei_doc != '-'
                GROUP BY termo_sei_doc
                HAVING COUNT(DISTINCT numero_termo) > 1
            ) dup ON ps.termo_sei_doc = dup.termo_sei_doc
            ORDER BY dup.total_termos_diferentes DESC, ps.termo_sei_doc, ps.numero_termo
        """)
        
        resultados = cur.fetchall()
        
        if not resultados:
            print("\n✅ Nenhum SEI duplicado encontrado!")
            cur.close()
            conn.close()
            return
        
        # Gerar nome do arquivo CSV com timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        arquivo_csv = f"sei_duplicados_{timestamp}.csv"
        
        # Obter nomes das colunas
        colunas = list(resultados[0].keys())
        
        # Escrever CSV
        print(f"\nExportando {len(resultados)} registros para {arquivo_csv}...")
        with open(arquivo_csv, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=colunas, delimiter=';')
            writer.writeheader()
            
            for row in resultados:
                # Converter valores None para string vazia
                row_limpa = {k: (v if v is not None else '') for k, v in row.items()}
                writer.writerow(row_limpa)
        
        # Estatísticas
        sei_unicos = set(r['termo_sei_doc'] for r in resultados)
        
        print(f"\n{'='*80}")
        print("📊 RESUMO DOS SEI DUPLICADOS (EM TERMOS DIFERENTES)")
        print(f"{'='*80}")
        print(f"Total de registros duplicados: {len(resultados)}")
        print(f"Total de SEI únicos duplicados: {len(sei_unicos)}")
        print(f"⚠️  Apenas SEI que aparecem em termos DIFERENTES")
        print(f"✅ Excluídos: duplicatas no mesmo termo e SEI com valor '-'")
        print(f"\n{'='*80}")
        print("DETALHAMENTO:")
        print(f"{'='*80}")
        
        # Agrupar por SEI para mostrar detalhes
        sei_agrupado = {}
        for r in resultados:
            sei = r['termo_sei_doc']
            if sei not in sei_agrupado:
                sei_agrupado[sei] = []
            sei_agrupado[sei].append(r)
        
        for sei, registros in sorted(sei_agrupado.items()):
            termos_unicos = set(r['numero_termo'] for r in registros)
            print(f"\n📄 SEI: {sei} ({len(registros)} registros em {len(termos_unicos)} termos diferentes)")
            for i, reg in enumerate(registros, 1):
                print(f"   {i}. Termo: {reg.get('numero_termo', 'N/A')}")
                print(f"      Tipo Doc: {reg.get('tipo_documento', 'N/A')}")
                print(f"      Aditamento: {reg.get('aditamento', 'N/A')}")
                print(f"      Data: {reg.get('data_assinatura_sei', 'N/A')}")
        
        print(f"\n{'='*80}")
        print(f"✅ Arquivo gerado: {arquivo_csv}")
        print(f"{'='*80}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"\n❌ ERRO: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("="*80)
    print("VERIFICADOR DE SEI DUPLICADOS - public.parcerias_sei")
    print("="*80)
    verificar_sei_duplicados()
