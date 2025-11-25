"""
Script para importar prazos de documentos do CSV para o banco de dados
Tabela: categoricas.c_documentos_dp_prazos
"""

import sys
import os
from pathlib import Path

# Adicionar diretório raiz ao path para importar módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor
import csv
from datetime import datetime
from config import DB_CONFIG


def importar_prazos_documentos():
    """
    Importa dados do CSV parcerias_documentos_prazos.csv para a tabela categoricas.c_documentos_dp_prazos
    """
    conn = None
    try:
        # Caminho do arquivo CSV
        csv_path = Path(__file__).parent.parent / 'docs' / 'prazos_temp.csv'
        
        if not csv_path.exists():
            print(f"[ERRO] Arquivo CSV não encontrado: {csv_path}")
            return False
        
        print(f"[INFO] Lendo arquivo: {csv_path}")
        
        # Conectar ao banco diretamente
        print(f"[INFO] Conectando ao banco de dados...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Limpar tabela antes de importar (opcional)
        print("[INFO] Limpando tabela categoricas.c_documentos_dp_prazos...")
        cur.execute("TRUNCATE TABLE categoricas.c_documentos_dp_prazos RESTART IDENTITY CASCADE")
        conn.commit()
        
        # Ler CSV
        registros_inseridos = 0
        with open(csv_path, 'r', encoding='utf-8') as file:
            # Usar ponto e vírgula como delimitador
            reader = csv.DictReader(file, delimiter=';')
            
            for row_num, row in enumerate(reader, start=2):  # Start at 2 to account for header
                tipo_documento = row.get('tipo_documento', '').strip()
                lei = row.get('lei', '').strip()
                prazo_dias_str = row.get('prazo_dias', '').strip()
                prazo_descricao = row.get('prazo_descricao', '').strip()
                
                print(f"[DEBUG] Linha {row_num}: tipo_documento='{tipo_documento}', lei='{lei}', prazo_dias='{prazo_dias_str}', prazo_descricao='{prazo_descricao}'")
                
                # Pular linhas vazias
                if not tipo_documento:
                    print(f"[AVISO] Linha {row_num} ignorada: tipo_documento vazio")
                    continue
                
                # Converter prazo_dias para inteiro
                prazo_dias = None
                if prazo_dias_str:
                    try:
                        prazo_dias = int(prazo_dias_str)
                    except ValueError:
                        print(f"[AVISO] Prazo inválido para '{tipo_documento}': '{prazo_dias_str}'")
                
                # Converter strings vazias para NULL
                lei = lei if lei else None
                prazo_descricao = prazo_descricao if prazo_descricao else None
                
                # Inserir registro
                cur.execute("""
                    INSERT INTO categoricas.c_documentos_dp_prazos 
                    (tipo_documento, lei, prazo_dias, prazo_descricao, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    tipo_documento,
                    lei,
                    prazo_dias,
                    prazo_descricao,
                    datetime.now()
                ))
                
                registros_inseridos += 1
                print(f"[OK] Inserido: {tipo_documento} - {lei} - {prazo_dias} dias")
        
        # Commit
        conn.commit()
        print(f"\n[SUCESSO] {registros_inseridos} registros importados com sucesso!")
        
        # Verificar quantidade de registros
        cur.execute("SELECT COUNT(*) as total FROM categoricas.c_documentos_dp_prazos")
        total = cur.fetchone()['total']
        print(f"[INFO] Total de registros na tabela: {total}")
        
        cur.close()
        return True
        
    except Exception as e:
        print(f"[ERRO] Erro ao importar dados: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    print("="*60)
    print("IMPORTAÇÃO DE PRAZOS DE DOCUMENTOS")
    print("="*60)
    
    sucesso = importar_prazos_documentos()
    
    if sucesso:
        print("\n✅ Importação concluída com sucesso!")
    else:
        print("\n❌ Falha na importação!")
        sys.exit(1)
