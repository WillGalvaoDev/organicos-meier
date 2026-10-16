# E02-10 — Separação de papéis e política de acesso por rota

Fatia 10 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

As restrições de papel precisam valer no servidor, inclusive em chamadas diretas. A conta de fornecedor nunca compra, a conta de comprador nunca acessa a área de fornecedor e a pessoa com as duas contas vê em cada uma só os dados dela. As rotas de compra e de fornecedor ainda não existem: elas nascem na E05, na E08 e na E13. Por isso, esta fatia entrega:

1. os decoradores de papel que essas rotas vão usar;
2. uma **política de acesso obrigatória por rota**, com um teste que falha se qualquer rota do projeto, atual ou futura, não declarar a sua;
3. a verificação final do T-37: todo ponto de comparação de e-mail passa por `normalizar_email`.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Restrições verificadas no servidor, inclusive em chamadas diretas e exportações. Ocultar controles não basta. Conta de fornecedor não compra. Sem permissões nem dados cruzados entre as contas da mesma pessoa. Comprador suspenso não adiciona interesses. |
| Especificação §15 | Autorização por perfil, usuário e fornecedor em toda leitura e escrita. |
| Cenários §16 | 61 e 62 (a conta de comprador não ganha o perfil de fornecedor). |
| Infraestrutura 4.11 | As rotas de compra exigem o papel de comprador, e as de fornecedor exigem o vínculo com o fornecedor, sempre verificado no servidor. `normalizar_email` em todos os fluxos, com testes que garantem que nenhum fluxo compara e-mails sem passar por ela. |
| Testes técnicos | T-25, T-37. |

## Escopo

**Dentro:**

- Decoradores e mixins em `apps/contas/permissoes.py`:
  - `exige_comprador`;
  - `exige_comprador_ativo`;
  - `exige_fornecedor`;
  - `publica`;
  - `exige_login`.
- Reaproveitamento de `somente_administrador` (E02-03).
- Registro da política de cada view, num atributo da view (ver Regras).
- Teste de varredura das rotas.
- Rotas só de teste no app `tests.apoio`, que simulam carrinho, pagamento e área do fornecedor, para o T-25.
- Teste de varredura do T-37.
- Ajuste das rotas existentes da E02 para declararem política.

**Fora:**

- Rotas reais de carrinho, pagamento e área do fornecedor (E05, E08 e E13), que usam estes decoradores.
- Isolamento de dados entre fornecedores dentro das consultas. Cada etapa filtra pelo `request.fornecedor_vinculado` fornecido aqui, com testes próprios (especificação §2, cenários da E13).

## Regras

**Políticas** (valores de `Politica`):

| Política | Quem passa | Recusa |
|---|---|---|
| `publica` | todos | — |
| `autenticada` | qualquer conta autenticada | anônimo: redirecionamento para `/entrar/` |
| `comprador` | papel comprador, `ativa` ou `suspensa` (consulta) | anônimo: redirecionamento; outro papel: 403 |
| `comprador_ativo` | papel comprador com `pode_adicionar_interesse` (E02-08) | anônimo: redirecionamento; outro papel ou comprador suspenso: 403 |
| `fornecedor` | papel fornecedor com fornecedor vinculado; expõe `request.fornecedor_vinculado` | anônimo: redirecionamento; outro papel: 403 |
| `administrador` | regra de `somente_administrador` (E02-03) | conforme a E02-03 |

**Ordem das verificações:**

- As recusas ocorrem antes da view, também para `POST`, `PUT`, `PATCH` e `DELETE`, com ou sem cabeçalho `HX-Request`.
- O 403 não revela dados da rota.

**Declaração obrigatória:**

- Cada decorador grava a política num atributo da função da view, por exemplo `view.politica_de_acesso`. Em views baseadas em classe, o atributo fica na view resultante de `as_view()`.
- As views de bibliotecas (allauth e arquivos estáticos em desenvolvimento) são declaradas numa lista explícita `POLITICAS_DE_TERCEIROS` em `apps/contas/permissoes.py`. Cada entrada leva o nome da rota e a política.
- A lista não aceita curingas além de um prefixo de namespace do allauth, cada um com justificativa em comentário.

**Teste de varredura das rotas:**

