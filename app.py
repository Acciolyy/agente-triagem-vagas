"""
Interface web (Streamlit) para o agente de triagem de vagas remotas.

Não duplica lógica: reaproveita o pacote src/triagem (busca no We Work
Remotely, avaliação via function calling, critérios de triagem). Este
arquivo só cuida da apresentação (formulário, spinner, cards).

Rodar com: streamlit run app.py
"""

import streamlit as st
from google import genai
from google.genai import errors, types

from src.triagem.agente import TOOLS, montar_system_prompt, rodar_triagem
from src.triagem.config import MAX_TOOL_ITERATIONS, obter_api_key
from src.triagem.criterios import carregar_criterios, gerar_resumo_criterios, salvar_criterios

st.set_page_config(page_title="Agente de Triagem de Vagas Remotas", layout="centered")


@st.cache_resource
def obter_client(api_key: str):
    return genai.Client(api_key=api_key)


def renderizar_resultados(avaliacoes: list):
    if not avaliacoes:
        st.info("Nenhuma vaga foi avaliada.")
        return

    aplicar = [vaga for vaga in avaliacoes if vaga["veredito"] == "aplicar"]
    nao_aplicar = [vaga for vaga in avaliacoes if vaga["veredito"] == "não aplicar"]

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de vagas", len(avaliacoes))
    col2.metric("Recomendadas", len(aplicar))
    col3.metric("Descartadas", len(nao_aplicar))

    st.divider()

    for vaga in avaliacoes:
        if vaga["veredito"] == "aplicar":
            icone, cor_fundo, cor_borda = "✅", "#e6f4ea", "#34a853"
        else:
            icone, cor_fundo, cor_borda = "❌", "#fce8e6", "#ea4335"

        link = vaga.get("link") or ""
        titulo_html = (
            f'<a href="{link}" target="_blank">{vaga["titulo"]}</a>' if link else vaga["titulo"]
        )

        st.markdown(
            f"""
            <div style="background-color:{cor_fundo}; border-left:4px solid {cor_borda};
                        padding:0.85rem 1rem; border-radius:0.4rem; margin-bottom:0.75rem;">
                <div style="font-weight:600; font-size:1.05rem;">{icone} {titulo_html}</div>
                <div style="margin-top:0.35rem;"><strong>Motivo:</strong> {vaga['motivo']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


api_key = obter_api_key()
if not api_key:
    st.error(
        "Variável de ambiente GEMINI_API_KEY não definida. Copie .env.example "
        "para .env, preencha sua chave e rode novamente."
    )
    st.stop()

client = obter_client(api_key)

if "criterios_texto" not in st.session_state:
    st.session_state["criterios_texto"] = carregar_criterios() or ""

st.title("Agente de Triagem de Vagas Remotas")
st.caption("Busca vagas no We Work Remotely e avalia cada uma com o Gemini.")

with st.sidebar:
    st.header("Critérios de triagem")

    if st.session_state["criterios_texto"]:
        st.caption("Critérios atuais:")
        st.info(st.session_state["criterios_texto"])
    else:
        st.warning("Nenhum critério definido ainda. Preencha o formulário abaixo.")

    with st.form("form_criterios"):
        nivel = st.text_input("Nível da vaga", placeholder="ex: júnior, pleno, sênior")
        stack = st.text_input(
            "Tecnologias/stack de interesse",
            placeholder="ex: Python, Django, automação de testes",
        )
        ingles = st.selectbox("Inglês exigido aceitável", ["nenhum", "básico", "avançado"])
        modelo_trabalho = st.selectbox(
            "Modelo de trabalho", ["remoto", "híbrido", "não importa"]
        )
        salvar_criterios_clicado = st.form_submit_button("Salvar critérios")

    if salvar_criterios_clicado:
        if not nivel.strip() or not stack.strip():
            st.warning("Preencha ao menos o nível e as tecnologias antes de salvar.")
        else:
            respostas = {
                "nivel": nivel,
                "stack": stack,
                "ingles": ingles,
                "modelo_trabalho": modelo_trabalho,
            }
            with st.spinner("Formatando critérios com o Gemini..."):
                try:
                    criterios_texto = gerar_resumo_criterios(client, respostas)
                except Exception as erro:
                    st.error(f"Falha ao formatar critérios: {erro}")
                    st.stop()
            salvar_criterios(criterios_texto)
            st.session_state["criterios_texto"] = criterios_texto
            st.success("Critérios salvos!")
            st.rerun()

termo = st.text_input("Termo de busca", placeholder="ex: python, qa, django")
buscar_clicado = st.button("Buscar vagas", type="primary")

if buscar_clicado:
    if not st.session_state["criterios_texto"]:
        st.warning("Defina e salve os critérios de triagem na barra lateral antes de buscar.")
    elif not termo.strip():
        st.warning("Informe um termo de busca.")
    else:
        config = types.GenerateContentConfig(
            system_instruction=montar_system_prompt(st.session_state["criterios_texto"]),
            tools=[TOOLS],
        )

        with st.spinner("Buscando e avaliando vagas..."):
            try:
                avaliacoes, atingiu_limite = rodar_triagem(client, config, termo.strip())
            except errors.APIError as erro:
                st.error(f"Erro da API do Gemini ({erro.code}): {erro.message}")
                avaliacoes = None
            except Exception as erro:
                st.error(f"Erro inesperado ao chamar a API do Gemini: {erro}")
                avaliacoes = None

        if avaliacoes is not None:
            if atingiu_limite:
                st.warning(
                    f"Número máximo de iterações ({MAX_TOOL_ITERATIONS}) atingido "
                    "antes do modelo finalizar a triagem."
                )
            renderizar_resultados(avaliacoes)
