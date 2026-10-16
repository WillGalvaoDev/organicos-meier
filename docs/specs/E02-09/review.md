# E02-09 — Revisão

Estado atual: **REPROVADO** no commit `8f4dc36` (revisão independente ao final). A E02 global está **REPROVADA**.

Abaixo, evidências históricas do implementador, preservadas.

## Dependência nova: Pillow (A-19)

Pillow é a única dependência acrescentada, como prevê o spec: sem ela não há como verificar com segurança que o arquivo é uma imagem nem regravá-la sem metadados. `uv add pillow` registrou `pillow>=12.3.0` em `pyproject.toml` (grupo de dependências do projeto) e travou **12.3.0** em `uv.lock`. `uv sync --locked` passa (`Checked 50 packages`), e o CI roda o mesmo comando.

## Ciclo Red → Green → Refactor

**Andaime (sem comportamento, exceção técnica registrada):** campos `telefone`, `avatar` e `whatsapp_consentido_em` em `Conta` (sem restrições; migração provisória), `apps/contas/perfil.py` com as exceções e funções que devolvem a entrada como veio, `FormularioPerfil` mínimo, views `perfil` e `avatar` vazias com as rotas `/perfil/` e `/perfil/avatar/<id>/`, `MEDIA_ROOT` e `media/` no `.gitignore`. Suíte antes do Red: `479 passed`.

**Red** (`uv run pytest` nos quatro arquivos de teste desta fatia, com o andaime):

```
62 failed, 7 passed
```

Falhas de asserção: `DID NOT RAISE TelefoneInvalido`, `DID NOT RAISE IntegrityError` (sem as restrições do banco), `assert 200 == 302` (perfil vazio), `'NoneType' object is not subscriptable` (sem formulário no contexto), resultados de normalização diferentes dos esperados (`- +5521999998888`).

**Green:** `perfil.py` (`normalizar_telefone`, `processar_avatar`, `atualizar_perfil`), `FormularioPerfil`, views `perfil` e `avatar`, restrições `conta_whatsapp_exige_telefone` e `conta_telefone_e164` (migração `0004_perfil` regerada), template `contas/perfil.html`.

**Refactor:** tipagem e ruff.

## Verificações (final)

```
uv run pytest -q                                  -> 548 passed em 74 s
uv run ruff check .                               -> All checks passed
uv run ruff format --check .                      -> ok
uv run mypy .                                     -> Success: no issues found in 109 source files
manage.py makemigrations --check --dry-run (test) -> No changes detected
uv sync --locked                                  -> Checked 50 packages
```

## Matriz

| Critério | Teste |
|---|---|
| A-1 a A-3, A-16 a A-18 | `test_perfil_tela.py` |
| A-4, A-5 | `test_perfil_telefone.py` (todos os exemplos do spec e mais casos-limite) |
| A-6 a A-9 | `test_perfil_whatsapp.py` |
| A-10 a A-15 | `test_perfil_avatar.py` (imagens geradas em memória; `MEDIA_ROOT` temporário; `django_db(transaction=True)` para a exclusão depois do commit) |
| A-19 | seção "Dependência nova" acima |

## Decisões técnicas (derivadas do spec; nenhuma muda regra de negócio)

