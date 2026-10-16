# E02-08 — Moderação: suspensão, reversão, remoção e banimento

Fatia 8 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O administrador modera usuários de três formas:

- suspende, de forma reversível;
- reverte a suspensão;
- remove, de forma definitiva, banindo o e-mail.

O banimento invalida na hora todas as sessões daquele e-mail e impede novos acessos por qualquer método. Esta fatia entrega a tela de usuários, os serviços de moderação, o encerramento de sessões e o middleware que recusa contas sem acesso.

Os efeitos da suspensão sobre interesses e pedidos (especificação §2) dependem de modelos das etapas E05 e E08. Por isso, esta fatia entrega o ponto de extensão (sinais), e essas etapas implementam os efeitos.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Suspenso: consulta listas e pedidos pagos; não adiciona interesses; interesses e pedidos não pagos são removidos ou cancelados; suspensão reversível. Removido: acesso bloqueado definitivamente, e-mail banido para login e novos cadastros, histórico preservado, pedidos pagos não apagados. Banimento só por e-mail, só do endereço banido; sessões ativas invalidadas; históricos preservados. |
| Especificação §13 | Admin: gestão de usuários, suspensão e reversão, remoção com banimento de e-mail. Histórico de ações relevantes. |
| Especificação §14 | E-mail banido com autor e momento. Invalida as sessões ativas daquele e-mail. |
| Cenários §16 | 19 (parte de acesso), 20, 58, 59, 60, 81, 83 e 84. |
| Infraestrutura 4.11 | Ao banir, na mesma transação, a conta é marcada e todas as sessões ativas dela são apagadas. Um middleware recusa qualquer requisição autenticada de conta banida. A suspensão é estado da conta e não entra na tabela de banimento. |
| Testes técnicos | T-24 (sessão encerrada), T-36. |

## Escopo

**Dentro:**

- Serviços `suspender`, `reativar` e `remover` em `apps/contas/moderacao.py`.
- Sinais `conta_suspensa` e `conta_removida`.
- Tela `/administracao/usuarios/`.
- Middleware `RecusaContaSemAcesso`.
- Encerramento de sessões por conta.
- Auditoria das ações.

**Fora:**

- Efeitos da suspensão sobre interesses e pedidos não pagos: remoção de interesses (E05) e cancelamento de pedidos não pagos (E08). Esses efeitos se conectam a `conta_suspensa` nas suas etapas.
- Restrição do comprador suspenso em rotas de compra: o predicado entra aqui e o uso na E02-10 e na E05.
- Suspensão de conta de fornecedor, que não está prevista (ver "Decisões em aberto").
- Banir um e-mail sem conta, que não está previsto. O banimento nasce da remoção.

## Regras

**Quem pode ser moderado:**

| Ação | Alvo permitido | Situação exigida |
|---|---|---|
| `suspender` | comprador | `ativa` |
| `reativar` | comprador | `suspensa` |
| `remover` | comprador ou fornecedor | `ativa` ou `suspensa` |

- **Outros alvos recusados:** o administrador nunca é alvo (`ModeracaoInvalida`). Qualquer outra combinação de papel e situação também é recusada com `ModeracaoInvalida`, sem efeito e sem auditoria.
- **Autor:** sempre o administrador. Outro autor levanta `PermissionDenied`.

**Serviços**, todos em `transaction.atomic`, com `select_for_update` da conta-alvo e revalidação da situação depois da trava:

- **`suspender(autor, conta)`:**
  - grava a situação `suspensa`;
  - registra a auditoria `conta.suspender`;
  - envia `conta_suspensa` dentro da transação, para que os efeitos das etapas futuras sejam atômicos com a suspensão.

  Não encerra sessões, porque o suspenso continua entrando.
- **`reativar(autor, conta)`:**
  - grava a situação `ativa`;
  - registra a auditoria `conta.reativar`.

  Não restaura nada (cenário 19: a reversão não restaura interesses antigos).
