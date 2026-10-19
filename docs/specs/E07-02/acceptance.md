# E07-02 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). Valem as regras de prevenção das correções E05-R04 (E05-01) e E06-R05 (E06-05). Os critérios de carregamento usam subprocesso, como `tests/tecnicos/test_configuracao_producao.py`, com `_AMBIENTE_MINIMO` mais as variáveis indicadas.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Cenário 38, T-12 | negativo | `AMBIENTE=producao`, `PROVEDOR_PAGAMENTOS=simulador` | carrego `config.settings.prod` em subprocesso | código de saída diferente de zero; o erro é `ImproperlyConfigured` com "O simulador de pagamentos não pode ser usado em produção."; o `stderr` não contém `SECRET_KEY` nem o segredo |
| A-2 | Cenário 38, T-12 | negativo | `AMBIENTE=producao`, sem `PROVEDOR_PAGAMENTOS` | o mesmo | a mesma recusa |
| A-3 | T-12 | negativo | o ambiente do A-1, com `DJANGO_SETTINGS_MODULE=config.settings.prod` | `python manage.py check` e `python manage.py procrastinate worker --help` em subprocesso | os dois saem com código diferente de zero e a mesma mensagem; nenhum dos dois chega a executar o comando |
| A-4 | Spec da fatia | positivo | `AMBIENTE=homologacao`, `PROVEDOR_PAGAMENTOS=simulador`, `SEGREDO_AVISOS_SIMULADOR` definido | carrego `config.settings.prod` | código zero; `AMBIENTE` `homologacao`; `PROVEDOR_PAGAMENTOS` `simulador` |
| A-5 | Spec da fatia | negativo | `prod.py` sem `AMBIENTE`; com `AMBIENTE=teste`; com `AMBIENTE=Producao` | carrego | código diferente de zero, com "AMBIENTE deve ser 'homologacao' ou 'producao'." |
| A-6 | Spec da fatia | negativo | `PROVEDOR_PAGAMENTOS` igual a `mercado_pago`, `Simulador` e `" simulador "` | carrego `config.settings.dev` e `config.settings.prod` (homologação) | código diferente de zero em todos |
| A-7 | Spec da fatia | negativo | `AMBIENTE=homologacao` com o simulador, sem `SEGREDO_AVISOS_SIMULADOR` | carrego `config.settings.prod` | código diferente de zero |
| A-8 | Spec da fatia | positivo | — | carrego `config.settings.dev` e `config.settings.test` | `AMBIENTE` `desenvolvimento` e `testes`; `PROVEDOR_PAGAMENTOS` `simulador`; `SEGREDO_AVISOS_SIMULADOR` não vazio |
| A-9 | Infra 4.1 | negativo | os testes, com `override_settings(AMBIENTE="producao")` | `obter_provedor()` | `ImproperlyConfigured` com a mesma mensagem; com `AMBIENTE="homologacao"`, devolve o simulador |
| A-10 | Spec da fatia | positivo | — | rodo `tests/tecnicos/test_configuracao_producao.py` e `tests/tecnicos/test_nucleo_campos_decimais.py` com os ajustes autorizados; depois a suíte inteira | verde; o diff dos dois arquivos mostra só as duas variáveis acrescentadas, registradas no `review.md` |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-8 | `tests/tecnicos/test_configuracao_pagamentos.py` |
| A-1 | também marcado `acceptance`, com o comentário `cenário 38` |
| A-9 | `tests/tecnicos/test_pagamentos_simulador.py` |
| A-10 | `tests/tecnicos/test_configuracao_producao.py` e `tests/tecnicos/test_nucleo_campos_decimais.py` (arquivos existentes) |
