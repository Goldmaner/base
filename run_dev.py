"""
Servidor de DESENVOLVIMENTO - Porta 8080
Com hot reload ativado para reiniciar automaticamente ao editar código
"""
import os
os.environ['FLASK_ENV'] = 'development'
os.environ['PORT'] = '8080'

from app import app

if __name__ == '__main__':
    print("=" * 60)
    print("🔧 SERVIDOR DE DESENVOLVIMENTO")
    print("=" * 60)
    print("Porta: 8080")
    print("URL: http://127.0.0.1:8080")
    print("Hot Reload: ATIVADO (reinicia automaticamente ao salvar)")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=8080, use_reloader=True)
