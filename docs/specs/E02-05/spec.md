# E02-05 — Cadastro por convite

Fatia 5 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O convite é o único caminho de criação de contas de comprador e de fornecedor. Esta fatia entrega a página do link do convite e o cadastro com nome e senha. O consumo é único, validado no servidor e seguro contra tentativas simultâneas. O cadastro com Google a partir do convite reaproveita o mesmo serviço de consumo e fica na E02-07.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §3.1 | Uso único, vinculado a um e-mail, 24 horas desde a emissão. Expirado não permite cadastro. O perfil vem do convite e não pode ser escolhido nem alterado. Convite de fornecedor vinculado ao fornecedor. Comprador não precisa de novo convite para novas rodadas. E-mail banido não se cadastra. E-mail já usado por outra conta não permite cadastro. Token, expiração e consumo único validados no servidor, inclusive com duas tentativas simultâneas. |
| Especificação §3.2 | Cadastro inicial exige nome e e-mail. Comprovação de controle do e-mail. |
| Especificação §2 | E-mail exclusivo, contas de papéis diferentes independentes. |
| Cenários §16 | 1, 62, 80 e 81 (cadastro). |
| Infraestrutura 4.11 | O consumo de convite para e-mail já associado a uma conta é recusado. Banimento verificado no consumo do convite. A restrição do banco resolve corridas. |
| Testes técnicos | T-34 (fluxo completo). |

## Escopo

**Dentro:**

- Rota `/convite/<token>/`, com `GET` para a página e `POST` para o cadastro.
- Serviço `consumir_convite`, reutilizável pela E02-07.
- Criação da conta, do `EmailAddress` verificado e da sessão.
- Auditoria do cadastro.

**Fora:**

- Cadastro com Google (E02-07), que só exibe o botão na página quando aquela fatia existir.
- Perfil opcional (E02-09).

## Regras

**Validação do convite (`validar_convite(token) -> Convite`):**

1. Calcula o hash do token e busca o convite. Token inexistente é recusado.
2. Recusa se `consumido_em` está preenchido.
3. Recusa se `prazo_encerrado(agora(), expira_em)`.
4. Recusa se `email_banido(convite.email_normalizado)`.
5. Recusa se já existe conta com `convite.email_normalizado`.

As recusas levantam `ConviteInvalido` com um código interno (`inexistente`, `consumido`, `expirado`, `banido`, `email_em_uso`). Para o visitante, a página mostra sempre a mesma mensagem: "Este convite não é mais válido. Solicite um novo convite ao administrador." Para o administrador, a causa está na lista de convites (E02-04).

**Página (`GET /convite/<token>/`):**

- **Convite válido:** mostra:
  - o e-mail do convite, só para leitura;
  - a finalidade (comprador, ou fornecedor com o nome do fornecedor);
  - os campos `nome`, `senha` e `confirmação da senha`.
- **Convite inválido:** mostra a mensagem única, com status 410.
- **Visitante já autenticado:** a página não oferece o cadastro e mostra "Saia da conta atual para usar este convite.", com o botão de sair. Isso evita misturar a sessão de uma conta com a criação de outra (especificação §2, contas independentes).
- **Sem consumo:** o `GET` não consome o convite.

**Cadastro (`POST /convite/<token>/`) e o serviço `consumir_convite(token, nome, senha=None, *, metodo) -> Conta`:**

1. Em `transaction.atomic`, busca o convite pelo hash com `select_for_update` e repete todas as validações de `validar_convite` com o relógio do servidor.
2. Valida o nome (sem espaços nas pontas, entre 1 e 150 caracteres) e, no método senha, a senha com os validadores da E02-02 e a confirmação.
3. Cria a `Conta` com:
   - `email_normalizado`, `papel` e `fornecedor` **do convite**;
   - situação `ativa`;
   - a senha definida.

   Campos `email`, `papel` ou `fornecedor` enviados no `POST` são ignorados.
4. Cria o `EmailAddress` do allauth com o mesmo e-mail, verificado e primário. O uso do link enviado ao e-mail do convite comprova o controle do endereço (especificação §3.2).
5. Marca `consumido_em = agora()` e `conta_criada`.
6. Registra a auditoria `convite.consumir`, com autor igual à conta criada e alterações `{"convite": <id>, "conta": <id>, "papel": <papel>}`.
7. Fora da transação e depois do commit, autentica a conta na sessão (backend do allauth) e redireciona para `/inicio/`.

**Erros no cadastro:**

- **Validação** (nome ou senha): devolve o formulário com as mensagens e não consome o convite.
- **Convite inválido no momento do `POST`:** mensagem única, status 410 e nada criado.
- **Erro de integridade pela unicidade de `email_normalizado`:** acontece numa corrida com outro convite do mesmo e-mail. A transação inteira é desfeita, o convite não é consumido e a página mostra a mensagem única.

**Depois do cadastro:**

- O comprador entra nas próximas vezes pelos métodos de login, sem novo convite.
- Outros convites pendentes para o mesmo e-mail passam a ser recusados por `email_em_uso`.

## Interfaces

- `apps/contas/convites.py`: `validar_convite`, `consumir_convite`, `ConviteInvalido` (com `codigo`) e `MetodoCadastro` (`senha` nesta fatia; `google` na E02-07).
- `apps/contas/views.py`: `aceitar_convite`.
- `apps/contas/forms.py`: `FormularioCadastroPorConvite`.

## Invariantes

- Um convite cria no máximo uma conta.
- A conta criada tem exatamente o e-mail, o papel e o fornecedor do convite.
- Nenhuma conta nasce com e-mail banido ou já usado.
- Um convite consumido nunca volta a ficar pendente.

## Casos-limite e concorrência

- **Fronteira de 24h:** `expira_em − 1 ms` aceita, e `expira_em` exato e `expira_em + 1 ms` recusam. O teste usa a fixture `relogio` no `POST`, não só no `GET`.
- **Convite válido no `GET` e expirado no `POST`:** recusado.
- **Mesmo convite enviado duas vezes em paralelo:** uma conta e um consumo. O teste usa `executar_em_paralelo` e repete 20 vezes.
- **Dois convites com o mesmo e-mail normalizado** (um de comprador e outro de fornecedor, com e-mails `Ana@x.com` e ` ana@x.com ` na emissão), consumidos em paralelo: uma conta e uma recusa. O convite recusado continua não consumido (T-34).
- **Banimento entre a emissão e o uso:** recusado.

## Dependências e decisões em aberto

- Depende de E02-04 e de E02-02 (sessão e validadores de senha).
- Sem decisões em aberto.
