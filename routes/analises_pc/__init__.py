from flask import Blueprint

analises_pc_bp = Blueprint('analises_pc', __name__, url_prefix='/analises_pc')

from . import routes
