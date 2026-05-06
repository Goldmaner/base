with open('routes/parcerias.py', 'rb') as f:
    content = f.read()

# Fix the problematic docstring lines in deletar_alteracao
# These contain mojibake that decodes to § which Python 3.12 rejects

old_line1 = b'    Deletar altera\xc3\x83\xc2\xa7\xc3\x83\xc2\xa3o(\xc3\x83\xc2\xb5es) de termo\r\n'
new_line1 = b'    Deletar alteracao(oes) de termo\r\n'

old_line2 = b'    Deleta todos os registros com a mesma combina\xc3\x83\xc2\xa7\xc3\x83\xc2\xa3o de termo/instrumento/n\xc3\x83\xc2\xbamero\r\n'
new_line2 = b'    Deleta todos os registros com a mesma combinacao de termo/instrumento/numero\r\n'

c1 = content.count(old_line1)
c2 = content.count(old_line2)
print('line1 occurrences:', c1)
print('line2 occurrences:', c2)

content = content.replace(old_line1, new_line1)
content = content.replace(old_line2, new_line2)

# Also fix the comment on line 5312 area which has similar bytes
old_comment = b'        # Deletar todos os registros com essa combina\xc3\x83\xc2\xa7\xc3\x83\xc2\xa3o\r\n'
new_comment = b'        # Deletar todos os registros com essa combinacao\r\n'
content = content.replace(old_comment, new_comment)

# Check for any remaining § (U+00A7) from the double encoding \xc2\xa7
import re
matches = list(re.finditer(b'\xc2\xa7', content))
print('Remaining \\xc2\\xa7 occurrences:', len(matches))
for m in matches:
    print(' at:', m.start(), repr(content[m.start()-30:m.start()+30]))

with open('routes/parcerias.py', 'wb') as f:
    f.write(content)
print('Done')
