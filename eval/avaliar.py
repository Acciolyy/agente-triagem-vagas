"""
Avalia o agente de triagem contra as vagas rotuladas em eval/vagas.csv.

Roda o agente de verdade (system prompt, ferramentas e loop de src/triagem) com os critérios
de eval/criterios_eval.txt. A única diferença é a fonte das vagas: em vez de baixar o feed,
buscar_vagas_wwr devolve, em lotes do tamanho do limite de resultados, as vagas do CSV com
o texto exato (título + descrição de 300 caracteres) que o agente veria.

Métricas: com positivos no conjunto, precisão e recall de "aplicar"; sempre, a taxa de
descarte correto (especificidade) e a lista de falsos positivos com o motivo do agente.
Sem positivos, precisão e recall não são calculadas.

Rodar da raiz do projeto: python eval/avaliar.py [--retomar] [vagas.csv] [resultados.csv]
Padrão: eval/vagas.csv -> eval/resultados_wwr.csv

Se o CSV tiver a coluna execucao (conjunto sintético), cada valor dela vira uma execução
separada, na ordem do CSV, em vez de lotes de 15; assim os dois lados de um par de contraste
nunca aparecem juntos para o agente. As demais colunas do CSV são ignoradas.

Com --retomar, reaproveita as decisões já gravadas no CSV de resultados e roda o agente só
nas vagas sem decisão. Os resultados são regravados a cada lote concluído.
"""

import csv
import sys
from pathlib import Path

from google.genai import errors, types

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from src.triagem import agente  # noqa: E402
from src.triagem.config import LIMITE_RESULTADOS, obter_api_key  # noqa: E402

CRITERIOS = RAIZ / "eval" / "criterios_eval.txt"
TENTATIVAS = 6
ESPERA_BASE = 30
COLUNAS = [
    "titulo", "link", "veredito_esperado", "veredito_agente", "motivo", "acerto",
]


def ler_vagas(caminho: Path) -> list[dict]:
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        vagas = list(csv.DictReader(arquivo))
    sem_rotulo = [v["titulo"] for v in vagas if not v["veredito_esperado"].strip()]
    if sem_rotulo:
        sys.exit(f"{len(sem_rotulo)} vaga(s) sem veredito_esperado (ex.: {sem_rotulo[0]}).")
    return vagas


def triar_lote(client, config, lote: list[dict]) -> list:
    """Roda o agente sobre um lote de vagas, com nova tentativa em timeout e erros transitórios."""
    dados = [{k: v[k] for k in ("titulo", "link", "descricao")} for v in lote]
    original = agente.buscar_vagas_wwr
    agente.buscar_vagas_wwr = lambda termo_busca: dados
    try:
        avaliacoes, atingiu_limite = agente.rodar_triagem(
            client,
            config,
            "python",
            on_aviso=lambda aviso: print(f"  {aviso}"),
            tentativas=TENTATIVAS,
            espera_base=ESPERA_BASE,
        )
        if atingiu_limite:
            print("  aviso: limite de iterações atingido neste lote.")
        return avaliacoes
    finally:
        agente.buscar_vagas_wwr = original


def ler_anteriores(caminho: Path) -> dict[str, dict]:
    """Decisões já gravadas (link -> linha de resultado) que podem ser reaproveitadas."""
    if not caminho.exists():
        return {}
    with open(caminho, encoding="utf-8", newline="") as arquivo:
        return {r["link"]: r for r in csv.DictReader(arquivo) if r["veredito_agente"]}


def montar_resultados(vagas: list[dict], decisoes: dict, anteriores: dict) -> list[dict]:
    resultados = []
    for vaga in vagas:
        decisao = decisoes.get(vaga["link"])
        if decisao:
            veredito, motivo = decisao.veredito, decisao.motivo
        elif vaga["link"] in anteriores:
            veredito = anteriores[vaga["link"]]["veredito_agente"]
            motivo = anteriores[vaga["link"]]["motivo"]
        else:
            veredito = motivo = ""
        resultados.append(
            {
                "titulo": vaga["titulo"],
                "link": vaga["link"],
                "veredito_esperado": vaga["veredito_esperado"],
                "veredito_agente": veredito,
                "motivo": motivo,
                "acerto": (veredito == vaga["veredito_esperado"]) if veredito else "",
            }
        )
    return resultados


