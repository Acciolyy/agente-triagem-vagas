import httpx
import pytest
from google.genai import errors, types

from src.triagem.agente import (
    TOOLS,
    TimeoutGemini,
    avaliar_vaga,
    criar_client,
    executar_function,
    rodar_triagem,
)
from src.triagem.config import MAX_TOOL_ITERATIONS, TIMEOUT_API_S
from src.triagem.modelos import Avaliacao
from tests.conftest import ClienteFalso, chamada, resposta_modelo

CONFIG = types.GenerateContentConfig(system_instruction="criterios", tools=[TOOLS])

VAGAS = [
    {"titulo": "Acme: Backend Engineer", "link": "https://exemplo.test/a", "descricao": "Django"},
    {"titulo": "Globex: Python Developer", "link": "https://exemplo.test/g", "descricao": "Python"},
]


def avaliar(titulo, link, veredito="aplicar", motivo="combina com o perfil"):
    return chamada(
        "avaliar_vaga",
        titulo=titulo,
        descricao_ou_tags="resumo",
        link=link,
        veredito=veredito,
        motivo=motivo,
    )


def respostas_das_ferramentas(cliente):
    """Extrai as respostas de função enviadas ao modelo no último turno."""
    ultimo = cliente.contents_recebidos[-1][-1]
    return [parte.function_response.response["result"] for parte in ultimo.parts]


def respostas_das_ferramentas_do_turno(cliente, indice):
    """Respostas de função enviadas ao modelo na chamada de índice `indice` (0 = primeira)."""
    contents = cliente.contents_recebidos[indice + 1]
    return [parte.function_response.response["result"] for parte in contents[-1].parts]


def test_loop_busca_avalia_e_devolve_lista_de_avaliacoes(mock_feed, feed_xml):
    mock_feed(feed_xml)
    cliente = ClienteFalso(
        [
            resposta_modelo(chamada("buscar_vagas_wwr", termo_busca="django")),
            resposta_modelo(
                avaliar("Acme: Backend Engineer", "https://exemplo.test/vagas/acme-backend-engineer"),
                avaliar(
                    "Globex: Python Developer", "https://exemplo.test/g", "não aplicar", "sênior"
                ),
            ),
            resposta_modelo(types.Part(text="Resumo final.")),
        ]
    )
    textos = []

    avaliacoes, atingiu_limite = rodar_triagem(cliente, CONFIG, "django", on_texto=textos.append)

    assert atingiu_limite is False
    assert all(isinstance(a, Avaliacao) for a in avaliacoes)
    assert [(a.titulo, a.veredito) for a in avaliacoes] == [
        ("Acme: Backend Engineer", "aplicar"),
        ("Globex: Python Developer", "não aplicar"),
    ]
    assert textos == ["Resumo final."]


def test_resultado_da_busca_volta_ao_modelo(mock_feed, feed_xml):
    mock_feed(feed_xml)
    cliente = ClienteFalso(
        [
            resposta_modelo(chamada("buscar_vagas_wwr", termo_busca="django")),
            resposta_modelo(types.Part(text="fim")),
        ]
    )

    rodar_triagem(cliente, CONFIG, "django")

    [resultado] = respostas_das_ferramentas(cliente)
    assert resultado[0]["titulo"] == "Acme: Backend Engineer"


def test_argumentos_invalidos_voltam_como_erro_e_nao_derrubam_o_loop():
    cliente = ClienteFalso(
        [
            resposta_modelo(
                avaliar("Vaga ruim", "https://exemplo.test/x", veredito="talvez"),
                avaliar("Vaga sem motivo", "https://exemplo.test/y", motivo="   "),
                chamada("avaliar_vaga", titulo="Faltam campos"),
            ),
            resposta_modelo(avaliar("Vaga ruim", "https://exemplo.test/x", veredito="aplicar")),
            resposta_modelo(types.Part(text="fim")),
        ]
    )

    avaliacoes, atingiu_limite = rodar_triagem(cliente, CONFIG, "python")

    assert atingiu_limite is False
    # só a reenviada com argumentos válidos é registrada
    assert [(a.titulo, a.veredito) for a in avaliacoes] == [("Vaga ruim", "aplicar")]
    # o modelo recebeu um erro de ferramenta para cada chamada inválida
    erros = respostas_das_ferramentas_do_turno(cliente, 0)
    assert len(erros) == 3
    assert all("erro" in r for r in erros)
    assert "veredito" in erros[0]["erro"]
    assert "motivo" in erros[1]["erro"]


