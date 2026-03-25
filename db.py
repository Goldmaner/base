"""
Módulo de gerenciamento de conexão com o banco de dados PostgreSQL LOCAL
"""

from flask import g
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG
import time

# Queries que demorem mais que este valor (em segundos) serão logadas
SLOW_QUERY_THRESHOLD = 1.0


def get_cursor():
    """
    Retorna um cursor instrumentado que loga queries lentas (> SLOW_QUERY_THRESHOLD segundos).
    """
    db = get_db()
    if db is None:
        return None
    raw_cursor = db.cursor(cursor_factory=RealDictCursor)

    class TimedCursor:
        def __init__(self, cursor):
            self._cur = cursor

        def execute(self, query, params=None):
            t0 = time.time()
            self._cur.execute(query, params)
            elapsed = time.time() - t0
            if elapsed >= SLOW_QUERY_THRESHOLD:
                print(f"[SLOW QUERY {elapsed:.2f}s] {str(query)[:200]}")

        def executemany(self, query, params_list):
            t0 = time.time()
            self._cur.executemany(query, params_list)
            elapsed = time.time() - t0
            if elapsed >= SLOW_QUERY_THRESHOLD:
                print(f"[SLOW QUERY BATCH {elapsed:.2f}s] {str(query)[:200]}")

        def __getattr__(self, name):
            return getattr(self._cur, name)

        def __iter__(self):
            return iter(self._cur)

    return TimedCursor(raw_cursor)


def get_db():
    """
    Obtém a conexão com o banco de dados LOCAL.
    Cria uma nova conexão se não existir uma no contexto da aplicação.
    Reconecta automaticamente se a conexão foi encerrada pelo servidor (ex: timeout SSL).
    """
    if "db" not in g or g.db is None or g.db.closed != 0:
        try:
            g.db = psycopg2.connect(**DB_CONFIG)
            g.db.autocommit = False  # Para controlar transações manualmente
        except Exception as e:
            print(f"[ERRO] Falha ao conectar no banco: {e}")
            g.db = None
    return g.db


def execute_query(query, params=None):
    """
    Executa uma operação de escrita (INSERT/UPDATE/DELETE).
    
    Args:
        query: String SQL a ser executada
        params: Parâmetros para a query (tuple ou dict)
    
    Returns:
        bool: True se sucesso, False se erro
    """
    cur = get_cursor()
    db = get_db()
    
    if not cur or not db:
        print(f"[ERRO execute_query] Falha ao obter conexão com banco")
        return False
    
    try:
        print(f"[DEBUG execute_query] Executando query: {query[:100]}...")
        print(f"[DEBUG execute_query] Parâmetros (primeiros 5): {params[:5] if params and len(params) > 5 else params}")
        
        cur.execute(query, params)
        
        print(f"[DEBUG execute_query] Query executada, fazendo commit...")
        db.commit()
        
        print(f"[DEBUG execute_query] Commit bem-sucedido! Retornando True")
        return True
    except Exception as e:
        print(f"[ERRO execute_query] Falha ao executar query: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        try:
            print(f"[DEBUG execute_query] Fazendo rollback...")
            db.rollback()
        except:
            pass
        return False


def execute_batch(query, params_list):
    """
    Executa uma operação de escrita em LOTE (INSERT/UPDATE/DELETE).
    Usa executemany para melhor performance com múltiplos registros.
    
    Args:
        query: String SQL a ser executada
        params_list: Lista de tuplas com os parâmetros para cada execução
    
    Returns:
        dict: {'success': bool, 'count': int}
    """
    if not params_list:
        return {'success': False, 'count': 0}
    
    count = len(params_list)
    cur = get_cursor()
    db = get_db()
    
    if not cur or not db:
        print(f"[ERRO] Falha ao obter conexão com banco")
        return {'success': False, 'count': 0}
    
    try:
        cur.executemany(query, params_list)
        db.commit()
        print(f"[OK] {count} registros inseridos em batch")
        return {
            'success': True,
            'count': count
        }
    except Exception as e:
        print(f"[ERRO] Falha ao executar batch: {e}")
        try:
            db.rollback()
        except:
            pass
        return {
            'success': False,
            'count': 0
        }


def close_db(e=None):
    """
    Fecha a conexão com o banco de dados ao final do contexto da aplicação.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()
