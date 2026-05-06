import sys, re
sys.stdout.reconfigure(encoding='utf-8')

with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

# Decode to check comparisons
text = content.decode('utf-8')

# Check key comparisons
checks = [
    ("'Concluído'", "'Concluído'" in text),
    ("'Adequação de vigência'", "'Adequação de vigência'" in text),
    ("alt_status == 'Concluído'", "alt_status == 'Concluído'" in text),
    ("= 'Concluído'", "= 'Concluído'" in text),
    ("mojibake Concluido gone", "ConcluÃ" not in text),
    ("mojibake Acao gone", "açÃ" not in text),
]

for desc, ok in checks:
    print(f'[{"OK" if ok else "FAIL"}] {desc}')

# Count occurrences of Concluído
cnt = text.count("'Concluído'")
print(f"Count of 'Concluído' in file: {cnt}")
