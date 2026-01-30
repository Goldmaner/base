"""
Teste direto da função encaminhamento_pagamento
"""
from app import app

numero_termo = "TCL/004/2024/SMDHC/SESANA"

print("\n" + "="*80)
print("TESTANDO FUNÇÃO DIRETAMENTE")
print("="*80 + "\n")

with app.test_request_context(f'/gestao_financeira/ultra-liquidacoes/encaminhamento-pagamento/{numero_termo}'):
    try:
        from routes.gestao_financeira_ultra_liquidacoes import encaminhamento_pagamento
        
        print(f"Termo: {numero_termo}")
        print("\nChamando função encaminhamento_pagamento()...")
        
        resultado = encaminhamento_pagamento(numero_termo)
        
        print(f"\n✅ SUCESSO!")
        print(f"Tipo de retorno: {type(resultado)}")
        
        if hasattr(resultado, 'data'):
            print(f"Tamanho do HTML: {len(resultado.data)} bytes")
            print(f"\n📄 CONTEÚDO DO HTML:")
            print("="*80)
            print(resultado.data.decode('utf-8'))
            print("="*80)
            
            # Verificar se contém o termo
            if numero_termo.encode() in resultado.data or numero_termo in str(resultado.data):
                print("\n✅ HTML contém o número do termo")
            else:
                print("\n⚠️ HTML não contém o número do termo")
                
    except Exception as e:
        print(f"\n❌ ERRO AO EXECUTAR FUNÇÃO:")
        print(f"Tipo: {type(e).__name__}")
        print(f"Mensagem: {str(e)}")
        
        import traceback
        print("\nStack trace completo:")
        traceback.print_exc()

print("\n" + "="*80)
