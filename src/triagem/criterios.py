"""Critérios de triagem: perguntas, formatação via Gemini e leitura/escrita de criterios.txt."""

import os

from google import genai

from .config import CRITERIOS_PATH, MODEL

PERGUNTAS_CRITERIOS = [
    {
        "chave": "nivel",
        "pergunta": "Qual o nível da vaga que você procura?",
        "exemplo": "ex: júnior, pleno, sênior",
    },
    {
        "chave": "stack",
        "pergunta": "Quais tecnologias/stack são do seu interesse?",
        "exemplo": "ex: Python, Django, automação de testes",
    },
    {
        "chave": "ingles",
        "pergunta": "Qual o nível de inglês exigido você aceita?",
        "exemplo": "ex: nenhum, básico, avançado",
    },
    {
        "chave": "modelo_trabalho",
        "pergunta": "Qual modelo de trabalho você aceita?",
        "exemplo": "ex: remoto, híbrido, não importa",
    },
]


def carregar_criterios():
    """Lê criterios.txt, se existir. Retorna None se não existir ou estiver vazio."""
    if os.path.exists(CRITERIOS_PATH):
        with open(CRITERIOS_PATH, "r", encoding="utf-8") as arquivo:
            conteudo = arquivo.read().strip()
        return conteudo or None
    return None


def salvar_criterios(texto: str) -> None:
    """Salva o texto de critérios em criterios.txt, sobrescrevendo o anterior."""
    with open(CRITERIOS_PATH, "w", encoding="utf-8") as arquivo:
        arquivo.write(texto.strip() + "\n")


def gerar_resumo_criterios(client: genai.Client, respostas: dict) -> str:
    """Usa o Gemini para transformar as respostas do usuário em um texto corrido
    descrevendo os critérios de triagem. Se a chamada falhar, cai de volta para
    uma lista simples de perguntas e respostas."""
    perguntas_e_respostas = "\n".join(
        f"- {pergunta['pergunta']} {respostas.get(pergunta['chave'], '').strip()}"
        for pergunta in PERGUNTAS_CRITERIOS
    )

    prompt = (
        "Transforme as respostas abaixo em um texto corrido, curto (3 a 5 frases), "
        "em português, descrevendo os critérios que uma vaga de emprego remota deve "
        "atender para ser recomendada a este candidato. Escreva apenas o texto dos "
        "critérios, sem introduções, saudações ou comentários extras.\n\n"
        f"{perguntas_e_respostas}"
    )

    try:
        resposta = client.models.generate_content(model=MODEL, contents=prompt)
    except Exception:
        return perguntas_e_respostas

    texto = (getattr(resposta, "text", None) or "").strip()
    return texto or perguntas_e_respostas


def obter_criterios_interativo(client: genai.Client) -> str:
    """Fluxo de perguntas no terminal para definir os critérios de triagem."""
    criterios_salvos = carregar_criterios()
    if criterios_salvos:
        reusar = (
            input(
                f"Encontrei critérios salvos em {CRITERIOS_PATH}:\n"
                f"---\n{criterios_salvos}\n---\n"
                "Quer reutilizá-los? (s/n): "
            )
            .strip()
            .lower()
        )
        if reusar in ("s", "sim", "y", "yes"):
            return criterios_salvos

    print("\nVamos definir os critérios de triagem. Responda objetivamente:\n")
    respostas = {}
    for pergunta in PERGUNTAS_CRITERIOS:
        texto_pergunta = f"{pergunta['pergunta']} ({pergunta['exemplo']}): "
        respostas[pergunta["chave"]] = input(texto_pergunta).strip()

    criterios_texto = gerar_resumo_criterios(client, respostas)
    salvar_criterios(criterios_texto)
    print(f"\nCritérios salvos em {CRITERIOS_PATH}:\n{criterios_texto}\n")
    return criterios_texto
