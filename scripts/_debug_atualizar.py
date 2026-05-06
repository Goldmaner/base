with open('routes/parcerias.py', 'rb') as f:
    lines = f.readlines()

# Find atualizar_alteracao and show the first 100 lines to understand what's being read
idx_func = None
for i, line in enumerate(lines):
    if b'def atualizar_alteracao' in line:
        idx_func = i
        break
print('def at line:', idx_func+1)
for i, line in enumerate(lines[idx_func:idx_func+100], start=idx_func+1):
    print(i, repr(line[:120]))
