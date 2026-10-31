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

Os feeds mudam todos os dias, então rodar `python eval/coletar.py` de novo gera outro
conjunto. Para comparar execuções, use sempre o mesmo `vagas.csv`.

## Arquivos

- `coletar.py` — coleta os feeds e gera `vagas.csv` e `rotular.md`.
- `criterios_eval.txt` — critérios de avaliação, no formato que `gerar_resumo_criterios` produz.
- `vagas.csv` — `titulo`, `link`, `descricao` e `veredito_esperado` (`aplicar` / `não aplicar`).
- `rotular.md` — tabela para rotular as vagas à mão (`A` ou `N`).
