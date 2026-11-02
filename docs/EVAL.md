# Avaliação do agente de triagem

Esta avaliação mede se o agente (Gemini com function calling, `gemini-flash-latest`) decide
"aplicar" / "não aplicar" de acordo com um conjunto fixo de critérios. Ela tem duas partes:
**vagas reais** (80 vagas rotuladas à mão) e um **controle sintético** (16 vagas fictícias em
pares de contraste). Os dados e scripts estão em `eval/`; o prompt e o código do agente **não
foram alterados** para esta avaliação.

**Critérios usados** (`eval/criterios_eval.txt`, mais abertos que os critérios pessoais, para o
conjunto poder ter vagas dos dois tipos): nível júnior ou pleno; Python no backend (Django,
FastAPI ou Flask) ou dados/IA com Python; inglês intermediário ou avançado aceitável; remoto
aceitando candidatos que morem fora dos EUA.

**Resumo.** Nas reais, o agente descartou corretamente 73 das 79 vagas "não aplicar" (92,4%) e
aprovou a única vaga "aplicar". Os 6 falsos positivos são todos vagas de IA/ML ou automação, e
nenhum menciona Python no texto que o agente recebe. O controle sintético confirma a causa: o
agente acertou os pares de nível, local, stack e modelo de trabalho, e errou os dois pares em
que só a menção a Python muda (0 de 2).

## Como a avaliação roda

`eval/avaliar.py` executa o agente de verdade (system prompt, ferramentas, validação com
pydantic e loop de `src/triagem/`). A única diferença é a fonte das vagas: no lugar de baixar o
feed, `buscar_vagas_wwr` devolve as vagas do CSV, em lotes de 15, com o texto exato que o agente
veria (título + descrição de 300 caracteres, mesma limpeza de HTML). Cada decisão é comparada
com o `veredito_esperado`. Em caso de erro 503/429 da API, o script tenta de novo e, se
desistir, marca as vagas como "sem decisão"; `--retomar` reaproveita as decisões já gravadas.

---

## Parte 1 — Vagas reais (80 vagas)

### Como foi montado
- **WWR (59 vagas).** Coleta de 2026-10-31 nos feeds de programação, back-end e full-stack do
  We Work Remotely (88 vagas distintas). 40 foram escolhidas com semente fixa, misturando vagas
  com termos do tema (python, django, data, machine learning, ai) e outras. Como só 3 haviam
  sido rotuladas "aplicar" (e, na revisão, nenhuma), acrescentaram-se 19 vagas extras, as de
  maior pontuação por termos como python, django, fastapi, flask, data, machine learning, ai,
  junior, mid e entry.
- **backend-br (21 vagas).** Issues abertas do repositório `backend-br/vagas` com "python" no
  título ou nos labels, coletadas em 2026-10-31. O repositório tinha 45 issues abertas; 21
  passaram no filtro, então não houve corte por limite.
- Todas usam o corte de 300 caracteres e a limpeza de `src/triagem/feed.py`. O corpo das issues
  é markdown, que a limpeza não converte.

### Rotulagem manual
Os rótulos são de uma pessoa só, feitos lendo apenas o texto que o agente recebe (`rotular*.md`,
sem resumo nem sugestão de veredito). No WWR, três vagas inicialmente marcadas "aplicar" foram
reclassificadas para "não aplicar" por pedirem nível sênior/staff; as 19 extras ficaram todas
"não aplicar".

### Desbalanceamento e o motivo
O conjunto real tem **1 "aplicar" e 79 "não aplicar"**. Isso é um achado sobre as fontes, não
só um defeito da amostra: neste dia, os feeds do WWR trazem quase nenhuma vaga júnior/pleno de
Python aberta a quem mora fora dos EUA, e as issues do backend-br com Python são em maioria
sênior. Mesmo reforçando a seleção das 19 extras com termos do tema, nenhuma foi rotulada
"aplicar". É um retrato de um único dia; outro dia pode dar outro resultado.

### Resultados

| Fonte | No conjunto | Avaliadas | Esperado aplicar / não | Especificidade | Falsos positivos |
|---|---|---|---|---|---|
| WWR | 59 | 59 | 0 / 59 | 54/59 = 91,5% | 5 |
| backend-br | 21 | 21 | 1 / 20 | 19/20 = 95,0% | 1 |
| **Somadas** | **80** | **80** | **1 / 79** | **73/79 = 92,4%** | **6** |

Nenhuma vaga ficou sem decisão. As decisões do WWR vêm de duas execuções (45 vagas e depois as
14 restantes, depois de a cota da API esgotar).

**Falsos positivos (agente disse "aplicar", esperado "não aplicar") e o motivo dado:**

