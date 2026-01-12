def converter_valor_para_db(valor, campo):
    if campo == 'status' and isinstance(valor, str):
        return valor.lower() in ['ativo', 'true', '1', 'sim']
    return valor

def converter_valor_para_frontend(valor, campo):
    if campo == 'status' and isinstance(valor, bool):
        return 'Ativo' if valor else 'Inativo'
    return valor

# Testes
print("=== Conversão para DB ===")
print(f"'Ativo' -> {converter_valor_para_db('Ativo', 'status')}")
print(f"'Inativo' -> {converter_valor_para_db('Inativo', 'status')}")
print(f"'ativo' -> {converter_valor_para_db('ativo', 'status')}")
print(f"'inativo' -> {converter_valor_para_db('inativo', 'status')}")

print("\n=== Conversão para Frontend ===")
print(f"True -> {converter_valor_para_frontend(True, 'status')}")
print(f"False -> {converter_valor_para_frontend(False, 'status')}")

print("\n=== Outros campos ===")
print(f"'João' -> {converter_valor_para_db('João', 'nome_analista')}")
print(f"'123456' -> {converter_valor_para_db('123456', 'rf')}")
