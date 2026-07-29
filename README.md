# Agente de Triagem de Vagas Remotas

Agente Python que usa a API do Google Gemini (SDK `google-genai`) com
function calling para buscar e triar vagas de emprego remotas no feed RSS de
programação do [We Work Remotely](https://weworkremotely.com/).

> A API pública do Remote OK foi descartada como fonte de dados: ela passou a
> servir um conjunto de vagas genérico/limitado (aparentemente uma medida
> anti-scraping), não o board real — resultando em pouquíssimos resultados
> para termos como "python" ou "backend" mesmo com o filtro correto.

## O que ele faz

1. **Critérios de triagem (só na primeira vez, ou quando você quiser refazer):**
   o agente faz 4 perguntas objetivas — nível da vaga, tecnologias/stack de
   interesse, inglês exigido aceitável e modelo de trabalho — usa o Gemini
   para transformar as respostas em um texto corrido e salva em
   `criterios.txt`. Se esse arquivo já existir, ele pergunta se você quer
   reutilizá-lo ou responder de novo. Esse texto é o que vira o system
   prompt/instrução usada na avaliação de cada vaga (item 4).
2. Você informa um termo de busca (ex: `python`, `qa`, `django`).
3. O modelo chama a função `buscar_vagas_wwr`, que faz o parsing do feed RSS
   `https://weworkremotely.com/categories/remote-programming-jobs.rss` e
   retorna até 15 vagas em que o termo apareça (case-insensitive) no título,
   nas tags/categoria ou na descrição (título, link e descrição resumida).
4. Para cada vaga retornada, o modelo decide se vale a pena aplicar, usando
   os critérios definidos no passo 1.
5. O modelo chama `avaliar_vaga` para registrar cada decisão (título, link,
   veredito `"aplicar"`/`"não aplicar"` e motivo curto). Essa função **não**
   decide nada — apenas formata e registra em JSON a decisão que o modelo já
   tomou.
6. No final, o resultado é exibido: resumo com as vagas recomendadas e as
   descartadas.

Há duas formas de usar o agente: pelo terminal (`main.py`) ou por uma
interface web (`app.py`, com Streamlit) — ambas reaproveitam exatamente as
mesmas funções de busca, avaliação e critérios.

## Como rodar

1. Crie e ative um ambiente virtual (opcional, mas recomendado):

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure sua chave de API:

   ```bash
   cp .env.example .env
   # edite .env e preencha GEMINI_API_KEY=sua-chave-aqui
   ```

   Obtenha uma chave em https://aistudio.google.com/apikey.

4. Rode pelo terminal:

   ```bash
   python main.py python
   ```

   Na primeira execução (ou se `criterios.txt` não existir), o agente
   pergunta os critérios de triagem antes de pedir o termo de busca. Sem
   argumento, o termo de busca também é pedido interativamente:

   ```bash
   python main.py
   ```

   Ou rode a interface web:

   ```bash
   streamlit run app.py
   ```

   Na interface web, defina e salve os critérios na barra lateral (formulário
   com campos de texto e seleção), depois digite o termo e clique em
   "Buscar vagas". Os resultados aparecem como cards (verde para vagas
   recomendadas, vermelho para descartadas), com um resumo (total de vagas e
   quantas foram recomendadas) no topo.

## Estrutura

- `main.py` — critérios de triagem (perguntas, formatação via Gemini,
  leitura/escrita de `criterios.txt`), busca no We Work Remotely, avaliação
  via function calling e o loop de conversa (`rodar_triagem`); tudo isso é
  reaproveitado por `app.py`. Rodado diretamente, também expõe a interface
  de linha de comando.
- `app.py` — interface web em Streamlit; importa `main.py` e não duplica
  nenhuma lógica de busca/avaliação/critérios, só cuida do formulário,
  spinner e cards.
- `criterios.txt` — gerado pelo agente na primeira execução (não versionado
  no git); contém o texto de critérios usado no system prompt.
- `requirements.txt` — dependências (`google-genai`, `requests`,
  `python-dotenv`, `feedparser`, `streamlit`).
- `.env.example` — modelo de variável de ambiente (`GEMINI_API_KEY`).

## Tratamento de erros

O script trata: chave de API ausente, falhas de conexão com a API do
Gemini ou com o feed RSS do We Work Remotely, respostas vazias/bloqueadas
por segurança, XML inválido do feed e erros ao executar as funções
(reportados de volta ao modelo como resultado de erro).

## Limitação conhecida

O feed RSS de programação do We Work Remotely traz apenas as ~25 vagas mais
recentes da categoria. Mesmo buscando o termo no título, nas tags e na
descrição, para termos muito específicos ainda é possível obter poucos ou
nenhum resultado — isso reflete o conteúdo real (e o tamanho) do feed, não
um bug no filtro.