1. *Toptal: AI Engineer - Agentic Systems* — "Vaga remota global para engenharia de inteligência
   artificial de nível pleno, perfeitamente compatível com os critérios." O texto pede "a proven
   track record of shipping agentic AI systems into production".
2. *Jumio: Machine Learning Engineer* — "Vaga de Inteligência Artificial/Machine Learning fora
   dos EUA compatível com nível pleno." O texto pede "deep expertise" e "lead the design and
   scaling".
3. *Welocalize: Automation Specialist* — "Posição de automação e IA fora dos EUA e adequada
   para nível pleno ou júnior." Sem indicação de nível no texto.
4. *Ritual: Developer Experience Engineer* — "Vaga remota global de IA e ferramentas para
   desenvolvedores compatível com nível pleno." Sem indicação de nível no texto.
5. *Sticker Mule: Software engineer* — "Vaga remota global de engenharia de software com IA sem
   restrição de senioridade avançada, sendo potencialmente aplicável a nível pleno." Sem
   indicação de nível no texto.
6. *[backend-br] Forward Deployed Engineer, Gen AI, Google Cloud, na Google* — "Vaga remota no
   Brasil focada em IA generativa, compatível com nível pleno e localizada fora dos EUA." Sem
   indicação de nível nos 300 caracteres.

