"""
Script para importar datas de assinatura em public.parcerias_sei
Lê CSV com datas em formato PT-BR (dd/mm/yyyy) e atualiza coluna data_assinatura
Mapeia por ordem de ID: linha 2 do CSV → id=1, linha 3 → id=2, etc.
"""

import csv
import sys
import os
from datetime import datetime
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

def converter_data_ptbr(data_str):
    """
    Converte data de formato PT-BR (dd/mm/yyyy) para formato SQL (yyyy-mm-dd)
    Retorna None se string estiver vazia
    """
    if not data_str or data_str.strip() == '':
        return None
    
    try:
        # Parse dd/mm/yyyy
        data_obj = datetime.strptime(data_str.strip(), '%d/%m/%Y')
        # Retorna em formato SQL
        return data_obj.strftime('%Y-%m-%d')
    except ValueError as e:
        print(f"[ERRO] Formato de data inválido: '{data_str}' - {e}")
        return None


def importar_assinaturas():
    """
    Importa datas de assinatura do CSV para public.parcerias_sei
    """
    csv_path = r"C:\Users\d843702\Downloads\assinatura.csv"
    
    print("=" * 70)
    print("IMPORTAÇÃO DE DATAS DE ASSINATURA - public.parcerias_sei")
    print("=" * 70)
    print(f"Arquivo: {csv_path}")
    print(f"Encoding: UTF-8")
    print(f"Formato de data: dd/mm/yyyy (PT-BR)")
    print("-" * 70)
    
    # Verificar se arquivo existe
    if not os.path.exists(csv_path):
        print(f"\n[ERRO] Arquivo não encontrado: {csv_path}")
        return
    
    # Conectar ao banco diretamente
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_DATABASE', 'projeto_parcerias'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD')
    )
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    try:
        # Ler CSV
        datas = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            
            # Pular cabeçalho (linha 1)
            next(reader, None)
            
            # Ler todas as datas da coluna A (a partir de A2)
            for row in reader:
                if row:  # Se linha não está vazia
                    data_str = row[0] if len(row) > 0 else ''
                    data_sql = converter_data_ptbr(data_str)
                    datas.append(data_sql)
                else:
                    datas.append(None)
        
        print(f"\n✓ CSV lido com sucesso!")
        print(f"Total de linhas (excluindo cabeçalho): {len(datas)}")
        print(f"Datas válidas: {sum(1 for d in datas if d is not None)}")
        print(f"Células vazias (NULL): {sum(1 for d in datas if d is None)}")
        
        # Buscar todos os IDs existentes em ordem
        cur.execute("""
            SELECT id 
            FROM public.parcerias_sei 
            ORDER BY id
        """)
        ids = [row['id'] for row in cur.fetchall()]
        
        print(f"\nTotal de registros em parcerias_sei: {len(ids)}")
        
        if len(datas) > len(ids):
            print(f"\n[AVISO] CSV tem mais linhas ({len(datas)}) do que registros no banco ({len(ids)})")
            print("Importando apenas até o último ID disponível...")
            datas = datas[:len(ids)]
        
        # Atualizar registros
        print("\n" + "-" * 70)
        print("Iniciando atualização...")
        print("-" * 70)
        
        atualizados = 0
        nulos = 0
        
        for idx, (id_registro, data_sql) in enumerate(zip(ids, datas), start=1):
            if data_sql is None:
                # Atualizar para NULL
                cur.execute("""
                    UPDATE public.parcerias_sei
                    SET data_assinatura = NULL
                    WHERE id = %s
                """, (id_registro,))
                nulos += 1
                print(f"  ID {id_registro:3d} → NULL")
            else:
                # Atualizar com data
                cur.execute("""
                    UPDATE public.parcerias_sei
                    SET data_assinatura = %s
                    WHERE id = %s
                """, (data_sql, id_registro))
                atualizados += 1
                print(f"  ID {id_registro:3d} → {data_sql}")
        
        # Commit
        conn.commit()
        
        print("\n" + "=" * 70)
        print("IMPORTAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 70)
        print(f"Total processado: {atualizados + nulos}")
        print(f"  • Datas atualizadas: {atualizados}")
        print(f"  • NULLs inseridos: {nulos}")
        print("=" * 70)
        
    except Exception as e:
        import traceback
        print("\n" + "=" * 70)
        print("ERRO NA IMPORTAÇÃO")
        print("=" * 70)
        print(traceback.format_exc())
        conn.rollback()
        
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    importar_assinaturas()
