# E04-01 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **REPROVADO** sobre `0b52010` (2026-10-17). E04 global: **REPROVADO**. Registro do implementador preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia.

## Arquivos

- Novo app `apps/notificacoes`: `eventos.py` (`Evento`, `Canal`, `CANAIS_POR_EVENTO`, `DESTINATARIO_POR_EVENTO`), `models.py` (`Notificacao`, queryset que só aceita `lida_em`), `gatilhos.py` (triggers), `servicos.py` (`validar_notificacao`, `criar_notificacao`, `NotificacaoInvalida`, `marcar_como_lida`, `marcar_todas_como_lidas`), `contexto.py`, `views.py`, `templatetags/notificacoes.py`, migração `0001_inicial`.
- `templates/notificacoes/central.html` e `_item.html`; `templates/base.html` (link e contador); `config/urls.py` e `config/settings/base.py` (app e processador de contexto).
- `tests/fabricas.py` (`NotificacaoFactory`) e quatro arquivos de teste em `tests/tecnicos/` (`test_notificacoes_eventos.py`, `_modelo.py`, `_central.py`, `_concorrencia.py`).

## Decisões técnicas

- Marcar como lida é um `UPDATE ... WHERE pk, conta, lida_em IS NULL` (`marcar_como_lida`): a segunda marcação simultânea espera a linha, reavalia a condição e não grava. O resultado distingue gravou (`True`), já lida (`False`) e inexistente ou de outra conta (`None`, que vira o mesmo 404).
- A proteção na aplicação: `save()` de objeto existente só com `update_fields=["lida_em"]`; `delete()`, `QuerySet.delete()` e `bulk_update()` levantam `RegistroImutavel`; `QuerySet.update()` só aceita `lida_em`. No banco, as triggers recusam `DELETE` e qualquer `UPDATE` que não seja `lida_em` de nulo para um instante.
- O campo de `NotificacaoInvalida` para papel errado da conta é `conta`; para evento desconhecido, `evento`.
- A validação segue a spec: só tamanhos (1 a N caracteres), sem rejeitar texto só com espaços, porque a spec não o pede.
- O contador devolve `0` para anônimo, sem consulta.

## TDD

**Red.** Andaime sem comportamento (matrizes vazias, `criar_notificacao` devolvendo objeto não gravado, `marcar_*` devolvendo `None`/`0`, views com corpo vazio, sem restrições nem triggers): `uv run pytest tests/tecnicos/test_notificacoes_*.py -q` deu **43 failed, 4 passed**, todas por asserção (matriz vazia, nada gravado, banco aceitando `DELETE`/`UPDATE`/linhas inválidas, central vazia, 200 sem corpo).

**Green.** Implementação mínima. Mesmos arquivos: **47 passed**. Suíte completa: **1256 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

Ajuste de teste feito no Green, por erro meu na escrita: `test_aplicacao_aceita_marcar_so_lida_em` marcava de novo uma notificação já lida, o que a spec recusa; passou a marcar uma notificação diferente. Nenhuma garantia foi afrouxada.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_notificacoes_eventos.py` |
| A-2 a A-5 (e restrições `CHECK`) | `test_notificacoes_modelo.py` |
| A-6 a A-12 | `test_notificacoes_central.py` |
| A-13 | `test_notificacoes_concorrencia.py` (a primeira marcação segura a linha até a segunda aparecer esperando trava em `pg_stat_activity`) |
| A-14 | `test_permissoes_politica_rotas.py` (varredura existente; as três rotas declaram `autenticada`) |

## Limites da verificação

Cliente HTTP do Django, sem navegador; o atributo `hx-*` do fragmento não foi exercitado em navegador (o teste cobre o cabeçalho `HX-Request` e o fragmento devolvido).


## Revisão independente — 0b52010 — 2026-10-17

**Parecer da fatia: REPROVADO. E04 global: REPROVADO.**

A-1 a A-14 conferidos: matriz, destinatários, imutabilidade, isolamento por conta, paginação, escape, leitura idempotente e concorrência. R01 importante: a regra de link relativo aceita endereços externos disfarçados, apesar dos exemplos dos critérios passarem.

Verificação independente: **1385 passed em 160,23 s** na suíte completa. Probes adicionais: **10 failed, 4 passed em 4,39 s**, mais **1 passed em 2,52 s** no caso de isolamento acrescentado. Dez falhas correspondem a R01 (oito) e R02 (duas). Lint, formatação, tipos, Django e CI passaram.

Comandos, matriz, reproduções, TDD, critérios de correção e limites no [parecer consolidado E04-07](../E04-07/review.md). Nenhum código ou teste versionado foi alterado pelo revisor.
