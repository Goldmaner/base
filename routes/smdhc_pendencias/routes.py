from __future__ import annotations

import io
import mimetypes
from datetime import datetime

from flask import (
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from decorators import requires_access, requires_write_access
from utils import login_required
import utils_storage as storage

from . import smdhc_pendencias_bp
from .forms import (
    AtualizacaoFormData,
    DocumentoRelacionadoFormData,
    FormValidationError,
    LinkRelacionadoFormData,
    MatrizFormData,
    PendenciaFiltersForm,
    PendenciaFormData,
    ProcessoSeiFormData,
    ResponsaveisFormData,
    pendencia_form_values,
)
from . import services


SITUACOES_OPTIONS = [
    "Sem prazo",
    "Vencido",
    "Prazo próximo",
    "Parado",
    "Aguardando validação",
    "Concluído",
]
DOCUMENTO_MAX_SIZE_BYTES = 30 * 1024 * 1024
DOCUMENTO_ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "txt", "png", "jpg", "jpeg", "odt", "ods",
}


def _usuario_atual() -> str:
    return session.get("email") or session.get("d_usuario") or "sistema"


def _wants_json() -> bool:
    return (
        request.is_json
        or request.path.startswith("/smdhc-pendencias/api/")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.accept_mimetypes.best == "application/json"
    )


def _build_documento_storage_path(pendencia_id: int, original_filename: str) -> tuple[str, str]:
    nome_seguro = secure_filename(original_filename)
    if not nome_seguro:
        nome_seguro = "documento"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_armazenado = f"{timestamp}_{nome_seguro}"
    return nome_armazenado, f"Pendencias/{pendencia_id}/{nome_armazenado}"


def _build_page_context(*, filtros=None, form_values=None) -> dict:
    filtros = filtros or PendenciaFiltersForm()
    return {
        "filtros": filtros,
        "form_values": form_values or {},
        "status_options": services.listar_status_options(),
        "atualizacao_tipos": services.listar_atualizacao_tipos(),
        "tema_tipos": services.listar_tema_tipos(),
        "areas_demandantes": services.listar_area_demandante(),
        "areas_responsaveis": services.listar_area_responsavel(),
        "areas_correlatas": services.listar_area_correlata(),
        "situacoes_options": SITUACOES_OPTIONS,
        "usuarios_options": services.listar_usuarios_infos(),
        "principios_options": services.listar_principios(),
    }


def _json_or_redirect_success(message: str, endpoint: str, **values):
    if _wants_json():
        payload = {"success": True, "mensagem": message}
        if values:
            payload.update(values)
        return jsonify(payload)
    flash(message, "success")
    return redirect(endpoint)


def _handle_form_error(exc: FormValidationError, *, template_name: str | None = None, context: dict | None = None, fallback_url: str | None = None):
    if _wants_json():
        return jsonify({"erro": "Dados invalidos.", "detalhes": exc.errors}), 400
    for error in exc.errors:
        flash(error, "warning")
    if template_name:
        return render_template(template_name, **(context or {})), 400
    return redirect(fallback_url or url_for("smdhc_pendencias.index"))


@smdhc_pendencias_bp.route("", methods=["GET"])
@login_required
@requires_access("smdhc_pendencias")
def index():
    filtros = PendenciaFiltersForm.from_args(request.args)
    context = _build_page_context(filtros=filtros)
    context["pendencias"] = services.listar_pendencias(filtros)
    context["resumo"] = services.obter_resumo_dashboard(filtros)
    context["alertas"] = services.obter_alertas_dashboard(filtros)
    return render_template("smdhc_pendencias/smdhc_pendencias.html", **context)


