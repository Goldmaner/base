"""
Script para sincronizar nomes de pessoas gestoras entre 
categoricas.c_pessoa_gestora e parcerias_analises
"""

import sys
sys.path.insert(0, '..')

import psycopg2
import psycopg2.extras
from config import DB_CONFIG

print("=== Sincronização de Pessoas Gestoras ===\n")

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

# Buscar todos os nomes de pessoas gestoras cadastrados
print("1. Buscando pessoas gestoras cadastradas...")
cur.execute("""
    SELECT id, nome_pg, setor
    FROM categoricas.c_pessoa_gestora
    ORDER BY nome_pg
""")
pessoas_gestoras = cur.fetchall()

print(f"   Encontradas {len(pessoas_gestoras)} pessoas gestoras\n")

# Buscar todas as pessoas gestoras únicas em parcerias_analises
print("2. Buscando pessoas gestoras em parcerias_analises...")
cur.execute("""
    SELECT DISTINCT responsavel_pg
    FROM parcerias_analises
    WHERE responsavel_pg IS NOT NULL
    ORDER BY responsavel_pg
""")
pessoas_em_analises = [row['responsavel_pg'] for row in cur.fetchall()]

print(f"   Encontradas {len(pessoas_em_analises)} pessoas únicas em parcerias_analises\n")

# Identificar inconsistências
print("3. Verificando inconsistências...\n")
print("=" * 80)

nomes_cadastrados = [pg['nome_pg'] for pg in pessoas_gestoras]
inconsistencias = []

for nome_analise in pessoas_em_analises:
    if nome_analise not in nomes_cadastrados:
        print(f"⚠️  '{nome_analise}' existe em parcerias_analises mas não em c_pessoa_gestora")
        
        # Tentar encontrar correspondência aproximada
        possibilidades = []
        palavras_analise = set(nome_analise.lower().split())
        
        for pg in pessoas_gestoras:
            palavras_cadastro = set(pg['nome_pg'].lower().split())
            
            # Verificar interseção de palavras (pelo menos 2 palavras em comum)
            palavras_comuns = palavras_analise.intersection(palavras_cadastro)
            
            if len(palavras_comuns) >= 2:
                possibilidades.append({
                    'pessoa': pg,
                    'palavras_comuns': len(palavras_comuns)
                })
        
        # Ordenar por número de palavras em comum
        possibilidades.sort(key=lambda x: x['palavras_comuns'], reverse=True)
        
        if possibilidades:
            print(f"   Possíveis correspondências:")
            for idx, poss in enumerate(possibilidades, 1):
                pg = poss['pessoa']
                print(f"   {idx}. {pg['nome_pg']} ({pg['setor']}) - {poss['palavras_comuns']} palavra(s) em comum")
            
            inconsistencias.append({
                'nome_antigo': nome_analise,
                'possibilidades': [p['pessoa'] for p in possibilidades]
            })
        else:
            print(f"   ❌ Nenhuma correspondência encontrada automaticamente")
            inconsistencias.append({
                'nome_antigo': nome_analise,
                'possibilidades': []
            })
        print()

print("=" * 80)

# Oferecer opção de corrigir automaticamente
if inconsistencias:
    print(f"\n📋 Encontradas {len(inconsistencias)} inconsistências\n")
    
    resposta = input("Deseja ver as sugestões de correção automática? (s/n): ").strip().lower()
    
    if resposta == 's':
        print("\n🔧 Sugestões de correção:\n")
        print("=" * 80)
        
        for incons in inconsistencias:
            nome_antigo = incons['nome_antigo']
            possibilidades = incons['possibilidades']
            
            if len(possibilidades) == 1:
                # Apenas uma correspondência - sugerir atualização automática
                novo_nome = possibilidades[0]['nome_pg']
                
                # Verificar quantos registros seriam afetados
                cur.execute("""
                    SELECT COUNT(*) as total
                    FROM parcerias_analises
                    WHERE responsavel_pg = %s
                """, (nome_antigo,))
                total = cur.fetchone()['total']
                
                print(f"📝 '{nome_antigo}' -> '{novo_nome}'")
                print(f"   Afetará {total} registro(s) em parcerias_analises")
                print()
        
        print("=" * 80)
        
        resposta_executar = input("\nDeseja executar as correções automáticas? (s/n): ").strip().lower()
        
        if resposta_executar == 's':
            print("\n🚀 Executando correções...\n")
            
            correcoes_realizadas = 0
            
            for incons in inconsistencias:
                nome_antigo = incons['nome_antigo']
                possibilidades = incons['possibilidades']
                
                if len(possibilidades) == 1:
                    novo_nome = possibilidades[0]['nome_pg']
                    
                    cur.execute("""
                        UPDATE parcerias_analises
                        SET responsavel_pg = %s
                        WHERE responsavel_pg = %s
                    """, (novo_nome, nome_antigo))
                    
                    registros_atualizados = cur.rowcount
                    print(f"✅ Atualizado '{nome_antigo}' -> '{novo_nome}' ({registros_atualizados} registro(s))")
                    correcoes_realizadas += 1
            
            if correcoes_realizadas > 0:
                conn.commit()
                print(f"\n🎉 {correcoes_realizadas} correção(ões) realizadas com sucesso!")
            else:
                print("\n⚠️ Nenhuma correção automática disponível")
        else:
            print("\n❌ Correções canceladas pelo usuário")
    else:
        print("\n❌ Operação cancelada")
else:
    print("\n✅ Nenhuma inconsistência encontrada! Todos os nomes estão sincronizados.")

cur.close()
conn.close()

print("\n=== Sincronização concluída ===")
