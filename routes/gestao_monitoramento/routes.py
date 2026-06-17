from __future__ import annotations

from flask import abort, flash, g, redirect, render_template, request, session, url_for

from decorators import requires_access, requires_write_access
from utils import login_required

from . import gestao_monitoramento_bp
from .forms import EquipamentoFormData, EscopoDgmFormData, FormValidationError, equipamentos_from_text
from . import services


def _usuario_atual() -> str:
    return session.get("email") or session.get("d_usuario") or "sistema"


def _flash_form_errors(exc: FormValidationError) -> None:
    for error in exc.errors:
        flash(error, "warning")


@gestao_monitoramento_bp.route("/parcerias-dgm", methods=["GET"])
@login_required
@requires_access("parcerias")
def parcerias_dgm():
    q = (request.args.get("q") or "").strip()
    escopo = request.args.get("escopo", "todos")
    ativo = request.args.get("ativo", "ativos")
    vigencia = request.args.get("vigencia", "todos")
    context = {
        "q": q,
        "escopo": escopo,
        "ativo": ativo,
        "vigencia": vigencia,
        "abrir_equipamentos": request.args.get("abrir_equipamentos", type=int),
        "resumo": services.obter_resumo(),
        "escopos": services.listar_escopos(q=q, escopo=escopo, ativo=ativo, vigencia=vigencia),
        "termos_options": services.listar_termos_colaboracao(),
    }
    return render_template("gestao_monitoramento/parcerias_dgm.html", **context)


@gestao_monitoramento_bp.route("/parcerias-dgm", methods=["POST"])
@login_required
@requires_access("parcerias")
@requires_write_access("parcerias")
def criar_escopo():
    try:
        data = EscopoDgmFormData.from_request(request)
    except FormValidationError as exc:
        _flash_form_errors(exc)
        return redirect(url_for("gestao_monitoramento.parcerias_dgm"))

    escopo_id = services.salvar_escopo(data, _usuario_atual())
    g.log_recurso_tipo = "parcerias_dgm_escopo"
    g.log_recurso_id = escopo_id
    g.log_detalhes = {
        "acao": "salvar_escopo_dgm",
        "numero_termo": data.numero_termo,
        "dgm_escopo_termo": data.dgm_escopo_termo,
    }
    flash("Termo salvo no escopo DGM.", "success")
    return redirect(url_for("gestao_monitoramento.parcerias_dgm"))


@gestao_monitoramento_bp.route("/parcerias-dgm/<int:escopo_id>/editar", methods=["POST"])
@login_required
@requires_access("parcerias")
@requires_write_access("parcerias")
def editar_escopo(escopo_id: int):
    dgm_escopo_termo = request.form.get("dgm_escopo_termo") == "on"
    if not services.atualizar_escopo(escopo_id, dgm_escopo_termo, _usuario_atual()):
        abort(404)
    g.log_recurso_tipo = "parcerias_dgm_escopo"
    g.log_recurso_id = escopo_id
    g.log_detalhes = {"acao": "editar_escopo_dgm", "dgm_escopo_termo": dgm_escopo_termo}
    flash("Escopo atualizado.", "success")
    return redirect(url_for("gestao_monitoramento.parcerias_dgm"))


@gestao_monitoramento_bp.route("/parcerias-dgm/<int:escopo_id>/desativar", methods=["POST"])
@login_required
@requires_access("parcerias")
@requires_write_access("parcerias")
def desativar_escopo(escopo_id: int):
    if not services.definir_ativo_escopo(escopo_id, False, _usuario_atual()):
        abort(404)
    g.log_recurso_tipo = "parcerias_dgm_escopo"
    g.log_recurso_id = escopo_id
    g.log_detalhes = {"acao": "desativar_escopo_dgm"}
    flash("Termo desativado do painel DGM.", "success")
    return redirect(url_for("gestao_monitoramento.parcerias_dgm"))


@gestao_monitoramento_bp.route("/parcerias-dgm/<int:escopo_id>/reativar", methods=["POST"])
@login_required
@requires_access("parcerias")
@requires_write_access("parcerias")
def reativar_escopo(escopo_id: int):
    if not services.definir_ativo_escopo(escopo_id, True, _usuario_atual()):
        abort(404)
    g.log_recurso_tipo = "parcerias_dgm_escopo"
    g.log_recurso_id = escopo_id
    g.log_detalhes = {"acao": "reativar_escopo_dgm"}
    flash("Termo reativado no painel DGM.", "success")
    return redirect(url_for("gestao_monitoramento.parcerias_dgm"))


