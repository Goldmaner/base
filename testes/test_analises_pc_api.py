"""
Script de teste para as APIs do módulo analises_pc
Testa criação, leitura e atualização de checklists
"""

import requests
import json

BASE_URL = "http://localhost:5000/analises_pc/api"

def test_carregar_checklist_vazio():
    """Testa carregamento de checklist que não existe"""
    print("\n1️⃣  Testando carregamento de checklist vazio...")
    
    response = requests.post(
        f"{BASE_URL}/carregar_checklist",
        json={
            "numero_termo": "999/2024",
            "meses_analisados": "01/2024"
        }
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    data = response.json()
    assert data['checklist'] is None, "Checklist deveria ser None"
    assert data['analistas'] == [], "Analistas deveria ser lista vazia"
    print("✓ Teste passou!")

def test_salvar_checklist():
    """Testa salvamento de novo checklist"""
    print("\n2️⃣  Testando salvamento de checklist...")
    
    payload = {
        "numero_termo": "TEST/2024",
        "meses_analisados": "11/2024",
        "nome_analista": "Analista Teste",
        "analistas": ["Analista Teste", "Analista Teste 2"],
        "checklist": {
            "avaliacao_celebracao": True,
            "avaliacao_prestacao_contas": True,
            "preenchimento_dados_base": False,
            "preenchimento_orcamento_anual": False,
            "preenchimento_conciliacao_bancaria": False,
            "avaliacao_dados_bancarios": False,
            "documentos_sei_1": False,
            "avaliacao_resposta_inconsistencia": False,
            "emissao_parecer": False,
            "documentos_sei_2": False,
            "tratativas_restituicao": False,
            "encaminhamento_encerramento": False
        },
        "recursos": []
    }
    
    response = requests.post(
        f"{BASE_URL}/salvar_checklist",
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    
    assert response.status_code == 200, "Deveria retornar 200"
    print("✓ Teste passou!")

def test_carregar_checklist_existente():
    """Testa carregamento de checklist existente"""
    print("\n3️⃣  Testando carregamento de checklist existente...")
    
    response = requests.post(
        f"{BASE_URL}/carregar_checklist",
        json={
            "numero_termo": "TEST/2024",
            "meses_analisados": "11/2024"
        }
    )
    
    print(f"Status: {response.status_code}")
    data = response.json()
    print(f"Checklist: {data['checklist'] is not None}")
    print(f"Analistas: {data['analistas']}")
    
    assert data['checklist'] is not None, "Checklist deveria existir"
    assert len(data['analistas']) == 2, "Deveria ter 2 analistas"
    assert data['checklist']['avaliacao_celebracao'] == True, "Primeira etapa deveria estar marcada"
    print("✓ Teste passou!")

def test_atualizar_checklist():
    """Testa atualização de checklist existente"""
    print("\n4️⃣  Testando atualização de checklist...")
    
    payload = {
        "numero_termo": "TEST/2024",
        "meses_analisados": "11/2024",
        "nome_analista": "Analista Teste",
        "analistas": ["Analista Teste", "Analista Teste 2", "Analista Teste 3"],
        "checklist": {
            "avaliacao_celebracao": True,
            "avaliacao_prestacao_contas": True,
            "preenchimento_dados_base": True,
            "preenchimento_orcamento_anual": True,
            "preenchimento_conciliacao_bancaria": False,
            "avaliacao_dados_bancarios": False,
            "documentos_sei_1": False,
            "avaliacao_resposta_inconsistencia": False,
            "emissao_parecer": False,
            "documentos_sei_2": False,
            "tratativas_restituicao": False,
            "encaminhamento_encerramento": False
        },
        "recursos": []
    }
    
    response = requests.post(
        f"{BASE_URL}/salvar_checklist",
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, "Deveria retornar 200"
    
    # Verificar atualização
    response = requests.post(
        f"{BASE_URL}/carregar_checklist",
        json={
            "numero_termo": "TEST/2024",
            "meses_analisados": "11/2024"
        }
    )
    
    data = response.json()
    assert len(data['analistas']) == 3, "Deveria ter 3 analistas agora"
    assert data['checklist']['preenchimento_dados_base'] == True, "Terceira etapa deveria estar marcada"
    print("✓ Teste passou!")

def test_salvar_com_recursos():
    """Testa salvamento com recursos"""
    print("\n5️⃣  Testando salvamento com recursos...")
    
    payload = {
        "numero_termo": "TEST/2024",
        "meses_analisados": "11/2024",
        "nome_analista": "Analista Teste",
        "analistas": ["Analista Teste"],
        "checklist": {
            "avaliacao_celebracao": True,
            "avaliacao_prestacao_contas": True,
            "preenchimento_dados_base": True,
            "preenchimento_orcamento_anual": True,
            "preenchimento_conciliacao_bancaria": True,
            "avaliacao_dados_bancarios": True,
            "documentos_sei_1": True,
            "avaliacao_resposta_inconsistencia": True,
            "emissao_parecer": True,
            "documentos_sei_2": True,
            "tratativas_restituicao": False,
            "encaminhamento_encerramento": False
        },
        "recursos": [
            {
                "tipo_recurso": 1,
                "avaliacao_resposta_recursal": True,
                "emissao_parecer_recursal": False,
                "documentos_sei": False
            },
            {
                "tipo_recurso": 2,
                "avaliacao_resposta_recursal": True,
                "emissao_parecer_recursal": True,
                "documentos_sei": False
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/salvar_checklist",
        json=payload
    )
    
    print(f"Status: {response.status_code}")
    assert response.status_code == 200, "Deveria retornar 200"
    
    # Verificar recursos salvos
    response = requests.post(
        f"{BASE_URL}/carregar_checklist",
        json={
            "numero_termo": "TEST/2024",
            "meses_analisados": "11/2024"
        }
    )
    
    data = response.json()
    assert len(data['recursos']) == 2, "Deveria ter 2 recursos"
    print(f"Recursos salvos: {len(data['recursos'])}")
    print("✓ Teste passou!")

def run_all_tests():
    """Executa todos os testes"""
    print("=" * 60)
    print("🧪 Iniciando testes do módulo analises_pc")
    print("=" * 60)
    
    try:
        test_carregar_checklist_vazio()
        test_salvar_checklist()
        test_carregar_checklist_existente()
        test_atualizar_checklist()
        test_salvar_com_recursos()
        
        print("\n" + "=" * 60)
        print("✅ Todos os testes passaram com sucesso!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Teste falhou: {e}")
    except requests.exceptions.ConnectionError:
        print("\n❌ Erro: Não foi possível conectar ao servidor.")
        print("   Certifique-se de que o servidor Flask está rodando em http://localhost:5000")
    except Exception as e:
        print(f"\n❌ Erro inesperado: {e}")

if __name__ == '__main__':
    run_all_tests()
