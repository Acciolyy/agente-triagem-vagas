from google.genai import types

from src.triagem.agente import TOOLS, avaliar_vaga, executar_function, rodar_triagem
from src.triagem.config import MAX_TOOL_ITERATIONS
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
                avaliar("Globex: Python Developer", "https://exemplo.test/g", "não aplicar", "sênior"),
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
