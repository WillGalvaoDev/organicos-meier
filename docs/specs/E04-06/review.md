# E04-06 — Registro do implementador (aguardando revisão independente)

Parecer atual do revisor: **APROVADO** sobre `8b4e771` (2026-10-18). E04 global: **APROVADO**. Histórico preservado abaixo.

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia e a E04-01 a E04-04.

## Arquivos

- `apps/notificacoes/models.py` (`Comunicado`, `RegistroSoInsercao`), migração `0005_comunicado` (com a trigger de só inserção da E01-04).
- `apps/notificacoes/comunicados.py` (`publicar_comunicado`, `compradores_do_comunicado`), `forms.py` (`FormularioComunicado`), `views.py` (`comunicados_administracao`, `comunicados`), `config/urls.py`.
- `templates/notificacoes/comunicados_administracao.html` e `comunicados.html`; `templates/inicio.html` (link "Comunicados").
- `tests/fabricas.py` (`ComunicadoFactory`); testes em `test_comunicados_servico.py`, `test_comunicados_telas.py` (novos) e `test_notificacoes_concorrencia.py`.

## Decisões técnicas

- Destinatários: compradores `ativa` e `suspensa` no momento da publicação, em ordem de `pk` (decisão da spec). Contas removidas, de fornecedor e o administrador ficam fora.
- Publicação: tudo numa `transaction.atomic()`. O token é conferido antes; o `INSERT` do comunicado fica num *savepoint* e um `IntegrityError` da `UNIQUE` vira `(existente, False)`, de modo que a segunda requisição simultânea espera a primeira e não emite nada. `destinatarios` é a contagem da seleção, gravada já no `INSERT`; se `emitir_evento_para_varios` devolver outro número, `RuntimeError` desfaz tudo.
- Histórico: a contagem de envios por canal e situação vem de uma única consulta agregada (`substring` da chave com `^comunicado:(\d+):`), então o número de consultas não depende do número de comunicados (A-12).
- Singular: a mensagem e o aviso "Será enviado para…" usam "1 comprador" no singular. A spec escreve só o plural ("<n> compradores"); a concordância com 1 é um detalhe de texto, sem efeito de regra.
- O aviso de token repetido usa `messages.info`; o de sucesso, `messages.success`. Ambos aparecem no `base.html`.
- A auditoria `comunicado.publicar` leva só os ids e a contagem, nunca título nem mensagem.

## TDD

**Red.** Andaime (`Comunicado` sem trigger, `publicar_comunicado` devolvendo objeto não gravado, views com corpo vazio): `uv run pytest tests/tecnicos/test_comunicados_servico.py tests/tecnicos/test_comunicados_telas.py tests/tecnicos/test_notificacoes_concorrencia.py -q` deu **21 failed, 6 passed**, por asserção (nada gravado ou distribuído, nenhuma `ValidationError`/`PermissionDenied`, telas vazias). Passaram já no Red os testes de política (a decoração das views existia no andaime) e os da E04-01 a E04-05.

**Green.** Mesmos arquivos: **27 passed**. Suíte completa: **1368 passed**. `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.

Ajustes de teste feitos antes do Red final, por erro meu de escrita: duas asserções frouxas demais (regex de erro de campo e contagem de destinatários) foram trocadas por verificações exatas (`"Este campo é obrigatório."` e `<td>3</td>`).

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1, A-2, A-4, A-5, A-13, A-14 | `test_comunicados_servico.py` |
| A-3 | `test_notificacoes_concorrencia.py::test_duas_publicacoes_com_o_mesmo_token_publicam_uma_so` |
| A-6 a A-12 | `test_comunicados_telas.py` |
| A-15 | `test_permissoes_politica_rotas.py` (varredura existente; `administrador` na tela administrativa e `comprador` em `/comunicados/`) |

## Limites da verificação

Cliente HTTP do Django; sem navegador. O WhatsApp e o e-mail usam o simulador e os backends de teste.


## Revisão independente — 0b52010 — 2026-10-17

**Parecer da fatia: APROVADO. E04 global: REPROVADO.**

A-1 a A-15 conferidos e verdes: destinatários, exclusões, imutabilidade, token único, concorrência, auditoria, validação, autorização, histórico sem N+1, comprador novo e zero destinatários. O link emitido é a constante interna /comunicados/. Sem achado próprio.

Verificação independente: **1385 passed em 160,23 s** na suíte completa. Probes adicionais: **10 failed, 4 passed em 4,39 s**, mais **1 passed em 2,52 s** no caso de isolamento acrescentado. Dez falhas correspondem a R01 (oito) e R02 (duas). Lint, formatação, tipos, Django e CI passaram.

Comandos, matriz, reproduções, TDD, critérios de correção e limites no [parecer consolidado E04-07](../E04-07/review.md). Nenhum código ou teste versionado foi alterado pelo revisor.


## Revalidação independente — 8b4e771 — 2026-10-18

**Parecer da fatia: APROVADO. E04 global: APROVADO.**

Aprovação mantida. Publicação, distribuição, permissões, concorrência, idempotência, histórico e consultas cobertos pela suíte integral. Sem alteração de implementação nesta correção.

Suíte completa: **1461 passed em 137,79 s**. Script independente original da revisão de 0b52010, sem alterações: **15 passed em 6,78 s**. As dez falhas anteriores não se reproduzem. Lint, formatação, tipos, verificações Django e CI passaram. Evidências e limites no [parecer consolidado](../E04-07/review.md), seção deste SHA.
