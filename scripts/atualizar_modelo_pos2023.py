#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para atualizar modelo de texto pós-2023 
para usar criar_tabela_pos2023 ao invés de criar_tabela_informado_usuario
"""

import sys
import os
import psycopg2
import psycopg2.extras

# Importar config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
from config import DB_CONFIG

def main():
    print("=" * 80)
    print("ATUALIZAÇÃO DO MODELO PÓS-2023")
    print("=" * 80)
    
    # Conectar diretamente sem Flask context
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # Buscar modelo atual
    cur.execute("""
        SELECT id, titulo_texto, modelo_texto 
        FROM categoricas.c_modelo_textos 
        WHERE titulo_texto LIKE '%pós-2023%'
    """)
    
    modelo = cur.fetchone()
    
    if not modelo:
        print("❌ Modelo 'Pesquisa de Parcerias: Parcerias pós-2023' não encontrado!")
        cur.close()
        conn.close()
        return
    
    print(f"\n✅ Modelo encontrado: {modelo['titulo_texto']}")
    print(f"ID: {modelo['id']}")
    
    texto_atual = modelo['modelo_texto']
    
    # Verificar se já usa criar_tabela_pos2023
    if 'criar_tabela_pos2023' in texto_atual:
        print("\n✅ Modelo já usa criar_tabela_pos2023. Nenhuma atualização necessária.")
        cur.close()
        conn.close()
        return
    
    # Substituir criar_tabela_informado_usuario por criar_tabela_pos2023
    texto_novo = texto_atual.replace(
        'criar_tabela_informado_usuario(cabeçalho: Número do Termo; Processo SEI PC; Nome do Projeto)',
        'criar_tabela_pos2023(cabeçalho: Número do Termo; Processo SEI PC; Nome do Projeto)'
    )
    
    # Também substituir variações
    texto_novo = texto_novo.replace('criar_tabela_informado_usuario', 'criar_tabela_pos2023')
    
    if texto_novo == texto_atual:
        print("\n⚠️  Nenhuma substituição foi feita. Verificar manualmente.")
        print(f"\nTexto atual (primeiros 500 chars):\n{texto_atual[:500]}")
        cur.close()
        conn.close()
        return
    
    # Atualizar no banco
    print("\n🔄 Atualizando modelo...")
    cur.execute("""
        UPDATE categoricas.c_modelo_textos
        SET modelo_texto = %s
        WHERE id = %s
    """, (texto_novo, modelo['id']))
    
    conn.commit()
    print("✅ Modelo atualizado com sucesso!")
    
    # Mostrar mudanças
    print("\n" + "=" * 80)
    print("MUDANÇAS REALIZADAS:")
    print("=" * 80)
    print("ANTES: criar_tabela_informado_usuario(...)")
    print("DEPOIS: criar_tabela_pos2023(...)")
    
    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
