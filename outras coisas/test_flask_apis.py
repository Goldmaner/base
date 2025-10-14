#!/usr/bin/env python3
"""
Script de teste das APIs do Flask com PostgreSQL.
"""

import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_login():
    """Testa o login (se precisar)."""
    login_data = {
        'username': 'admin@admin.com',  # Substitua pelos dados corretos
        'password': 'admin123'  # Substitua pela senha correta
    }
    
    session = requests.Session()
    
    # Fazer login
    response = session.post(f"{BASE_URL}/login", data=login_data)
    print(f"Login status: {response.status_code}")
    
    return session

def test_api_instrucoes(session):
    """Testa a API de instruções."""
    try:
        response = session.get(f"{BASE_URL}/api/instrucoes")
        print(f"✅ API /api/instrucoes - Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   📋 Instruções encontradas: {len(data)}")
        else:
            print(f"   ❌ Erro: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro ao testar API instrucoes: {e}")

def test_api_despesas(session):
    """Testa a API de despesas com um termo específico."""
    try:
        # Usar um número de termo que sabemos que existe (baseado no teste anterior)
        numero_termo = "TFM/072/2022/SMDHC/CFM"  # Exemplo do attachment
        
        response = session.get(f"{BASE_URL}/api/despesas/{numero_termo}")
        print(f"✅ API /api/despesas/{numero_termo} - Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   💰 Despesas encontradas: {len(data.get('despesas', []))}")
        else:
            print(f"   ❌ Erro: {response.text}")
            
    except Exception as e:
        print(f"❌ Erro ao testar API despesas: {e}")

def main():
    """Executa os testes das APIs."""
    print("🚀 Testando APIs do Flask com PostgreSQL...\n")
    
    try:
        session = test_login()
        
        # Testar APIs sem autenticação primeiro
        print("\n📡 Testando APIs:")
        test_api_instrucoes(session)
        test_api_despesas(session)
        
        print("\n🎉 Testes de API concluídos!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Erro: Não foi possível conectar ao servidor Flask.")
        print("   Verifique se a aplicação está rodando em http://127.0.0.1:5000")
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")

if __name__ == "__main__":
    main()