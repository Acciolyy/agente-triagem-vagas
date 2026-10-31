"""
Coleta as issues abertas mais recentes do repositório backend-br/vagas (GitHub) que mencionam
Python no título ou nos labels, e gera a segunda fonte do conjunto de avaliação:

- eval/vagas_backendbr.csv: titulo, link, descricao, veredito_esperado (vazia, para rotular)
- eval/rotular_backendbr.md: tabela de rotulagem, numerada a partir de 60

Cada issue vira o que o agente recebe: título + primeiros 300 caracteres do corpo, com a mesma
limpeza de src/triagem/feed.py (tags HTML removidas, espaços normalizados). Usa o gh se estiver
logado; senão, a API pública do GitHub sem token.

Rodar da raiz do projeto: python eval/coletar_backendbr.py
"""

import csv
import json
import subprocess
import sys
from datetime import date

import requests
from coletar import RAIZ, escrever_rotular

sys.path.insert(0, str(RAIZ))

from src.triagem.feed import _limpar_html, _truncar  # noqa: E402

REPO = "backend-br/vagas"
TERMO = "python"
TOTAL = 25
PRIMEIRO_NUMERO = 60
POR_PAGINA = 100
MAX_PAGINAS = 10
CAMINHO_CSV = RAIZ / "eval" / "vagas_backendbr.csv"
COLUNAS = ["titulo", "link", "descricao", "veredito_esperado"]


def pagina_issues(pagina: int) -> list[dict]:
    caminho = f"repos/{REPO}/issues?state=open&sort=created&direction=desc"
    caminho += f"&per_page={POR_PAGINA}&page={pagina}"
    try:
        saida = subprocess.run(
            ["gh", "api", caminho], capture_output=True, text=True, check=True
        ).stdout
        return json.loads(saida)
    except (OSError, subprocess.CalledProcessError):
        resposta = requests.get(
            f"https://api.github.com/{caminho}",
            headers={"Accept": "application/vnd.github+json"},
            timeout=15,
        )
        resposta.raise_for_status()
        return resposta.json()


def menciona_python(issue: dict) -> bool:
    nomes_labels = [label["name"] for label in issue.get("labels", [])]
    return TERMO in " ".join([issue["title"], *nomes_labels]).lower()


def coletar() -> list[dict]:
    vagas = []
    for pagina in range(1, MAX_PAGINAS + 1):
        issues = pagina_issues(pagina)
        for issue in issues:
            if "pull_request" in issue or not menciona_python(issue):
                continue
            descricao = _truncar(_limpar_html(issue.get("body") or "")) or "N/A"
            vagas.append(
                {"titulo": issue["title"], "link": issue["html_url"], "descricao": descricao}
            )
            if len(vagas) == TOTAL:
                return vagas
        if len(issues) < POR_PAGINA:
            break
    return vagas


def main():
    if CAMINHO_CSV.exists():
        sys.exit("eval/vagas_backendbr.csv já existe; apague-o antes (perderia os rótulos).")
    vagas = coletar()
    with open(CAMINHO_CSV, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        for vaga in vagas:
            escritor.writerow({**vaga, "veredito_esperado": ""})
    escrever_rotular(vagas, arquivo="rotular_backendbr.md", inicio=PRIMEIRO_NUMERO)
    print(f"{len(vagas)} issues de {REPO} com '{TERMO}' (em {date.today().isoformat()}).")


if __name__ == "__main__":
    main()
