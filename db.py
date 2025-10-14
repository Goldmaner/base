"""
Módulo de gerenciamento de conexão com o banco de dados PostgreSQL
"""

from flask import g
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG


def get_db():
    """
    Obtém a conexão com o banco de dados.
    Cria uma nova conexão se não existir uma no contexto da aplicação.
    """
    if "db" not in g:
        g.db = psycopg2.connect(**DB_CONFIG)
        g.db.autocommit = False  # Para controlar transações manualmente
    return g.db


def get_cursor():
    """
    Retorna um cursor que funciona como dictionary (similar ao sqlite3.Row).
    Facilita o acesso aos dados por nome de coluna.
    """
    db = get_db()
    return db.cursor(cursor_factory=RealDictCursor)


def close_db(e=None):
    """
    Fecha a conexão com o banco de dados ao final do contexto da aplicação.
    """
    db = g.pop("db", None)
    if db is not None:
        db.close()
