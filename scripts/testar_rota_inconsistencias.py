"""
Script de teste para verificar se a rota de inconsistências está funcionando
"""
import requests
import sys

# Configurações
BASE_URL = "http://localhost:8080"  # Porta do servidor de desenvolvimento
TERMO_TESTE = "001/2024"  # Ajuste para um termo válido no seu banco

def testar_rota_identificar():
    """Testa a rota de identificação de inconsistências"""
    print("="*60)
    print("TESTE: Identificar Inconsistências")
    print("="*60)
    
    url = f"{BASE_URL}/analises_pc/api/identificar-inconsistencias/{TERMO_TESTE}"
    print(f"\n📍 URL: {url}")
    
    try:
        print(f"🔄 Enviando requisição...")
        response = requests.get(url, timeout=10)
        
        print(f"\n✅ Status Code: {response.status_code}")
        print(f"📋 Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("\n✅ SUCESSO! Rota funcionando corretamente.")
            data = response.json()
            print(f"\n📊 Dados retornados:")
            print(f"   - Inconsistências encontradas: {len(data.get('inconsistencias', []))}")
            
            if data.get('inconsistencias'):
                for i, inc in enumerate(data['inconsistencias'], 1):
                    print(f"\n   {i}. {inc['nome_item']}")
                    print(f"      Transações: {len(inc.get('transacoes', []))}")
        elif response.status_code == 404:
            print("\n❌ ERRO 404: Rota não encontrada!")
            print("\n🔧 Possíveis causas:")
            print("   1. O servidor não foi reiniciado após adicionar a rota")
            print("   2. O blueprint 'analises_pc_bp' não está registrado")
            print("   3. O prefixo da URL está incorreto")
            print("\n💡 Solução: Reinicie o servidor Flask")
        elif response.status_code == 500:
            print("\n❌ ERRO 500: Erro interno no servidor!")
            print(f"\n📄 Resposta: {response.text[:500]}")
            print("\n🔧 Verifique os logs do servidor Flask para detalhes")
        else:
            print(f"\n⚠️ Status inesperado: {response.status_code}")
            print(f"📄 Resposta: {response.text[:500]}")
            
    except requests.exceptions.ConnectionError:
        print("\n❌ ERRO DE CONEXÃO!")
        print(f"   Não foi possível conectar em {BASE_URL}")
        print("\n🔧 Verifique se o servidor Flask está rodando")
        print("   Execute: python run_dev.py")
    except requests.exceptions.Timeout:
        print("\n❌ TIMEOUT!")
        print("   A requisição demorou mais de 10 segundos")
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {type(e).__name__}")
        print(f"   {str(e)}")

def testar_servidor():
    """Testa se o servidor Flask está respondendo"""
    print("\n" + "="*60)
    print("TESTE: Verificar Servidor Flask")
    print("="*60)
    
    try:
        response = requests.get(BASE_URL, timeout=5)
        print(f"\n✅ Servidor respondendo! Status: {response.status_code}")
        return True
    except:
        print(f"\n❌ Servidor não está respondendo em {BASE_URL}")
        return False

if __name__ == "__main__":
    print("\n🔍 TESTADOR DE ROTAS - INCONSISTÊNCIAS\n")
    
    # Testar servidor
    if testar_servidor():
        # Testar rota de inconsistências
        testar_rota_identificar()
    else:
        print("\n⚠️ Inicie o servidor Flask antes de testar as rotas!")
        print("   Execute: python run_dev.py")
    
    print("\n" + "="*60)
    print("TESTE CONCLUÍDO")
    print("="*60 + "\n")