@gestao_monitoramento_bp.route("/parcerias-dgm/<int:escopo_id>/equipamentos", methods=["GET", "POST"])
@login_required
@requires_access("parcerias")
@requires_write_access("parcerias")
def equipamentos(escopo_id: int):
    escopo = services.obter_escopo(escopo_id)
    if not escopo:
        abort(404)

    if request.method == "GET":
        return redirect(url_for("gestao_monitoramento.parcerias_dgm", abrir_equipamentos=escopo_id))

    try:
        equipamentos_nomes = equipamentos_from_text(request.form.get("termo_equipamento") or "")
    except FormValidationError as exc:
        _flash_form_errors(exc)
        return redirect(url_for("gestao_monitoramento.parcerias_dgm", abrir_equipamentos=escopo_id))

    total = services.criar_equipamentos(escopo["numero_termo"], equipamentos_nomes, _usuario_atual())
    g.log_recurso_tipo = "parcerias_equipamentos"
    g.log_recurso_id = escopo_id
    g.log_detalhes = {
        "acao": "criar_equipamentos_dgm",
        "numero_termo": escopo["numero_termo"],
        "total": total,
    }
    flash(f"{total} equipamento(s) incluido(s).", "success")
    return redirect(url_for("gestao_monitoramento.parcerias_dgm", abrir_equipamentos=escopo_id))


@gestao_monitoramento_bp.route("/parcerias-dgm/<int:escopo_id>/equipamentos/<int:equipamento_id>/editar", methods=["POST"])
@login_required
@requires_access("parcerias")
@requires_write_access("parcerias")
def editar_equipamento(escopo_id: int, equipamento_id: int):
    if not services.obter_escopo(escopo_id):
        abort(404)
    try:
        data = EquipamentoFormData.from_request(request)
    except FormValidationError as exc:
        _flash_form_errors(exc)
        return redirect(url_for("gestao_monitoramento.parcerias_dgm"))

    if not services.atualizar_equipamento(equipamento_id, data, _usuario_atual()):
        abort(404)
    g.log_recurso_tipo = "parcerias_equipamentos"
    g.log_recurso_id = equipamento_id
    g.log_detalhes = {"acao": "editar_equipamento_dgm", "termo_equipamento": data.termo_equipamento}
    flash("Equipamento atualizado.", "success")
    return redirect(url_for("gestao_monitoramento.parcerias_dgm", abrir_equipamentos=escopo_id))


@gestao_monitoramento_bp.route("/parcerias-dgm/<int:escopo_id>/equipamentos/<int:equipamento_id>/desativar", methods=["POST"])
@login_required
@requires_access("parcerias")
@requires_write_access("parcerias")
def desativar_equipamento(escopo_id: int, equipamento_id: int):
    if not services.obter_escopo(escopo_id):
        abort(404)
    if not services.definir_ativo_equipamento(equipamento_id, False, _usuario_atual()):
        abort(404)
    g.log_recurso_tipo = "parcerias_equipamentos"
    g.log_recurso_id = equipamento_id
    g.log_detalhes = {"acao": "desativar_equipamento_dgm"}
    flash("Equipamento desativado.", "success")
    return redirect(url_for("gestao_monitoramento.parcerias_dgm", abrir_equipamentos=escopo_id))


@gestao_monitoramento_bp.route("/parcerias-dgm/<int:escopo_id>/equipamentos/<int:equipamento_id>/reativar", methods=["POST"])
@login_required
@requires_access("parcerias")
@requires_write_access("parcerias")
def reativar_equipamento(escopo_id: int, equipamento_id: int):
    if not services.obter_escopo(escopo_id):
        abort(404)
    if not services.definir_ativo_equipamento(equipamento_id, True, _usuario_atual()):
        abort(404)
    g.log_recurso_tipo = "parcerias_equipamentos"
    g.log_recurso_id = equipamento_id
    g.log_detalhes = {"acao": "reativar_equipamento_dgm"}
    flash("Equipamento reativado.", "success")
    return redirect(url_for("gestao_monitoramento.parcerias_dgm", ativo="todos", abrir_equipamentos=escopo_id))
