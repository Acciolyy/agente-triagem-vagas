import pytest
import requests

from src.triagem.feed import buscar_vagas_wwr


def titulos(resultado):
    return [vaga["titulo"] for vaga in resultado]


def test_parsing_devolve_titulo_link_e_descricao_sem_html(mock_feed, feed_xml):
    mock_feed(feed_xml)

    resultado = buscar_vagas_wwr("backend")

    assert resultado == [
        {
            "titulo": "Acme: Backend Engineer",
            "link": "https://exemplo.test/vagas/acme-backend-engineer",
            "descricao": "Trabalhe com Django e APIs REST em time remoto.",
        }
    ]


@pytest.mark.parametrize(
    "termo, esperado",
    [
        ("python", ["Globex: Senior PYTHON Developer"]),  # título, sem diferenciar maiúsculas
        ("PYTHON", ["Globex: Senior PYTHON Developer"]),
        ("rust", ["Umbrella: QA Engineer"]),  # tag
        ("kubernetes", ["Hooli: DevOps Engineer"]),  # descrição
        ("  Django ", ["Acme: Backend Engineer"]),  # espaços ao redor são ignorados
    ],
)
def test_filtro_por_titulo_tags_e_descricao(mock_feed, feed_xml, termo, esperado):
    mock_feed(feed_xml)

    assert titulos(buscar_vagas_wwr(termo)) == esperado


def test_termo_sem_resultado_devolve_aviso(mock_feed, feed_xml):
    mock_feed(feed_xml)

    resultado = buscar_vagas_wwr("cobol")

    assert "aviso" in resultado
    assert "cobol" in resultado["aviso"]


def test_termo_vazio_devolve_erro_sem_acessar_a_rede(mock_feed, feed_xml):
    get = mock_feed(feed_xml)

    assert "erro" in buscar_vagas_wwr("   ")
    get.assert_not_called()


def test_feed_vazio_devolve_erro(mock_feed):
    vazio = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'
    mock_feed(vazio)

    resultado = buscar_vagas_wwr("python")

    assert "vazia" in resultado["erro"]


def test_xml_invalido_devolve_erro(mock_feed):
    mock_feed(b"isto <nao e> xml de forma alguma")

    resultado = buscar_vagas_wwr("python")

    assert "inválido" in resultado["erro"]


def test_falha_de_rede_devolve_erro(mocker):
    mocker.patch(
        "src.triagem.feed.requests.get",
        side_effect=requests.exceptions.ConnectionError("sem rede"),
    )

    resultado = buscar_vagas_wwr("python")

    assert "Falha ao acessar o feed" in resultado["erro"]
