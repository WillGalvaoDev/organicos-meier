# E02-02 — Login por senha, sessão e recuperação de acesso

Fatia 2 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Esta fatia ativa o django-allauth para login com e-mail e senha, saída e recuperação de acesso por e-mail. Também cria o ponto único de decisão de acesso, `verificar_acesso`, que todos os métodos de login usam nas fatias seguintes. O cadastro aberto do allauth fica desligado: contas só nascem por convite (E02-05) ou pelo comando do administrador (E02-01).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Comprador suspenso consulta listas e pedidos pagos (portanto entra). Comprador removido tem acesso bloqueado definitivamente. E-mail banido não faz login por nenhum método. |
| Especificação §3.1 | E-mail banido não pode se cadastrar nem fazer login. |
| Especificação §3.2 | E-mail e senha. Todos os métodos respeitam a identidade autorizada e o bloqueio. Definir recuperação de acesso e comprovação de controle do e-mail. |
| Especificação §13 | Login e recuperação de acesso. |
| Especificação §18 | Cadastro público fora do escopo. |
| Cenários §16 | 2 e 58, na parte de senha. |
| Infraestrutura 2 | django-allauth. Adaptador próprio. Limite de requisições nas rotas de login. Admin com passkey obrigatória. |
| Infraestrutura 4.11 | Normalização em login. Verificação de banimento no adaptador, para todos os métodos. |
| Testes técnicos | T-24 (parte da senha), T-37 (ponto de login). |

## Escopo

**Dentro:**

- Instalação de `allauth`, `allauth.account` e `allauth.usersessions` em `INSTALLED_APPS`, com os middlewares exigidos: o `AccountMiddleware` e o middleware de `usersessions`.
- Adaptador `apps.contas.adaptadores.AdaptadorConta`.
- Função `apps.contas.acesso.verificar_acesso` e exceção `AcessoRecusado`.
- Rotas: entrar, sair, recuperar acesso (pedido, link do e-mail e nova senha) e página inicial autenticada.
- Templates mínimos em pt-BR, só com HTML do servidor. O HTMX não entra nesta fatia.
- Validadores de senha.
- Configuração de e-mail por ambiente.
- Passo do comando `criar_administrador` que cria o `EmailAddress` verificado (pendente da E02-01).

**Fora:**

- Login do administrador, que fica recusado nesta fatia e é liberado com passkey na E02-03.
- Link de acesso (E02-06), Google (E02-07), invalidação de sessões no banimento (E02-08) e cadastro por convite (E02-05).
- Envio pelo Amazon SES (E04 e homologação).

## Regras

**`verificar_acesso(conta: Conta | None, email: str, metodo: Metodo) -> None`:**

- **Métodos:** `Metodo` é `senha`, `link`, `google` ou `passkey`.
- **Recusas:** levanta `AcessoRecusado` com um código interno, que vai para testes e logs sem dados pessoais. Os casos são:
  1. `email_banido(email)` é verdadeiro (`banido`);
  2. a conta não existe (`sem_conta`);
  3. a situação da conta é `removida` (`removida`);
  4. o papel é `administrador` e o método é `link` ou `google` (`metodo_nao_permitido_admin`).
- **Situação suspensa:** não é motivo de recusa.
- **Ponto único:** é o único lugar que decide se um login é permitido. Os métodos das fatias E02-03, E02-06 e E02-07 chamam esta função, sem repetir a lógica.
- **Administrador nesta fatia:** o login por senha é recusado pelo adaptador até a E02-03 entregar a exigência de passkey. Assim, nunca existe sessão de administrador só com senha. A recusa fica fora de `verificar_acesso` e é removida na E02-03.

**Configuração do allauth:**

- `ACCOUNT_LOGIN_METHODS = {"email"}`;
- `ACCOUNT_USER_MODEL_USERNAME_FIELD = None`;
- `ACCOUNT_USER_MODEL_EMAIL_FIELD = "email_normalizado"`;
- `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`;
- `ACCOUNT_UNIQUE_EMAIL = True`;
- `ACCOUNT_LOGIN_BY_CODE_ENABLED = False`, porque o link de acesso é próprio (E02-06);
- os limites de requisição padrão do allauth (`ACCOUNT_RATE_LIMITS`) ficam ativos;
- `ACCOUNT_ADAPTER` aponta para `AdaptadorConta`.

