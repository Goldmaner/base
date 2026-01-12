"""
Script de teste para verificar a lógica de matching de R.F. (Registro Funcional)
entre o formato do usuário e o formato dos analistas.
"""
import re

def normalizar_rf(rf):
    """
    Normaliza um número de R.F. removendo prefixos e caracteres especiais.
    
    Exemplos:
    - "d843702" -> "843702"
    - "843.702-5" -> "8437025"
    - "D843.702-5" -> "8437025"
    """
    if not rf:
        return None
    rf_str = str(rf).lower().strip()
    rf_normalizado = re.sub(r'^d|[.\-\s]', '', rf_str)
    return rf_normalizado if rf_normalizado else None

def normalizar_rf_v2(rf):
    """
    Versão 2: Normaliza extraindo apenas os primeiros 6 dígitos numéricos.
    Ignora dígito verificador.
    
    Exemplos:
    - "d843702" -> "843702"
    - "843.702-5" -> "843702"
    - "D843.702-5" -> "843702"
    """
    if not rf:
        return None
    rf_str = str(rf).lower().strip()
    # Remover o 'd' inicial se existir
    rf_str = re.sub(r'^d', '', rf_str)
    # Extrair apenas dígitos
    digitos = re.sub(r'[^\d]', '', rf_str)
    # Pegar apenas os primeiros 6 dígitos (ignorar dígito verificador)
    return digitos[:6] if len(digitos) >= 6 else digitos

# Casos de teste
test_cases = [
    # (usuario_rf, analista_rf, devem_coincidir)
    ("d843702", "843.702-5", True),
    ("D843702", "843.702-5", True),
    ("d843702", "843702", True),
    ("843702", "843.702-5", True),
    ("d123456", "123.456-7", True),
    ("d123456", "654.321-0", False),
    ("", "123.456-7", False),
    (None, "123.456-7", False),
    ("d843702", "", False),
]

print("=" * 80)
print("TESTE DE NORMALIZAÇÃO DE R.F. - VERSÃO 1 (Atual)")
print("=" * 80)

for usuario_rf, analista_rf, should_match in test_cases:
    user_norm = normalizar_rf(usuario_rf)
    analista_norm = normalizar_rf(analista_rf)
    matches = user_norm == analista_norm if user_norm and analista_norm else False
    
    status = "✓ PASS" if matches == should_match else "✗ FAIL"
    
    print(f"\n{status}")
    print(f"  Usuário:  '{usuario_rf}' -> '{user_norm}'")
    print(f"  Analista: '{analista_rf}' -> '{analista_norm}'")
    print(f"  Match: {matches} (esperado: {should_match})")

print("\n" + "=" * 80)
print("TESTE DE NORMALIZAÇÃO DE R.F. - VERSÃO 2 (Primeiros 6 dígitos)")
print("=" * 80)

for usuario_rf, analista_rf, should_match in test_cases:
    user_norm = normalizar_rf_v2(usuario_rf)
    analista_norm = normalizar_rf_v2(analista_rf)
    matches = user_norm == analista_norm if user_norm and analista_norm else False
    
    status = "✓ PASS" if matches == should_match else "✗ FAIL"
    
    print(f"\n{status}")
    print(f"  Usuário:  '{usuario_rf}' -> '{user_norm}'")
    print(f"  Analista: '{analista_rf}' -> '{analista_norm}'")
    print(f"  Match: {matches} (esperado: {should_match})")

print("\n" + "=" * 80)
print("RECOMENDAÇÃO")
print("=" * 80)
print("""
A VERSÃO 2 é mais robusta pois:
1. Ignora o dígito verificador (último número após o hífen)
2. Compara apenas os 6 primeiros dígitos significativos
3. Funciona independentemente do formato (com ou sem 'd', pontos, hífens)

Sugestão: Atualizar a função normalizar_rf() em routes/analises_pc/routes.py
para usar a lógica da versão 2.
""")
