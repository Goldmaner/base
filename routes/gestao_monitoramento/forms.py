from __future__ import annotations

from dataclasses import dataclass


class FormValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


@dataclass
class EscopoDgmFormData:
    numero_termo: str
    dgm_escopo_termo: bool

    @classmethod
    def from_request(cls, request) -> "EscopoDgmFormData":
        numero_termo = (request.form.get("numero_termo") or "").strip()
        errors: list[str] = []
        if not numero_termo:
            errors.append("Selecione um termo.")
        if errors:
            raise FormValidationError(errors)
        return cls(
            numero_termo=numero_termo,
            dgm_escopo_termo=request.form.get("dgm_escopo_termo") == "on",
        )


@dataclass
class EquipamentoFormData:
    termo_equipamento: str

    @classmethod
    def from_request(cls, request) -> "EquipamentoFormData":
        termo_equipamento = (request.form.get("termo_equipamento") or "").strip()
        errors: list[str] = []
        if not termo_equipamento:
            errors.append("Informe o nome do equipamento.")
        if len(termo_equipamento) > 300:
            errors.append("O nome do equipamento deve ter no maximo 300 caracteres.")
        if errors:
            raise FormValidationError(errors)
        return cls(termo_equipamento=termo_equipamento)


def equipamentos_from_text(text: str) -> list[str]:
    equipamentos: list[str] = []
    for line in (text or "").splitlines():
        nome = line.strip()
        if nome:
            equipamentos.append(nome)
    if not equipamentos:
        raise FormValidationError(["Informe ao menos um equipamento."])
    longos = [nome for nome in equipamentos if len(nome) > 300]
    if longos:
        raise FormValidationError(["Cada equipamento deve ter no maximo 300 caracteres."])
    return equipamentos
