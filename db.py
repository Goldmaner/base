"""
Módulo de gerenciamento de conexão com o banco de dados PostgreSQL LOCAL
"""

from flask import g, request as _flask_request
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool, PoolError
from config import DB_CONFIG
import time

# Queries que demorem mais que este valor (em segundos) serão logadas
SLOW_QUERY_THRESHOLD = 1.0

# ---------------------------------------------------------------------------
# Connection Pool (criado uma única vez por processo)
# ---------------------------------------------------------------------------
_pool: ThreadedConnectionPool = None


def _get_pool() -> ThreadedConnectionPool:
    """Retorna o pool de conexões, inicializando-o na primeira chamada."""
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(minconn=2, maxconn=20, **DB_CONFIG)
    return _pool


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
            try:
                self._cur.execute(query, params)
            except psycopg2.OperationalError as e:
                # Conexão SSL caiu — reconectar e repetir com backoff
                if 'SSL' in str(e) or 'connection' in str(e).lower():
                    print(f"[DB] Reconectando após queda SSL: {e}")
                    last_err = e
                    for tentativa, espera in enumerate([0.3, 1.0, 2.0], start=1):
                        try:
                            time.sleep(espera)
                            # Descarta a conexão corrompida do pool
                            try:
                                _get_pool().putconn(g.db, close=True)
                            except Exception:
                                pass
                            new_conn = _get_pool().getconn()
                            new_conn.autocommit = False
                            g.db = new_conn
                            self._cur = g.db.cursor(cursor_factory=RealDictCursor)
                            self._cur.execute(query, params)
                            print(f"[DB] Reconexão bem-sucedida na tentativa {tentativa}")
                            last_err = None
                            break
                        except Exception as e2:
                            print(f"[DB] Tentativa {tentativa} falhou: {e2}")
                            last_err = e2
                    if last_err is not None:
                        raise last_err
                else:
                    raise
            elapsed = time.time() - t0
            if elapsed >= SLOW_QUERY_THRESHOLD:
                print(f"[SLOW QUERY {elapsed:.2f}s] {str(query)[:200]}")
                try:
                    from decorators import registrar_erro
                    # Capturar rota que originou a query (contexto de request)
                    try:
                        _endpoint = _flask_request.path
                        _metodo   = _flask_request.method
                    except RuntimeError:
                        _endpoint = None
                        _metodo   = None
                    registrar_erro(
                        tipo_erro='query_lenta',
                        duracao_ms=int(elapsed * 1000),
                        query_preview=str(query),  # query completa, sem truncamento
                        endpoint=_endpoint,
                        metodo=_metodo,
                        mensagem=f'Query lenta: {elapsed:.2f}s',
                    )
                except Exception:
                    pass

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
    db = g.get('db', None)

    # Verificar se conexão está fechada ou inválida
    if db is None or db.closed != 0:
        db = None
    else:
        try:
            # poll() não envia dados — apenas verifica o estado do socket
            db.poll()
        except Exception:
            try:
                db.close()
            except Exception:
                pass
            db = None

    if db is None:
        try:
            db = _get_pool().getconn()
            db.autocommit = False
            g.db = db
        except PoolError:
            print("[ERRO] Pool de conexões esgotado — tente novamente em instantes")
            g.db = None
            return None
        except Exception as e:
            print(f"[ERRO] Falha ao obter conexão do pool: {e}")
            g.db = None
            return None

    return db


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
    Devolve a conexão ao pool ao final do contexto da aplicação.
    """
    db = g.pop("db", None)
    if db is not None:
        try:
            _get_pool().putconn(db)
        except Exception:
            try:
                db.close()
            except Exception:
                pass
