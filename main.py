"""
Agente de triagem de vagas remotas.

Usa a API do Google Gemini (SDK google-genai) com function calling para:
1. Buscar vagas remotas no feed RSS de programação do We Work Remotely
   (buscar_vagas_wwr).
2. Avaliar cada vaga encontrada segundo critérios definidos pelo próprio
   usuário em um fluxo de perguntas (avaliar_vaga).

O modelo é quem decide o veredito de cada vaga; a função avaliar_vaga apenas
formata e registra essa decisão em JSON.

Este módulo é reaproveitado por app.py (interface Streamlit) — as funções e
constantes aqui não têm efeito colateral na importação, exceto main(), que só
roda quando o arquivo é executado diretamente.
"""

import json
import os
import re
import sys

import feedparser
import requests
from google import genai
from google.genai import errors, types

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

MODEL = "gemini-flash-latest"
MAX_TOOL_ITERATIONS = 20
WWR_RSS_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"
LIMITE_RESULTADOS = 15
TAMANHO_MAX_DESCRICAO = 300
VEREDITOS_VALIDOS = {"aplicar", "não aplicar"}
CRITERIOS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "criterios.txt")

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

SYSTEM_PROMPT_TEMPLATE = """Você é um agente de triagem de vagas de emprego remotas.

Você tem duas ferramentas disponíveis:
1. buscar_vagas_wwr: busca vagas no feed RSS de programação remota do We Work
   Remotely, filtradas por um termo no título, nas tags ou na descrição.
2. avaliar_vaga: registra a SUA decisão (veredito e motivo) sobre uma vaga específica.
   Esta ferramenta não decide nada sozinha — ela só formata e registra a decisão que
   você já tomou. Você deve chamá-la para CADA vaga retornada pela busca.

Fluxo esperado:
1. Chame buscar_vagas_wwr com o termo de busca fornecido.
2. O feed retorna título, link e uma descrição resumida de cada vaga. Avalie cada
   vaga com base nesses dados.
3. Para cada vaga retornada, chame avaliar_vaga informando: titulo, descricao_ou_tags
   (um resumo da descrição que você usou para decidir), link (o link da vaga,
   copiado exatamente como veio da busca), veredito ("aplicar" ou "não aplicar") e
   motivo (uma frase curta explicando a decisão).

Critérios definidos pelo usuário para decidir "aplicar":
{criterios}

Se a vaga não deixar um critério claro, use seu melhor julgamento e diga isso no
motivo. Depois de avaliar todas as vagas, escreva um resumo curto em texto para o
usuário."""

BUSCAR_VAGAS_DECLARATION = types.FunctionDeclaration(
    name="buscar_vagas_wwr",
    description=(
        "Busca vagas remotas no feed RSS de programação do We Work Remotely "
        "(https://weworkremotely.com/categories/remote-programming-jobs.rss), "
        "filtrando pelas vagas em que o termo de busca apareça (case-insensitive) "
        "no título, nas tags/categoria ou na descrição da vaga. Retorna até 15 "
        "resultados com título, link e descrição resumida."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "termo_busca": types.Schema(
                type=types.Type.STRING,
                description=(
                    "Termo a ser buscado no título, nas tags ou na descrição das "
                    "vagas, ex: 'python', 'qa', 'django', 'test automation'."
                ),
            )
        },
        required=["termo_busca"],
    ),
)

AVALIAR_VAGA_DECLARATION = types.FunctionDeclaration(
    name="avaliar_vaga",
    description=(
        "Registra a decisão de triagem sobre uma vaga específica, formatando-a em JSON. "
        "Esta função NÃO toma a decisão — apenas formata e registra o veredito e o "
        "motivo que você (o modelo) já decidiu com base nos critérios do sistema."
    ),
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "titulo": types.Schema(
                type=types.Type.STRING, description="Título da vaga avaliada."
            ),
            "descricao_ou_tags": types.Schema(
                type=types.Type.STRING,
                description=(
                    "Resumo da descrição da vaga (retornada pelo feed RSS) usada "
                    "para avaliar a vaga."
                ),
            ),
            "link": types.Schema(
                type=types.Type.STRING,
                description="Link da vaga, exatamente como retornado por buscar_vagas_wwr.",
            ),
            "veredito": types.Schema(
                type=types.Type.STRING,
                enum=["aplicar", "não aplicar"],
                description="Decisão final sobre a vaga.",
            ),
            "motivo": types.Schema(
                type=types.Type.STRING,
                description="Motivo curto (uma frase) para a decisão.",
            ),
        },
        required=["titulo", "descricao_ou_tags", "link", "veredito", "motivo"],
    ),
)

