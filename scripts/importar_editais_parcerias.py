#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para importar nomes de editais para a tabela public.parcerias
usando busca fuzzy (PROCX) no numero_termo

CSV esperado: numero_termo; edital_nome
"""

import os
import csv
import psycopg2
import psycopg2.extras

# Configuração do banco de dados
DB_CONFIG = {
    'host': 'localhost',
    'database': 'projeto_parcerias',
    'user': 'postgres',
    'password': 'Coração01',
    'port': 5432
}

# Caminho do CSV
CSV_PATH = r'C:\Users\d843702\Downloads\parcerias_editais.csv'

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

def adicionar_coluna():
    """Adiciona a coluna edital_nome à tabela parcerias se não existir"""
    print("[ETAPA 1] Verificando/adicionando coluna edital_nome...")
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cur = conn.cursor()
        
        # Verificar se coluna já existe
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
              AND table_name = 'parcerias' 
              AND column_name = 'edital_nome'
        """)
        
        if cur.fetchone():
            print("   [OK] Coluna 'edital_nome' ja existe!")
        else:
            # Adicionar coluna
            cur.execute("""
                ALTER TABLE public.parcerias 
                ADD COLUMN edital_nome VARCHAR(50)
            """)
            conn.commit()
            print("   [OK] Coluna 'edital_nome' adicionada com sucesso!")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   [ERRO] ao adicionar coluna: {e}")
        if conn:
            conn.close()
        return False

def importar_csv():
    """Importa dados do CSV para a tabela parcerias usando PROCX"""
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
        
        # Processar cada linha
        conn = get_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        print("\n[ETAPA 3] Atualizando registros usando PROCX...")
        
        total_atualizados = 0
        total_nao_encontrados = 0
        total_erros = 0
        
        for i, row in enumerate(dados, 1):
            numero_termo = row.get('numero_termo', '').strip()
            edital_nome = row.get('edital_nome', '').strip()
            
            if not numero_termo:
                if i % 100 == 0 or i <= 10:  # Mostrar menos warnings
                    print(f"   [AVISO] Linha {i}: numero_termo vazio, pulando...")
                continue
            
            if not edital_nome:
                continue
            
            try:
                # Buscar registro mais similar usando PROCX
                cur.execute("""
                    SELECT numero_termo, SIMILARITY(numero_termo, %s) as sim
                    FROM public.parcerias
                    WHERE numero_termo %% %s
                    ORDER BY sim DESC
                    LIMIT 1
                """, (numero_termo, numero_termo))
                
                resultado = cur.fetchone()
                
                if resultado and resultado['sim'] > 0.3:  # Threshold de similaridade
                    # Atualizar registro
                    cur.execute("""
                        UPDATE public.parcerias
                        SET edital_nome = %s
                        WHERE numero_termo = %s
                    """, (edital_nome, resultado['numero_termo']))
                    
                    total_atualizados += 1
                    
                    if total_atualizados <= 10:  # Mostrar primeiros 10
                        print(f"   [OK] {numero_termo} -> {resultado['numero_termo']} (sim: {resultado['sim']:.2f})")
                
                else:
                    total_nao_encontrados += 1
                    if total_nao_encontrados <= 5:  # Mostrar primeiros 5
                        print(f"   [AVISO] Nao encontrado: {numero_termo}")
                        
            except Exception as e:
                total_erros += 1
                if total_erros <= 5:  # Mostrar primeiros 5
                    print(f"   [ERRO] Linha {i}: {e}")
        
        # Commit das alterações
        conn.commit()
        
        print("\n" + "="*60)
        print("RESUMO DA IMPORTACAO")
        print("="*60)
        print(f"Total de registros no CSV: {len(dados)}")
        print(f"[OK] Registros atualizados:   {total_atualizados}")
        print(f"[AVISO] Nao encontrados:      {total_nao_encontrados}")
        print(f"[ERRO] Erros:                 {total_erros}")
        print("="*60)
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"   [ERRO] durante importacao: {e}")
        return False

def main():
    """Função principal"""
    print("="*60)
    print("IMPORTACAO DE EDITAIS PARA PARCERIAS")
    print("="*60)
    
    # Etapa 1: Adicionar coluna
    if not adicionar_coluna():
        print("\n[ERRO] Falha ao adicionar coluna. Abortando.")
        return
    
    # Etapa 2: Importar dados
    if not importar_csv():
        print("\n[ERRO] Falha na importacao.")
        return
    
    print("\n[OK] IMPORTACAO CONCLUIDA COM SUCESSO!")

if __name__ == '__main__':
    main()
