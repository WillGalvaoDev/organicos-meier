# E02-03 — Acesso do administrador com passkey e área administrativa

Fatia 3 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

A especificação exige proteção reforçada para a conta administrativa, e a infraestrutura definiu passkey obrigatória para o administrador e nova autenticação antes de operações financeiras. Esta fatia entrega:

- login do administrador com passkey;
- cadastro da primeira passkey;
- proteção da área administrativa (`somente_administrador`);
- utilitário de nova autenticação por passkey, que as etapas financeiras vão usar;
- comando de recuperação para quando o administrador perde todas as passkeys.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | O administrador é o único responsável por convites, cadastros, moderação e operações. |
| Especificação §15 | Proteção reforçada para conta administrativa e operações financeiras. Autorização por perfil em toda leitura e escrita. |
| Infraestrutura 2 | MFA com passkeys pelo django-allauth. Admin: passkey obrigatória e nova autenticação antes de autorizar apuração, estornos, devoluções excepcionais, repasses, aportes e movimentações entre destinações. |
| Infraestrutura 4.8 | A nova autenticação é proteção de acesso, não etapa de aprovação. |
| AGENTS.md §6 | Menor privilégio. |

## Escopo

**Dentro:**

- Instalação de `allauth.mfa` com só passkeys:
  - `MFA_SUPPORTED_TYPES = ["webauthn"]`;
  - `MFA_PASSKEY_LOGIN_ENABLED = True`;
  - `MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN` só em `dev.py` e `test.py`.
- Fim da recusa temporária do login do administrador por senha (E02-02), substituída pelas regras abaixo.
- Middleware que exige o cadastro da primeira passkey.
- Decorador e mixin `somente_administrador`.
- Decorador `exige_reautenticacao_por_passkey`.
- Página inicial da área administrativa, `/administracao/`, sem conteúdo de negócio.
- Comando `manage.py redefinir_passkeys_administrador`.

**Fora:**

- TOTP, códigos de recuperação e MFA para compradores e fornecedores: não previstos nos documentos para esses papéis.
- Telas de negócio da área administrativa (E02-04, E02-08 e etapas seguintes).
- Uso concreto da nova autenticação em operações financeiras (E08 a E13). Aqui ela só é entregue e testada.

## Regras

**Métodos de login do administrador:**

- **Passkey direta:** login sem senha, `MFA_PASSKEY_LOGIN_ENABLED`.
- **Senha seguida da etapa de passkey:** o allauth pede a passkey depois da senha sempre que o administrador tem ao menos uma cadastrada.
- **Métodos recusados:** link e Google já são recusados por `verificar_acesso` (E02-02).

**Primeira passkey (situação sem nenhuma passkey cadastrada):**

- Depois do login por senha, a sessão fica restrita. O middleware `ExigePasskeyDoAdministrador` redireciona toda requisição do administrador para a tela de cadastro de passkey do allauth.
- As únicas exceções são as rotas do próprio cadastro de passkey, `POST /sair/` e os arquivos estáticos.
- Cadastrada a primeira passkey, a restrição acaba. A sessão continua sem comprovação de passkey e por isso não acessa a área administrativa: o administrador sai e entra de novo com passkey, ou passa por uma nova autenticação por passkey. A tela de conclusão orienta isso.

**`somente_administrador`:** a view é liberada só quando as três condições valem:

1. a requisição está autenticada;
2. o papel da conta é `administrador`;
3. a sessão tem registro de autenticação por passkey (`webauthn`), obtido no login ou numa nova autenticação. O registro vem dos registros de autenticação que o allauth guarda na sessão. O implementador usa a API pública do allauth, se houver, e documenta o ponto usado no `review.md`.

Respostas:

- **Visitante anônimo:** redirecionamento para `/entrar/`.
- **Conta autenticada de outro papel:** 403.
- **Administrador sem comprovação de passkey na sessão:** redirecionamento para a nova autenticação por passkey. Isso inclui sessões criadas por `force_login` nos testes.

**`exige_reautenticacao_por_passkey`:**

- Exige que a última autenticação por passkey da sessão tenha ocorrido há no máximo `ACCOUNT_REAUTHENTICATION_TIMEOUT` segundos, que é 300, o padrão do allauth.
- Se passou do prazo, redireciona para a nova autenticação do MFA do allauth e, depois do sucesso, volta para a ação original. A nova autenticação por senha não serve.
- O tempo é medido com `agora()` (E01-03), ou com o mecanismo do allauth, desde que seja controlável pela fixture `relogio` nos testes.
- Sempre inclui `somente_administrador`.

**Gestão de passkeys:**

- O administrador pode cadastrar outras passkeys, sempre depois de uma nova autenticação por passkey.
- A última passkey não pode ser removida: o adaptador de MFA (`can_delete_authenticator`) recusa.
- As rotas de MFA do allauth respondem só ao administrador. Para os outros papéis, devolvem 403, porque MFA não está previsto para eles.

**Comando `redefinir_passkeys_administrador`:**

- Remove todas as passkeys do administrador e encerra todas as sessões dele.
- Registra a auditoria `conta.redefinir_passkeys`, com autor `SISTEMA` e alterações `{"conta": <id>, "removidas": <n>}`.
- Funciona só pela linha de comando do servidor, por ser o caminho de recuperação com menor privilégio, e não tem rota.
- Depois dele, o próximo login por senha volta à regra da primeira passkey.

**Testes de WebAuthn:**