TOOLS = types.Tool(function_declarations=[BUSCAR_VAGAS_DECLARATION, AVALIAR_VAGA_DECLARATION])


def _limpar_html(html_ou_texto: str) -> str:
    """Remove tags HTML e normaliza espaços em branco."""
    sem_tags = re.sub(r"<[^>]+>", " ", html_ou_texto or "")
    return re.sub(r"\s+", " ", sem_tags).strip()


def _truncar(texto: str, tamanho: int = TAMANHO_MAX_DESCRICAO) -> str:
    """Corta o texto em um tamanho legível, se necessário."""
    if len(texto) > tamanho:
        return texto[:tamanho].rstrip() + "..."
    return texto


def buscar_vagas_wwr(termo_busca: str):
    """Busca vagas no feed RSS de programação remota do We Work Remotely."""
    termo = termo_busca.strip().lower()
    if not termo:
        return {"erro": "termo_busca não pode ser vazio."}

    try:
        resposta = requests.get(
            WWR_RSS_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AgenteTriagemVagas/1.0)"},
            timeout=10,
        )
        resposta.raise_for_status()
    except requests.exceptions.RequestException as erro:
        return {"erro": f"Falha ao acessar o feed RSS do We Work Remotely: {erro}"}

    feed = feedparser.parse(resposta.content)

    if feed.bozo and not feed.entries:
        return {"erro": "O feed RSS do We Work Remotely retornou um XML inválido."}

    if not feed.entries:
        return {"erro": "O feed RSS do We Work Remotely retornou uma resposta vazia."}

    resultados = []
    for entrada in feed.entries:
        titulo = str(getattr(entrada, "title", "") or "")
        descricao_limpa = _limpar_html(getattr(entrada, "summary", ""))
        tags = [str(tag.get("term", "")) for tag in (getattr(entrada, "tags", None) or [])]

        titulo_encontrado = termo in titulo.lower()
        tags_encontrado = any(termo in tag.lower() for tag in tags)
        descricao_encontrada = termo in descricao_limpa.lower()

        if titulo_encontrado or tags_encontrado or descricao_encontrada:
            resultados.append(
                {
                    "titulo": titulo,
                    "link": getattr(entrada, "link", "N/A"),
                    "descricao": _truncar(descricao_limpa) or "N/A",
                }
            )

        if len(resultados) >= LIMITE_RESULTADOS:
            break

    if not resultados:
        return {"aviso": f"Nenhuma vaga encontrada para o termo '{termo_busca}'."}

    return resultados


def avaliar_vaga(titulo: str, descricao_ou_tags: str, link: str, veredito: str, motivo: str):
    """Formata e registra a decisão que o modelo já tomou sobre uma vaga."""
    veredito_normalizado = veredito.strip().lower()
    if veredito_normalizado not in VEREDITOS_VALIDOS:
        return {
            "erro": (
                f"Veredito inválido: '{veredito}'. "
                "Use exatamente 'aplicar' ou 'não aplicar'."
            )
        }

    return {
        "titulo": titulo,
        "contexto": descricao_ou_tags,
        "link": link,
        "veredito": veredito_normalizado,
        "motivo": motivo,
    }


def executar_function(nome: str, args: dict):
    if nome == "buscar_vagas_wwr":
        return buscar_vagas_wwr(**args)
    if nome == "avaliar_vaga":
        return avaliar_vaga(**args)
    raise ValueError(f"Função desconhecida: {nome}")


# --- Critérios de triagem (fluxo conversacional) -----------------------------


def montar_system_prompt(criterios_texto: str) -> str:
    """Monta o system prompt final, embutindo os critérios definidos pelo usuário."""
    return SYSTEM_PROMPT_TEMPLATE.format(criterios=criterios_texto.strip())


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


# --- Loop de conversa com function calling -----------------------------------


