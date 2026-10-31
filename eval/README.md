# Conjunto de avaliação

Vagas reais do We Work Remotely usadas para avaliar o agente de triagem contra os
critérios de `criterios_eval.txt` (mais abertos que os critérios pessoais, para o
conjunto ter vagas dos dois tipos).

## Coleta

- **Data:** 2026-10-31
- **Feeds** (`https://weworkremotely.com/categories/<feed>.rss`):
  - `remote-programming-jobs` — 25 itens
  - `remote-back-end-programming-jobs` — 9 itens
  - `remote-full-stack-programming-jobs` — 79 itens
- **Vagas distintas** (sem duplicatas, pelo link): 88. Como passou de 30, o feed
  `remote-devops-sysadmin-jobs` não foi usado.
- **Selecionadas:** 40, com a semente 42. A seleção embaralha as vagas, pega até 20 que
  mencionem termos do tema (python, django, fastapi, flask, data, machine learning, ai/ml)
  e completa com as demais, para o conjunto ter uma mistura. Essas palavras só ajudam a
  montar a mistura; o rótulo de cada vaga é feito à mão.
- **Descrição:** a mesma que o agente vê: HTML removido e corte em 300 caracteres
  (`_limpar_html` e `_truncar` de `src/triagem/feed.py`).

## Vagas extras

Depois de rotular as 40 primeiras, só 3 tinham ficado como "aplicar" (e, na revisão, nenhuma),
pouco para avaliar. Foram acrescentadas vagas extras, com a coleta refeita em 2026-10-31
(os feeds já tinham mudado um pouco: 93 vagas distintas em vez de 88; programação 25,
back-end 11, full-stack 82):

- Partindo das vagas distintas dos três feeds, tiraram-se as 40 já no `vagas.csv`
  (sobraram 54), sem repetir nenhuma.
- Cada vaga restante recebe pontos pelos termos python, django, fastapi, flask, data,
  machine learning, ai, junior, mid e entry (palavra inteira, sem diferenciar maiúsculas):
  2 pontos por termo no título e 1 por termo na descrição de 300 caracteres.
- Entram até 20 vagas com ao menos 1 ponto, das mais pontuadas para as menos (empate: ordem do
  feed). Só 19 atingiram o mínimo, então entraram 19 (números 41 a 59).
- A ordem é embaralhada (semente 42) para a numeração não revelar a pontuação.
- A descrição segue o corte de 300 caracteres e a limpeza de HTML de `src/triagem/feed.py`.
- `veredito_esperado` fica vazio até a rotulagem.

Os feeds mudam todos os dias, então rodar `python eval/coletar.py` de novo gera outro
conjunto. Para comparar execuções, use sempre o mesmo `vagas.csv`.

## Arquivos

- `coletar.py` — coleta os feeds e gera `vagas.csv` e `rotular.md` (recusa rodar se o `vagas.csv` já existir, para não perder rótulos).
- `coletar_extra.py` — acrescenta as vagas extras ao `vagas.csv` e gera `rotular_extra.md`.
- `criterios_eval.txt` — critérios de avaliação, no formato que `gerar_resumo_criterios` produz.
- `vagas.csv` — `titulo`, `link`, `descricao` e `veredito_esperado` (`aplicar` / `não aplicar`).
- `rotular.md` — tabela para rotular as vagas 1 a 40 à mão (`A` ou `N`).
- `rotular_extra.md` — mesma tabela para as vagas extras (41 em diante).
