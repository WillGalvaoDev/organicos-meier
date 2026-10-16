# E02-06 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** modelo `LinkDeAcesso` só com campos (migração provisória), `apps/contas/link_de_acesso.py` com `LinkInvalido`, `pedir_link` que não faz nada e `usar_link` que devolve uma conta vazia, views `pedir_link_de_acesso` e `usar_link_de_acesso` que respondem vazio e as duas rotas. Suíte antes do Red: `378 passed`.

**Red** (`uv run pytest` nos dois arquivos de teste desta fatia, com o andaime):

```
29 failed, 1 passed
```

Falhas: `assert 'Se houver uma conta para este e-mail, enviaremos um link de acesso válido por 15 minutos.' in ''` (a página padrão não existia), `IndexError` ao procurar o link na caixa de saída vazia, `'NoneType' object is not subscriptable` (sem formulário no contexto) e `DID NOT RAISE LinkInvalido`.

**Green:** `apps/contas/link_de_acesso.py` (`pedir_link`, `validar_link`, `usar_link`), views, `FormularioPedidoDeLink`, templates `contas/link_*`, `LinkDeAcesso` com restrições (migração `0003_link_de_acesso` regerada) e o link "Receber link de acesso por e-mail" em `/entrar/`.

**Refactor:** tipagem e ruff.

## Verificações (final)

```
uv run pytest -q                                  -> 408 passed em 65 s
test_contas_link_de_acesso_concorrencia.py (3 execuções seguidas) -> 1 passed em todas
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 93 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
```

## Matriz

| Critério | Teste |
|---|---|
| A-1 | `test_pedido_cria_link_e_envia_email_para_o_endereco_normalizado` |
| A-2, A-3, A-4 | `test_get_mostra_o_botao_sem_autenticar_nem_consumir`, `test_post_autentica_e_consome`, `test_link_usado_nao_autentica_de_novo` |
| A-5 | `test_fronteira_de_15_minutos` |
| A-6 | `test_email_sem_conta_tem_a_mesma_resposta_e_nao_envia` (corpo idêntico) |
| A-7, A-9 | `test_banido_ou_removido_nao_recebe_link`, `test_banimento_ou_remocao_depois_do_pedido_bloqueia_o_uso` (`acceptance` e `tecnico`; cenários 2 e 58, T-24 link) |
| A-8 | `test_administrador_nao_recebe_link` |
| A-10, A-11 | `test_suspensao_depois_do_pedido_nao_bloqueia`, `test_alias_de_email_banido_recebe_e_usa_o_link` |
| A-12 | `test_limite_de_tres_links_em_15_minutos` (+ limite por conta) |
| A-13 | `test_mesmo_link_em_paralelo_autentica_uma_vez` (20 repetições) |
| A-14 a A-17 | `test_token_alterado_e_recusado`, `test_token_so_existe_como_hash`, `test_dois_links_pendentes_..._independentes`, `test_email_mal_formado_e_erro_de_formulario` |

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **Registro do método na sessão:** antes do `perform_login`, a view chama `record_authentication(request, conta, "link")`. O `metodo_do_login` do adaptador passa a reconhecer `link` e `pre_login` aplica `verificar_acesso(..., Metodo.LINK)`: uma segunda barreira contra o administrador (já recusado em `usar_link`).
- **Janela do limite:** `criado_em > agora() − 15 min` e no máximo 3 links por conta; no instante exato de 15 min o pedido antigo sai da contagem. A conta é travada (`select_for_update`) durante o pedido, para que pedidos simultâneos não furem o limite.
- **Resposta do pedido:** a página de confirmação não tem formulário nem token CSRF, então o corpo é idêntico (byte a byte) para qualquer e-mail (A-6). E-mail mal formado devolve o formulário com erro (único caso diferente).
- **Origem do link:** `pedir_link(email, *, origem=None)`; a view passa `request.build_absolute_uri("/")` e, sem requisição, vale `ORIGEM_PUBLICA` (definida na E02-04).
- **E-mail em `transaction.on_commit`**, com falha registrada apenas por `pk` do link e nome da classe do erro (sem e-mail nem token). O corpo diz "15 minutos" e não traz horário.
- **Restrições no banco:** `link_token_unico` e `link_validade_15min` (`expira_em = criado_em + 15 min`), além de índice `(conta, criado_em)` para a contagem do limite.
- **Sessão já autenticada:** nada especial na view; o `login()` do Django (via `perform_login`) troca a sessão. Testado em `test_link_usado_por_quem_ja_esta_autenticado_troca_a_sessao`.
- **Limites por IP:** os do allauth/Cloudflare não foram duplicados; o spec define o limite por conta nesta rota.

## Limitações

- Nenhuma revisão independente feita ainda.
- Login por código do allauth continua desligado; link para administrador é recusado (spec).
