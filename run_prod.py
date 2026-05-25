"""
Servidor de PRODUÇÃO - Porta 5000
Sem hot reload - precisa reiniciar manualmente para aplicar mudanças
& C:/Users/d843702/AppData/Local/Programs/Python/Python312/python.exe "c:/Users/d843702/OneDrive - rede.sp/Área de Trabalho/FAF/FAF/run_prod.py"

"""
import os
import logging
import sys

os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_DEBUG'] = '0'
os.environ['DEBUG'] = 'False'
os.environ['PORT'] = '5000'

from app import app

# Garantir que debug/reloader nunca ficam ativos em produção,
# independente do que estiver no .env
app.config['DEBUG'] = False
app.config['TESTING'] = False

if __name__ == '__main__':
    try:
        from waitress import serve

        # Redirecionar logs do waitress para stdout
        logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                            format='%(asctime)s [%(levelname)s] %(message)s',
                            datefmt='%d/%b/%Y %H:%M:%S', force=True)

        print("=" * 60)
        print("SERVIDOR DE PRODUCAO (Waitress)")
        print("=" * 60)
        print("Porta: 5000")
        print("Threads: 8")
        print("URL: http://127.0.0.1:5000")
        print("=" * 60)

        serve(app, host='0.0.0.0', port=5000, threads=8)

    except ImportError:
        print("=" * 60)
        print("Waitress nao encontrado — usando Flask threaded")
        print("Execute: pip install waitress")
        print("=" * 60)
        app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False, threaded=True)
