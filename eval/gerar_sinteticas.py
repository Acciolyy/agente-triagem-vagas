"""
Gera o conjunto sintético de controle, eval/vagas_sinteticas.csv: 16 vagas fictícias em
8 pares de contraste. Em cada par, as duas vagas são iguais exceto por um único fator
(coluna fator_variado). O veredito_esperado sai por construção, pelos critérios de
eval/criterios_eval.txt: o lado A de cada par atende aos critérios e o lado B não.

A coluna execucao separa as vagas em duas execuções de 8 vagas, sem nenhum par junto
(avaliar.py roda cada execução separadamente, para o agente nunca ver os dois lados de um
par no mesmo lote), cada uma com 4 "aplicar" e 4 "não aplicar":
- execução 1: lado A de p1 a p4 + lado B de p5 a p8
- execução 2: lado B de p1 a p4 + lado A de p5 a p8

Empresas e links são fictícios (domínio .example).

Rodar da raiz do projeto: python eval/gerar_sinteticas.py
"""

import csv
import random
from pathlib import Path

EN_GLOBAL = "Open to candidates anywhere in the world."
PARES = [
 ("p1","nível (pleno vs experiência comprovada)","Quillbrook: Python Backend Developer",
  "Headquarters: Remote (worldwide) We need a mid-level engineer with 3 years of experience to build REST APIs with FastAPI and PostgreSQL. Intermediate English required. "+EN_GLOBAL,
  "Headquarters: Remote (worldwide) We need an engineer with a proven track record of leading backend teams to build REST APIs with FastAPI and PostgreSQL. Intermediate English required. "+EN_GLOBAL),
 ("p2","nível (pleno vs Staff/Senior explícito)","Zorvane: Desenvolvedor(a) Python",
  "Remoto (qualquer lugar do mundo). Vaga de nível pleno (3 a 5 anos de experiência) para desenvolver APIs com Django e PostgreSQL. Inglês intermediário. Aceitamos candidatos de qualquer país.",
  "Remoto (qualquer lugar do mundo). Vaga de nível Staff/Senior (8+ anos de experiência) para desenvolver APIs com Django e PostgreSQL. Inglês intermediário. Aceitamos candidatos de qualquer país."),
 ("p3","Python explícito vs omitido (IA/ML, inglês)","Fennimore Labs: Machine Learning Engineer",
  "Headquarters: Remote (worldwide) Mid-level Machine Learning Engineer to train and deploy recommendation models in Python. Intermediate English required. "+EN_GLOBAL,
  "Headquarters: Remote (worldwide) Mid-level Machine Learning Engineer to train and deploy recommendation models. Intermediate English required. "+EN_GLOBAL),
 ("p4","Python explícito vs omitido (dados/IA, português)","Tapioca Dados: Engenheiro(a) de Dados",
  "Remoto (qualquer lugar do mundo). Vaga de nível pleno para construir pipelines de dados e modelos de IA em Python. Inglês intermediário. Aceitamos candidatos de qualquer país.",
  "Remoto (qualquer lugar do mundo). Vaga de nível pleno para construir pipelines de dados e modelos de IA. Inglês intermediário. Aceitamos candidatos de qualquer país."),
 ("p5","local (remoto global vs só EUA)","Marlowe Quay: Python Data Engineer",
  "Headquarters: Remote (worldwide) Mid-level Python Data Engineer to build data pipelines and ML features. Advanced English required. Candidates from anywhere in the world are welcome.",
  "Headquarters: Remote (US only) Mid-level Python Data Engineer to build data pipelines and ML features. Advanced English required. Candidates must reside in the United States."),
 ("p6","local (remoto global vs só EUA, português)","Pitanga Systems: Desenvolvedor(a) Python Pleno",
  "Remoto. Desenvolvimento de serviços backend com Flask e PostgreSQL, nível pleno. Inglês intermediário. Aceitamos candidatos de qualquer país.",
  "Remoto. Desenvolvimento de serviços backend com Flask e PostgreSQL, nível pleno. Inglês intermediário. Apenas para residentes nos Estados Unidos."),
 ("p7","stack (Django vs Java)","Velkor: Backend Developer",
  "Headquarters: Remote (worldwide) Mid-level backend developer to build payment APIs with Django and PostgreSQL. Intermediate English required. "+EN_GLOBAL,
  "Headquarters: Remote (worldwide) Mid-level backend developer to build payment APIs with Java and Spring Boot. Intermediate English required. "+EN_GLOBAL),
 ("p8","modelo de trabalho (remoto vs híbrido em São Paulo)","Jabuti Digital: Desenvolvedor(a) Python Pleno",
  "100% remoto (Brasil). Vaga de nível pleno para desenvolver APIs com FastAPI e PostgreSQL. Inglês intermediário.",
  "Híbrido em São Paulo (3 dias por semana no escritório). Vaga de nível pleno para desenvolver APIs com FastAPI e PostgreSQL. Inglês intermediário."),
]
COLUNAS = [
    "titulo", "link", "descricao", "veredito_esperado", "par_id", "fator_variado", "execucao",
]
CAMINHO = Path(__file__).resolve().parent / "vagas_sinteticas.csv"


def main():
    linhas = []
    for pid, fator, titulo, a, b in PARES:
        assert len(a) <= 300 and len(b) <= 300, pid
        primeira_metade = int(pid[1:]) <= 4
        for lado, desc, veredito in (("a", a, "aplicar"), ("b", b, "não aplicar")):
            execucao = 1 if (lado == "a") == primeira_metade else 2
            linhas.append(
                {
                    "titulo": titulo,
                    "link": f"https://vagas-ficticias.example/{pid}-{lado}",
                    "descricao": desc,
                    "veredito_esperado": veredito,
                    "par_id": pid,
                    "fator_variado": fator,
                    "execucao": execucao,
                }
            )
    random.Random(42).shuffle(linhas)
    linhas.sort(key=lambda linha: linha["execucao"])  # estável: mantém o embaralhamento
    with open(CAMINHO, "w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=COLUNAS)
        escritor.writeheader()
        escritor.writerows(linhas)
    print(f"{len(linhas)} vagas sintéticas em {CAMINHO}")


if __name__ == "__main__":
    main()