- Percorre recursivamente o `URLResolver` do projeto, com as configurações de teste, e falha listando cada rota sem política. Também falha se uma entrada de `POLITICAS_DE_TERCEIROS` apontar para uma rota inexistente.
- Assim, toda rota futura sem política quebra o CI.

**Rotas de teste (só em `tests.apoio`, registradas apenas pelas configurações de teste):**

| Rota | Política |
|---|---|
| `/teste/carrinho/` (`GET` e `POST`) | `comprador_ativo` |
| `/teste/pagamento/` (`POST`) | `comprador_ativo` |
| `/teste/meus-pedidos/` (`GET`) | `comprador` |
| `/teste/fornecedor/painel/` (`GET`) | `fornecedor`; devolve o `id` de `request.fornecedor_vinculado` |

As rotas existem só para provar os decoradores e nunca entram em `config/urls.py` fora dos testes. Seguem o mesmo padrão do app `tests.apoio` da E01-02.

**T-37 (varredura da normalização):**

1. **Propriedade (hypothesis):** para e-mails gerados com variações de maiúsculas e espaços nas pontas, cada fluxo trata a variação como o mesmo endereço:
   - emissão de convite (recusa por uso e por banimento);
   - consumo de convite;
   - login por senha;
   - pedido de link;
   - Google;
   - recuperação de acesso;
   - unicidade da conta;
   - `email_banido`.

   Os aliases com `+` continuam distintos.
2. **Estática:** um teste lê o código-fonte de `apps/` (AST) e falha se encontrar:
   - consultas com `email__iexact` ou `email_normalizado__iexact`;
   - `.lower()` ou `.casefold()` sobre expressões cujo nome contenha `email`, fora de `apps/contas/emails.py`;
   - consultas de `Conta`, `Convite` ou `EmailBanido` por `email_normalizado` com um valor que não passe por `normalizar_email` na mesma função. Esse item é verificado por revisão, porque a análise estática completa não é viável. O teste cobre os dois primeiros itens, e o terceiro fica no `review.md`.

**Cenário 61:** a pessoa com conta de comprador e conta de fornecedor:

- em cada sessão, `/inicio/` e `/perfil/` mostram só a conta da sessão;
- a conta de fornecedor recebe 403 nas rotas de compra de teste, inclusive por `POST` direto;
- a conta de comprador recebe 403 no painel de fornecedor de teste.

**Cenário 62:** não existe rota nem serviço que mude o papel de uma conta. O teste verifica:

- que `Conta.papel` não é editável por nenhum formulário do projeto;
- que uma tentativa por `POST` no perfil é ignorada (E02-09, A-16);
- que uma atualização de `papel` por SQL direto é recusada pelo banco.

Para isso, esta fatia acrescenta uma trigger que recusa `UPDATE` da coluna `papel` em `Conta` (a imutabilidade do papel). Ela usa uma operação de migração própria, simples, no mesmo estilo da E01-04.

## Interfaces

- `apps/contas/permissoes.py`:
  - `Politica`;
  - os decoradores `publica`, `exige_login`, `exige_comprador`, `exige_comprador_ativo` e `exige_fornecedor`;
  - os mixins equivalentes para views baseadas em classe;
  - `POLITICAS_DE_TERCEIROS`;
  - `politica_da_view(callback) -> Politica | None`.
- Migração com a trigger de imutabilidade de `papel`.
- `tests/apoio/urls.py` e `tests/apoio/views.py` (rotas de teste).

## Invariantes

- Toda rota do projeto tem uma política declarada, garantida pelo CI.
- Nenhuma conta muda de papel depois de criada.
- A conta de fornecedor nunca passa por `exige_comprador` nem por `exige_comprador_ativo`, e a conta de comprador nunca passa por `exige_fornecedor`.

## Casos-limite e concorrência

- **Comprador suspenso:** passa em `comprador` e é recusado em `comprador_ativo`.
- **Conta removida:** é barrada antes, pelo middleware da E02-08.
- **Fornecedor sem vínculo:** impossível pela restrição da E02-01. O decorador ainda assim recusa com 403, como defesa em profundidade, verificado com um objeto em memória.
- **Sem concorrência crítica.**

## Dependências e decisões em aberto

- Depende de todas as fatias anteriores da E02, porque varre as rotas e os fluxos delas.
- Sem decisões em aberto.
