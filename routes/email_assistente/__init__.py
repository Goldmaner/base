from flask import Blueprint

email_assistente_bp = Blueprint(
    'email_assistente',
    __name__,
    url_prefix='/email-assistente'
)

from . import routes  # noqa: E402, F401
