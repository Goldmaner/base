import re

def converter_sei_para_cod_sof(sei_celeb):
    if not sei_celeb:
        return None
    return re.sub(r'[.\-/]', '', sei_celeb)

sei = '6074.2023/0004039-2'
cod_sof = converter_sei_para_cod_sof(sei)
print(f"SEI: {sei}")
print(f"cod_sof: {cod_sof}")
print(f"Esperado: 6074202300040392")
print(f"Match: {cod_sof == '6074202300040392'}")
