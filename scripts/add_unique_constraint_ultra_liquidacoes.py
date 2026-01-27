#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script: add_unique_constraint_ultra_liquidacoes.py
Descrição: Adiciona constraint UNIQUE em (numero_termo, vigencia_inicial) 
           para permitir UPSERT no modo de parcelas projetadas
Data: 2026-01-26
"""

import sys
import os
import psycopg2

# Adicionar diretório raiz ao path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import DB_CONFIG

def main():
    print("=" * 80)
    print("ADICIONAR CONSTRAINT UNIQUE - ULTRA LIQUIDAÇÕES")
    print("=" * 80)
    
    conn = None
    try:
        # Conectar diretamente ao banco (sem contexto Flask)
        print("\n0. Conectando ao banco de dados...")
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )
        cur = conn.cursor()
        print("   ✅ Conexão estabelecida!")
        
        # Verificar se constraint já existe
        print("\n1. Verificando se constraint já existe...")
        cur.execute("""
            SELECT 1 FROM pg_constraint 
            WHERE conname = 'ultra_liquidacoes_termo_vigencia_key'
        """)
        
        if cur.fetchone():
            print("   ✅ Constraint já existe! Nada a fazer.")
            return
        
        print("   ℹ️  Constraint não existe, vamos criar...")
        
        # Verificar se há duplicatas antes de criar a constraint
        print("\n2. Verificando duplicatas existentes...")
        cur.execute("""
            SELECT 
                numero_termo, 
                vigencia_inicial::text,
                COUNT(*) as total
            FROM gestao_financeira.ultra_liquidacoes
            GROUP BY numero_termo, vigencia_inicial
            HAVING COUNT(*) > 1
        """)
        
        duplicatas = cur.fetchall()
        
        if duplicatas:
            print(f"   ⚠️  ATENÇÃO: Encontradas {len(duplicatas)} duplicatas!")
            print("\n   Duplicatas encontradas:")
            for termo, vigencia, total in duplicatas:
                print(f"      - {termo} | {vigencia} | {total} registros")
            
            resposta = input("\n   Deseja continuar mesmo assim? (s/N): ").strip().lower()
            if resposta != 's':
                print("   ❌ Operação cancelada pelo usuário.")
                return
            
            print("\n   ⚠️  Nota: A constraint será criada, mas as duplicatas continuarão.")
            print("   Recomenda-se limpar as duplicatas manualmente antes.")
        else:
            print("   ✅ Nenhuma duplicata encontrada!")
        
        # Adicionar a constraint
        print("\n3. Adicionando constraint UNIQUE...")
        cur.execute("""
            ALTER TABLE gestao_financeira.ultra_liquidacoes
            ADD CONSTRAINT ultra_liquidacoes_termo_vigencia_key 
            UNIQUE (numero_termo, vigencia_inicial)
        """)
        
        conn.commit()
        print("   ✅ Constraint adicionada com sucesso!")
        
        # Verificar se foi criada
        print("\n4. Verificando constraint criada...")
        cur.execute("""
            SELECT 
                conname AS constraint_name,
                contype AS constraint_type,
                pg_get_constraintdef(oid) AS definition
            FROM pg_constraint
            WHERE conrelid = 'gestao_financeira.ultra_liquidacoes'::regclass
            AND conname = 'ultra_liquidacoes_termo_vigencia_key'
        """)
        
        resultado = cur.fetchone()
        if resultado:
            print(f"   ✅ Constraint: {resultado[0]}")
            print(f"      Tipo: {resultado[1]}")
            print(f"      Definição: {resultado[2]}")
        
        print("\n" + "=" * 80)
        print("✅ OPERAÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERRO: {e}")
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            print("\n✅ Conexão fechada.")

if __name__ == '__main__':
    main()
