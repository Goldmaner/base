from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Any
from urllib.parse import urlparse


class FormValidationError(Exception):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _as_int(value: Any, label: str, errors: list[str], *, minimum: int | None = None) -> int | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        number = int(text)
    except (TypeError, ValueError):
        errors.append(f"{label}: valor invalido.")
        return None
    if minimum is not None and number < minimum:
        errors.append(f"{label}: valor minimo e {minimum}.")
    return number


def _as_date(value: Any, label: str, errors: list[str]):
    text = _clean_text(value)
    if text is None:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    errors.append(f"{label}: data invalida.")
    return None


def _extract_multi(source: Any, key: str) -> list[str]:
    values: list[str] = []

    if hasattr(source, "getlist"):
        values.extend(source.getlist(key))
        values.extend(source.getlist(f"{key}[]"))
        if values:
            return _normalize_list(values)

    raw = None
    if isinstance(source, dict):
        raw = source.get(key, source.get(f"{key}[]"))
    elif hasattr(source, "get"):
        raw = source.get(key)

    if raw is None:
        return []
    if isinstance(raw, list):
        return _normalize_list(raw)
    if isinstance(raw, tuple):
        return _normalize_list(list(raw))
    if isinstance(raw, str):
        return _normalize_list(re.split(r"[\n,;]+", raw))
    return _normalize_list([raw])


