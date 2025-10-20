"""
Módulo de gerenciamento de conexão com o banco de dados PostgreSQL
Suporta conexões duais: local e Railway (para redundância)
"""

from flask import g
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG, DB_CONFIG_LOCAL, DB_CONFIG_RAILWAY


def get_db_local():
    """
    Obtém a conexão com o banco de dados LOCAL.
    Cria uma nova conexão se não existir uma no contexto da aplicação.
    """
    if "db_local" not in g:
        try:
            g.db_local = psycopg2.connect(**DB_CONFIG_LOCAL)
            g.db_local.autocommit = False  # Para controlar transações manualmente
        except Exception as e:
            print(f"[AVISO] Falha ao conectar no banco LOCAL: {e}")
            g.db_local = None
    return g.db_local


def get_db_railway():
    """
    Obtém a conexão com o banco de dados RAILWAY.
    Cria uma nova conexão se não existir uma no contexto da aplicação.
    """
    if "db_railway" not in g:
        try:
            g.db_railway = psycopg2.connect(**DB_CONFIG_RAILWAY)
            g.db_railway.autocommit = False  # Para controlar transações manualmente
        except Exception as e:
            print(f"[AVISO] Falha ao conectar no banco RAILWAY: {e}")
            g.db_railway = None
    return g.db_railway


def get_db():
    """
    Obtém a conexão com o banco de dados padrão (Railway para compatibilidade).
    Mantida para retrocompatibilidade com código existente.
    """
    if "db" not in g:
        g.db = psycopg2.connect(**DB_CONFIG)
        g.db.autocommit = False
    return g.db


def get_cursor_local():
    """
    Retorna um cursor do banco LOCAL que funciona como dictionary.
    Facilita o acesso aos dados por nome de coluna.
    """
    db = get_db_local()
    if db is None:
        return None
    return db.cursor(cursor_factory=RealDictCursor)


def get_cursor_railway():
    """
    Retorna um cursor do banco RAILWAY que funciona como dictionary.
    Facilita o acesso aos dados por nome de coluna.
    """
    db = get_db_railway()
    if db is None:
        return None
    return db.cursor(cursor_factory=RealDictCursor)


def get_cursor():
    """
    Retorna um cursor do banco padrão (Railway).
    Mantida para retrocompatibilidade com código existente.
    """
    db = get_db()
    return db.cursor(cursor_factory=RealDictCursor)


def execute_dual(query, params=None):
    """
    Executa uma operação de escrita (INSERT/UPDATE/DELETE) nos dois bancos de dados.
    Retorna True se pelo menos um banco foi atualizado com sucesso.
    
    Args:
        query: String SQL a ser executada
        params: Parâmetros para a query (tuple ou dict)
    
    Returns:
        bool: True se sucesso em pelo menos um banco
    """
    success_local = False
    success_railway = False
    
    # Executar no banco LOCAL
    cur_local = get_cursor_local()
    if cur_local:
        try:
            cur_local.execute(query, params)
            get_db_local().commit()
            success_local = True
        except Exception as e:
            print(f"[ERRO] Falha ao executar no banco LOCAL: {e}")
            try:
                get_db_local().rollback()
            except:
                pass
    
    # Executar no banco RAILWAY
    cur_railway = get_cursor_railway()
    if cur_railway:
        try:
            cur_railway.execute(query, params)
            get_db_railway().commit()
            success_railway = True
        except Exception as e:
            print(f"[ERRO] Falha ao executar no banco RAILWAY: {e}")
            try:
                get_db_railway().rollback()
            except:
                pass
    
    return success_local or success_railway


def close_db(e=None):
    """
    Fecha as conexões com os bancos de dados ao final do contexto da aplicação.
    """
    # Fechar conexão local
    db_local = g.pop("db_local", None)
    if db_local is not None:
        db_local.close()
    
    # Fechar conexão railway
    db_railway = g.pop("db_railway", None)
    if db_railway is not None:
        db_railway.close()
    
    # Fechar conexão padrão (retrocompatibilidade)
    db = g.pop("db", None)
    if db is not None:
        db.close()
