"""
Servidor de PRODUÇÃO - Porta 5000
Sem hot reload - precisa reiniciar manualmente para aplicar mudanças
& C:/Users/d843702/AppData/Local/Programs/Python/Python312/python.exe "c:/Users/d843702/OneDrive - rede.sp/Área de Trabalho/FAF/FAF/run_prod.py"

"""
import os
os.environ['FLASK_ENV'] = 'production'
os.environ['PORT'] = '5000'

from app import app

if __name__ == '__main__':
    try:
        from waitress import serve

        print("=" * 60)
        print("🚀 SERVIDOR DE PRODUÇÃO (Waitress)")
        print("=" * 60)
        print("Porta: 5000")
        print("Threads: 8 (Windows-safe, 8 requisições simultâneas)")
        print("URL: http://127.0.0.1:5000")
        print("=" * 60)

        serve(app, host='0.0.0.0', port=5000, threads=8)

    except ImportError:
        print("=" * 60)
        print("⚠️  Waitress não encontrado — usando Flask threaded")
        print("Execute: pip install waitress")
        print("=" * 60)
        app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False, threaded=True)
