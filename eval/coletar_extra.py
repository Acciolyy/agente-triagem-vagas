"""
Acrescenta ao eval/vagas.csv até 20 vagas extras com mais chance de encaixar nos critérios.

Parte das vagas distintas dos feeds de programação, back-end e full-stack do We Work
Remotely (as mesmas de coletar.py), tira as que já estão no vagas.csv e pontua as restantes
pelos termos python, django, fastapi, flask, data, machine learning, ai, junior, mid e entry
(palavra inteira, sem diferenciar maiúsculas): 2 pontos por termo no título e 1 por termo na
descrição de 300 caracteres. Entram as 20 de maior pontuação (empate: ordem do feed) com
pelo menos 1 ponto, embaralhadas com a semente 42 para a numeração não revelar a pontuação.
Gera eval/rotular_extra.md, numerado a partir do fim do vagas.csv.

Rodar da raiz do projeto: python eval/coletar_extra.py
"""

import csv
import random
import re
import sys

from coletar import FEEDS_PRINCIPAIS, RAIZ, SEMENTE, escrever_rotular, juntar

TERMOS = ["python", "django", "fastapi", "flask", "data", "machine learning", "ai",
          "junior", "mid", "entry"]
TOTAL_EXTRAS = 20
CAMINHO_CSV = RAIZ / "eval" / "vagas.csv"
COLUNAS = ["titulo", "link", "descricao", "veredito_esperado"]


def pontuacao(vaga: dict) -> int:
    pontos = 0
    for termo in TERMOS:
        padrao = re.compile(rf"\b{re.escape(termo)}\b", re.IGNORECASE)
        pontos += 2 * bool(padrao.search(vaga["titulo"])) + bool(padrao.search(vaga["descricao"]))
    return pontos


def main():
    with open(CAMINHO_CSV, encoding="utf-8", newline="") as arquivo:
        atuais = list(csv.DictReader(arquivo))
    links_atuais = {linha["link"] for linha in atuais}
    if len(atuais) != 40:
        sys.exit(f"Esperava 40 vagas no vagas.csv, achei {len(atuais)} (extras já adicionadas?).")

    distintas = juntar(FEEDS_PRINCIPAIS)
    restantes = [v for link, v in distintas.items() if link not in links_atuais]
    print(f"{len(restantes)} vagas restantes (fora das {len(atuais)} atuais).")

    pontuadas = [(pontuacao(v), v) for v in restantes]
    ranqueadas = sorted((p for p in pontuadas if p[0] > 0), key=lambda p: -p[0])  # estável
    extras = [v for _, v in ranqueadas[:TOTAL_EXTRAS]]
    random.Random(SEMENTE).shuffle(extras)

    with open(CAMINHO_CSV, "a", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        for vaga in extras:
            escritor.writerow({**vaga, "veredito_esperado": ""})
    escrever_rotular(extras, arquivo="rotular_extra.md", inicio=len(atuais) + 1)
    print(f"{len(extras)} vagas extras acrescentadas (números {len(atuais) + 1} a "
          f"{len(atuais) + len(extras)}); rotular_extra.md gerado.")


if __name__ == "__main__":
    main()