**A vaga 76** (*[Remoto] Desenvolvedor(a) Full Stack Pleno (Python / TypeScript / IA) na
Ártemis*), a única "aplicar" do conjunto real: o agente respondeu **aplicar** ("Vaga 100% remota,
de nível pleno, envolvendo Python e IA, totalmente alinhada aos critérios"). Com um único
positivo, isso equivale a recall de 1/1, o que não diz nada sobre a taxa de acerto geral. A
precisão de "aplicar" nas reais é 1/7 (14,3%), também puxada pelos 6 falsos positivos acima.

### Padrões de erro nas vagas reais
1. **O agente não exige Python.** Nos 6 falsos positivos, o texto recebido não menciona Python.
   Os critérios pedem "dados/IA com Python", mas o agente aceita qualquer vaga de IA/ML ou
   automação como compatível. É o padrão dominante (6 de 6).
2. **O nível é inferido como "pleno" mesmo sem evidência, ou contra ela.** Em 2 dos 6 (Toptal,
   Jumio), o texto traz sinais de experiência avançada ("proven track record", "deep expertise",
   "lead") e o agente ainda assim escreveu "nível pleno". Nos outros 4, o texto não diz o nível, e
   o agente assumiu "pleno" (ou "pleno ou júnior") em vez de tratar como incerto.
3. **O local é bem tratado.** Nenhum falso positivo é por restrição geográfica.

---

## Parte 2 — Controle sintético (16 vagas)

### Como foi montado
Como as reais têm um único positivo, não dá para medir precisão e recall. O conjunto sintético
(`eval/vagas_sinteticas.csv`, gerado por `eval/gerar_sinteticas.py`) tem 16 vagas fictícias,
curtas, em inglês e português, de empresas inventadas, organizadas em **8 pares de contraste**.
As duas vagas de um par são iguais exceto por um único fator, e o `veredito_esperado` sai por
construção (lado A atende aos critérios = "aplicar"; lado B não = "não aplicar"):

| Par | Fator variado |
|---|---|
| p1 | nível: pleno vs "proven track record" |
| p2 | nível: pleno vs Staff/Senior explícito |
| p3 | Python explícito vs omitido (IA/ML, inglês) |
| p4 | Python explícito vs omitido (dados/IA, português) |
| p5 | local: remoto global vs só EUA (inglês) |
| p6 | local: remoto global vs só EUA (português) |
| p7 | stack: Django vs Java |
| p8 | modelo de trabalho: 100% remoto (Brasil) vs híbrido em São Paulo |

**Leitura estrita de "dados/IA com Python".** Nos pares p3 e p4, o lado B não menciona a
linguagem e é rotulado "não aplicar": sem menção a Python, a vaga não satisfaz o critério. Uma
leitura mais branda trataria o caso como indefinido; o conjunto adota a estrita, e é nela que se
baseia a conclusão abaixo.

**Execuções sem par junto.** Com lotes grandes, os dois lados de um par poderiam cair juntos e o
agente veria o contraste. Por isso o conjunto roda em duas execuções de 8 vagas (4 "aplicar" e
4 "não aplicar" cada): execução 1 = lado A de p1–p4 + lado B de p5–p8; execução 2 = lado B de
p1–p4 + lado A de p5–p8. Nenhum par aparece inteiro numa execução. (Na prática, a execução 2 foi
retomada com `--retomar` depois de uma requisição travar sem resposta; a execução 1 não foi
refeita.)

### Resultados
Matriz de confusão (linhas = esperado, colunas = agente):

| | Agente: aplicar | Agente: não aplicar |
|---|---|---|
| **Esperado: aplicar** | 8 (VP) | 0 (FN) |
| **Esperado: não aplicar** | 2 (FP) | 6 (VN) |

- Precisão de "aplicar": 8/10 = **80,0%**
- Recall de "aplicar": 8/8 = **100,0%**
- Especificidade: 6/8 = 75,0% · acurácia: 14/16 = 87,5%
- **Pares com os dois lados certos: 6 de 8.**

### Análise por fator variado

| Fator | Pares | Os dois lados certos | Observação |
|---|---|---|---|
| Nível | p1, p2 | 2 de 2 | Distinguiu pleno de "proven track record" (p1) e de Staff/Senior (p2). |
| Python | p3, p4 | **0 de 2** | O lado B (sem Python) foi aprovado nos dois pares. |
| Local | p5, p6 | 2 de 2 | Rejeitou "só EUA" em inglês e em português. |
| Stack | p7 | 1 de 1 | Rejeitou Java e aceitou Django. |
| Modelo de trabalho | p8 | 1 de 1 | Rejeitou o híbrido em São Paulo e aceitou o 100% remoto. |

Os dois erros foram os lados B de p3 e p4. Motivos dados pelo agente: "Posição remota mundial de
nível pleno focada em Machine Learning/IA com inglês intermediário" (p3) e "Vaga remota mundial de
nível pleno para dados e inteligência artificial com inglês intermediário" (p4). Em nenhum
aparece Python.

---

## O que as duas partes mostram juntas
- O erro mais consistente é **não exigir Python em vagas de IA/ML/dados**: 6 de 6 falsos
  positivos reais e 2 de 2 do controle sintético, em que Python é o único fator que muda.
- O controle sintético mostra que, quando o nível está **explícito** (p1, p2), o agente o
  respeita. Nas reais, o problema de nível aparece quando o texto é vago ou só sugere
  senioridade ("proven track record" em p1 foi bem tratado no sintético, onde o texto é curto e
  limpo; nas reais, o mesmo tipo de frase passou).

## Limitações
- **Poucos positivos.** Nas reais há 1 "aplicar" em 80; recall e precisão de "aplicar" nas reais
  não são informativos. A especificidade (92,4%) é o único número estável, e ainda assim com
  6 erros.
- **Uma só execução por conjunto.** O modelo não é determinístico e `gemini-flash-latest` é um
  alias que pode mudar de versão; os números podem variar em outra rodada.
- **Um só rotulador**, sem medir concordância entre pessoas. Nos falsos positivos 3 a 6, o texto
  de 300 caracteres não informa o nível, mas também não menciona Python; pela leitura estrita do
  critério "dados/IA com Python", o rótulo "não aplicar" se sustenta independentemente do nível.
- **Só 300 caracteres.** O agente decide com um trecho curto; a vaga completa poderia mudar
  tanto o rótulo quanto a decisão.
- **Retrato de um dia e de duas fontes.** Os feeds mudam; as 80 reais não representam o mercado.
- **O sintético é limpo demais.** Os pares são curtos e sem ruído, então mostram se o agente
  reage a cada fator isolado, mas superestimam o desempenho em textos reais.
- **Execuções interrompidas.** Parte das decisões vem de execuções retomadas depois de erros
  503/429 e de uma requisição travada.

## Próximo passo
Fazer o agente **checar o nível e o Python de forma explícita antes de decidir**: por exemplo,
extrair da vaga, em campos estruturados, o nível pedido (com a evidência no texto) e se Python
é mencionado, tratando "não informado" como incerto, e só então aplicar os critérios. Depois,
rodar de novo os mesmos três conjuntos e comparar: o alvo é reduzir os falsos positivos reais
(hoje 6) e acertar p3 e p4, sem perder os pares que já passam. Nada disso foi implementado
ainda: o prompt do agente continua o mesmo desta avaliação.

## Como reproduzir
```
python eval/avaliar.py                                   # WWR -> eval/resultados_wwr.csv
python eval/avaliar.py eval/vagas_backendbr.csv eval/resultados_backendbr.csv
python eval/avaliar.py eval/vagas_sinteticas.csv eval/resultados_sinteticas.csv
```
Use `--retomar` para continuar uma execução interrompida. Os feeds mudam todo dia, então
`eval/coletar.py` gera outro conjunto; para comparar execuções, use sempre os mesmos CSVs.
