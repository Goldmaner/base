with open('routes/parcerias.py', 'rb') as f:
    lines = f.readlines()

# Show lines 5070-5130 (the full SEI read block in editar_alteracao)
for i, line in enumerate(lines[5069:5130], start=5070):
    print(i, repr(line[:130]))
