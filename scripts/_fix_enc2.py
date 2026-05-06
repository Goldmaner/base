import re, sys
sys.stdout.reconfigure(encoding='utf-8')
filepath = 'routes/parcerias.py'
with open(filepath, 'rb') as f:
    content = f.read()
original_len = len(content)
pat1 = re.compile(b'\xc3\x83\xc2[\x80-\xbf]')
pat2 = re.compile(b'\xc3\x82\xc2[\x80-\xbf]')
count1 = len(pat1.findall(content))
count2 = len(pat2.findall(content))
content = pat1.sub(lambda m: b'\xc3' + m.group(0)[3:4], content)
content = pat2.sub(lambda m: b'\xc2' + m.group(0)[3:4], content)
print('Pattern 1 fixes:', count1)
print('Pattern 2 fixes:', count2)
print('Size:', original_len, '->', len(content))
ok1 = b'Conclu\xc3\xaddo' in content
ok2 = b'Conclu\xc3\x83\xc2\xaddo' not in content
print('Concluido correct UTF-8 present:', ok1)
print('Old mojibake gone:', ok2)
with open(filepath, 'wb') as f:
    f.write(content)
print('Done')
