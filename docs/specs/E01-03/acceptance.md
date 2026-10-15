# E01-03 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com falha observada (Red). `T` é um instante fixo em UTC, por exemplo `2026-10-14T15:00:00.000000+00:00`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §15 | positivo | o relógio real | chamo `agora()` | recebo `datetime` com fuso UTC |
| A-2 | Spec §15 | positivo | o relógio congelado em `T` | chamo `agora()` | recebo exatamente `T` |
| A-3 | Spec §15 | positivo | o relógio congelado em `T` | avanço 24h e chamo `agora()` | recebo `T + 24h` |
| A-4 | Infra 4.3, T-1 | fronteira | limite `L = T + 24h` | testo `prazo_encerrado` em `L − 1 ms`, `L` e `L + 1 ms` | falso, verdadeiro, verdadeiro |
| A-5 | Infra 4.3, T-2 | fronteira | limite `L = T + 48h` | testo `ate_o_limite` em `L − 1 ms`, `L` e `L + 1 ms` | verdadeiro, verdadeiro, falso |
| A-6 | Spec §15 | positivo | `T = 2026-10-14T23:30:00-03:00` (convertido para UTC) | somo 24 horas | o resultado é `2026-10-15T23:30:00-03:00` em America/Sao_Paulo, com 24h decorridas exatas |
| A-7 | Spec §15 | positivo | um instante em UTC | converto para o fuso da operação | o fuso é America/Sao_Paulo e o instante absoluto é o mesmo |
| A-8 | Spec §15 | negativo | um `datetime` sem fuso | chamo qualquer função desta fatia | `InstanteSemFuso` |
| A-9 | Spec §15 | positivo | um instante com microssegundos | gravo em um campo `timestamptz` e releio | o valor relido é igual ao original |
| A-10 | Spec da fatia, invariantes | negativo | um arquivo de código com `datetime.now()` sem fuso | rodo o ruff | o ruff acusa a violação (`DTZ`) |

O modelo de teste de A-9 fica no app só de testes `tests/apoio` (definido na spec da E01-02). A-10 pode ser verificado por um teste que roda o ruff sobre um trecho temporário, ou registrado como evidência de configuração no `review.md`.

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-3 | `tests/tecnicos/test_nucleo_tempo.py::test_agora_*` |
| A-4, A-5 | `tests/tecnicos/test_nucleo_tempo.py::test_fronteira_*` |
| A-6 a A-8 | `tests/tecnicos/test_nucleo_tempo.py::test_fuso_*` |
| A-9 | `tests/tecnicos/test_nucleo_tempo_persistencia.py` (requer `django_db`) |
| A-10 | `tests/tecnicos/test_regras_estaticas.py::test_dtz` ou evidência no `review.md` |