def _normalize_list(values: list[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = _clean_text(value)
        if text and text not in result:
            result.append(text)
    return result


def _extract_multi_raw(source: Any, key: str) -> list[str]:
    values: list[Any] = []

    if hasattr(source, "getlist"):
        values.extend(source.getlist(key))
        values.extend(source.getlist(f"{key}[]"))
        if values:
            return [str(value).strip() if value is not None else "" for value in values]

    raw = None
    if isinstance(source, dict):
        raw = source.get(key, source.get(f"{key}[]"))
    elif hasattr(source, "get"):
        raw = source.get(key)

    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(value).strip() if value is not None else "" for value in raw]
    if isinstance(raw, tuple):
        return [str(value).strip() if value is not None else "" for value in raw]
    if isinstance(raw, str):
        return [raw.strip()]
    return [str(raw).strip()]


def pendencia_form_values(request) -> dict[str, Any]:
    payload = request.get_json(silent=True) if request.is_json else request.form
    return {
        "tema_nome": _clean_text((payload or {}).get("tema_nome")) or "",
        "tema_tipo": _clean_text((payload or {}).get("tema_tipo")) or "",
        "tema_descricao": _clean_text((payload or {}).get("tema_descricao")) or "",
        "tema_area_demandante": _clean_text((payload or {}).get("tema_area_demandante")) or "",
        "tema_area_responsavel": _extract_multi(payload or request.form, "tema_area_responsavel"),
        "tema_area_correlata": _extract_multi(payload or request.form, "tema_area_correlata"),
        "tema_status": _clean_text((payload or {}).get("tema_status")) or "",
        "tema_prazo_estimado": _clean_text((payload or {}).get("tema_prazo_estimado")) or "",
        "tema_observacoes": _clean_text((payload or {}).get("tema_observacoes")) or "",
        "situacao_automatica": _clean_text((payload or {}).get("situacao_automatica")) or "",
        "prioridade_manual": _clean_text((payload or {}).get("prioridade_manual")) or "",
        "prioridade_observacao": _clean_text((payload or {}).get("prioridade_observacao")) or "",
    }


@dataclass(slots=True)
class PendenciaFiltersForm:
    q: str | None = None
    status: str | None = None
    tipo: str | None = None
    area_demandante: str | None = None
    area_responsavel: list[str] = field(default_factory=list)
    situacao: str | None = None
    somente_sem_prazo: bool = False
    somente_vencidas: bool = False
    somente_paradas: bool = False

    @classmethod
    def from_args(cls, args) -> "PendenciaFiltersForm":
        return cls(
            q=_clean_text(args.get("q")),
            status=_clean_text(args.get("status")),
            tipo=_clean_text(args.get("tipo")),
            area_demandante=_clean_text(args.get("area_demandante")),
            area_responsavel=_extract_multi(args, "area_responsavel"),
            situacao=_clean_text(args.get("situacao")),
            somente_sem_prazo=args.get("somente_sem_prazo") in {"1", "true", "True", "on"},
            somente_vencidas=args.get("somente_vencidas") in {"1", "true", "True", "on"},
            somente_paradas=args.get("somente_paradas") in {"1", "true", "True", "on"},
        )


@dataclass(slots=True)
class PendenciaFormData:
    tema_nome: str
    tema_tipo: str | None
    tema_descricao: str | None
    tema_area_demandante: str | None
    tema_area_responsavel: list[str]
    tema_area_correlata: list[str]
    tema_status: str | None
    tema_prazo_estimado: Any
    tema_observacoes: str | None
    situacao_automatica: str | None
    prioridade_manual: int | None
    prioridade_observacao: str | None

    @classmethod
    def from_request(cls, request) -> "PendenciaFormData":
        errors: list[str] = []
        payload = request.get_json(silent=True) if request.is_json else request.form
        payload = payload or {}

        tema_nome = _clean_text(payload.get("tema_nome"))
        if not tema_nome:
            errors.append("Tema: campo obrigatorio.")

        prioridade_manual = _as_int(payload.get("prioridade_manual"), "Prioridade manual", errors, minimum=1)
        if prioridade_manual is not None and prioridade_manual > 9999:
            errors.append("Prioridade manual: valor maximo sugerido e 9999.")

        data = cls(
            tema_nome=tema_nome or "",
            tema_tipo=_clean_text(payload.get("tema_tipo")),
            tema_descricao=_clean_text(payload.get("tema_descricao")),
            tema_area_demandante=_clean_text(payload.get("tema_area_demandante")),
            tema_area_responsavel=_extract_multi(payload or request.form, "tema_area_responsavel"),
            tema_area_correlata=_extract_multi(payload or request.form, "tema_area_correlata"),
            tema_status=_clean_text(payload.get("tema_status")),
            tema_prazo_estimado=_as_date(payload.get("tema_prazo_estimado"), "Prazo estimado", errors),
            tema_observacoes=_clean_text(payload.get("tema_observacoes")),
            situacao_automatica=_clean_text(payload.get("situacao_automatica")),
            prioridade_manual=prioridade_manual,
            prioridade_observacao=_clean_text(payload.get("prioridade_observacao")),
        )

        if errors:
            raise FormValidationError(errors)
        return data


@dataclass(slots=True)
class AtualizacaoFormData:
    tema_atualizacao: str
    tema_atualizacao_data: Any
    tema_atualizacao_tipo: str | None
    tema_acao_subsequente: str | None
    participantes_usuario_ids: list[int]
    participantes_externos: list[dict[str, str]]

    @classmethod
    def from_request(cls, request) -> "AtualizacaoFormData":
        errors: list[str] = []
        payload = request.get_json(silent=True) if request.is_json else request.form
        payload = payload or {}

        tema_atualizacao = _clean_text(payload.get("tema_atualizacao"))
        if not tema_atualizacao:
            errors.append("Atualizacao: campo obrigatorio.")

        tema_atualizacao_tipo = _clean_text(payload.get("tema_atualizacao_tipo")) or "Outros"

        participantes_usuario_ids: list[int] = []
        for raw in _extract_multi(payload or request.form, "participante_usuario_ids"):
            parsed = _as_int(raw, "Participante interno", errors, minimum=1)
            if parsed is not None and parsed not in participantes_usuario_ids:
                participantes_usuario_ids.append(parsed)

        nomes_externos = _extract_multi_raw(payload or request.form, "participante_externo_nome")
        setores_externos = _extract_multi_raw(payload or request.form, "participante_externo_setor")
        total_externos = max(len(nomes_externos), len(setores_externos))
        participantes_externos: list[dict[str, str]] = []
        for idx in range(total_externos):
            nome = nomes_externos[idx].strip() if idx < len(nomes_externos) else ""
            setor = setores_externos[idx].strip() if idx < len(setores_externos) else ""
            if not nome and not setor:
                continue
            if not nome:
                errors.append(f"Participante externo #{idx + 1}: informe o nome.")
                continue
            if not setor:
                errors.append(f"Participante externo #{idx + 1}: informe o setor.")
                continue
            participantes_externos.append({"nome": nome, "setor": setor})

        tipo_norm = (tema_atualizacao_tipo or "").strip().lower()
        if tipo_norm.startswith("reuni") and not participantes_usuario_ids and not participantes_externos:
            errors.append("Reuniao: informe ao menos um participante interno ou externo.")

        data = cls(
            tema_atualizacao=tema_atualizacao or "",
            tema_atualizacao_data=_as_date(payload.get("tema_atualizacao_data"), "Data da atualizacao", errors),
            tema_atualizacao_tipo=tema_atualizacao_tipo,
            tema_acao_subsequente=_clean_text(payload.get("tema_acao_subsequente")),
            participantes_usuario_ids=participantes_usuario_ids,
            participantes_externos=participantes_externos,
        )
        if errors:
            raise FormValidationError(errors)
        return data


@dataclass(slots=True)
class ProcessoSeiFormData:
    tema_processo: str | None
    tema_processo_observacao: str | None

    @classmethod
    def from_request(cls, request) -> "ProcessoSeiFormData":
        payload = request.get_json(silent=True) if request.is_json else request.form
        payload = payload or {}
        tema_processo = _clean_text(payload.get("tema_processo"))
        tema_processo_observacao = _clean_text(payload.get("tema_processo_observacao"))
        if not tema_processo and not tema_processo_observacao:
            raise FormValidationError(["Processo SEI: informe o numero ou uma observacao."])
        return cls(
            tema_processo=tema_processo,
            tema_processo_observacao=tema_processo_observacao,
        )


@dataclass(slots=True)
class LinkRelacionadoFormData:
    tema_link_titulo: str | None
    tema_link_url: str
    tema_link_descricao: str | None

    @classmethod
    def from_request(cls, request) -> "LinkRelacionadoFormData":
        payload = request.get_json(silent=True) if request.is_json else request.form
        payload = payload or {}

        errors: list[str] = []
        tema_link_url = _clean_text(payload.get("tema_link_url"))
        if not tema_link_url:
            errors.append("Link: informe a URL.")
        else:
            parsed = urlparse(tema_link_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                errors.append("Link: informe uma URL valida iniciada por http:// ou https://.")

        data = cls(
            tema_link_titulo=_clean_text(payload.get("tema_link_titulo")),
            tema_link_url=tema_link_url or "",
            tema_link_descricao=_clean_text(payload.get("tema_link_descricao")),
        )
        if errors:
            raise FormValidationError(errors)
        return data


@dataclass(slots=True)
class ResponsaveisFormData:
    tema_responsavel: str | None
    tema_envolvidos: list[str]

    @classmethod
    def from_request(cls, request) -> "ResponsaveisFormData":
        payload = request.get_json(silent=True) if request.is_json else request.form
        payload = payload or {}
        tema_responsavel = _clean_text(payload.get("tema_responsavel"))
        tema_envolvidos = _extract_multi(payload or request.form, "tema_envolvidos")
        if not tema_responsavel and not tema_envolvidos:
            raise FormValidationError(["Responsaveis: informe um responsavel ou ao menos um envolvido."])
        return cls(tema_responsavel=tema_responsavel, tema_envolvidos=tema_envolvidos)


@dataclass(slots=True)
class DocumentoRelacionadoFormData:
    arquivo: Any | None
    documento_titulo: str | None
    documento_descricao: str | None
    arquivo_nome_original: str | None
    arquivo_content_type: str | None
    arquivo_tamanho_bytes: int | None

    @classmethod
    def from_request(
        cls,
        request,
        *,
        allowed_extensions: set[str],
        max_size_bytes: int,
        require_file: bool = True,
    ) -> "DocumentoRelacionadoFormData":
        errors: list[str] = []
        arquivo = request.files.get("documento_arquivo")
        arquivo_nome_original: str | None = None
        arquivo_content_type: str | None = None
        arquivo_tamanho_bytes: int | None = None

        if arquivo and getattr(arquivo, "filename", ""):
            arquivo_nome_original = str(arquivo.filename).strip()
            extensao = arquivo_nome_original.rsplit(".", 1)[1].lower() if "." in arquivo_nome_original else ""
            if not extensao or extensao not in allowed_extensions:
                errors.append(
                    "Documento: formato nao permitido. Use PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, TXT, PNG, JPG, JPEG, ODT ou ODS."
                )

            try:
                posicao_atual = arquivo.stream.tell()
            except Exception:
                posicao_atual = None
            arquivo.stream.seek(0, 2)
            arquivo_tamanho_bytes = int(arquivo.stream.tell())
            arquivo.stream.seek(posicao_atual or 0)

            if arquivo_tamanho_bytes <= 0:
                errors.append("Documento: o arquivo enviado esta vazio.")
            if arquivo_tamanho_bytes > max_size_bytes:
                errors.append("Documento: tamanho maximo permitido e 30 MB por arquivo.")

            arquivo_content_type = _clean_text(getattr(arquivo, "mimetype", None)) or "application/octet-stream"
        elif require_file:
            errors.append("Documento: selecione um arquivo.")
            raise FormValidationError(errors)

        data = cls(
            arquivo=arquivo,
            documento_titulo=_clean_text(request.form.get("documento_titulo")),
            documento_descricao=_clean_text(request.form.get("documento_descricao")),
            arquivo_nome_original=arquivo_nome_original,
            arquivo_content_type=arquivo_content_type,
            arquivo_tamanho_bytes=arquivo_tamanho_bytes,
        )
        if errors:
            raise FormValidationError(errors)
        return data


@dataclass(slots=True)
class MatrizItemFormData:
    principio_id: int
    tema_principios_nota: int | None
    principio_nota_ids: list[int]


@dataclass(slots=True)
class MatrizFormData:
    itens: list[MatrizItemFormData]

    @classmethod
    def from_request(cls, request) -> "MatrizFormData":
        if request.is_json:
            return cls._from_json_payload(request.get_json(silent=True) or {})
        return cls._from_form_payload(request.form)

    @classmethod
    def _from_json_payload(cls, payload: dict[str, Any]) -> "MatrizFormData":
        errors: list[str] = []
        itens: list[MatrizItemFormData] = []

        for idx, item in enumerate(payload.get("itens", []), start=1):
            principio_id = _as_int(item.get("principio_id"), f"Principio #{idx}", errors, minimum=1)
            nota = _as_int(item.get("tema_principios_nota"), f"Nota do principio #{idx}", errors, minimum=0)
            nota_ids = []
            for raw in item.get("principio_nota_ids", []) or []:
                parsed = _as_int(raw, f"Fator do principio #{idx}", errors, minimum=1)
                if parsed is not None and parsed not in nota_ids:
                    nota_ids.append(parsed)
            if principio_id is not None:
                itens.append(MatrizItemFormData(principio_id=principio_id, tema_principios_nota=nota, principio_nota_ids=nota_ids))

        if not itens:
            errors.append("Matriz: nenhum principio informado.")
        if errors:
            raise FormValidationError(errors)
        return cls(itens=itens)

    @classmethod
    def _from_form_payload(cls, form) -> "MatrizFormData":
        errors: list[str] = []
        itens: list[MatrizItemFormData] = []
        principio_ids = []

        for raw in form.getlist("principio_ids"):
            parsed = _as_int(raw, "Principio", errors, minimum=1)
            if parsed is not None and parsed not in principio_ids:
                principio_ids.append(parsed)

        if not principio_ids:
            for key in form.keys():
                match = re.match(r"^tema_principios_nota_(\d+)$", key)
                if match:
                    principio_ids.append(int(match.group(1)))

        for principio_id in principio_ids:
            nota = _as_int(form.get(f"tema_principios_nota_{principio_id}"), f"Nota do principio {principio_id}", errors, minimum=0)
            nota_ids = []
            for raw in form.getlist(f"principio_nota_ids_{principio_id}"):
                parsed = _as_int(raw, f"Fator do principio {principio_id}", errors, minimum=1)
                if parsed is not None and parsed not in nota_ids:
                    nota_ids.append(parsed)
            itens.append(MatrizItemFormData(principio_id=principio_id, tema_principios_nota=nota, principio_nota_ids=nota_ids))

        if not itens:
            errors.append("Matriz: nenhum principio informado.")
        if errors:
            raise FormValidationError(errors)
        return cls(itens=itens)
