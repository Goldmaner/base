"""
Script para listar rotas relacionadas ao encaminhamento de pagamento
"""
from app import app

print("\n" + "="*80)
print("ROTAS RELACIONADAS A ENCAMINHAMENTO DE PAGAMENTO")
print("="*80 + "\n")

encontrou = False
for rule in app.url_map.iter_rules():
    if 'encaminhamento' in rule.rule or 'parcelas-disponiveis' in rule.rule:
        print(f"✅ {rule.rule}")
        print(f"   Métodos: {', '.join(rule.methods - {'HEAD', 'OPTIONS'})}")
        print(f"   Endpoint: {rule.endpoint}")
        print()
        encontrou = True

if not encontrou:
    print("❌ NENHUMA ROTA DE ENCAMINHAMENTO ENCONTRADA!")
    print("   O servidor precisa ser REINICIADO para carregar as novas rotas.\n")
    print("   Execute: python run_prod.py\n")
else:
    print("✅ Rotas carregadas com sucesso!")

print("="*80)
