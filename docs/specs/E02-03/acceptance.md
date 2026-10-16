# E02-03 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com a falha da asserção observada (Red). A cerimônia WebAuthn usa o dublê determinístico descrito na spec. Views, estágios e sessão são reais.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 2 | positivo | o administrador com senha e sem passkey | entro por senha e acesso `/administracao/`, `/inicio/` e uma URL qualquer | todas redirecionam para o cadastro de passkey; o cadastro e `POST /sair/` funcionam |
| A-2 | Infra 2 | positivo | o estado do A-1 | cadastro uma passkey (dublê) e acesso `/administracao/` na mesma sessão | não acessa (redireciona para a nova autenticação por passkey); depois de fazê-la, acessa com 200 |
| A-3 | Infra 2 | positivo | o administrador com uma passkey | entro por senha | o allauth pede a etapa de passkey; antes de concluí-la, `/administracao/` não responde 200; depois de concluída, responde 200 |
| A-4 | Infra 2 | negativo | o administrador com uma passkey | entro por senha e a etapa de passkey falha (o dublê recusa) | nenhuma sessão autenticada |
| A-5 | Infra 2 | positivo | o administrador com uma passkey | entro por passkey direta | `/administracao/` responde 200 |
| A-6 | Spec §15 | negativo | um comprador e um fornecedor autenticados | acessam `/administracao/` por `GET` e por `POST` | 403 nos dois |
| A-7 | Spec §15 | negativo | um visitante anônimo | acessa `/administracao/` | redirecionamento para `/entrar/` |
| A-8 | Spec da fatia | negativo | o administrador autenticado por `client.force_login`, sem registro de passkey na sessão | acessa `/administracao/` | não recebe 200 (redireciona para a nova autenticação) |
| A-9 | Infra 2, 4.8 | positivo | o administrador autenticado por passkey, com o relógio congelado | acessa a rota de teste protegida por `exige_reautenticacao_por_passkey` logo depois do login | 200 sem pedir nova autenticação |
| A-10 | Infra 2, 4.8 | fronteira | o mesmo, com o relógio avançado além do prazo (fronteira registrada pelo implementador: no limite e 1 s depois) | acessa a rota de teste | no limite, o comportamento observado e documentado; depois do limite, redireciona para a nova autenticação por passkey; com a nova autenticação por passkey concluída, responde 200; uma nova autenticação por senha não libera |
| A-11 | Spec da fatia | negativo | o administrador com uma única passkey | tenta removê-la pela tela do allauth | recusado; a passkey continua |
| A-12 | Spec da fatia | positivo | o administrador com duas passkeys, depois de nova autenticação | remove uma | removida; resta uma |
| A-13 | Spec da fatia | positivo | o administrador com passkeys e duas sessões abertas (dois clientes) | rodo `redefinir_passkeys_administrador` | zero passkeys; a próxima requisição de cada cliente não está autenticada; uma entrada de auditoria `conta.redefinir_passkeys`; o próximo login por senha cai na regra da primeira passkey (A-1) |
| A-14 | E02-02 (A-8 revogado) | positivo | o administrador com senha e sem passkey | entro por senha | a sessão existe, mas só com o acesso restrito do A-1. O critério A-8 da E02-02 fica substituído por este, e o teste dele é atualizado para a nova regra, com registro no `review.md` |
| A-15 | Spec da fatia | negativo | um comprador autenticado | acessa as rotas de MFA do allauth para cadastrar passkey | 403 ou 404 (MFA restrito ao administrador) |

### Correção E02-R02

Os critérios abaixo seguem a seção "Correção E02-R02" do `spec.md`. Os dois clientes são sessões reais do administrador autenticadas por passkey (dublê da cerimônia). Os testes usam `executar_em_paralelo` (E01-05) e `django_db(transaction=True)`.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-16 | E02-R02, Infra 2 | concorrência | o administrador com duas passkeys `P1` e `P2` e duas sessões com nova autenticação recente | uma sessão envia `POST` de remoção de `P1` e a outra de `P2`, em paralelo, repetido 10 vezes; antes de cada repetição o mesmo administrador volta a ter exatamente duas passkeys, cadastradas pelo dublê (o índice parcial da E02-01 impede um segundo administrador) | em todas: exatamente uma passkey restante; uma remoção bem-sucedida; a outra redirecionada para a lista com a mensagem da última passkey; nenhuma exceção nas operações |
| A-17 | E02-R02 | concorrência | o administrador com três passkeys | três `POST` de remoção em paralelo, cada um de uma passkey diferente, por três sessões | exatamente uma passkey restante; duas remoções bem-sucedidas |

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-5, A-14 | `tests/tecnicos/test_admin_passkey_login.py` |
| A-6 a A-8 | `tests/tecnicos/test_admin_area_restrita.py` |
| A-9, A-10 | `tests/tecnicos/test_admin_reautenticacao.py` |
| A-11, A-12, A-15 | `tests/tecnicos/test_admin_passkeys_gestao.py` |
| A-13 | `tests/tecnicos/test_admin_redefinir_passkeys.py` |
| A-16, A-17 | `tests/tecnicos/test_admin_passkeys_concorrencia.py` (marcador `concorrencia`), com `test_duas_remocoes_preservam_ultima_passkey` do revisor (nome original no comentário) |