- **`remover(autor, conta)`:**
  1. grava a situação `removida`;
  2. insere `EmailBanido(email_normalizado=conta.email_normalizado, banido_por=autor)`;
  3. apaga todas as sessões da conta: os registros do `usersessions` e as linhas correspondentes de `django_session`;
  4. registra a auditoria `conta.remover`;
  5. envia `conta_removida` dentro da transação.

  A conta, seus vínculos (convite, conta social) e o histórico não são apagados.

**Auditoria:** autor administrador; alterações `{"conta": <id>, "situacao_anterior": ..., "situacao_nova": ...}`, sem e-mail.

**Middleware `RecusaContaSemAcesso`:**

- Fica depois do `AuthenticationMiddleware` e do `AccountMiddleware`.
- **Verificação:** a cada requisição autenticada, relê do banco a situação da conta e consulta `email_banido`.
- **Situação `removida` ou e-mail banido:**
  - encerra a sessão (`logout`);
  - em `GET`, redireciona para `/entrar/` com a mensagem "Sua sessão foi encerrada.";
  - nos demais métodos, devolve 403;
  - a view nunca é executada.
- **Por que reler do banco:** cobre sessões criadas durante uma corrida com a remoção e sessões que o apagamento não alcançou (infraestrutura 4.11).

**Predicado para as etapas seguintes:** `Conta.pode_adicionar_interesse`, verdadeiro só para comprador `ativa`. É usado pela E02-10 e pela E05.

**Tela `/administracao/usuarios/`** (`somente_administrador`):

- **Lista:** compradores e fornecedores, com nome, e-mail, papel, fornecedor vinculado e situação.
- **Ações:** botões conforme a tabela "Quem pode ser moderado", cada um por `POST` com CSRF.
- **Remoção:** pede confirmação numa página intermediária que avisa: "A remoção é definitiva e bane o e-mail."
- **Mensagens:** as recusas do serviço aparecem como mensagem, sem erro 500.

## Interfaces

- `apps/contas/moderacao.py`: `suspender`, `reativar`, `remover`, `ModeracaoInvalida`, e os sinais `conta_suspensa` e `conta_removida` (`django.dispatch.Signal`, com o argumento `conta`).
- `apps/contas/sessoes.py`: `encerrar_sessoes(conta) -> int`, que devolve quantas sessões foram encerradas.
- `apps/contas/middleware.py`: `RecusaContaSemAcesso`.
- `apps/contas/views.py`: `usuarios_administracao` e `confirmar_remocao`.

## Invariantes

- Toda conta removida tem `EmailBanido` do seu e-mail, gravado na mesma transação.
- Nenhuma requisição de conta removida ou banida chega a uma view.
- O banimento afeta só o endereço exato normalizado. Aliases e outras contas da mesma pessoa não são afetados.
- Moderação nunca apaga conta nem histórico.

## Casos-limite e concorrência

- **Duas remoções simultâneas da mesma conta:** uma conclui e a outra recebe `ModeracaoInvalida` (já removida). Resulta em um `EmailBanido` e uma auditoria. O teste usa `executar_em_paralelo` e repete 10 vezes.
- **Suspensão e remoção simultâneas:** a situação final é `removida`, com banimento. Fica uma auditoria de cada ação concluída, ou só a da remoção, se a suspensão encontrar a conta já removida.
- **Requisição em andamento durante a remoção:** a próxima requisição é recusada pelo middleware.
- **Falha durante a remoção** (por exemplo, erro forçado ao apagar sessões): a transação é desfeita, a situação não muda e o `EmailBanido` não é gravado.

## Dependências e decisões em aberto

- Depende de E02-03 (área administrativa) e E02-02 (`usersessions`).
- **D-1 (não bloqueia):** a especificação define suspensão só para comprador. Para fornecedor, ela não diz se existe suspensão nem quais seriam os efeitos. Esta fatia não oferece suspensão de fornecedor (só remoção) e não cria regra. Se o responsável quiser suspender fornecedores, a decisão precisa definir o efeito sobre o acesso e o vínculo.