def rodar_triagem(client: genai.Client, config: types.GenerateContentConfig, termo: str, on_texto=None):
    """Roda o loop de conversa com function calling para triar vagas do termo dado.

    on_texto, se fornecido, é chamado com cada trecho de texto narrado pelo modelo
    assim que ele chega (útil para feedback em tempo real na CLI).

    Retorna (avaliacoes, atingiu_limite):
    - avaliacoes: lista de dicts retornados por avaliar_vaga (sem erro de veredito)
    - atingiu_limite: True se o loop foi interrompido por MAX_TOOL_ITERATIONS sem o
      modelo finalizar a triagem
    """
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part(
                    text=(
                        f"Busque vagas remotas para o termo '{termo}' usando a função "
                        "buscar_vagas_wwr e depois avalie cada vaga retornada chamando "
                        "avaliar_vaga, seguindo os critérios definidos nas instruções do sistema."
                    )
                )
            ],
        )
    ]

    avaliacoes = []
    atingiu_limite = True

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=config,
        )

        if not response.candidates:
            if on_texto:
                motivo_bloqueio = getattr(response.prompt_feedback, "block_reason", None)
                on_texto(f"[aviso] resposta vazia da API (bloqueada? motivo: {motivo_bloqueio}).")
            atingiu_limite = False
            break

        candidate = response.candidates[0]
        parts = candidate.content.parts or []

        for parte in parts:
            if parte.text and on_texto:
                on_texto(parte.text)

        function_calls = [parte.function_call for parte in parts if parte.function_call]

        if not function_calls:
            atingiu_limite = False
            break

        contents.append(candidate.content)  # turno do modelo, com as function calls

        response_parts = []
        for chamada in function_calls:
            args = dict(chamada.args) if chamada.args else {}
            try:
                resultado = executar_function(chamada.name, args)
            except Exception as erro:
                resultado = {"erro": f"Falha ao executar '{chamada.name}': {erro}"}

            if chamada.name == "avaliar_vaga" and "erro" not in resultado:
                avaliacoes.append(resultado)

            response_parts.append(
                types.Part.from_function_response(
                    name=chamada.name,
                    response={"result": resultado},
                )
            )

        contents.append(types.Content(role="user", parts=response_parts))

    return avaliacoes, atingiu_limite


def imprimir_resultado_final(avaliacoes: list):
    if not avaliacoes:
        print("\nNenhuma vaga foi avaliada nesta execução.")
        return

    aplicar = [a for a in avaliacoes if a["veredito"] == "aplicar"]
    nao_aplicar = [a for a in avaliacoes if a["veredito"] == "não aplicar"]

    print("\n" + "=" * 60)
    print(f"RESULTADO DA TRIAGEM ({len(avaliacoes)} vaga(s) avaliada(s))")
    print("=" * 60)

    print(f"\n>> Vagas para APLICAR ({len(aplicar)}):")
    if not aplicar:
        print("  (nenhuma)")
    for vaga in aplicar:
        print(f"  - {vaga['titulo']}")
        print(f"    Link: {vaga.get('link', 'N/A')}")
        print(f"    Motivo: {vaga['motivo']}")

    print(f"\n>> Vagas para NÃO aplicar ({len(nao_aplicar)}):")
    if not nao_aplicar:
        print("  (nenhuma)")
    for vaga in nao_aplicar:
        print(f"  - {vaga['titulo']}")
        print(f"    Link: {vaga.get('link', 'N/A')}")
        print(f"    Motivo: {vaga['motivo']}")

    print()


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(
            "Erro: variável de ambiente GEMINI_API_KEY não definida.\n"
            "Copie .env.example para .env, preencha sua chave e rode novamente."
        )
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    criterios_texto = obter_criterios_interativo(client)

    termo = " ".join(sys.argv[1:]).strip() or input(
        "Digite o termo de busca (ex: python, qa, django): "
    ).strip()
    if not termo:
        print("Termo de busca vazio. Encerrando.")
        sys.exit(1)

    config = types.GenerateContentConfig(
        system_instruction=montar_system_prompt(criterios_texto),
        tools=[TOOLS],
    )

    try:
        avaliacoes, atingiu_limite = rodar_triagem(
            client, config, termo, on_texto=lambda texto: print(f"\n[Gemini] {texto}")
        )
    except errors.APIError as erro:
        print(f"Erro da API do Gemini ({erro.code}): {erro.message}")
        sys.exit(1)
    except Exception as erro:
        print(f"Erro inesperado ao chamar a API do Gemini: {erro}")
        sys.exit(1)

    if atingiu_limite:
        print(
            f"\nAviso: número máximo de iterações ({MAX_TOOL_ITERATIONS}) atingido "
            "antes do modelo finalizar a triagem."
        )

    imprimir_resultado_final(avaliacoes)


if __name__ == "__main__":
    main()
