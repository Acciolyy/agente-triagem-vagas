"""Busca e parsing do feed RSS de programação do We Work Remotely."""

import re

import feedparser
import requests

from .config import LIMITE_RESULTADOS, TAMANHO_MAX_DESCRICAO, WWR_RSS_URL
from .modelos import Vaga


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
            vaga = Vaga(
                titulo=titulo,
                link=getattr(entrada, "link", "N/A"),
                descricao=_truncar(descricao_limpa) or "N/A",
            )
            resultados.append(vaga.model_dump())

        if len(resultados) >= LIMITE_RESULTADOS:
            break

    if not resultados:
        return {"aviso": f"Nenhuma vaga encontrada para o termo '{termo_busca}'."}

    return resultados
