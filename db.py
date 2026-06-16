"""
Modulo de gerenciamento de conexao com o banco de dados PostgreSQL.
"""

import time

import psycopg2
from config import DB_CONFIG
from flask import g, request as _flask_request
from psycopg2.extras import RealDictCursor
from psycopg2.pool import PoolError, ThreadedConnectionPool


SLOW_QUERY_THRESHOLD = 1.0


class DatabaseUnavailable(Exception):
    """Banco indisponivel ou conexao perdida durante a requisicao."""


_pool: ThreadedConnectionPool = None


def _get_pool() -> ThreadedConnectionPool:
    """Retorna o pool de conexoes, inicializando-o na primeira chamada."""
    global _pool
    if _pool is None:
        _pool = ThreadedConnectionPool(minconn=2, maxconn=20, **DB_CONFIG)
    return _pool


def _is_connection_error(exc):
    msg = str(exc).lower()
    return (
        isinstance(exc, (psycopg2.OperationalError, PoolError))
        or "ssl" in msg
        or "connection" in msg
        or "server closed" in msg
        or "terminating connection" in msg
    )


def _discard_current_connection():
    db = g.pop("db", None)
    if db is None:
        return
    try:
        _get_pool().putconn(db, close=True)
    except Exception:
        try:
            db.close()
        except Exception:
            pass


def _return_connection(db, close=False):
    if db is None:
        return
    try:
        _get_pool().putconn(db, close=close)
    except Exception:
        try:
            db.close()
        except Exception:
            pass


def get_cursor():
    """
    Retorna um cursor instrumentado que loga queries lentas.

    Importante: se a conexao cair no meio da requisicao, nao reconectamos
    dentro do mesmo execute. Reconectar nesse ponto troca a transacao por baixo
    do codigo chamador e invalida savepoints.
    """
    db = get_db()
    raw_cursor = db.cursor(cursor_factory=RealDictCursor)

    class TimedCursor:
        def __init__(self, cursor):
            self._cur = cursor

        def execute(self, query, params=None):
            t0 = time.time()
            try:
                self._cur.execute(query, params)
            except psycopg2.OperationalError as e:
                if _is_connection_error(e):
                    _discard_current_connection()
                    raise DatabaseUnavailable(
                        f"Conexao com o banco perdida durante a query: {e}"
                    ) from e
                raise
            elapsed = time.time() - t0
            if elapsed >= SLOW_QUERY_THRESHOLD:
                query_text = str(query)
                is_advisory_lock = 'pg_advisory_xact_lock' in query_text
                log_label = 'LOCK WAIT' if is_advisory_lock else 'SLOW QUERY'
                mensagem = (
                    f"Espera de lock do termo: {elapsed:.2f}s"
                    if is_advisory_lock
                    else f"Query lenta: {elapsed:.2f}s"
                )
                print(f"[{log_label} {elapsed:.2f}s] {query_text[:200]}")
                try:
                    from decorators import registrar_erro

                    try:
                        endpoint = _flask_request.path
                        metodo = _flask_request.method
                    except RuntimeError:
                        endpoint = None
                        metodo = None
                    registrar_erro(
                        tipo_erro="query_lenta",
                        duracao_ms=int(elapsed * 1000),
                        query_preview=query_text,
                        endpoint=endpoint,
                        metodo=metodo,
                        mensagem=mensagem,
                    )
                except Exception:
                    pass

        def executemany(self, query, params_list):
            t0 = time.time()
            try:
                self._cur.executemany(query, params_list)
            except psycopg2.OperationalError as e:
                if _is_connection_error(e):
                    _discard_current_connection()
                    raise DatabaseUnavailable(
                        f"Conexao com o banco perdida durante batch: {e}"
                    ) from e
                raise
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
    Obtem a conexao com o banco.

    Falhas de pool/conexao agora geram DatabaseUnavailable. Isso evita que
    rotas recebam None e quebrem mais tarde com AttributeError em cur.execute.
    """
    db = g.get("db", None)

    if db is None or db.closed != 0:
        db = None
    else:
        try:
            db.poll()
        except Exception:
            try:
                db.close()
            except Exception:
                pass
            db = None

    if db is None:
        last_error = None
        for tentativa in range(1, 4):
            db = None
            try:
                db = _get_pool().getconn()
                db.autocommit = False
                with db.cursor() as cur:
                    cur.execute("SET timezone = 'America/Sao_Paulo'")
                db.rollback()
                g.db = db
                break
            except PoolError as e:
                print("[ERRO] Pool de conexoes esgotado - tente novamente em instantes")
                g.db = None
                raise DatabaseUnavailable("Pool de conexoes esgotado") from e
            except Exception as e:
                last_error = e
                _return_connection(db, close=True)
                g.db = None
                if tentativa < 3 and _is_connection_error(e):
                    print(f"[DB] Conexao stale descartada no checkout (tentativa {tentativa}/3): {e}")
                    time.sleep(0.15 * tentativa)
                    continue
                print(f"[ERRO] Falha ao obter conexao do pool: {e}")
                raise DatabaseUnavailable(f"Falha ao obter conexao do banco: {e}") from e

        if g.get("db") is None:
            raise DatabaseUnavailable(f"Falha ao obter conexao do banco: {last_error}")

    return db


def execute_query(query, params=None):
    """
    Executa uma operacao de escrita (INSERT/UPDATE/DELETE).

    Returns:
        bool: True se sucesso, False se erro.
    """
    try:
        cur = get_cursor()
        db = get_db()

        print(f"[DEBUG execute_query] Executando query: {query[:100]}...")
        print(
            "[DEBUG execute_query] Parametros (primeiros 5): "
            f"{params[:5] if params and len(params) > 5 else params}"
        )

        cur.execute(query, params)

        print("[DEBUG execute_query] Query executada, fazendo commit...")
        db.commit()

        print("[DEBUG execute_query] Commit bem-sucedido! Retornando True")
        return True
    except Exception as e:
        print(f"[ERRO execute_query] Falha ao executar query: {type(e).__name__}: {str(e)}")
        import traceback

        traceback.print_exc()
        try:
            get_db().rollback()
        except Exception:
            pass
        return False


def execute_batch(query, params_list):
    """
    Executa uma operacao de escrita em lote (INSERT/UPDATE/DELETE).

    Returns:
        dict: {'success': bool, 'count': int}
    """
    if not params_list:
        return {"success": False, "count": 0}

    count = len(params_list)
    try:
        cur = get_cursor()
        db = get_db()
        cur.executemany(query, params_list)
        db.commit()
        print(f"[OK] {count} registros inseridos em batch")
        return {"success": True, "count": count}
    except Exception as e:
        print(f"[ERRO] Falha ao executar batch: {e}")
        try:
            get_db().rollback()
        except Exception:
            pass
        return {"success": False, "count": 0}


def close_db(e=None):
    """
    Devolve a conexao ao pool ao final do contexto da aplicacao.
    """
    db = g.pop("db", None)
    if db is not None:
        close = bool(getattr(db, "closed", 0))
        if not close:
            try:
                db.rollback()
            except Exception:
                close = True
        _return_connection(db, close=close)
