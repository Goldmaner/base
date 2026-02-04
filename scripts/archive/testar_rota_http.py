"""
Teste de acesso direto à rota de encaminhamento via requests
"""
import requests
from urllib.parse import quote

numero_termo = "TCL/004/2024/SMDHC/SESANA"
numero_termo_encoded = quote(numero_termo, safe='')

url = f"http://127.0.0.1:8080/gestao_financeira/ultra-liquidacoes/encaminhamento-pagamento/{numero_termo_encoded}"

print("\n" + "="*80)
print("TESTANDO ACESSO À ROTA VIA HTTP")
print("="*80)
print(f"\nURL: {url}")
print(f"Termo: {numero_termo}")
print("\nEnviando requisição...\n")

try:
    response = requests.get(url, allow_redirects=False, timeout=5)
    
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ SUCESSO! Rota funcionando corretamente")
        print(f"Tamanho da resposta: {len(response.content)} bytes")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')}")
        
        # Verificar se é HTML
        if 'html' in response.headers.get('Content-Type', '').lower():
            if 'Encaminhamento de Pagamento' in response.text:
                print("✅ Página HTML correta carregada (contém título esperado)")
            else:
                print("⚠️ HTML carregado mas sem título esperado")
                
    elif response.status_code == 302 or response.status_code == 301:
        print(f"🔄 REDIRECIONAMENTO para: {response.headers.get('Location', 'N/A')}")
        print("   (provavelmente requer autenticação)")
        
    elif response.status_code == 404:
        print("❌ ERRO 404 - Rota não encontrada!")
        print("\nConteúdo da resposta:")
        print(response.text[:500])
        
    else:
        print(f"⚠️ Status inesperado")
        print(response.text[:500])
        
except requests.exceptions.ConnectionError:
    print("❌ ERRO: Não foi possível conectar ao servidor")
    print("   Verifique se o servidor está rodando na porta 8080")
    
except Exception as e:
    print(f"❌ ERRO: {str(e)}")

print("\n" + "="*80)
