# E09-08 — Registro do implementador (2026-10-22)

Agente 2. Este arquivo traz a evidência da implementação; a aprovação é do agente 3.

## Arquivos

- `apps/financeiro/views.py` (as dez views), `apps/financeiro/urls.py`, `config/urls.py` (inclusão em `/administracao/financeiro/`), `templates/financeiro/` (`resumo`, `movimentos`, `reserva`, `aporte`, `retirada`, `conciliacoes` e o menu `_menu`), o link "Financeiro" em `templates/administracao/painel.html` e o link do aviso `alerta_financeiro` em `apps/financeiro/alertas.py` (agora `financeiro_resumo`).
- Testes: `tests/tecnicos/test_financeiro_telas.py` (A-1 a A-13, A-14 rota a rota e A-15); o teste de link do aviso em `tests/tecnicos/test_financeiro_alertas.py` foi ajustado (abaixo).

## Andaime (exceção técnica)

Antes do Red: as dez rotas, com os nomes e as políticas de acesso (`somente_administrador` nas de leitura e `exige_reautenticacao_por_passkey` nas de ação), e as views com resposta vazia. Sem comportamento testável além da política.

## Red (arquivo inteiro, sem `-k`)

`uv run pytest tests/tecnicos/test_financeiro_telas.py -q -p no:cacheprovider` contra o andaime: **21 falharam, 13 passaram**. As falhas são asserções sobre o conteúdo e o status (a resposta vazia não traz o resumo, a mensagem nem o redirecionamento). As 13 que passaram são as que só dependem da política do andaime: o redirecionamento para a nova autenticação (A-4), a recusa a comprador, fornecedor e anônimo (A-5), a política de cada rota (A-14) e a resposta 200 das telas de leitura. Os dois ajustes de teste que apareceram no Red: o `Tela.entrar()` precisa sair da sessão antes de entrar de novo por passkey (senão o login não cria outro registro de passkey recente), e o `Client.get` com filtro leva o `pk` como texto.

O link do aviso (A-13) teve o Red à parte: o teste do E09-03 (`test_abrir_o_alerta_avisa_so_o_administrador`) foi atualizado para o link novo e falhou por `assert '/inicio/' == '/administracao/financeiro/'`; só depois o link mudou.

## Green

`views.py`, as seis telas HTML e o link novo: `test_financeiro_telas.py` + `test_financeiro_alertas.py` + `test_permissoes_politica_rotas.py`: **69 passaram**; `test_financeiro_telas.py` sozinho: **34 passed**.

## Teste antigo ajustado

`tests/tecnicos/test_financeiro_alertas.py` (E09-03), `test_abrir_o_alerta_avisa_so_o_administrador`: o link do aviso era `/inicio/` (a spec da E09-03 diz que ele passa a apontar para `financeiro_resumo` quando a tela existir; a E09-08 A-13 pede isso). Agora a asserção é `notificacao.link == "/administracao/financeiro/"`. Nenhuma outra asserção mudou.

## Decisões técnicas e pontos para o revisor