- **O que é substituído:** a verificação criptográfica da cerimônia é responsabilidade do allauth e do `fido2`. Nos testes, ela é trocada por um dublê determinístico, aplicado com `monkeypatch` nas funções de `allauth.mfa.webauthn.internal.auth`: `begin_registration`, `complete_registration`, `begin_authentication`, `complete_authentication` e `extract_user_from_response`.
- **Versão:** o caminho vale para o allauth 65.19.7, a versão travada no `uv.lock`, e o implementador o registra no `review.md`.
- **O que continua real:** o dublê não substitui as views, os estágios de login, o registro na sessão nem o modelo `Authenticator`.

## Interfaces

- `apps/contas/administracao.py`: `somente_administrador` (decorador), `SomenteAdministradorMixin` e `exige_reautenticacao_por_passkey`.
- `apps/contas/middleware.py`: `ExigePasskeyDoAdministrador`, registrado depois do `AuthenticationMiddleware` e do `AccountMiddleware`.
- `apps/contas/adaptadores.py`: `AdaptadorMFA` (recusa remover a última passkey), em `MFA_ADAPTER`.
- `apps/contas/views.py`: `painel_administracao`, em `/administracao/`.
- `apps/contas/management/commands/redefinir_passkeys_administrador.py`.
- No app `tests.apoio`, uma rota só de testes protegida por `exige_reautenticacao_por_passkey`, para os critérios A-9 e A-10.

## Invariantes

- Nenhuma view administrativa responde a uma sessão sem comprovação de passkey.
- O administrador sempre tem ao menos uma passkey depois de cadastrar a primeira, exceto pelo comando de recuperação.
- Compradores e fornecedores nunca acessam a área administrativa, nem por chamada direta.

## Casos-limite e concorrência

- **Login por senha com passkey cadastrada e etapa de passkey abandonada:** nenhuma sessão autenticada é criada, e `/administracao/` redireciona para `/entrar/`.
- **Nova autenticação na fronteira:** exatamente 300 s depois da última autenticação ainda vale, e 300 s mais 1 s exige outra. Segue o limite inclusivo do allauth, e o implementador confirma e registra o comportamento real.
- **Comando de recuperação com o administrador logado em dois navegadores:** as duas sessões são encerradas.
- **Concorrência:** duas remoções de passkey simultâneas, em sessões diferentes do administrador, não podem apagar a última. As regras obrigatórias estão em "Correção E02-R02", que prevalece sobre a versão anterior desta seção ("sem concorrência crítica").

## Correção E02-R02 — revisão da especificação em 2026-10-16

### Diagnóstico

O revisor reprovou a E02 no commit `8f4dc36` (achado E02-R02, importante, em `review.md`). Confirmei a causa:

- `remover_passkey` (`apps/contas/views.py:59`) consulta `can_delete_authenticator` (`apps/contas/adaptadores.py:111`), que verifica se existe outra passkey;
- depois disso, delega a exclusão à view do allauth;
- a verificação e a exclusão não estão serializadas.

Com duas passkeys e dois `POST` simultâneos, cada requisição vê a outra passkey, as duas apagam e o administrador fica com zero, fora do comando de recuperação. Isso viola a invariante "o administrador sempre tem ao menos uma passkey". A frase "sem concorrência crítica" desta spec estava errada.

### Regra

1. **Serialização por conta.** No `POST`, `remover_passkey` abre `transaction.atomic()` e trava a linha da conta da sessão com `Conta.objects.select_for_update().get(pk=request.user.pk)`. Toda remoção de passkey da mesma conta passa por essa trava.
2. **Decisão sob a trava.** Com a trava obtida, uma consulta nova conta as passkeys WebAuthn da conta diferentes da que vai ser removida. Se não houver outra, a remoção é recusada com a mensagem "A última passkey não pode ser removida." e o redirecionamento para a lista, como hoje. Se houver, a view do allauth (`remove_webauthn`) é chamada dentro do mesmo bloco atômico.
3. **Checagem prévia.** A consulta prévia por `can_delete_authenticator` antes da trava pode continuar, como resposta rápida. A decisão que vale é sempre a do item 2, feita por uma função própria sobre o estado travado. `can_delete_authenticator` nunca é chamado com a trava obtida. Isso mantém o teste do revisor válido: ele pausa as duas requisições logo depois de `can_delete_authenticator`, e a trava só é pedida depois.
4. **Sem mudança de comportamento sequencial.** A-11, A-12 e a exigência de nova autenticação do allauth continuam como estão. Se o allauth pedir nova autenticação, nada é removido.
5. **Comando de recuperação.** `redefinir_passkeys_administrador` continua removendo todas as passkeys. Ele é a única exceção à invariante.

### Testes obrigatórios

- O teste do revisor `test_duas_remocoes_preservam_ultima_passkey`, em `docs/specs/E02-10/review.md`, entra literal na suíte.
- Os critérios A-16 e A-17 do `acceptance.md`.
- Red: com o código do commit `8f4dc36`, o teste do revisor falha pela asserção (zero passkeys) de forma determinística, porque a barreira dele força a intercalação. A-16 e A-17 dependem da ordem real das threads e podem passar em alguma execução do código antigo. Eles ficam como testes de regressão, e o implementador registra no `review.md` o resultado observado no Red.

### O que não fazer

- Não travar só a linha do `Authenticator` a remover: as duas requisições travam linhas diferentes e a corrida continua.
- Não resolver com `count()` antes da exclusão sem trava, nem com uma nova verificação depois da exclusão seguida de recriação.

## Dependências e decisões em aberto

- Depende de E02-02.
- O comportamento exato do allauth na fronteira de 300 s é técnico, não uma regra de negócio. O implementador o observa e escreve o teste com o resultado real.
- Sem decisões em aberto.
