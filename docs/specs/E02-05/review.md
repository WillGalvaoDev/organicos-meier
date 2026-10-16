# E02-05 — Revisão

Estado atual: **REPROVADO** no commit `8f4dc36` (revisão independente ao final). A E02 global está **REPROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

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


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

### Matriz da fatia

A-1 a A-18: validação/consumo do convite, fronteiras, vínculo/papel imutáveis, auditoria e corridas cobertos. A-13 repete o mesmo convite 20 vezes; A-14 repete convites do mesmo e-mail 10 vezes. A-10 não cobre a senha idêntica ao nome que é aceita pela configuração compartilhada (E02-R04).

### Verificação independente comum

SHA auditado: `8f4dc36e91833ad11e327bcfb99e34fa81ba6eb8`, main/PR #32. Documentos de referência: especificação funcional v1.6 (§§2, 3 e 15), infraestrutura v1.7 (§§2, 4.11 e 5), spec e acceptance de cada fatia. Nenhuma mudança de regra de negócio foi presumida.

- `uv run pytest -q`: **594 passed em 75,74 s**, banco Postgres real, incluindo E01 e todas as fatias E02.
- `uv run ruff check .`: limpo; `uv run ruff format --check .`: 156 arquivos.
- `uv run mypy .`: 120 arquivos, sem erros.
- `uv run python manage.py makemigrations --check --dry-run --settings=config.settings.test`: sem mudanças.
- `uv run python manage.py check --settings=config.settings.test`: zero issues.
- `uv sync --locked`: lock resolvido (51 pacotes), ambiente conferido (50 pacotes).
- CI do SHA exato: [run 38914653756](https://github.com/WillGalvaoDev/organicos-meier/actions/runs/38914653756), sucesso.

A suíte verde não basta para aprovar E02: os probes adicionais do revisor terminaram em **6 failed, 1 passed em 2,65 s**, reproduzindo quatro achados distintos. Script, comando e matriz global estão em `../E02-10/review.md`, seção de revisão independente. O probe de PNG/EXIF passou e não gerou achado.

### Evidência TDD e limites

Conferidos os relatos de andaime, Red por asserção/comportamento, Green e refatoração de cada fatia, comparados com o diff e os testes. As alterações autorizadas de testes anteriores estão identificadas: fábrica de conta na auditoria E01; regra temporária de login administrativo substituída pela E02-03. Ajustes de instrumentação relatados pelo implementador não foram tratados como prova de defeito em produção. Limitação: a cronologia dos ciclos é documentada pelo implementador, sem logs brutos/commits intermediários para comprovar independentemente cada passo. A execução Green acima é independente; não foi apresentada como prova retrospectiva de toda a sequência TDD.

WebAuthn usa o dublê criptográfico expressamente previsto, com views, sessão e Authenticator reais. Google usa o fluxo real do allauth com resposta simulada, sem chamada ao provedor. Cerimônia física de passkey, OAuth/credenciais reais, SES, R2 e efeitos futuros sobre pedidos/interesses não foram validados nesta etapa; permanecem nos gates previstos pelos documentos. D-1 da E02-08 (suspensão de fornecedor) não foi implementado nem reaberto.

### Pendência de integração: E02-R04

O probe de cadastro envia nome e senha idênticos, com tamanho suficiente e sem senha comum/numeric-only. A conta é criada e autenticada. O serviço chama `validate_password` como previsto, mas o validador configurado não conhece os atributos do modelo. A causa e a correção estão na E02-02/review.md (E02-R04). Esta fatia fica REPROVADA no aceite integrado até a política compartilhada funcionar e os casos novos serem cobertos. Os critérios de convite/consumo e suas corridas passaram.

## Correção E02-R04 — integração (implementador)

Conforme a seção "Correção E02-R04 (integração)" do `spec.md`, esta fatia não muda código: a causa e a correção estão em `docs/specs/E02-02/review.md` (validador de semelhança com `user_attributes` correto). O serviço `consumir_convite` e o `FormularioCadastroPorConvite` já validavam a senha com uma `Conta` provisória preenchida (nome e e-mail); o que faltava era o validador conhecer esses atributos.

**Red** (código do commit `8f4dc36`): o teste do revisor `test_cadastro_recusa_senha_igual_ao_nome` (A-19, literal), as variações do A-19 e o A-20 falham: `assert 302 == 200` (a conta era criada com a senha igual ao nome) e `DID NOT RAISE ValidationError` no serviço. **Green:** passam depois da correção do validador. Testes em `tests/tecnicos/test_convites_cadastro.py`: `test_cadastro_recusa_senha_igual_ao_nome` (revisor), `test_cadastro_recusa_senha_semelhante_ao_nome_com_mensagem` (A-19 a e b, confere `password_too_similar` e que o convite continua pendente), `test_cadastro_recusa_senha_semelhante_ao_email` (A-20) e `test_servico_tambem_recusa_senha_semelhante_ao_nome`.