**Adaptador (`AdaptadorConta`):**

- **`is_open_for_signup`:** devolve sempre `False`. A rota de cadastro do allauth nunca cria conta.
- **`clean_email`:** devolve `normalizar_email(email)`.
- **`pre_login`:** chama `verificar_acesso` com o método do login em curso. Se houver recusa, o login não acontece. Neste ponto também fica a recusa temporária do administrador.
- **Mensagem de recusa:** a tela mostra uma única mensagem, "Não foi possível entrar com esses dados.", para senha errada, e-mail inexistente, banido ou removido, sem revelar a causa. As páginas de conta inativa do allauth não aparecem.

**Recuperação de acesso:**

- É o fluxo de redefinição de senha do allauth, com link no e-mail.
- **Envio:** o e-mail só sai quando existe conta e `verificar_acesso(..., metodo=senha)` não recusa. O administrador está incluído, para que defina a primeira senha.
- **Resposta igual:** o formulário responde igual para qualquer e-mail, existente ou não, banido ou não.
- **Uso do link:** o link é de uso único e expira no prazo padrão do allauth.
- **Situação revalidada:** ao definir a nova senha, a situação é verificada outra vez. Conta removida ou e-mail banido depois do envio não consegue redefinir.
- **Sem login automático:** definir a senha não faz login. O usuário entra depois pelo fluxo normal, e o administrador passa pela E02-03.

**Sessão:**

- **Armazenamento:** sessões no banco (`django.contrib.sessions`), registradas pelo `usersessions` para que a E02-08 consiga encerrá-las por conta.
- **Sair:** só por `POST`, com CSRF.
- **Página inicial:** `/inicio/` exige login e mostra o nome e o papel da conta. Ela substitui a futura área de cada papel até as fatias de tela.
- **Produção** (`config/settings/prod.py`):
  - `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` ligados;
  - `SESSION_COOKIE_HTTPONLY` ligado;
  - `SESSION_COOKIE_SAMESITE = "Lax"`.

**Senhas:** `AUTH_PASSWORD_VALIDATORS` com os quatro validadores do Django:

- semelhança com atributos da conta;
- tamanho mínimo de 10 caracteres;
- senhas comuns;
- senha só numérica.

**E-mail por ambiente:**

- **Testes:** `locmem`.
- **Desenvolvimento:** `console`.
- **Produção:** `EMAIL_BACKEND` e `DEFAULT_FROM_EMAIL` lidos do ambiente e obrigatórios, sem valor padrão. Se faltarem, o carregamento das configurações falha. Configurar o SES fica para a E04 e a homologação.

**Rotas (prefixo sugerido, ajustável):**

| Rota | Origem |
|---|---|
| `/entrar/` | login do allauth |
| `/sair/` | logout do allauth, só `POST` |
| `/recuperar-acesso/...` | redefinição de senha do allauth |
| `/inicio/` | própria, exige login |

As demais rotas do allauth que esta fatia não usa ficam de fora do `urls.py`, ou ficam inertes, como o cadastro, que está fechado. O A-12 verifica isso.

## Interfaces

- `apps/contas/acesso.py`: `Metodo`, `verificar_acesso`, `AcessoRecusado` (com o atributo `codigo`).
- `apps/contas/adaptadores.py`: `AdaptadorConta`.
- `apps/contas/views.py`: `inicio`.
- `config/urls.py`: rotas acima.

## Invariantes

- Nenhuma conta é criada por rota do allauth.
- Nenhum login por senha acontece sem passar por `verificar_acesso`.
- Nenhuma sessão de administrador existe ao fim desta fatia.
- Respostas de login e de recuperação não revelam se um e-mail existe, está banido ou foi removido.

## Casos-limite e concorrência

- **E-mail digitado com variações** (maiúsculas e espaços): o login funciona, e a recuperação envia para a conta certa.
- **Conta suspensa:** entra.
- **Conta removida com senha correta:** é recusada.
- **Banimento entre o envio do link de recuperação e o uso:** a redefinição é recusada.
- **Sem concorrência crítica nesta fatia:** o login não altera dados de negócio.

## Dependências e decisões em aberto

- Depende de E02-01.
- Sem decisões em aberto.
