with open('routes/parcerias.py', 'rb') as f:
    lines = f.readlines()

# Show lines 5225-5270
for i, line in enumerate(lines[5224:5270], start=5225):
    print(i, repr(line[:100]))
