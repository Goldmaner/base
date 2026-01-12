"""
Script para preencher a coluna 'portaria' da tabela public.parcerias
Preenche apenas valores NULL seguindo regras de legislação por período
"""

import sys
import os
from pathlib import Path

# Adicionar diretório raiz ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from config import DB_CONFIG


def preencher_portarias():
    """
    Preenche coluna portaria em public.parcerias onde portaria IS NULL
    """
    conn = None
    try:
        print("="*70)
        print("PREENCHIMENTO DE PORTARIAS - public.parcerias")
        print("="*70)
        
        # Conectar ao banco
        print("\n[INFO] Conectando ao banco de dados...")
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # Contar registros com portaria NULL
        cur.execute("SELECT COUNT(*) as total FROM parcerias WHERE portaria IS NULL")
        total_null = cur.fetchone()['total']
        print(f"[INFO] Registros com portaria NULL: {total_null}")
        
        if total_null == 0:
            print("[INFO] Nenhum registro para processar!")
            return True
        
        # Contadores por caso
        caso1_count = 0  # Portaria nº 072/SMPP/2012
        caso2_count = 0  # Portaria nº 006/2008/SF-SEMPLA
        caso3_count = 0  # Decreto nº 6.170
        caso4_count = 0  # Portaria nº 009/SMDHC/2014
        
        print("\n[INFO] Processando registros...\n")
        
        # CASO 1: TCV + FUMCAD + início entre 22/03/2012 e 21/05/2014
        print("─" * 70)
        print("CASO 1: TCV + FUMCAD + início entre 22/03/2012 e 21/05/2014")
        print("        → Portaria nº 072/SMPP/2012")
        print("─" * 70)
        
        cur.execute("""
            UPDATE parcerias
            SET portaria = 'Portaria nº 072/SMPP/2012'
            WHERE portaria IS NULL
            AND numero_termo ILIKE '%TCV%'
            AND numero_termo ILIKE '%FUMCAD%'
            AND inicio >= '2012-03-22'
            AND inicio <= '2014-05-21'
        """)
        caso1_count = cur.rowcount
        conn.commit()
        print(f"✅ Atualizados: {caso1_count} registros\n")
        
        # CASO 4: TCV + FUMCAD + início entre 22/05/2014 e 30/09/2017
        print("─" * 70)
        print("CASO 4: TCV + FUMCAD + início entre 22/05/2014 e 30/09/2017")
        print("        → Portaria nº 009/SMDHC/2014")
        print("─" * 70)
        
        cur.execute("""
            UPDATE parcerias
            SET portaria = 'Portaria nº 009/SMDHC/2014'
            WHERE portaria IS NULL
            AND numero_termo ILIKE '%TCV%'
            AND numero_termo ILIKE '%FUMCAD%'
            AND inicio >= '2014-05-22'
            AND inicio <= '2017-09-30'
        """)
        caso4_count = cur.rowcount
        conn.commit()
        print(f"✅ Atualizados: {caso4_count} registros\n")
        
        # CASO 2: TCV + início entre 12/08/2008 e 21/05/2017 (SEM FUMCAD após 22/03/2012)
        print("─" * 70)
        print("CASO 2: TCV + início entre 12/08/2008 e 21/05/2017")
        print("        SEM FUMCAD se após 22/03/2012")
        print("        → Portaria nº 006/2008/SF-SEMPLA")
        print("─" * 70)
        
        cur.execute("""
            UPDATE parcerias
            SET portaria = 'Portaria nº 006/2008/SF-SEMPLA'
            WHERE portaria IS NULL
            AND numero_termo ILIKE '%TCV%'
            AND inicio >= '2008-08-12'
            AND inicio <= '2017-05-21'
            AND (
                -- Permite FUMCAD antes de 22/03/2012
                (numero_termo ILIKE '%FUMCAD%' AND inicio < '2012-03-22')
                OR 
                -- Permite sem FUMCAD em qualquer data
                (numero_termo NOT ILIKE '%FUMCAD%')
            )
        """)
        caso2_count = cur.rowcount
        conn.commit()
        print(f"✅ Atualizados: {caso2_count} registros\n")
        
        # CASO 3: Qualquer termo que inicia antes de 12/08/2008
        print("─" * 70)
        print("CASO 3: Qualquer termo com início antes de 12/08/2008")
        print("        → Decreto nº 6.170")
        print("─" * 70)
        
        cur.execute("""
            UPDATE parcerias
            SET portaria = 'Decreto nº 6.170'
            WHERE portaria IS NULL
            AND inicio < '2008-08-12'
        """)
        caso3_count = cur.rowcount
        conn.commit()
        print(f"✅ Atualizados: {caso3_count} registros\n")
        
        # Resumo final
        print("="*70)
        print("RESUMO DA ATUALIZAÇÃO")
        print("="*70)
        print(f"Caso 1 (Portaria 072/SMPP/2012)     : {caso1_count:>6} registros")
        print(f"Caso 2 (Portaria 006/2008/SF-SEMPLA): {caso2_count:>6} registros")
        print(f"Caso 3 (Decreto 6.170)              : {caso3_count:>6} registros")
        print(f"Caso 4 (Portaria 009/SMDHC/2014)    : {caso4_count:>6} registros")
        print("─" * 70)
        total_atualizados = caso1_count + caso2_count + caso3_count + caso4_count
        print(f"TOTAL ATUALIZADO                     : {total_atualizados:>6} registros")
        print("="*70)
        
        # Verificar registros ainda NULL
        cur.execute("SELECT COUNT(*) as total FROM parcerias WHERE portaria IS NULL")
        ainda_null = cur.fetchone()['total']
        print(f"\n[INFO] Registros ainda com portaria NULL: {ainda_null}")
        
        if ainda_null > 0:
            print("\n[AVISO] Alguns registros não foram atualizados (fora dos critérios)")
            print("[INFO] Exemplos de registros não atualizados:")
            cur.execute("""
                SELECT numero_termo, inicio, final
                FROM parcerias 
                WHERE portaria IS NULL
                LIMIT 5
            """)
            exemplos = cur.fetchall()
            for ex in exemplos:
                print(f"  - {ex['numero_termo']}: início={ex['inicio']}, fim={ex['final']}")
        
        cur.close()
        return True
        
    except Exception as e:
        print(f"\n[ERRO] Erro ao preencher portarias: {e}")
        import traceback
        traceback.print_exc()
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == '__main__':
    print("\n")
    sucesso = preencher_portarias()
    
    if sucesso:
        print("\n✅ Script executado com sucesso!\n")
    else:
        print("\n❌ Falha na execução do script!\n")
        sys.exit(1)
