"""
Fix double-encoded UTF-8 in parcerias.py.

The file contains text that was encoded twice:
  - 'í' (U+00ED) should be bytes \xc3\xad but is stored as \xc3\x83\xc2\xad
  - 'ã' (U+00E3) should be \xc3\xa3 but is stored as \xc3\x83\xc2\xa3
  - 'ç' (U+00E7) should be \xc3\xa7 but is stored as \xc3\x83\xc2\xa7
  etc.

This causes ALL string comparisons with accented chars (like == 'Concluído') to silently fail.

Fix: replace \xc3\x83\xc2\xXX -> \xc3\xXX for continuation bytes 0x80-0xBF
     replace \xc3\x82\xc2\xXX -> \xc2\xXX for the 0x80-0xBF range
"""
import re

filepath = 'routes/parcerias.py'

with open(filepath, 'rb') as f:
    content = f.read()

original_len = len(content)

# Pattern 1: chars originally U+00C0 to U+00FF (ç ã é í ó ú à â ô etc.)
# Double-encoded: \xc3\x83 + \xc2\xXX  ->  should be: \xc3\xXX
count1 = len(re.findall(b'\xc3\x83\xc2[\x80-\xbf]', content))
content = re.sub(b'\xc3\x83\xc2([\x80-\xbf])', lambda m: b'\xc3' + m.group(1), content)

# Pattern 2: chars originally U+0080 to U+00BF  
# Double-encoded: \xc3\x82 + \xc2\xXX  ->  should be: \xc2\xXX
count2 = len(re.findall(b'\xc3\x82\xc2[\x80-\xbf]', content))
content = re.sub(b'\xc3\x82\xc2([\x80-\xbf])', lambda m: b'\xc2' + m.group(1), content)

print(f'Pattern 1 (U+00C0-U+00FF) fixes: {count1}')
print(f'Pattern 2 (U+0080-U+00BF) fixes: {count2}')
print(f'File size: {original_len} -> {len(content)} bytes')

# Quick sanity check: verify 'Concluido' and 'Concluído' appear
if b'Conclu\xc3\xaddo' in content:
    print('OK: Concluido (correct UTF-8) present')
if b'Conclu\xc3\x83\xc2\xaddo' not in content:
    print('OK: old mojibake Concluido gone')
else:
    print('WARNING: old mojibake still present')

with open(filepath, 'wb') as f:
    f.write(content)

print('Done')
