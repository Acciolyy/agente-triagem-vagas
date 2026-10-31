"""Agente: declaração das ferramentas, system prompt e loop de function calling."""

from google import genai
from google.genai import types
from pydantic import ValidationError

from .config import MAX_TOOL_ITERATIONS, MODEL
from .feed import buscar_vagas_wwr
from .modelos import Avaliacao

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


def avaliar_vaga(**argumentos):
    """Valida a decisão que o modelo já tomou sobre uma vaga.

    Retorna a Avaliacao, ou um dict de erro de ferramenta se os argumentos forem inválidos.
    """
    try:
        return Avaliacao.model_validate(argumentos)
    except ValidationError as erro:
        detalhes = "; ".join(
            f"{'.'.join(str(parte) for parte in e['loc'])}: {e['msg']}" for e in erro.errors()
        )
        return {
            "erro": (
                f"Argumentos inválidos para avaliar_vaga ({detalhes}). "
                "Use veredito exatamente 'aplicar' ou 'não aplicar' e um motivo não vazio."
            )
        }


def executar_function(nome: str, args: dict):
    if nome == "buscar_vagas_wwr":
        return buscar_vagas_wwr(**args)
    if nome == "avaliar_vaga":
        return avaliar_vaga(**args)
    raise ValueError(f"Função desconhecida: {nome}")


def montar_system_prompt(criterios_texto: str) -> str:
    """Monta o system prompt final, embutindo os critérios definidos pelo usuário."""
    return SYSTEM_PROMPT_TEMPLATE.format(criterios=criterios_texto.strip())


def rodar_triagem(
    client: genai.Client, config: types.GenerateContentConfig, termo: str, on_texto=None
):
    """Roda o loop de conversa com function calling para triar vagas do termo dado.

    on_texto, se fornecido, é chamado com cada trecho de texto narrado pelo modelo
    assim que ele chega (útil para feedback em tempo real na CLI).

    Retorna (avaliacoes, atingiu_limite):
    - avaliacoes: list[Avaliacao] com as decisões válidas registradas por avaliar_vaga
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

            if isinstance(resultado, Avaliacao):
                avaliacoes.append(resultado)
                resultado = resultado.model_dump()

            response_parts.append(
                types.Part.from_function_response(
                    name=chamada.name,
                    response={"result": resultado},
                )
            )

        contents.append(types.Content(role="user", parts=response_parts))

    return avaliacoes, atingiu_limite
