"""Remove dead code in dgp_alteracoes function (lines 3242-3439)"""

with open('routes/parcerias.py', 'rb') as f:
    lines = f.readlines()

# Find the redirect line (should be line 3241)
redirect_line = None
for i, line in enumerate(lines):
    if b"return redirect(url_for('parcerias.dgp_kanban'))" in line and i > 3230 and i < 3250:
        redirect_line = i
        break

if redirect_line is None:
    print("ERROR: Could not find redirect line")
    exit(1)

print(f"Redirect at line {redirect_line+1}: {repr(lines[redirect_line])}")

# Find the next @parcerias_bp.route after that
next_route_line = None
for i in range(redirect_line + 1, len(lines)):
    if lines[i].startswith(b'@parcerias_bp.route('):
        next_route_line = i
        break

if next_route_line is None:
    print("ERROR: Could not find next route")
    exit(1)

print(f"Next route at line {next_route_line+1}: {repr(lines[next_route_line])}")

# Remove lines between redirect_line+1 and next_route_line (exclusive)
dead_start = redirect_line + 1
dead_end = next_route_line

print(f"Removing {dead_end - dead_start} lines of dead code ({dead_start+1} to {dead_end})")

new_lines = lines[:dead_start] + lines[dead_end:]

with open('routes/parcerias.py', 'wb') as f:
    f.writelines(new_lines)

print('Done!')

import py_compile
py_compile.compile('routes/parcerias.py', doraise=True)
print('Syntax OK')
