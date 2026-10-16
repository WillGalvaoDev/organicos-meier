# E02-07 — Login e cadastro com Google

Fatia 7 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O login com Google precisa respeitar a identidade de e-mail autorizada. O e-mail do Google só acessa a conta com o mesmo e-mail normalizado e nunca cria uma conta fora do fluxo de convite. Esta fatia entrega:

- o login com Google para contas existentes;
- o cadastro com Google a partir de um convite válido, usando o mesmo serviço de consumo da E02-05.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §3.2 | Conta Google como método. Login por Google não cria conta fora do fluxo de convite. O e-mail do Google só acessa a conta com o mesmo e-mail normalizado. Evitar associação insegura entre métodos de login. |
| Especificação §2 | E-mail exclusivo, inclusive no login com Google. |
| Especificação §3.1 | E-mail banido não faz login por nenhum método. Convite usado com outro e-mail não cadastra. |
| Cenários §16 | 1 (outro e-mail), 2, 58 e 82. |
| Infraestrutura 2 | Adaptador próprio recusa cadastros sem convite válido ou com e-mail banido, inclusive pelo Google. |
| Infraestrutura 4.11 | O adaptador associa o login somente à conta com o mesmo `email_normalizado`. Nunca cria uma segunda conta e só cria a primeira com convite válido. |
| Testes técnicos | T-24 (parte do Google), T-35, T-37 (ponto do Google). |

## Escopo

**Dentro:**

- Instalação de `allauth.socialaccount` e do provedor `allauth.socialaccount.providers.google`.
- Credenciais do Google lidas do ambiente (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`):
  - obrigatórias em `prod.py`;
  - opcionais em `dev.py`, com o botão escondido se faltarem;
  - valores fictícios em `test.py`.
- Adaptador `apps.contas.adaptadores.AdaptadorContaSocial`.
- Botão "Entrar com Google" em `/entrar/`.
- Botão "Cadastrar com Google" na página do convite (E02-05).
- Formulário de conclusão do cadastro com Google: nome, com o valor do Google já preenchido.

**Fora:**

- Outros provedores sociais.
- Gerenciar ou desconectar contas sociais pelo usuário (não previsto).
- Configurar o projeto no Google Cloud, que é tarefa de homologação.

## Regras

**Dados aceitos do Google:**

- O e-mail vem dos dados devolvidos pelo provedor.
- Se o e-mail estiver ausente ou não estiver marcado como verificado pelo Google (`email_verified` diferente de verdadeiro), o login é recusado.
- O e-mail do Google passa por `normalizar_email`, e o resultado é chamado `e` abaixo.

**Decisão no retorno do Google** (`pre_social_login` e métodos de signup do adaptador), na ordem:

1. **Conta social já vinculada a uma conta `C`:** exige `C.email_normalizado == e`. Se o e-mail do Google mudou, o login é recusado e o vínculo não é alterado. Em seguida, aplica `verificar_acesso(C, e, Metodo.google)`.
2. **Sem vínculo, mas existe uma conta `C` com `email_normalizado == e`:** aplica `verificar_acesso(C, e, Metodo.google)`, vincula a conta social a `C` e entra. Nunca cria outra conta (cenário 82, T-35).
3. **Sem conta com `e`:**
   - Sem convite pendente na sessão: recusa sem criar nada.
   - Com convite pendente: chama `validar_convite(token)` (E02-05) e exige `convite.email_normalizado == e`. Se o e-mail do Google for diferente, recusa (cenário 1, "outro e-mail"). Se tudo bater, segue para o formulário de conclusão.
4. **E-mail banido em qualquer caso:** recusado (`verificar_acesso`, ou `validar_convite` no caso 3).

**Recusa:**

- Redireciona para `/entrar/` com a mensagem única "Não foi possível entrar com essa conta Google.".
- Não cria `Conta`, `SocialAccount` nem `EmailAddress`.
- Remove da sessão o convite pendente.

**Convite pendente na sessão:**

- O botão "Cadastrar com Google" da página do convite envia `POST /convite/<token>/google/`.
- A view valida o convite com `validar_convite`, guarda o token na sessão (chave `convite_pendente`) e inicia o login do Google.
- O token sai da sessão no fim do cadastro, numa recusa ou num novo login.
- Se o convite for inválido, a view mostra a mensagem única da E02-05, com status 410, sem ir ao Google.

**Conclusão do cadastro com Google:**

- **Sem conta automática:** `is_auto_signup_allowed` devolve `False`. O usuário confirma o nome num formulário, já preenchido com o nome do Google e com as mesmas regras de nome da E02-05.
- **Envio do formulário:**
  1. Em uma transação, chama `consumir_convite(token, nome, metodo=MetodoCadastro.google)`. O serviço repete todas as validações com `select_for_update` e cria a conta sem senha utilizável, com o `EmailAddress` verificado.
  2. Vincula a conta social à conta criada.
  3. Depois do commit, entra.
- **Falha no consumo** (convite consumido, expirado ou outra causa): recusa, sem nenhuma conta nem conta social.
- **Login por senha:** a conta criada por Google não tem senha utilizável e pode defini-la pela recuperação de acesso (E02-02).

**`is_open_for_signup` (social):** devolve `True` só quando há convite pendente válido na sessão para o mesmo `e`.

**Testes sem rede:**

- O retorno do Google é simulado montando o `SocialLogin` do allauth (`SocialAccount` com `provider="google"`, `uid` e `extra_data` com `email`, `email_verified` e `name`).
- O `SocialLogin` é levado pelo fluxo do allauth por sua API de conclusão de login social. O implementador registra no `review.md` a função usada, válida para o allauth 65.19.7.
- O teste não faz chamadas HTTP ao Google e não substitui o adaptador do projeto.

## Interfaces

- `apps/contas/adaptadores.py`: `AdaptadorContaSocial`, em `SOCIALACCOUNT_ADAPTER`.
- `apps/contas/views.py`: `cadastrar_com_google(token)`.
- `apps/contas/forms.py`: `FormularioConclusaoGoogle`.
- `apps/contas/convites.py`: `MetodoCadastro.google`.

## Invariantes

- Nenhuma conta é criada pelo Google sem convite válido do mesmo e-mail normalizado.
- Uma conta social só autentica a conta cujo e-mail normalizado é igual ao e-mail atual do Google.
- Nenhuma segunda conta é criada para um e-mail já usado.

## Casos-limite e concorrência

- **E-mail do Google com maiúsculas diferentes** das da conta: entra na conta (T-35).
- **Alias com `+` de um e-mail banido:** é outro endereço e segue as regras normais (cenário 59).
- **Convite consumido por senha enquanto o usuário está no Google:** a conclusão é recusada, porque `consumir_convite` usa `select_for_update`, e a concorrência do consumo já está coberta na E02-05.
- **Administrador:** recusado pelo Google em qualquer caso.
- **Conta suspensa:** entra.

## Dependências e decisões em aberto

- Depende de E02-05 (serviço de consumo) e E02-02 (`verificar_acesso`).
- Sem decisões em aberto.
