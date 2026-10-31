"""
Coleta vagas dos feeds de programação, back-end e full-stack do We Work Remotely
(e do de devops, se faltar) e gera os arquivos do conjunto de avaliação:

- eval/vagas.csv: titulo, link, descricao, veredito_esperado (vazia, para rotular)
- eval/rotular.md: tabela de rotulagem com o texto exato que o agente recebe

A descrição usa o mesmo tratamento que o agente vê (HTML removido, corte em 300
caracteres), reaproveitando as funções de src/triagem/feed.py.

Rodar da raiz do projeto: python eval/coletar.py
"""

import csv
import random
import sys
from datetime import date
from pathlib import Path

import feedparser
import requests

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.triagem.feed import _limpar_html, _truncar  # noqa: E402

BASE_URL = "https://weworkremotely.com/categories/{}.rss"
FEEDS_PRINCIPAIS = [
    "remote-programming-jobs",
    "remote-back-end-programming-jobs",
    "remote-full-stack-programming-jobs",
]
FEED_EXTRA = "remote-devops-sysadmin-jobs"
MINIMO_SEM_EXTRA = 30
TOTAL = 40
SEMENTE = 42
# Palavras que aproximam as vagas dos critérios, só para garantir uma mistura no
# conjunto (não é o veredito: o rótulo vem do arquivo rotular.md, preenchido à mão).
PALAVRAS_TEMA = ("python", "django", "fastapi", "flask", "data", "machine learning", "ai ", " ml")
CANDIDATAS_ALVO = 20


def baixar(slug: str) -> list[dict]:
    resposta = requests.get(
        BASE_URL.format(slug),
        headers={"User-Agent": "Mozilla/5.0 (compatible; AgenteTriagemVagas/1.0)"},
        timeout=10,
    )
    resposta.raise_for_status()
    feed = feedparser.parse(resposta.content)
    vagas = []
    for entrada in feed.entries:
        descricao = _truncar(_limpar_html(getattr(entrada, "summary", ""))) or "N/A"
        vagas.append(
            {
                "titulo": str(getattr(entrada, "title", "") or ""),
                "link": getattr(entrada, "link", "N/A"),
                "descricao": descricao,
            }
        )
    return vagas


def juntar(slugs: list[str]) -> dict[str, dict]:
    distintas: dict[str, dict] = {}
    for slug in slugs:
        itens = baixar(slug)
        novas = 0
        for vaga in itens:
            if vaga["link"] not in distintas:
                distintas[vaga["link"]] = vaga
                novas += 1
        print(f"{slug}: {len(itens)} itens, {novas} novos")
    return distintas


def tem_tema(vaga: dict) -> bool:
    texto = f"{vaga['titulo']} {vaga['descricao']} ".lower()
    return any(palavra in texto for palavra in PALAVRAS_TEMA)


def selecionar(distintas: dict[str, dict]) -> list[dict]:
    aleatorio = random.Random(SEMENTE)
    vagas = list(distintas.values())
    aleatorio.shuffle(vagas)
    tematicas = [v for v in vagas if tem_tema(v)][:CANDIDATAS_ALVO]
    outras = [v for v in vagas if v not in tematicas][: TOTAL - len(tematicas)]
    escolhidas = tematicas + outras
    aleatorio.shuffle(escolhidas)  # a ordem do arquivo não agrupa por tipo
    return escolhidas[:TOTAL]


def empresa_do_titulo(titulo: str) -> str:
    return titulo.split(":", 1)[0].strip() if ":" in titulo else ""


def celula(texto: str) -> str:
    return texto.replace("|", "\\|").replace("\n", " ")


def escrever_csv(vagas: list[dict]) -> None:
    with open(RAIZ / "eval" / "vagas.csv", "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(
            arquivo, fieldnames=["titulo", "link", "descricao", "veredito_esperado"]
        )
        escritor.writeheader()
        for vaga in vagas:
            escritor.writerow({**vaga, "veredito_esperado": ""})


def escrever_rotular(vagas: list[dict], arquivo: str = "rotular.md", inicio: int = 1) -> None:
    linhas = [
        "# Rotulagem",
        "",
        "Preencha a última coluna com `A` (aplicar) ou `N` (não aplicar), "
        "usando só o texto da coluna \"O que o agente recebe\".",
        "",
        "| # | Título | Empresa | O que o agente recebe (título + descrição, 300 caracteres) "
        "| Link | Meu veredito |",
        "|---|---|---|---|---|---|",
    ]
    for numero, vaga in enumerate(vagas, start=inicio):
        recebido = f"{vaga['titulo']} — {vaga['descricao']}"
        linhas.append(
            f"| {numero} | {celula(vaga['titulo'])} | {celula(empresa_do_titulo(vaga['titulo']))} "
            f"| {celula(recebido)} | {vaga['link']} |  |"
        )
    (RAIZ / "eval" / arquivo).write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main():
    if (RAIZ / "eval" / "vagas.csv").exists():
        sys.exit("eval/vagas.csv já existe; apague-o antes (perderia os rótulos).")
    distintas = juntar(FEEDS_PRINCIPAIS)
    if len(distintas) < MINIMO_SEM_EXTRA:
        print(f"Só {len(distintas)} vagas distintas; incluindo o feed de devops.")
        for vaga in baixar(FEED_EXTRA):
            distintas.setdefault(vaga["link"], vaga)
    print(f"Vagas distintas coletadas: {len(distintas)} (em {date.today().isoformat()})")
    if len(distintas) < TOTAL:
        print(f"Aviso: menos de {TOTAL} vagas disponíveis.")
    vagas = selecionar(distintas)
    escrever_csv(vagas)
    escrever_rotular(vagas)
    print(f"Gravadas {len(vagas)} vagas em eval/vagas.csv e eval/rotular.md.")


if __name__ == "__main__":
    main()
