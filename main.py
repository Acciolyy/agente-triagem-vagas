"""
Agente de triagem de vagas remotas.

Usa a API do Google Gemini (SDK google-genai) com function calling para:
1. Buscar vagas remotas no feed RSS de programação do We Work Remotely
   (buscar_vagas_wwr).
2. Avaliar cada vaga encontrada segundo critérios definidos pelo próprio
   usuário em um fluxo de perguntas (avaliar_vaga).

A lógica fica no pacote src/triagem; este arquivo é só a interface de linha
de comando (python main.py <termo>).
"""

import sys

from google.genai import errors, types

from src.triagem.agente import (
    TOOLS,
    TimeoutGemini,
    criar_client,
    montar_system_prompt,
    rodar_triagem,
)
from src.triagem.config import MAX_TOOL_ITERATIONS, obter_api_key
from src.triagem.criterios import obter_criterios_interativo


def imprimir_resultado_final(avaliacoes: list):
    if not avaliacoes:
        print("\nNenhuma vaga foi avaliada nesta execução.")
        return

    aplicar = [a for a in avaliacoes if a.veredito == "aplicar"]
    nao_aplicar = [a for a in avaliacoes if a.veredito == "não aplicar"]

    print("\n" + "=" * 60)
    print(f"RESULTADO DA TRIAGEM ({len(avaliacoes)} vaga(s) avaliada(s))")
    print("=" * 60)

    print(f"\n>> Vagas para APLICAR ({len(aplicar)}):")
    if not aplicar:
        print("  (nenhuma)")
    for vaga in aplicar:
        print(f"  - {vaga.titulo}")
        print(f"    Link: {vaga.link}")
        print(f"    Motivo: {vaga.motivo}")

    print(f"\n>> Vagas para NÃO aplicar ({len(nao_aplicar)}):")
    if not nao_aplicar:
        print("  (nenhuma)")
    for vaga in nao_aplicar:
        print(f"  - {vaga.titulo}")
        print(f"    Link: {vaga.link}")
        print(f"    Motivo: {vaga.motivo}")

    print()


def main():
    api_key = obter_api_key()
    if not api_key:
        print(
            "Erro: variável de ambiente GEMINI_API_KEY não definida.\n"
            "Copie .env.example para .env, preencha sua chave e rode novamente."
        )
        sys.exit(1)

    client = criar_client(api_key)

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
            client,
            config,
            termo,
            on_texto=lambda texto: print(f"\n[Gemini] {texto}"),
            on_aviso=lambda aviso: print(f"\n[aviso] {aviso}"),
        )
    except TimeoutGemini as erro:
        print(f"{erro} Tente novamente em instantes.")
        sys.exit(1)
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