- **Telefone:** ao normalizar, `+` só é aceito no início e só como `+55`; sem `+`, o prefixo `55` só é descartado quando a entrada tem 12 ou 13 dígitos (assim o DDD 55 do Rio Grande do Sul, como em `(55) 99999-8888`, não é confundido com o país). Restam 10 ou 11 dígitos, com DDD que não começa com 0. A mensagem do erro não repete o número.
- **Restrição extra no banco:** `conta_telefone_e164` (`telefone IS NULL OR telefone ~ '^\+55[1-9][0-9][0-9]{8,9}$'`) garante a invariante "o telefone gravado é sempre E.164 brasileiro ou nulo" mesmo por SQL, além do `conta_whatsapp_exige_telefone` pedido.
- **Consentimento (regra completa em `atualizar_perfil`):** marcar com telefone grava `agora()` e audita `perfil.whatsapp_consentir`; desmarcar, remover o telefone ou trocar o número (com consentimento ativo) grava nulo e audita `perfil.whatsapp_revogar`. Na gravação em que o número muda, a caixa marcada é ignorada: é preciso aceitar de novo, numa gravação seguinte (teste `test_aceitar_de_novo_depois_de_trocar_o_numero`). Marcar sem telefone é erro de formulário, a menos que o consentimento já estivesse ativo e o usuário esteja removendo o número (nesse caso revoga). Manter o consentimento ativo não muda o instante nem gera auditoria. A auditoria nunca traz o número.
- **Avatar:** limite de 2 MB conferido antes de abrir; `Image.open` lê só o cabeçalho, então formato e dimensões (4096 × 4096) são validados antes de decodificar; `verify()` e reabertura para regravar; `ImageOps.exif_transpose` aplica a orientação antes de descartar o EXIF; a regravação não repassa `exif`, `pnginfo` nem perfis, então EXIF/GPS e textos de PNG saem (testados nos bytes do arquivo gravado). Extensão e nome vêm do formato verificado e de um UUID, nunca do nome enviado. A imagem de um tipo não aceito (GIF, texto com extensão `.png`) é recusada.
- **Armazenamento:** `ImageField` com `upload_to="avatares/"` no storage padrão (`MEDIA_ROOT`); o arquivo novo é gravado dentro da transação e removido se ela falhar; o antigo é apagado em `transaction.on_commit`.
- **Acesso ao avatar:** `/perfil/avatar/<id>/` exige login (anônimo vai ao `/entrar/`), serve à própria conta e ao administrador **com prova de passkey na sessão**; qualquer outro caso, inclusive conta sem avatar, dá 404. Resposta com `Cache-Control: private, no-store`.
- **Perfil:** a view carrega a conta da sessão e não aceita identificador de conta; o formulário só tem `nome`, `telefone`, `avatar`, `remover_avatar` e `whatsapp`, então `email`, `papel`, `fornecedor` e `situacao` enviados no `POST` são ignorados.

## Limitações

- Nenhuma revisão independente feita ainda.
- O storage do R2 em produção entra com a homologação (E16); aqui vale o storage padrão (spec).
- Envio de WhatsApp e templates ficam para a fase 3.


## Revisão independente — 8f4dc36 — 2026-10-16

Revisor: Codex, agente 3. **Decisão desta fatia: REPROVADO.**

### Matriz da fatia

A-1 a A-19: perfil, telefone, consentimento/auditoria, validação e limpeza de avatares, acesso e dependência cobertos. Um probe adicional de PNG com EXIF/GPS também passou. A gravação integral da conta sobrescreve campos fora do perfil sob intercalação (E02-R01), contra o isolamento de A-16 e das regras de moderação/credenciais.

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

### E02-R01 — bloqueador: salvar perfil restaura estado de acesso e credenciais antigos

Referências: especificação funcional §§2 e 15; E02-09 Campos editáveis/A-16; E02-08 moderação/invariantes; E02-02 recuperação de acesso. Local: `apps/contas/perfil.py:124` (`conta.save()`), com a conta lida em `apps/contas/views.py` antes da gravação.

O perfil grava todas as colunas de uma instância já lida, incluindo `situacao` e `password`, embora só deva editar dados de perfil. Se outra operação suspender/remover a conta ou alterar a senha entre a leitura e a gravação, o POST de perfil restaura os valores antigos. Em três reproduções determinísticas pela rota real, a situação voltou a `ativa` após suspensão e após remoção, e a senha nova deixou de conferir após o perfil ser salvo.

No caso de remoção, o registro EmailBanido permanece e continua protegendo a entrada; o achado não afirma bypass desse banimento. A suspensão, porém, é efetivamente desfeita sem ação do administrador. Restaurar o hash antigo também contraria a recuperação e pode voltar a aceitar uma credencial substituída. Nenhuma nova ação de reativação é auditada.

Reprodução: `test_perfil_preserva_alteracao_concorrente`, parâmetros `suspender`, `remover` e `senha`, preservado em E02-10. O monkeypatch intercala a alteração depois de a view ler a conta e antes de chamar a função original de salvamento. Não altera a função auditada nem os resultados; representa deterministicamente a ordem possível de duas requisições. Falhas: `ativa != suspensa`, `ativa != removida` e senha nova não confere.

Devolução: restringir a gravação aos campos efetivamente editáveis e proteger a leitura/gravação dos estados do próprio perfil que precisam de consistência (consentimento e avatar), sem sobrescrever credenciais, papel, vínculo ou moderação. Testar a intercalação com suspensão, remoção e recuperação de senha antes da correção, e demonstrar Red → Green. Não há decisão comercial em aberto.