def test_funcao_desconhecida_vira_erro_de_ferramenta():
    cliente = ClienteFalso(
        [
            resposta_modelo(chamada("inexistente")),
            resposta_modelo(types.Part(text="fim")),
        ]
    )

    avaliacoes, _ = rodar_triagem(cliente, CONFIG, "python")

    assert avaliacoes == []
    [resultado] = respostas_das_ferramentas(cliente)
    assert "Função desconhecida" in resultado["erro"]


def test_limite_de_iteracoes():
    respostas = [
        resposta_modelo(avaliar(f"Vaga {i}", f"https://exemplo.test/{i}"))
        for i in range(MAX_TOOL_ITERATIONS)
    ]
    cliente = ClienteFalso(respostas)

    avaliacoes, atingiu_limite = rodar_triagem(cliente, CONFIG, "python")

    assert atingiu_limite is True
    assert len(avaliacoes) == MAX_TOOL_ITERATIONS


def test_resposta_sem_candidatos_encerra_com_aviso():
    vazia = resposta_modelo()
    vazia.candidates = []
    vazia.prompt_feedback = None
    cliente = ClienteFalso([vazia])
    avisos = []

    avaliacoes, atingiu_limite = rodar_triagem(cliente, CONFIG, "python", on_texto=avisos.append)

    assert (avaliacoes, atingiu_limite) == ([], False)
    assert "resposta vazia" in avisos[0]


def test_avaliar_vaga_e_executar_function_validam_com_o_modelo():
    argumentos = {"titulo": "V", "link": "l", "veredito": "aplicar", "motivo": "ok"}

    assert executar_function("avaliar_vaga", argumentos) == avaliar_vaga(**argumentos)
    assert "erro" in executar_function("avaliar_vaga", {**argumentos, "veredito": "x"})


# --- timeout e novas tentativas ----------------------------------------------


@pytest.fixture
def sem_espera(mocker):
    return mocker.patch("src.triagem.agente.time.sleep")


def erro_api(codigo):
    return errors.APIError(codigo, {"error": {"message": "falha simulada"}})


def test_client_e_criado_com_timeout():
    assert criar_client("chave")._api_client._http_options.timeout == TIMEOUT_API_S * 1000


def test_timeout_e_tentado_de_novo_com_espera_e_aviso(sem_espera):
    cliente = ClienteFalso(
        [
            httpx.ReadTimeout("sem resposta"),
            resposta_modelo(avaliar("Vaga", "https://exemplo.test/v")),
            resposta_modelo(types.Part(text="fim")),
        ]
    )
    avisos = []

    avaliacoes, atingiu_limite = rodar_triagem(
        cliente, CONFIG, "python", on_aviso=avisos.append, espera_base=5
    )

    assert atingiu_limite is False
    assert [a.titulo for a in avaliacoes] == ["Vaga"]
    sem_espera.assert_called_once_with(5)
    assert len(avisos) == 1 and "nova tentativa" in avisos[0]
    # a requisição repetida é a mesma: o turno do usuário não foi duplicado
    assert len(cliente.contents_recebidos[0]) == len(cliente.contents_recebidos[1]) == 1


def test_timeout_em_todas_as_tentativas_levanta_timeout_gemini(sem_espera):
    cliente = ClienteFalso([httpx.ReadTimeout("sem resposta")] * 3)

    with pytest.raises(TimeoutGemini) as excecao:
        rodar_triagem(cliente, CONFIG, "python", tentativas=3, espera_base=1)

    assert len(cliente.contents_recebidos) == 3
    assert [chamada.args[0] for chamada in sem_espera.call_args_list] == [1, 2]
    assert isinstance(excecao.value.__cause__, httpx.ReadTimeout)
    assert str(TIMEOUT_API_S) in str(excecao.value)


@pytest.mark.parametrize("codigo", [429, 503, 504])
def test_erro_transitorio_da_api_e_tentado_de_novo(sem_espera, codigo):
    cliente = ClienteFalso([erro_api(codigo), resposta_modelo(types.Part(text="fim"))])

    avaliacoes, atingiu_limite = rodar_triagem(cliente, CONFIG, "python")

    assert (avaliacoes, atingiu_limite) == ([], False)
    assert len(cliente.contents_recebidos) == 2


def test_erro_transitorio_persistente_levanta_o_erro_da_api(sem_espera):
    cliente = ClienteFalso([erro_api(503)] * 2)

    with pytest.raises(errors.APIError) as excecao:
        rodar_triagem(cliente, CONFIG, "python", tentativas=2)

    assert excecao.value.code == 503


def test_erro_nao_transitorio_nao_e_tentado_de_novo(sem_espera):
    cliente = ClienteFalso([erro_api(400), resposta_modelo(types.Part(text="fim"))])

    with pytest.raises(errors.APIError):
        rodar_triagem(cliente, CONFIG, "python")

    assert len(cliente.contents_recebidos) == 1
    sem_espera.assert_not_called()
