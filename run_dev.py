"""
Servidor de DESENVOLVIMENTO - Porta 8080
& C:/Users/d843702/AppData/Local/Programs/Python/Python312/python.exe "c:/Users/d843702/OneDrive - rede.sp/Área de Trabalho/FAF/FAF/run_dev.py"

NOTA: use_reloader=False é intencional.
O reloader do Werkzeug reinicia o processo quando detecta mudança de arquivo.
No OneDrive, a sync modifica timestamps continuamente, causando reloads
aleatórios que apagam dados em memória (tarefas de classificação, caches, etc.).
Para aplicar alterações no código: pare o servidor (Ctrl+C) e reinicie.
"""
import os
os.environ['FLASK_ENV'] = 'development'
os.environ['PORT'] = '8080'

from app import app

if __name__ == '__main__':
    print("=" * 60)
    print("SERVIDOR DE DESENVOLVIMENTO")
    print("=" * 60)
    print("Porta: 8080")
    print("URL: http://127.0.0.1:8080")
    print("Hot Reload: DESATIVADO (OneDrive interfere com o reloader)")
    print("Para recarregar: Ctrl+C e reinicie o servidor.")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=8080, use_reloader=False, threaded=True)