@smdhc_pendencias_bp.route("/nova", methods=["GET", "POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def nova():
    if request.method == "POST":
        form_values = pendencia_form_values(request)
        try:
            data = PendenciaFormData.from_request(request)
        except FormValidationError as exc:
            context = _build_page_context(form_values=form_values)
            context["modo"] = "nova"
            context["titulo_pagina"] = "Nova Pendência"
            return _handle_form_error(
                exc,
                template_name="smdhc_pendencias/smdhc_pendencia_form.html",
                context=context,
            )

        pendencia_id = services.criar_pendencia(data, _usuario_atual())
        g.log_recurso_tipo = "pendencia"
        g.log_recurso_id = pendencia_id
        g.log_detalhes = {"acao": "criacao_pendencia", "tema_nome": data.tema_nome}
        detail_url = url_for("smdhc_pendencias.detalhe", id=pendencia_id)
        return _json_or_redirect_success("Pendência criada com sucesso.", detail_url, id=pendencia_id, redirect=detail_url)

    context = _build_page_context(form_values={})
    context["modo"] = "nova"
    context["titulo_pagina"] = "Nova Pendência"
    return render_template("smdhc_pendencias/smdhc_pendencia_form.html", **context)


@smdhc_pendencias_bp.route("/<int:id>", methods=["GET"])
@login_required
@requires_access("smdhc_pendencias")
def detalhe(id: int):
    pendencia = services.obter_pendencia(id)
    if not pendencia:
        abort(404)
    context = _build_page_context()
    context["pendencia"] = pendencia
    return render_template("smdhc_pendencias/smdhc_pendencia_detalhe.html", **context)


@smdhc_pendencias_bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def editar(id: int):
    pendencia = services.obter_pendencia(id)
    if not pendencia:
        abort(404)

    if request.method == "POST":
        form_values = pendencia_form_values(request)
        try:
            data = PendenciaFormData.from_request(request)
        except FormValidationError as exc:
            context = _build_page_context(form_values=form_values)
            context["modo"] = "editar"
            context["pendencia"] = pendencia
            context["titulo_pagina"] = "Editar Pendência"
            return _handle_form_error(
                exc,
                template_name="smdhc_pendencias/smdhc_pendencia_form.html",
                context=context,
            )

        services.atualizar_pendencia(id, data, _usuario_atual())
        g.log_recurso_tipo = "pendencia"
        g.log_recurso_id = id
        g.log_detalhes = {"acao": "edicao_pendencia", "tema_nome": data.tema_nome}
        detail_url = url_for("smdhc_pendencias.detalhe", id=id)
        return _json_or_redirect_success("Pendência atualizada com sucesso.", detail_url, id=id, redirect=detail_url)

    context = _build_page_context(form_values={
        "tema_nome": pendencia.get("tema_nome") or "",
        "tema_tipo": pendencia.get("tema_tipo_id") or "",
        "tema_descricao": pendencia.get("tema_descricao") or "",
        "tema_area_demandante": pendencia.get("tema_area_demandante_id") or "",
        "tema_area_responsavel": pendencia.get("tema_area_responsavel_ids") or [],
        "tema_area_correlata": pendencia.get("tema_area_correlata_ids") or [],
        "tema_status": pendencia.get("tema_status_id") or "",
        "tema_prazo_estimado": pendencia.get("tema_prazo_estimado").isoformat() if pendencia.get("tema_prazo_estimado") else "",
        "tema_observacoes": pendencia.get("tema_observacoes") or "",
        "situacao_automatica": pendencia.get("situacao_automatica") or "",
        "prioridade_manual": pendencia.get("prioridade_manual") or "",
        "prioridade_observacao": pendencia.get("prioridade_observacao") or "",
    })
    context["modo"] = "editar"
    context["pendencia"] = pendencia
    context["titulo_pagina"] = "Editar Pendência"
    return render_template("smdhc_pendencias/smdhc_pendencia_form.html", **context)


@smdhc_pendencias_bp.route("/<int:id>/excluir", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def excluir(id: int):
    services.excluir_pendencia_logicamente(id, _usuario_atual())
    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "exclusao_logica_pendencia"}
    return _json_or_redirect_success("Pendência arquivada com sucesso.", url_for("smdhc_pendencias.index"), id=id)


@smdhc_pendencias_bp.route("/<int:id>/atualizacao", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def registrar_atualizacao(id: int):
    try:
        data = AtualizacaoFormData.from_request(request)
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    if services.tipo_atualizacao_requer_participantes(data.tema_atualizacao_tipo) and not data.participantes_usuario_ids and not data.participantes_externos:
        return _handle_form_error(
            FormValidationError(["Reuniao: informe ao menos um participante interno ou externo."]),
            fallback_url=url_for("smdhc_pendencias.detalhe", id=id),
        )

    registro_id = services.registrar_atualizacao(id, data, _usuario_atual())
    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "registro_atualizacao", "atualizacao_id": registro_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Atualização registrada com sucesso.", detail_url, id=registro_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/atualizacao/<int:atualizacao_id>/editar", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def editar_atualizacao(id: int, atualizacao_id: int):
    try:
        data = AtualizacaoFormData.from_request(request)
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    if services.tipo_atualizacao_requer_participantes(data.tema_atualizacao_tipo) and not data.participantes_usuario_ids and not data.participantes_externos:
        return _handle_form_error(
            FormValidationError(["Reuniao: informe ao menos um participante interno ou externo."]),
            fallback_url=url_for("smdhc_pendencias.detalhe", id=id),
        )

    atualizado = services.atualizar_atualizacao(id, atualizacao_id, data, _usuario_atual())
    if not atualizado:
        abort(404)

    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "edicao_atualizacao", "atualizacao_id": atualizacao_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Atualização editada com sucesso.", detail_url, id=atualizacao_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/sei", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def registrar_sei(id: int):
    try:
        data = ProcessoSeiFormData.from_request(request)
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    registro_id = services.registrar_processo_sei(id, data, _usuario_atual())
    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "registro_processo_sei", "processo_id": registro_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Processo SEI registrado com sucesso.", detail_url, id=registro_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/sei/<int:processo_id>/editar", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def editar_sei(id: int, processo_id: int):
    try:
        data = ProcessoSeiFormData.from_request(request)
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    atualizado = services.atualizar_processo_sei(id, processo_id, data, _usuario_atual())
    if not atualizado:
        abort(404)

    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "edicao_processo_sei", "processo_id": processo_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Processo SEI atualizado com sucesso.", detail_url, id=processo_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/links", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def registrar_link(id: int):
    try:
        data = LinkRelacionadoFormData.from_request(request)
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    registro_id = services.registrar_link_relacionado(id, data, _usuario_atual())
    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "registro_link_relacionado", "link_id": registro_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Link relacionado incluído com sucesso.", detail_url, id=registro_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/links/<int:link_id>/editar", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def editar_link(id: int, link_id: int):
    try:
        data = LinkRelacionadoFormData.from_request(request)
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    atualizado = services.atualizar_link_relacionado(id, link_id, data, _usuario_atual())
    if not atualizado:
        abort(404)

    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "edicao_link_relacionado", "link_id": link_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Link relacionado atualizado com sucesso.", detail_url, id=link_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/links/<int:link_id>/excluir", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def excluir_link(id: int, link_id: int):
    excluido = services.excluir_link_relacionado(id, link_id, _usuario_atual())
    if not excluido:
        abort(404)
    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "exclusao_link_relacionado", "link_id": link_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Link relacionado removido com sucesso.", detail_url, id=link_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/documentos", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def registrar_documento(id: int):
    try:
        data = DocumentoRelacionadoFormData.from_request(
            request,
            allowed_extensions=DOCUMENTO_ALLOWED_EXTENSIONS,
            max_size_bytes=DOCUMENTO_MAX_SIZE_BYTES,
        )
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    nome_armazenado, storage_path = _build_documento_storage_path(id, data.arquivo_nome_original)
    data.arquivo.stream.seek(0)

    try:
        storage.upload_file(storage_path, data.arquivo.read(), data.arquivo_content_type)
        registro_id = services.registrar_documento_relacionado(
            id,
            documento_titulo=data.documento_titulo,
            documento_descricao=data.documento_descricao,
            documento_nome_original=data.arquivo_nome_original,
            documento_storage_path=storage_path,
            documento_content_type=data.arquivo_content_type,
            documento_tamanho_bytes=data.arquivo_tamanho_bytes,
            usuario=_usuario_atual(),
        )
    except Exception:
        storage.delete_file(storage_path)
        raise

    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {
        "acao": "registro_documento_relacionado",
        "documento_id": registro_id,
        "documento_nome_original": data.arquivo_nome_original,
        "documento_nome_storage": nome_armazenado,
    }
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Documento incluído com sucesso.", detail_url, id=registro_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/documentos/<int:documento_id>/editar", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def editar_documento(id: int, documento_id: int):
    documento_atual = services.obter_documento_relacionado(id, documento_id)
    if not documento_atual:
        abort(404)

    try:
        data = DocumentoRelacionadoFormData.from_request(
            request,
            allowed_extensions=DOCUMENTO_ALLOWED_EXTENSIONS,
            max_size_bytes=DOCUMENTO_MAX_SIZE_BYTES,
            require_file=False,
        )
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    storage_path_antigo = documento_atual["documento_storage_path"]
    storage_path = storage_path_antigo
    documento_nome_original = documento_atual["documento_nome_original"]
    documento_content_type = documento_atual.get("documento_content_type")
    documento_tamanho_bytes = documento_atual.get("documento_tamanho_bytes")
    nome_armazenado = None
    substituiu_arquivo = bool(data.arquivo and data.arquivo_nome_original)

    if substituiu_arquivo:
        nome_armazenado, storage_path = _build_documento_storage_path(
            id,
            data.arquivo_nome_original or documento_nome_original,
        )
        documento_nome_original = data.arquivo_nome_original or documento_nome_original
        documento_content_type = data.arquivo_content_type or documento_content_type
        documento_tamanho_bytes = data.arquivo_tamanho_bytes
        data.arquivo.stream.seek(0)

        try:
            storage.upload_file(storage_path, data.arquivo.read(), documento_content_type or "application/octet-stream")
            atualizado = services.atualizar_documento_relacionado(
                id,
                documento_id,
                documento_titulo=data.documento_titulo,
                documento_descricao=data.documento_descricao,
                documento_nome_original=documento_nome_original,
                documento_storage_path=storage_path,
                documento_content_type=documento_content_type,
                documento_tamanho_bytes=documento_tamanho_bytes,
                usuario=_usuario_atual(),
            )
        except Exception:
            storage.delete_file(storage_path)
            raise

        if not atualizado:
            storage.delete_file(storage_path)
            abort(404)

        if storage_path_antigo and storage_path_antigo != storage_path:
            storage.delete_file(storage_path_antigo)
    else:
        atualizado = services.atualizar_documento_relacionado(
            id,
            documento_id,
            documento_titulo=data.documento_titulo,
            documento_descricao=data.documento_descricao,
            documento_nome_original=documento_nome_original,
            documento_storage_path=storage_path,
            documento_content_type=documento_content_type,
            documento_tamanho_bytes=documento_tamanho_bytes,
            usuario=_usuario_atual(),
        )
        if not atualizado:
            abort(404)

    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {
        "acao": "edicao_documento_relacionado",
        "documento_id": documento_id,
        "arquivo_substituido": substituiu_arquivo,
        "documento_nome_original": documento_nome_original,
        "documento_nome_storage": nome_armazenado,
    }
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Documento atualizado com sucesso.", detail_url, id=documento_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/documentos/<int:documento_id>/download", methods=["GET"])
@login_required
@requires_access("smdhc_pendencias")
def baixar_documento(id: int, documento_id: int):
    documento = services.obter_documento_relacionado(id, documento_id)
    if not documento:
        abort(404)

    try:
        file_bytes = storage.download_file(documento["documento_storage_path"])
    except FileNotFoundError:
        flash("Arquivo não encontrado no storage.", "warning")
        return redirect(url_for("smdhc_pendencias.detalhe", id=id))

    mimetype = documento.get("documento_content_type") or mimetypes.guess_type(documento["documento_nome_original"])[0] or "application/octet-stream"
    return send_file(
        io.BytesIO(file_bytes),
        mimetype=mimetype,
        as_attachment=True,
        download_name=documento["documento_nome_original"],
    )


@smdhc_pendencias_bp.route("/<int:id>/documentos/<int:documento_id>/excluir", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def excluir_documento(id: int, documento_id: int):
    documento = services.excluir_documento_relacionado(id, documento_id, _usuario_atual())
    if not documento:
        abort(404)

    storage_path = documento.get("documento_storage_path")
    if storage_path:
        storage.delete_file(storage_path)

    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "exclusao_documento_relacionado", "documento_id": documento_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Documento removido com sucesso.", detail_url, id=documento_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/responsaveis", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def registrar_responsaveis(id: int):
    try:
        data = ResponsaveisFormData.from_request(request)
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    registro_id = services.registrar_responsaveis(id, data, _usuario_atual())
    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "registro_responsaveis", "responsavel_id": registro_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Responsáveis atualizados com sucesso.", detail_url, id=registro_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/responsaveis/<int:responsavel_id>/editar", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def editar_responsaveis(id: int, responsavel_id: int):
    try:
        data = ResponsaveisFormData.from_request(request)
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    atualizado = services.atualizar_responsaveis(id, responsavel_id, data, _usuario_atual())
    if not atualizado:
        abort(404)

    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "edicao_responsaveis", "responsavel_id": responsavel_id}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success("Responsaveis atualizados com sucesso.", detail_url, id=responsavel_id, redirect=detail_url)


@smdhc_pendencias_bp.route("/<int:id>/matriz", methods=["POST"])
@login_required
@requires_access("smdhc_pendencias")
@requires_write_access("smdhc_pendencias")
def salvar_matriz(id: int):
    try:
        data = MatrizFormData.from_request(request)
    except FormValidationError as exc:
        return _handle_form_error(exc, fallback_url=url_for("smdhc_pendencias.detalhe", id=id))

    services.salvar_matriz_pendencia(id, data, _usuario_atual())
    ranking = services.calcular_matriz_pendencia(id)
    g.log_recurso_tipo = "pendencia"
    g.log_recurso_id = id
    g.log_detalhes = {"acao": "salvar_matriz_pendencia"}
    detail_url = url_for("smdhc_pendencias.detalhe", id=id)
    return _json_or_redirect_success(
        "Matriz de priorização atualizada com sucesso.",
        detail_url,
        pendencia_id=id,
        ranking=ranking,
        redirect=detail_url,
    )


@smdhc_pendencias_bp.route("/relatorio", methods=["GET"])
@login_required
@requires_access("smdhc_pendencias")
def relatorio():
    filtros = PendenciaFiltersForm.from_args(request.args)
    context = _build_page_context(filtros=filtros)
    context["pendencias"] = services.listar_pendencias(filtros)
    context["resumo"] = services.obter_resumo_dashboard(filtros)
    return render_template("smdhc_pendencias/smdhc_pendencia_relatorio.html", **context)


@smdhc_pendencias_bp.route("/api/resumo", methods=["GET"])
@login_required
@requires_access("smdhc_pendencias")
def api_resumo():
    filtros = PendenciaFiltersForm.from_args(request.args)
    return jsonify(
        {
            "resumo": services.obter_resumo_dashboard(filtros),
            "alertas": services.obter_alertas_dashboard(filtros),
        }
    )


@smdhc_pendencias_bp.route("/api/matriz", methods=["GET"])
@login_required
@requires_access("smdhc_pendencias")
def api_matriz():
    limit = request.args.get("limit", "25")
    try:
        limit_int = max(1, min(int(limit), 100))
    except ValueError:
        limit_int = 25
    return jsonify(
        {
            "ranking": services.calcular_matriz_geral(limit_int),
            "principios": services.listar_principios(),
        }
    )


@smdhc_pendencias_bp.route("/api/usuarios", methods=["GET"])
@login_required
@requires_access("smdhc_pendencias")
def api_usuarios():
    return jsonify({"usuarios": services.listar_usuarios_infos()})


@smdhc_pendencias_bp.route("/api/status-options", methods=["GET"])
@login_required
@requires_access("smdhc_pendencias")
def api_status_options():
    return jsonify(
        {
            "status": services.listar_status_options(),
            "atualizacao_tipos": services.listar_atualizacao_tipos(),
            "tipos": services.listar_tema_tipos(),
            "areas_demandantes": services.listar_area_demandante(),
            "areas_responsaveis": services.listar_area_responsavel(),
            "areas_correlatas": services.listar_area_correlata(),
            "situacoes": SITUACOES_OPTIONS,
        }
    )
