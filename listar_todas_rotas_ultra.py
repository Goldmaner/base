"""
Lista todas as rotas do blueprint ultra_liquidacoes
"""
from app import app

print("\n" + "="*80)
print("TODAS AS ROTAS DO BLUEPRINT ultra_liquidacoes")
print("="*80 + "\n")

rotas_encaminhamento = []
todas_rotas_ultra = []

for rule in app.url_map.iter_rules():
    if 'ultra-liquidacoes' in rule.rule or 'ultra_liquidacoes' in rule.endpoint:
        todas_rotas_ultra.append((rule.rule, rule.endpoint))
        
        if 'encaminhamento' in rule.rule.lower() or 'encaminhamento' in rule.endpoint.lower():
            rotas_encaminhamento.append((rule.rule, rule.endpoint))

print(f"📊 Total de rotas relacionadas a ultra-liquidacoes: {len(todas_rotas_ultra)}\n")

if rotas_encaminhamento:
    print("✅ ROTAS DE ENCAMINHAMENTO ENCONTRADAS:")
    print("-" * 80)
    for rota, endpoint in rotas_encaminhamento:
        print(f"   {rota}")
        print(f"   └─ Endpoint: {endpoint}\n")
else:
    print("❌ NENHUMA ROTA DE ENCAMINHAMENTO ENCONTRADA!\n")

print("\n" + "="*80)
print("TODAS AS ROTAS DE ultra-liquidacoes:")
print("="*80 + "\n")

for i, (rota, endpoint) in enumerate(todas_rotas_ultra, 1):
    print(f"{i:3}. {rota}")
    print(f"     └─ {endpoint}")

print("\n" + "="*80)
