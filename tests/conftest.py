from pathlib import Path
from types import SimpleNamespace

import pytest
from google.genai import types

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def feed_xml() -> bytes:
    return (FIXTURES / "feed.xml").read_bytes()


@pytest.fixture
def mock_feed(mocker):
    """Substitui requests.get em src.triagem.feed, devolvendo o conteúdo dado."""

    def _mock(conteudo: bytes):
        resposta = mocker.Mock()
        resposta.content = conteudo
        return mocker.patch("src.triagem.feed.requests.get", return_value=resposta)

    return _mock


def chamada(nome: str, **args) -> types.Part:
    return types.Part(function_call=types.FunctionCall(name=nome, args=args))


def resposta_modelo(*partes: types.Part) -> SimpleNamespace:
    conteudo = types.Content(role="model", parts=list(partes))
    return SimpleNamespace(candidates=[SimpleNamespace(content=conteudo)], prompt_feedback=None)


class ClienteFalso:
    """Cliente Gemini falso: devolve as respostas pré-definidas em ordem e guarda as chamadas.

    Se um item da lista for uma exceção, ela é levantada em vez de devolvida.
    """

    def __init__(self, respostas):
        self._respostas = iter(respostas)
        self.contents_recebidos = []
        self.models = self

    def generate_content(self, model, contents, config=None):
        self.contents_recebidos.append(list(contents))
        resposta = next(self._respostas)
        if isinstance(resposta, Exception):
            raise resposta
        return resposta
