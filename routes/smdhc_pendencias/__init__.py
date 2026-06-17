from flask import Blueprint


smdhc_pendencias_bp = Blueprint(
    "smdhc_pendencias",
    __name__,
    url_prefix="/smdhc-pendencias",
)


from . import routes  # noqa: E402,F401
