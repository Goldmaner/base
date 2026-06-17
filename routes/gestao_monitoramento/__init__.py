from flask import Blueprint


gestao_monitoramento_bp = Blueprint(
    "gestao_monitoramento",
    __name__,
    url_prefix="/gestao-monitoramento",
)


from . import routes  # noqa: E402,F401
