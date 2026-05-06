with open('routes/parcerias.py', 'rb') as f:
    lines = f.readlines()

idx_func = None
for i, line in enumerate(lines):
    if b'def atualizar_alteracao' in line:
        idx_func = i
        break
print('atualizar_alteracao at line:', idx_func+1)

for i in range(idx_func, min(idx_func+1000, len(lines))):
    line = lines[i]
    cnt = line.count(b'"""')
    if cnt > 0:
        print(f'  line {i+1}: {cnt} triple-quote(s): {repr(line[:90])}')
