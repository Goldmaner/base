with open('routes/parcerias.py', 'rb') as f:
    lines = f.readlines()

# Show editar_alteracao - the part that reads SEI/date from termos_alteracoes
idx_func = None
for i, line in enumerate(lines):
    if b'def editar_alteracao' in line:
        idx_func = i
        break
print('editar_alteracao at line:', idx_func+1)

# Find the part that reads sei from termos_alteracoes
for i, line in enumerate(lines[idx_func:idx_func+200], start=idx_func+1):
    if b'sei' in line.lower() or b'assinatura' in line.lower() or b'termo_sei' in line.lower():
        print(i, repr(line[:120]))

print('\n--- Context around SEI read ---')
for i, line in enumerate(lines[idx_func:idx_func+200], start=idx_func+1):
    if b'Buscar SEI' in line or b'termos_alteracoes' in line:
        start = max(0, i - idx_func - 3)
        for j, l in enumerate(lines[idx_func+start:idx_func+start+20], start=idx_func+start+1):
            print(j, repr(l[:120]))
        break
