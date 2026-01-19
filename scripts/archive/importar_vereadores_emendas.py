#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para importar vereadores de emendas parlamentares para a tabela public.parcerias_emendas

CSV esperado (delimitador: ponto-e-vírgula):
A1: sei_celeb
B1: vereador_nome

Exemplo:
sei_celeb;vereador_nome
6074.2018/0001262-4;Fulano de Tal
6074.2018/0001262-4;Ciclano da Silva
"""

import os
import csv
import psycopg2
import psycopg2.extras
from datetime import datetime

# Configuração do banco de dados
DB_CONFIG = {
    'host': 'localhost',
    'database': 'projeto_parcerias',
    'user': 'postgres',
    'password': 'Coração01',
    'port': 5432
}

# Caminho do CSV
CSV_PATH = r'C:\Users\d843702\Downloads\vereadores_termos.csv'

def get_connection():
    """Retorna uma conexão com o banco de dados"""
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port'],
            client_encoding='UTF8'
        )
        return conn
    except Exception as e:
        print(f"   [ERRO] ao conectar ao banco: {e}")
        print(f"   [DEBUG] DB_CONFIG: host={DB_CONFIG['host']}, db={DB_CONFIG['database']}, user={DB_CONFIG['user']}")
        return None

def verificar_tabela():
    """Verifica se a tabela parcerias_emendas existe"""
    print("[ETAPA 1] Verificando tabela parcerias_emendas...")
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar se tabela existe
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
              AND table_name = 'parcerias_emendas'
        """)
        
        if cur.fetchone():
            print("   [OK] Tabela 'parcerias_emendas' existe!")
        else:
            print("   [ERRO] Tabela 'parcerias_emendas' nao encontrada!")
            cur.close()
            conn.close()
            return False
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   [ERRO] ao verificar tabela: {e}")
        if conn:
            conn.close()
        return False

def importar_csv():
    """Importa dados do CSV para a tabela parcerias_emendas"""
    print(f"\n[ETAPA 2] Importando dados de {CSV_PATH}...")
    
    if not os.path.exists(CSV_PATH):
        print(f"   [ERRO] Arquivo nao encontrado: {CSV_PATH}")
        return False
    
    try:
        # Ler CSV com UTF-8-SIG para remover BOM automaticamente
        with open(CSV_PATH, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f, delimiter=';')  # Delimitado por PONTO-E-VIRGULA
            dados = list(reader)
        
        print(f"   [OK] CSV lido com sucesso! Total de registros: {len(dados)}")
        
        # Mostrar primeiros 3 registros para debug
        print("\n   [DEBUG] Primeiros 3 registros:")
        for i, row in enumerate(dados[:3], 1):
            print(f"      {i}. sei_celeb='{row.get('sei_celeb', '')}', vereador_nome='{row.get('vereador_nome', '')}'")
        
        # Processar cada linha
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print("\n[ETAPA 3] Inserindo registros na tabela parcerias_emendas...")
        
        total_inseridos = 0
        total_duplicados = 0
        total_erros = 0
        total_sem_sei = 0
        
        # Buscar status automaticamente para cada sei_celeb
        print("\n   [INFO] Buscando status 'Celebrado' baseado em data_assinatura...")
        
        for i, row in enumerate(dados, 1):
            sei_celeb = row.get('sei_celeb', '').strip()
            vereador_nome = row.get('vereador_nome', '').strip()
            
            if not sei_celeb:
                total_sem_sei += 1
                if total_sem_sei <= 10:
                    print(f"   [AVISO] Linha {i}: sei_celeb vazio, pulando...")
                continue
            
            if not vereador_nome:
                if i <= 10:
                    print(f"   [AVISO] Linha {i}: vereador_nome vazio, pulando...")
                continue
            
            try:
                # Buscar se existe data_assinatura para este sei_celeb
                # Procura em parcerias_sei usando sei_celeb
                cur.execute("""
                    SELECT ps.data_assinatura
                    FROM public.parcerias_sei ps
                    JOIN public.parcerias p ON ps.numero_termo = p.numero_termo
                    WHERE p.sei_celeb = %s
                    LIMIT 1
                """, (sei_celeb,))
                
                resultado = cur.fetchone()
                status = 'Celebrado' if (resultado and resultado['data_assinatura']) else None
                
                # Verificar se já existe este registro (sei_celeb + vereador_nome)
                cur.execute("""
                    SELECT id FROM public.parcerias_emendas
                    WHERE sei_celeb = %s AND vereador_nome = %s
                """, (sei_celeb, vereador_nome))
                
                if cur.fetchone():
                    total_duplicados += 1
                    if total_duplicados <= 5:
                        print(f"   [AVISO] Duplicado: {sei_celeb} - {vereador_nome}")
                    continue
                
                # Inserir registro
                cur.execute("""
                    INSERT INTO public.parcerias_emendas (sei_celeb, vereador_nome, status, criado_em)
                    VALUES (%s, %s, %s, %s)
                """, (sei_celeb, vereador_nome, status, datetime.now()))
                
                total_inseridos += 1
                
                if total_inseridos <= 10:  # Mostrar primeiros 10
                    status_str = f"status={status}" if status else "status=NULL"
                    print(f"   [OK] {sei_celeb} - {vereador_nome} ({status_str})")
                        
            except Exception as e:
                total_erros += 1
                if total_erros <= 5:  # Mostrar primeiros 5
                    print(f"   [ERRO] Linha {i}: {e}")
        
        # Commit das alterações
        conn.commit()
        
        print("\n" + "="*60)
        print("RESUMO DA IMPORTACAO")
        print("="*60)
        print(f"Total de registros no CSV:    {len(dados)}")
        print(f"[OK] Registros inseridos:     {total_inseridos}")
        print(f"[AVISO] Duplicados (pulados): {total_duplicados}")
        print(f"[AVISO] Sem SEI (pulados):    {total_sem_sei}")
        print(f"[ERRO] Erros:                 {total_erros}")
        print("="*60)
        
        # Mostrar estatísticas de status
        cur.execute("""
            SELECT status, COUNT(*) as total
            FROM public.parcerias_emendas
            GROUP BY status
            ORDER BY status NULLS LAST
        """)
        
        print("\n   [INFO] Estatisticas de status:")
        for row in cur.fetchall():
            status_display = row['status'] if row['status'] else '(sem status)'
            print(f"      - {status_display}: {row['total']} registros")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   [ERRO] durante importacao: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Função principal"""
    print("="*60)
    print("IMPORTACAO DE VEREADORES (EMENDAS PARLAMENTARES)")
    print("="*60)
    
    # Etapa 1: Verificar tabela
    if not verificar_tabela():
        print("\n[ERRO] Falha ao verificar tabela. Abortando.")
        return
    
    # Etapa 2: Importar dados
    if not importar_csv():
        print("\n[ERRO] Falha na importacao.")
        return
    
    print("\n[OK] IMPORTACAO CONCLUIDA COM SUCESSO!")

if __name__ == '__main__':
    main()