def gravar(resultados: list[dict], saida: Path) -> None:
    with open(saida, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(resultados)


def dividir_em_lotes(vagas: list[dict]) -> list[list[dict]]:
    """Lotes de LIMITE_RESULTADOS vagas, ou um lote por valor da coluna execucao, se existir."""
    if vagas and "execucao" in vagas[0]:
        execucoes = sorted({v["execucao"] for v in vagas})
        return [[v for v in vagas if v["execucao"] == e] for e in execucoes]
    return [vagas[i : i + LIMITE_RESULTADOS] for i in range(0, len(vagas), LIMITE_RESULTADOS)]


def avaliar(vagas: list[dict], saida: Path, anteriores: dict) -> list[dict]:
    client = agente.criar_client(obter_api_key())
    config = types.GenerateContentConfig(
        system_instruction=agente.montar_system_prompt(CRITERIOS.read_text(encoding="utf-8")),
        tools=[agente.TOOLS],
    )
    pendentes = [v for v in vagas if v["link"] not in anteriores]
    print(f"{len(vagas) - len(pendentes)} decisões reaproveitadas; {len(pendentes)} a avaliar.")

    decisoes = {}  # link -> Avaliacao (a última decisão do agente vale)
    for numero, lote in enumerate(dividir_em_lotes(pendentes), start=1):
        print(f"Lote {numero}: {len(lote)} vagas")
        try:
            avaliacoes = triar_lote(client, config, lote)
        except (errors.APIError, agente.TimeoutGemini) as erro:
            codigo = getattr(erro, "code", "timeout")
            print(f"  lote abandonado após erro da API ({codigo}); fica sem decisão.")
            continue
        for avaliacao in avaliacoes:
            decisoes[avaliacao.link] = avaliacao
        gravar(montar_resultados(vagas, decisoes, anteriores), saida)

    return montar_resultados(vagas, decisoes, anteriores)


def porcentagem(parte: int, total: int) -> str:
    return f"{100 * parte / total:.1f}%" if total else "n/a"


def resumir(resultados: list[dict]) -> str:
    avaliadas = [r for r in resultados if r["veredito_agente"]]
    nao_avaliadas = [r for r in resultados if not r["veredito_agente"]]
    positivos = [r for r in avaliadas if r["veredito_esperado"] == "aplicar"]
    negativos = [r for r in avaliadas if r["veredito_esperado"] == "não aplicar"]
    falsos_positivos = [r for r in negativos if r["veredito_agente"] == "aplicar"]
    verdadeiros_positivos = [r for r in positivos if r["veredito_agente"] == "aplicar"]
    aplicar_previstos = len(verdadeiros_positivos) + len(falsos_positivos)

    linhas = [
        f"Vagas no conjunto: {len(resultados)} | avaliadas pelo agente: {len(avaliadas)} "
        f"| sem decisão do agente: {len(nao_avaliadas)}",
        f"Esperado: {len(positivos)} aplicar, {len(negativos)} não aplicar",
        f"Descarte correto (especificidade): {len(negativos) - len(falsos_positivos)}/"
        f"{len(negativos)} = {porcentagem(len(negativos) - len(falsos_positivos), len(negativos))}",
        f"Falsos positivos (agente disse aplicar, esperado não aplicar): {len(falsos_positivos)}",
    ]
    if positivos:
        linhas.append(
            f"Recall de aplicar: {len(verdadeiros_positivos)}/{len(positivos)} = "
            f"{porcentagem(len(verdadeiros_positivos), len(positivos))}"
        )
        linhas.append(
            f"Precisão de aplicar: {len(verdadeiros_positivos)}/{aplicar_previstos} = "
            f"{porcentagem(len(verdadeiros_positivos), aplicar_previstos)}"
        )
    else:
        linhas.append("Sem positivos no conjunto: precisão e recall de aplicar não calculados.")
    for r in falsos_positivos:
        linhas.append(f"  - {r['titulo']}\n    {r['link']}\n    Motivo do agente: {r['motivo']}")
    for r in nao_avaliadas:
        linhas.append(f"  [sem decisão] {r['titulo']}")
    return "\n".join(linhas)


def main():
    if not obter_api_key():
        sys.exit("GEMINI_API_KEY não definida.")
    argumentos = [a for a in sys.argv[1:] if a != "--retomar"]
    retomar = len(argumentos) != len(sys.argv) - 1
    entrada = Path(argumentos[0]) if argumentos else RAIZ / "eval" / "vagas.csv"
    saida = Path(argumentos[1]) if len(argumentos) > 1 else RAIZ / "eval" / "resultados_wwr.csv"

    anteriores = ler_anteriores(saida) if retomar else {}
    resultados = avaliar(ler_vagas(entrada), saida, anteriores)
    gravar(resultados, saida)
    print("\n" + resumir(resultados))
    print(f"\nResultados em {saida}")


if __name__ == "__main__":
    main()
