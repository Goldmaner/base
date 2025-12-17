"""
Script para listar todas as rotas registradas no Flask
"""
import sys
sys.path.insert(0, '.')

from app import app

print("\n" + "="*80)
print("ROTAS REGISTRADAS NO FLASK")
print("="*80 + "\n")

rotas_analises = []
outras_rotas = []

for rule in app.url_map.iter_rules():
    rota_str = f"{rule.methods} {rule.rule}"
    
    if '/analises_pc/' in rule.rule:
        rotas_analises.append(rota_str)
    else:
        outras_rotas.append(rota_str)

print(f"📊 ROTAS DE ANÁLISES PC ({len(rotas_analises)} rotas):")
print("-" * 80)
for rota in sorted(rotas_analises):
    destaque = "✅" if "identificar-inconsistencias" in rota else "  "
    print(f"{destaque} {rota}")

print(f"\n📌 PROCURANDO: identificar-inconsistencias")
encontrada = any("identificar-inconsistencias" in r for r in rotas_analises)

if encontrada:
    print("✅ ROTA ENCONTRADA! O servidor está com a rota registrada.")
else:
    print("❌ ROTA NÃO ENCONTRADA! O servidor precisa ser reiniciado.")

print("\n" + "="*80)
print(f"Total de rotas: {len(rotas_analises) + len(outras_rotas)}")
print("="*80 + "\n")
