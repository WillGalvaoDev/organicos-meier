# E02-06 — Login por link de acesso

Fatia 6 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

A especificação exige "link de acesso por e-mail" como método de login. O django-allauth 65 oferece login por **código** (`LOGIN_BY_CODE`), que só funciona no mesmo navegador que pediu o código e que não é um link. A infraestrutura cita "link ou código". Pela precedência do AGENTS.md §2, vale a especificação funcional: esta fatia implementa um link de acesso próprio, que funciona em qualquer navegador, e mantém o login por código do allauth desligado (E02-02).

**Decisão técnica registrada:** link próprio em vez do código do allauth. A decisão não muda o comportamento comercial: é a forma de cumprir literalmente a §3.2. Detalhes de segurança:

- token aleatório, guardado só como hash;
- uso único;
- validade de 15 minutos;
- confirmação por `POST`, para que leitores automáticos de e-mail não consumam o link;
- mesma decisão de acesso dos outros métodos.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §3.2 | Link de acesso por e-mail. Todos os métodos respeitam a identidade autorizada e o bloqueio. |
| Especificação §2, §3.1 | E-mail banido não faz login por nenhum método. Conta removida bloqueada. |
| Cenários §16 | 2 (link não contorna suspensão nem banimento) e 58 (recusa por link). |
| Infraestrutura 2 | Link ou código por e-mail. Limite de requisições nas rotas de login. Admin com passkey obrigatória. |
| Infraestrutura 4.11 | Normalização no login por link. |
| Testes técnicos | T-24 (parte do link), T-37 (ponto do link). |

## Escopo

**Dentro:**

- Modelo `LinkDeAcesso` em `apps.contas`.
- Rota de pedido do link, `/entrar/link/`.
- Rota de uso do link, `/entrar/link/<token>/`, com `GET` para confirmar e `POST` para entrar.
- E-mail do link.
- Limite de pedidos.

**Fora:**

- Login por código do allauth, que continua desligado.
- Link de acesso para o administrador: recusado por `verificar_acesso`.

## Regras

**Modelo `LinkDeAcesso`:**

| Campo | Regra |
|---|---|
| `conta` | chave estrangeira para `Conta`, `PROTECT` |
| `token_hash` | SHA-256 em hexadecimal, `UNIQUE` |
| `criado_em` | `agora()` |
| `expira_em` | `criado_em + 15 minutos` |
| `usado_em` | nulo até o uso |

**Pedido (`POST /entrar/link/`, campo `email`):**

1. Normaliza o e-mail. Um e-mail inválido mostra erro de formulário, o único caso com resposta diferente.
2. Responde sempre com a mesma página: "Se houver uma conta para este e-mail, enviaremos um link de acesso válido por 15 minutos."
3. Cria o link e envia o e-mail só se:
   - existe conta com esse e-mail;
   - `verificar_acesso(conta, email, Metodo.link)` não recusa, o que exclui administrador, banido e removido;
   - o limite de pedidos não foi atingido.
4. **Limite:** no máximo 3 links criados por conta em 15 minutos, contados na tabela `LinkDeAcesso` pela janela de `criado_em`: entram na contagem os links com `criado_em > agora() − 15 min`. No instante exato de 15 minutos depois de um pedido, esse pedido já sai da contagem. Acima disso, a resposta é a mesma e nenhum link nem e-mail é gerado. Os limites por IP do allauth e da Cloudflare (infraestrutura 2) continuam valendo.
5. O e-mail é enviado com `transaction.on_commit`. O corpo tem o link `/entrar/link/<token>/` e a validade em minutos, sem o horário.

**Uso:**

- **`GET /entrar/link/<token>/`:** mostra o botão "Entrar". Não autentica e não consome. Se o link for inválido, mostra a mensagem única "Este link de acesso não é mais válido. Peça um novo.", com status 410.
- **`POST /entrar/link/<token>/`**, em `transaction.atomic`:
  1. Busca o link pelo hash com `select_for_update`.
  2. Recusa, com a mensagem única e status 410, se:
     - o link não existe;
     - `usado_em` está preenchido;
     - `prazo_encerrado(agora(), expira_em)`;
     - `verificar_acesso` recusa. A situação e o banimento são verificados de novo no uso.
  3. Marca `usado_em = agora()`.
  4. Depois do commit, autentica a conta na sessão e redireciona para `/inicio/`.
- **Links independentes:** usar um link não invalida outros links pendentes da mesma conta. Cada um tem uso único e prazo próprio.

**Sessão já autenticada:** um link usado por quem já está autenticado em outra conta encerra a sessão anterior e autentica a conta do link. Isso segue o comportamento padrão do `login()` do Django, que troca a sessão.

## Interfaces

- `apps/contas/models.py`: `LinkDeAcesso`.
- `apps/contas/link_de_acesso.py`: `pedir_link(email) -> None` e `usar_link(token) -> Conta` (levanta `LinkInvalido`).
- `apps/contas/views.py`: `pedir_link_de_acesso` e `usar_link_de_acesso`.
- A tela `/entrar/` ganha o link "Receber link de acesso por e-mail".

## Invariantes

- Um link autentica no máximo uma vez.
- Nenhum link é criado ou enviado para administrador, conta removida ou e-mail banido.
- A resposta do pedido não revela se o e-mail tem conta.
- Nenhum token em texto é persistido.

## Casos-limite e concorrência

- **Fronteira de 15 minutos:** `expira_em − 1 ms` aceita, e `expira_em` exato e `expira_em + 1 ms` recusam.
- **Remoção ou banimento entre o pedido e o uso:** o uso é recusado.
- **Suspensão entre o pedido e o uso:** o uso é aceito, porque a conta suspensa entra (especificação §2).
- **Mesmo link enviado por dois `POST` em paralelo:** um sucesso e uma recusa. O teste usa `executar_em_paralelo` e repete 20 vezes.

## Dependências e decisões em aberto

- Depende de E02-02.
- Sem decisões em aberto.
