# Guia de uso e instalação

Este guia reúne o que é preciso para rodar o agente de triagem de vagas. Para o contexto do
projeto e os resultados da avaliação, veja o [README](../README.md) e o [EVAL.md](EVAL.md).

## O que o agente faz

1. **Critérios de triagem (só na primeira vez, ou quando você quiser refazer).** O agente faz 4
   perguntas objetivas: nível da vaga, tecnologias/stack de interesse, inglês exigido aceitável e
   modelo de trabalho. O Gemini transforma as respostas em um texto corrido, salvo em
   `criterios.txt`. Se o arquivo já existir, o agente pergunta se você quer reutilizá-lo. Esse
   texto entra no system prompt usado na avaliação de cada vaga.
2. Você informa um termo de busca (por exemplo `python`, `qa`, `django`).
3. O modelo chama `buscar_vagas_wwr`, que lê o feed RSS
   `https://weworkremotely.com/categories/remote-programming-jobs.rss` e devolve até 15 vagas em
   que o termo aparece (sem diferenciar maiúsculas) no título, nas tags/categoria ou na
   descrição, com título, link e descrição resumida.
4. Para cada vaga devolvida, o modelo decide se vale a pena aplicar, com base nos critérios.
5. O modelo chama `avaliar_vaga` para registrar cada decisão (título, link, veredito
   `"aplicar"` / `"não aplicar"` e motivo). A função não decide nada: valida com Pydantic a
   decisão que o modelo já tomou.
6. No final, o resultado é exibido: vagas recomendadas e descartadas.

Há duas formas de usar: pelo terminal (`main.py`) ou pela interface web (`app.py`, Streamlit).
As duas usam o mesmo código de `src/triagem/`.

## Rodar com Python

1. Crie e ative um ambiente virtual (opcional, mas recomendado):

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. Instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

3. Configure a chave da API do Gemini (crie uma em https://aistudio.google.com/apikey):

   ```bash
   cp .env.example .env
   # edite .env e preencha GEMINI_API_KEY=sua-chave-aqui
   ```

4. Rode pelo terminal:

   ```bash
   python main.py python
   ```

   Na primeira execução (ou se `criterios.txt` não existir), o agente pergunta os critérios antes
   de buscar. Sem argumento, o termo de busca também é pedido interativamente (`python main.py`).

   Ou rode a interface web:

   ```bash
   streamlit run app.py
   ```

   Na interface, defina e salve os critérios na barra lateral, digite o termo e clique em
   "Buscar vagas". Os resultados aparecem como cards (verde para recomendadas, vermelho para
   descartadas), com o total no topo.

## Rodar com Docker

A imagem contém só a interface web. A chave vem de fora da imagem:

```bash
docker build -t agente-triagem-vagas .
docker run --env-file .env -p 8501:8501 agente-triagem-vagas
```

A interface abre em http://localhost:8501. O contêiner roda como usuário não root, e o `.env` e o
`criterios.txt` não entram na imagem (`.dockerignore`).

## Testes e lint

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

Os testes não chamam a API real: o cliente do Gemini é substituído por um falso que devolve
chamadas de função pré-definidas, e o feed vem de `tests/fixtures/feed.xml`. O mesmo comando
roda no CI a cada push.

## Avaliação

Os scripts e dados da avaliação ficam em `eval/`, e o relatório em [EVAL.md](EVAL.md). Para
reproduzir, veja a seção "Como reproduzir" do relatório e o `eval/README.md`.

## Estrutura

- `main.py`: interface de linha de comando.
- `app.py`: interface web em Streamlit.
- `src/triagem/config.py`: variáveis de ambiente e constantes.
- `src/triagem/feed.py`: busca e parsing do feed RSS do We Work Remotely.
- `src/triagem/criterios.py`: perguntas, formatação via Gemini e leitura/escrita de `criterios.txt`.
- `src/triagem/modelos.py`: modelos Pydantic (`Vaga`, `Avaliacao`).
- `src/triagem/agente.py`: system prompt, declaração das ferramentas e loop de function calling
  (`rodar_triagem`).
- `tests/`: testes com pytest. `eval/`: avaliação. `docs/`: documentação.
- `criterios.txt`: gerado na primeira execução, fora do git.
- `.env.example`: modelo da variável `GEMINI_API_KEY`.

## Tratamento de erros

O agente trata chave de API ausente, falhas de conexão com a API do Gemini ou com o feed,
respostas vazias ou bloqueadas, XML inválido do feed e erros ao executar as ferramentas. Esses
últimos, e argumentos inválidos de `avaliar_vaga`, voltam ao modelo como resultado de erro de
ferramenta, sem derrubar o programa.

## Limitação conhecida

O feed RSS de programação do We Work Remotely traz apenas as cerca de 25 vagas mais recentes da
categoria. Para termos muito específicos, é possível obter poucos ou nenhum resultado: isso
reflete o tamanho do feed, não um erro no filtro. A API pública do Remote OK foi descartada como
fonte porque passou a servir um conjunto genérico e limitado de vagas.
