# E02-05 — Revisão

Estado: **aguardando revisão independente (agente 3)**. Abaixo, evidências do implementador.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** `ConviteInvalido` ganhou o atributo `codigo` (e `mensagem`) e `MetodoCadastro`; `validar_convite` e `consumir_convite` como stubs; `FormularioCadastroPorConvite` mínimo; `aceitar_convite` devolvendo resposta vazia; rota `/convite/<token>/`. A emissão da E02-04 passou a levantar `ConviteInvalido` com códigos `papel_invalido` e `fornecedor_inconsistente`, sem mudar o comportamento (os testes da E02-04 continuaram verdes: `344 passed`).

**Red** (`uv run pytest` nos dois arquivos de teste desta fatia, com o andaime):

```
33 failed, 1 passed
```

Falhas de asserção: `assert 200 == 410` (página sem validação), `DID NOT RAISE ConviteInvalido`, `Conta matching query does not exist` (nada criado), `'NoneType' object is not subscriptable` (a resposta vazia não tem contexto de formulário), `assert 0 == 1` nas corridas.

**Green:** `apps/contas/convites.py` (`validar_convite`, `consumir_convite`), `apps/contas/forms.py`, `apps/contas/views.py` (`aceitar_convite`) e os templates `convites/cadastro.html`, `invalido.html`, `sair_antes.html`.

Durante o Green apareceu um erro real de integração, corrigido com `select_for_update(of=("self",))`: `FOR UPDATE cannot be applied to the nullable side of an outer join` (o `select_related("fornecedor")` da consulta travada).

**Refactor:** tipagem e ruff.

## Verificações (final)

```
uv run pytest -q                                  -> 378 passed em 59 s
test_convites_cadastro_concorrencia.py (3 execuções seguidas) -> 2 passed em todas
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 89 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
```

## Matriz

| Critério | Teste |
|---|---|
| A-1 | `test_pagina_mostra_email_so_leitura_finalidade_e_campos` (+ fornecedor, + GET não consome) |
| A-2 | `test_cadastro_cria_conta_email_verificado_e_sessao` |
| A-3 | `test_convite_consumido_nao_pode_ser_reutilizado` |
| A-4, A-5 | `test_fronteira_de_24h_no_post`, `test_valido_no_get_e_expirado_no_post_e_recusado` (relógio controlado no `POST`) |
| A-6, A-7 | `test_campos_extras_do_post_sao_ignorados_comprador` / `_fornecedor` |
| A-8, A-9 | `test_email_banido_depois_da_emissao_e_recusado`, `test_email_que_virou_conta_depois_da_emissao_e_recusado` |
| A-10 | `test_validacao_de_nome_e_senha_devolve_formulario` (6 casos) |
| A-11, A-12 | `test_token_alterado_ou_aleatorio_e_recusado`, `test_conta_autenticada_nao_usa_convite` |
| A-13 | `test_mesmo_convite_em_paralelo_cria_uma_conta_e_um_consumo` (20 repetições) |
| A-14 | `test_dois_convites_com_mesmo_email_normalizado_em_paralelo` (10 repetições; `tecnico`, T-34) |
| A-15 a A-17 | `test_auditoria_do_cadastro_nao_tem_dado_pessoal`, `test_conta_criada_entra_depois_por_senha_sem_novo_convite`, `test_comprador_e_fornecedor_..._independentes` (cenário 81) |
| A-18 | `test_codigo_interno_corresponde_a_causa_e_a_pagina_e_identica`, `test_corpo_da_resposta_e_identico_nas_cinco_causas` |

Marcados `acceptance` com o cenário no comentário: A-2 (cenário 1), A-3, A-4, A-6, A-7, A-9 (80), A-17 (81).

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **Login depois do cadastro:** `allauth.account.internal.flows.login.perform_login(request, Login(user=conta, email=...))`. Assim `pre_login` (banimento, e-mail verificado) e os registros de autenticação da sessão continuam valendo, e a resposta é o redirecionamento padrão para `/inicio/`. Roda fora da transação do cadastro, depois do commit.
- **Ordem das verificações em `_conferir`:** inexistente, consumido, expirado, banido, e-mail em uso — a ordem do spec. A página do visitante é a mesma mensagem (410) para as cinco causas (o corpo é byte a byte idêntico, testado).
- **Corrida de e-mail (A-14):** o perdedor falha no `INSERT` único da conta; `Conta.save` converte a violação de `conta_email_unico` em `EmailEmUso`, e o serviço a traduz em `ConviteInvalido("email_em_uso")`. A transação inteira é desfeita, então o convite do perdedor continua não consumido.
- **Validação de nome e senha em dois níveis:** o formulário mostra as mensagens; o serviço valida de novo (nome 1 a 150 e validadores de senha da E02-02), para outros chamadores (E02-07).
- **`MetodoCadastro`:** só `senha` agora. No método `google` (E02-07) a conta nasce com senha inutilizável (padrão do modelo).
- **Formulário em `apps/contas/forms.py`** (nome do spec), separado de `formularios.py` (formulários do allauth e o de emissão, das fatias anteriores).
- **Visitante autenticado:** vale tanto no `GET` quanto no `POST`, e é checado antes do convite, para a página não revelar nada sobre o token a quem já está logado.

## Limitações

- Nenhuma revisão independente feita ainda.
- O botão de cadastro com Google fica para a E02-07 (spec).
