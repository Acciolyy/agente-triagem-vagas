"""Configuração: variáveis de ambiente (.env) e constantes compartilhadas."""

import os

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
CRITERIOS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "criterios.txt",
)


def obter_api_key():
    """Retorna GEMINI_API_KEY do ambiente, ou None se não estiver definida."""
    return os.environ.get("GEMINI_API_KEY")
