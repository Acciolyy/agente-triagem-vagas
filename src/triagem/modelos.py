"""Modelos de dados: vaga lida do feed e avaliação decidida pelo modelo."""

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, StringConstraints


def _normalizar_veredito(valor):
    return valor.strip().lower() if isinstance(valor, str) else valor


class Vaga(BaseModel):
    titulo: str
    link: str
    descricao: str


class Avaliacao(BaseModel):
    titulo: str
    link: str
    veredito: Annotated[Literal["aplicar", "não aplicar"], BeforeValidator(_normalizar_veredito)]
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    descricao_ou_tags: str | None = None
