import pytest
from pydantic import ValidationError

from src.triagem.modelos import Avaliacao


def avaliacao(**campos):
    base = {
        "titulo": "Vaga",
        "link": "https://exemplo.test/v",
        "veredito": "aplicar",
        "motivo": "ok",
    }
    return Avaliacao(**{**base, **campos})


@pytest.mark.parametrize("veredito", ["aplicar", "não aplicar"])
def test_vereditos_validos(veredito):
    assert avaliacao(veredito=veredito).veredito == veredito


def test_veredito_e_normalizado():
    assert avaliacao(veredito="  Não Aplicar ").veredito == "não aplicar"


@pytest.mark.parametrize("veredito", ["talvez", "nao_aplicar", "", None])
def test_veredito_invalido(veredito):
    with pytest.raises(ValidationError):
        avaliacao(veredito=veredito)


@pytest.mark.parametrize("motivo", ["", "   ", "\n\t"])
def test_motivo_vazio_e_invalido(motivo):
    with pytest.raises(ValidationError):
        avaliacao(motivo=motivo)


def test_motivo_e_aparado_e_nao_tem_limite_maximo():
    longo = "a" * 1000
    assert avaliacao(motivo=f"  {longo}  ").motivo == longo


def test_descricao_ou_tags_e_opcional():
    assert avaliacao().descricao_ou_tags is None
    assert avaliacao(descricao_ou_tags="resumo").descricao_ou_tags == "resumo"


def test_campo_obrigatorio_ausente():
    with pytest.raises(ValidationError):
        Avaliacao(titulo="Vaga", veredito="aplicar", motivo="ok")
