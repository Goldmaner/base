"""
Teste de acesso à rota de encaminhamento de pagamento
"""
from app import app

# Simular requisição
with app.test_client() as client:
    numero_termo = "TCL/004/2024/SMDHC/SESANA"
    
    print("\n" + "="*80)
    print(f"TESTANDO ACESSO À ROTA COM TERMO: {numero_termo}")
    print("="*80 + "\n")
    
    # Testar rota de encaminhamento
    from urllib.parse import quote
    numero_termo_encoded = quote(numero_termo, safe='')
    url = f'/gestao_financeira/ultra-liquidacoes/encaminhamento-pagamento/{numero_termo_encoded}'
    
    print(f"URL Testada: {url}\n")
    
    response = client.get(url)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ ROTA FUNCIONANDO!")
        print(f"Tamanho da resposta: {len(response.data)} bytes")
    elif response.status_code == 302:
        print("🔄 REDIRECIONAMENTO (provavelmente para login)")
        print(f"Location: {response.headers.get('Location', 'N/A')}")
    elif response.status_code == 404:
        print("❌ ERRO 404 - Rota não encontrada")
        print("\nConteúdo da resposta:")
        print(response.data.decode('utf-8')[:500])
    else:
        print(f"⚠️ Status inesperado: {response.status_code}")
        print(response.data.decode('utf-8')[:500])
    
    print("\n" + "="*80)
