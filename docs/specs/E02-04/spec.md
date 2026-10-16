# E02-04 — Emissão e consulta de convites

Fatia 4 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Só o administrador emite convites. Cada convite é individual, de uso único, vinculado a um e-mail, define o papel e vale por 24 horas. Esta fatia entrega o modelo de convite, a tela de emissão e consulta na área administrativa e o e-mail com o link. O uso do convite para cadastro fica na E02-05.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §3.1 | Somente o administrador emite. Convite individual, uso único, vinculado a um e-mail, validade fixa de 24 horas desde a emissão. Define o perfil (comprador ou fornecedor). Convite de fornecedor vinculado ao fornecedor já cadastrado. E-mail banido não se cadastra, mesmo com convite novo. Convite para e-mail já usado por outra conta não permite cadastro. Tokens imprevisíveis. |
| Especificação §12 | Notificação de convite: link, finalidade e expiração de 24h. |
| Especificação §13 | Admin: emissão e consulta de convites, inclusive vínculo ao fornecedor. |
| Especificação §14 | Convite: e-mail, papel, fornecedor vinculado, emissão, expiração e consumo. |
| Cenários §16 | 80 (emissão recusada para e-mail em uso, com variações). |
| Infraestrutura 4.11 | A emissão de convite para e-mail já associado a uma conta é recusada. |
| Infraestrutura 5 | `UNIQUE` em convites. |
| Infraestrutura 4.3 | Convenção de fronteira: no instante exato do limite de 24h, o prazo está encerrado (limite exclusivo). |

## Escopo

**Dentro:**

- Modelo `Convite` em `apps.contas`.
- Serviço `emitir_convite`.
- Tela `/administracao/convites/`, com formulário de emissão e lista.
- E-mail do convite.
- Auditoria da emissão.

**Fora:**

- Uso do convite, cadastro e consumo (E02-05). Cadastro com Google por convite (E02-07).
- Cancelamento ou revogação de convite: não previsto nos documentos. Um convite não usado simplesmente expira.
- Envio pelo SES e registro do resultado de entrega (E04).

## Regras

**Modelo `Convite`:**

| Campo | Regra |
|---|---|
| `email_normalizado` | normalizado por `normalizar_email`, com o mesmo `CHECK` de normalização da conta |
| `papel` | `comprador` ou `fornecedor`. `administrador` é recusado pelo modelo e por `CHECK` no banco |
| `fornecedor` | chave estrangeira para `Fornecedor` com `PROTECT`; obrigatória se, e só se, o papel é `fornecedor` (`CHECK`) |
| `token_hash` | SHA-256 em hexadecimal do token, `UNIQUE`. O token em texto nunca é gravado |
| `emitido_por` | chave estrangeira para `Conta` (o administrador), `PROTECT` |
| `emitido_em` | `agora()` |
| `expira_em` | `somar_horas(emitido_em, 24)` (E01-03), gravado e nunca recalculado |
| `consumido_em` | nulo até o consumo (E02-05) |
| `conta_criada` | chave estrangeira para `Conta`, nula até o consumo, `PROTECT` |

**Token:**

- É gerado com `secrets.token_urlsafe(32)`.
- O link é `<origem>/convite/<token>/`. A origem vem da requisição, ou de uma configuração equivalente se não houver requisição.
- O token aparece só no e-mail e nunca na tela, nos logs ou na auditoria.

**Situação exibida** (derivada, sem coluna):

| Situação | Condição |
|---|---|
| `consumido` | `consumido_em` preenchido |
| `expirado` | não consumido e `prazo_encerrado(agora(), expira_em)` |
| `pendente` | nos demais casos |

**Emissão (`emitir_convite(autor, email, papel, fornecedor=None) -> Convite`):**

- **Permissão:** só o administrador (`autor` com papel administrador). Outro autor levanta `PermissionDenied`.
- **Recusas**, com mensagem clara e sem gravar nada:
  - e-mail inválido (`EmailInvalido`);
  - e-mail em uso por qualquer conta, de qualquer papel, inclusive removida (`EmailEmUso`);
  - e-mail banido (`EmailBanidoErro`, nome ajustável);
  - papel fora de `comprador` e `fornecedor`;
  - papel `fornecedor` sem fornecedor, ou papel `comprador` com fornecedor.
- **Convites repetidos:** vários convites pendentes para o mesmo e-mail são permitidos. Os documentos não proíbem, e o consumo de um deles torna o e-mail usado, o que inutiliza os outros (E02-05).
- **Transação:** a gravação ocorre em `transaction.atomic`, junto com a auditoria `convite.emitir`. A auditoria tem autor administrador e alterações `{"convite": <id>, "papel": <papel>, "fornecedor": <id ou None>}`, sem o e-mail, que é dado pessoal mínimo.
- **E-mail:** é enviado com `transaction.on_commit`, para nunca sair e-mail de um convite que não foi gravado.
  - Se o envio falhar, o convite continua gravado. A tela mostra "Convite criado, mas o e-mail não pôde ser enviado. Emita um novo convite.", e o log registra a falha sem e-mail nem token.
  - O registro estruturado de entregas de notificação fica na E04.

**E-mail do convite** (especificação §12):

- **Destino:** o e-mail normalizado do convite.
- **Assunto:** em português.
- **Corpo:** o link, a finalidade (cadastro como comprador, ou como fornecedor com o nome do fornecedor) e a data e hora de expiração no fuso de America/Sao_Paulo (`no_fuso_da_operacao`).

**Tela `/administracao/convites/`** (protegida por `somente_administrador`):

- **Formulário:**
  - e-mail;
  - papel (comprador ou fornecedor);
  - fornecedor, escolhido entre os fornecedores existentes e obrigatório para o papel fornecedor.
- **Validação no servidor:** o servidor valida tudo de novo. Um `id` de fornecedor inexistente ou um papel adulterado no `POST` são recusados.
- **Lista:** convites do mais recente para o mais antigo, com:
  - e-mail;
  - papel;
  - fornecedor;
  - emissão e expiração no fuso de America/Sao_Paulo;
  - situação derivada;
  - para os consumidos, a conta criada.
- **Volume:** a lista não pagina nesta fatia, por causa da escala de 150 contas.

## Interfaces

- `apps/contas/models.py`: `Convite`, com a propriedade `situacao` e o método de classe `hash_do_token(token) -> str`.
- `apps/contas/convites.py`: `emitir_convite` e as exceções.
- `apps/contas/views.py`: `convites_administracao` (GET e POST).
- Templates: e-mail em texto (`.txt`) e tela.

## Invariantes

- Nenhum convite tem papel `administrador`.
- Nenhum token em texto é persistido.
- `expira_em - emitido_em` é sempre exatamente 24 horas.
- Nenhum e-mail de convite sai sem o convite gravado.

## Casos-limite e concorrência

- **Fronteira de expiração:** `expira_em − 1 ms` está pendente, `expira_em` exato está expirado e `expira_em + 1 ms` está expirado.
- **Banimento depois da emissão:** a emissão foi válida. A recusa ocorre no uso (E02-05).
- **Duas emissões simultâneas para o mesmo e-mail:** as duas são válidas (convites distintos), sem teste de corrida específico.

## Dependências e decisões em aberto

- Depende de E02-03 (`somente_administrador`).
- Sem decisões em aberto.