- **A-3 e o valor com separador de milhar.** O critério A-3 diz "`POST` com `1.000,00`", enquanto o texto das regras (e o A-10) recusam separador de milhar (`1.000`, `1.000,00` não passam em `ler_decimal_digitado`). Li o A-3 como o valor de R$ 1.000,00, digitado `1000,00`; o teste usa `1000,00` e o A-10 cobre `1.000`. **Peço ao especificador que confirme** (ou corrija a redação do A-3).
- **400 e 409.** Entrada inválida (valor, identificação ou justificativa ausentes) responde 400; recusa do serviço (reserva insuficiente, liberado insuficiente, depósito repetido, designação encerrada, cobertura acima do pendente, invariante violado) responde 409, sempre sem escrita.
- **Onde a recusa aparece.** A recusa das ações do resumo (designar, cobrir) volta a página do resumo com a mensagem; a de desfazer volta a da reserva; a do aporte e a da retirada voltam o próprio formulário, com os valores digitados.
- **Mensagens com os valores.** "O valor passa do saldo livre da reserva (R$ 20,00)." e "Só R$ 0,00 da receita desta rodada estão liberados no provedor." são montadas na view com o estado atual (leitura depois da recusa), e não copiadas do texto da exceção.
- **Sem passkey recente.** As rotas de ação redirecionam para `mfa_reauthenticate_webauthn` com `next` (política `exige_reautenticacao_por_passkey` da E02-03); o `POST` não é reaplicado depois da nova autenticação (o formulário volta em branco), como nas outras telas do administrador.
- **Resumo.** Os blocos seguem a tabela da spec; as linhas de custódia, frete e receita citam rodada e ciclo (não o nome do fornecedor), e só a obrigação com fornecedor traz o nome dele.
- **Escala.** O resumo percorre todas as contas, obrigações e despesas, sem paginação (as listas desta etapa são pequenas); os movimentos paginam de 50 em 50. Candidata a melhoria na revisão final (M-5 abaixo).
- **Sem concorrência nova.** A fatia não acrescenta travas: o duplo clique no aporte é barrado pela identificação única (A-15), que é a proteção da E09-05.

## Verificação

Os arquivos da fatia: **69 passed**. A suíte completa e as verificações estáticas estão na verificação final da E09, abaixo.

## Verificação final da E09 (2026-10-22)

Suíte completa, sem filtro e sem `--deselect`, no HEAD da E09-08: `uv run pytest -q -p no:cacheprovider` → **2398 passed in 230.76s**. `uv run ruff check .` limpo; `uv run ruff format --check .` (328 arquivos) limpo; `uv run mypy .` (391 arquivos) sem erros; `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test` sem mudanças. Antes da E09 eram 2160 testes (E08 reaprovada); a E09 acrescentou 238.

### Resumo por fatia

| Fatia | Registro | Commit |
|---|---|---|
| E09-01 | `docs/specs/E09-01/review.md` | `cbe5ae3`, `301dfd5` |
| E09-02 | `docs/specs/E09-02/review.md` | `aa65a6a` |
| E09-03 | `docs/specs/E09-03/review.md` | `7f8b0af` |
| E09-04 | `docs/specs/E09-04/review.md` | `cc6b944` |
| E09-05 | `docs/specs/E09-05/review.md` | `ec52e1b` |
| E09-06 | `docs/specs/E09-06/review.md` | `917f375` |
| E09-07 | `docs/specs/E09-07/review.md` | `3f7e6e7` |
| E09-08 | este arquivo | o commit que contém este registro |

### Desvios e pendências para o revisor e o especificador

- **E09-06, concorrência sem Red próprio.** Escrevi as travas junto com as operações; a prova é por mutação (A-17 e A-18 detectadas; A-19 não, M-6). Registrado na E09-06.
- **E09-06, `deficit_coberto`.** Implementei só a parcela das despesas de déficit; a segunda parcela da spec ("coberturas do componente frete sem cobertura das obrigações") não tem como ser atribuída por componente. **Pendência de especificação** registrada na E09-06.
- **E09-08, A-3.** O critério diz `1.000,00`, que as próprias regras recusam; li como R$ 1.000,00 digitado `1000,00`. **Pedido de confirmação** registrado acima.
- **Sem Red em `extrato` (E09-01) e A-12 da E09-04 e A-20 da E09-07** como critérios de concorrência: provas por mutação, registradas em cada fatia.
- **Melhorias novas:** M-5, M-6 e M-7 em `docs/melhorias.md`. A M-4 (já registrada pelo revisor da E08) continua para a revisão final.
- **Fora do escopo, como manda a spec:** o estorno e os movimentos de devolução no provedor (E10), a apuração real e a regra de quando acontece (E11), o repasse e o pagamento do frete pelo fluxo real (E13), o painel consolidado (E15). Mercado Pago real (fase 2a) não foi tocado; as limitações L-8 a L-11 seguem abertas.

