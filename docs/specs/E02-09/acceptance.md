# E02-09 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). As imagens de teste são geradas em memória com Pillow. Os testes usam um `MEDIA_ROOT` temporário.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Spec §3.2, §13 | positivo | um comprador autenticado | abro `/perfil/` | 200 com nome, telefone, avatar e consentimento de WhatsApp; o e-mail aparece só para leitura |
| A-2 | Spec §3.2 | positivo | o mesmo comprador | altero o nome para `" Ana Souza "` | nome gravado `"Ana Souza"` |
| A-3 | Spec §3.2 | negativo | o mesmo comprador | envio nome vazio | erro de formulário; nada alterado |
| A-4 | Spec da fatia | positivo | os telefones válidos listados na spec | chamo `normalizar_telefone` | os resultados E.164 listados |
| A-5 | Spec da fatia | negativo | os telefones inválidos listados na spec | chamo `normalizar_telefone` | `TelefoneInvalido` em cada um |
| A-6 | Spec §3.2 | positivo | um comprador com telefone | marco o consentimento de WhatsApp | `whatsapp_consentido_em` preenchido com `agora()`; auditoria `perfil.whatsapp_consentir` sem o número |
| A-7 | Spec §3.2 | negativo | um comprador sem telefone | marco o consentimento | erro de formulário; consentimento nulo |
| A-8 | Spec §3.2 | positivo | um comprador com consentimento ativo | (a) desmarco; (b) noutro caso, removo o telefone; (c) noutro caso, troco o número | consentimento nulo nos três; auditoria `perfil.whatsapp_revogar` em cada um |
| A-9 | Spec da fatia | negativo | uma conta | atualizo por SQL direto `whatsapp_consentido_em` sem telefone | o banco recusa (`CHECK`) |
| A-10 | Spec §3.2 | positivo | um comprador | envio um PNG válido de 100 × 100 | avatar gravado com nome UUID; o arquivo abre como PNG |
| A-11 | Spec §15 | positivo | um JPEG com EXIF contendo GPS | envio como avatar | o arquivo gravado não tem EXIF |
| A-12 | Spec da fatia | negativo | (a) um texto com extensão `.png`; (b) um GIF; (c) um PNG de 2 MB + 1 byte; (d) um PNG de 4097 × 10 | envio como avatar | erro de formulário em cada um; nenhum arquivo gravado |
| A-13 | Spec da fatia | positivo | um comprador com avatar | troco o avatar; depois removo | o arquivo anterior some do storage depois de cada operação |
| A-14 | Spec §2, §15 | positivo | um comprador com avatar | ele e o administrador (com passkey) acessam `/perfil/avatar/<id>/` | 200 com a imagem para os dois |
| A-15 | Spec §15 | negativo | o avatar do comprador A | o comprador B, um fornecedor e um visitante anônimo acessam `/perfil/avatar/<id de A>/` | 404 para B e para o fornecedor; o anônimo é redirecionado para `/entrar/` |
| A-16 | Spec §15 | negativo | um comprador autenticado | envio `POST /perfil/` com campos extras `email`, `papel`, `fornecedor` e `situacao` | esses campos não mudam |
| A-17 | Spec da fatia | positivo | um fornecedor, um comprador suspenso e o administrador | abro e salvo `/perfil/` | 200 e alteração gravada para os três |
| A-18 | Infra 5 | negativo | uma alteração de perfil com telefone | capturo os logs da requisição | nenhum log contém o telefone nem o e-mail |
| A-19 | Spec da fatia | positivo | `pyproject.toml` e `uv.lock` | inspeciono | Pillow declarado e travado; `uv sync --locked` passa no CI |

### Correção E02-R01

Os critérios abaixo seguem a seção "Correção E02-R01" do `spec.md`. A intercalação determinística envolve `views.atualizar_perfil` por `monkeypatch`, como no teste do revisor: a alteração concorrente é feita depois da leitura da view e antes da chamada à função original, que é a função sob teste e nunca é substituída. Os testes com threads usam `executar_em_paralelo` (E01-05) e `django_db(transaction=True)`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-20 | E02-R01, Spec §2 | concorrência | um comprador ativo com sessão aberta | o administrador o suspende depois da leitura da view e antes da gravação; o `POST /perfil/` altera o nome | 302; nome novo gravado; situação `suspensa`; `pode_adicionar_interesse` falso; nenhuma auditoria `conta.reativar` |
| A-21 | E02-R01, Spec §2, cenário 58 | concorrência | o mesmo comprador | o administrador o remove na mesma intercalação | 403; nome inalterado; situação `removida`; `EmailBanido` presente; nenhuma auditoria de perfil; nenhum arquivo de avatar novo no storage, mesmo quando o `POST` envia avatar |
| A-22 | E02-R01, Spec §3.2 | concorrência | um comprador com a senha `S1` | a senha passa a `S2` (`set_password` e `save(update_fields=["password"])`) na mesma intercalação | 302; `check_password(S2)` verdadeiro e `check_password(S1)` falso |
| A-23 | E02-R01 | estático-comportamental | um comprador | capturo as consultas de um `POST /perfil/` válido (`CaptureQueriesContext`) | exatamente um `UPDATE` em `contas_conta`, cujas colunas atribuídas são só `nome`, `telefone`, `whatsapp_consentido_em` e `avatar`; existe um `SELECT ... FOR UPDATE` da conta antes dele |
| A-24 | E02-R01, Spec §3.2 | concorrência | um comprador com telefone e sem consentimento, lido em duas instâncias antes do paralelo | duas chamadas de `atualizar_perfil` em paralelo, uma com cada instância, as duas marcando o consentimento, repetidas 10 vezes com contas novas | em todas: consentimento preenchido e exatamente uma auditoria `perfil.whatsapp_consentir` |
| A-25 | E02-R01, Spec §2 | concorrência | um comprador ativo, lido antes do paralelo | `atualizar_perfil` (com essa instância) e `suspender` em paralelo, repetidos 10 vezes com contas novas | em todas: situação final `suspensa`, nome novo gravado e uma auditoria `conta.suspender` |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-3, A-16 a A-18 | `tests/tecnicos/test_perfil_tela.py` |
| A-4, A-5 | `tests/tecnicos/test_perfil_telefone.py` |
| A-6 a A-9 | `tests/tecnicos/test_perfil_whatsapp.py` |
| A-10 a A-15 | `tests/tecnicos/test_perfil_avatar.py` |
| A-19 | evidência no `review.md` |
| A-20 a A-23 | `tests/tecnicos/test_perfil_concorrencia.py`, com `test_perfil_preserva_alteracao_concorrente` do revisor (ajuste do parâmetro `remover` descrito no `spec.md`) |
| A-24, A-25 | `tests/tecnicos/test_perfil_concorrencia.py` (marcador `concorrencia`) |
