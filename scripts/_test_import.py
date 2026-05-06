import sys
sys.path.insert(0, '.')
try:
    from routes.parcerias import parcerias_bp
    print('Import OK')
except SyntaxError as e:
    print('SyntaxError:', e)
except Exception as e:
    print('Other error:', e)
