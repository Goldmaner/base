"""
Script para verificar se há erros ao importar o módulo ultra_liquidacoes
"""
import sys
import traceback

print("\n" + "="*80)
print("VERIFICANDO IMPORTAÇÃO DO MÓDULO ultra_liquidacoes")
print("="*80 + "\n")

try:
    from routes.gestao_financeira_ultra_liquidacoes import ultra_liquidacoes_bp
    print("✅ Módulo importado com sucesso!")
    print(f"✅ Blueprint: {ultra_liquidacoes_bp}")
    print(f"✅ URL Prefix: {ultra_liquidacoes_bp.url_prefix}")
    print(f"\n✅ Total de rotas no blueprint: {len([r for r in ultra_liquidacoes_bp.url_map.iter_rules()]) if hasattr(ultra_liquidacoes_bp, 'url_map') else 'N/A'}")
    
except SyntaxError as e:
    print(f"❌ ERRO DE SINTAXE:")
    print(f"   Arquivo: {e.filename}")
    print(f"   Linha: {e.lineno}")
    print(f"   Mensagem: {e.msg}")
    print(f"   Texto: {e.text}")
    traceback.print_exc()
    
except ImportError as e:
    print(f"❌ ERRO DE IMPORTAÇÃO:")
    print(f"   {str(e)}")
    traceback.print_exc()
    
except Exception as e:
    print(f"❌ ERRO DESCONHECIDO:")
    print(f"   {str(e)}")
    traceback.print_exc()

print("\n" + "="*80)
