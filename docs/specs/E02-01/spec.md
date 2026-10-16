# E02-01 — Contas, papéis e e-mail normalizado

Fatia 1 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Todas as fatias da E02 dependem de uma conta própria do projeto, com papel único, situação de acesso e e-mail normalizado exclusivo. Esta fatia cria:

- o modelo de conta (`AUTH_USER_MODEL`);
- a função única de normalização de e-mail;
- a tabela de e-mails banidos;
- a entidade mínima de fornecedor, necessária para o vínculo da conta de fornecedor;
- o comando que cria o único administrador.

Esta fatia não tem rotas nem telas.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §1 | Um único administrador. |
| Especificação §2 | Papéis comprador, fornecedor e administrador. Contas de comprador e fornecedor independentes. E-mail exclusivo por conta, qualquer que seja o papel. Normalização: maiúsculas/minúsculas e espaços nas pontas, sem aliases. Suspensão reversível; remoção definitiva, com banimento do e-mail. |
| Especificação §14 | Conta e perfil: e-mail normalizado exclusivo, papel único por conta, status de acesso. E-mail banido: endereço normalizado, autor e momento. |
| Especificação §15 | Remoção de conta não apaga fatos operacionais. |
| Cenários §16 | 80 (unicidade com variações), 84 (aliases distintos). |
| Infraestrutura 4.11 | Uma conta, um papel. `normalizar_email` única. Coluna `email_normalizado` com `UNIQUE` cobrindo todos os papéis. Tabela de banimento com `email_normalizado` único. Suspensão é estado da conta, fora da tabela de banimento. |
| Infraestrutura 5 | `UNIQUE` no `email_normalizado` das contas e na tabela de banimento. |
| Testes técnicos | T-34 (parte do banco), T-37 (propriedade da função). |

## Escopo

**Dentro:**

- App `apps.contas` com o modelo `Conta`, registrado como `AUTH_USER_MODEL = "contas.Conta"`.
- Função `normalizar_email` e exceção `EmailInvalido`.
- Modelo `EmailBanido`, só de inserção (mecanismo da E01-04), e a consulta `email_banido`.
- App `apps.fornecedores` com o modelo mínimo `Fornecedor`, que tem só `nome`. A E03 acrescenta os demais campos e a gestão pelo administrador.
- Comando `manage.py criar_administrador`.
- Fábricas de teste (factory-boy) para `Conta` e `Fornecedor`, em `tests/fabricas.py`.
- Remoção de `django.contrib.admin` de `INSTALLED_APPS`.
- Ajuste do auxiliar de criação de usuário nos testes da E01-04 (ver "Compatibilidade").
- `README.md`: instrução para recriar o banco local.

**Fora:**

- Login, sessões, convites, telas e moderação (E02-02 a E02-10).
- Campos de perfil opcionais: telefone, avatar e consentimento de WhatsApp (E02-09).
- Campos de negócio do fornecedor e sua gestão (E03).

## Regras

**Normalização (`normalizar_email(texto: str) -> str`):**

1. Remove espaços em branco no início e no fim, com `str.strip()`.
2. Converte para minúsculas com `str.lower()`.
3. Valida o resultado com o `EmailValidator` do Django. Se for inválido ou vazio, levanta `EmailInvalido`.
4. Não altera aliases: `+` e pontos permanecem.
5. Recebe só `str`. Qualquer outro tipo levanta `EmailInvalido`.
6. É idempotente: `normalizar_email(normalizar_email(x)) == normalizar_email(x)`.

**Conta:**

- **Herança:** `AbstractBaseUser`, sem `PermissionsMixin`. O projeto não usa o sistema de permissões nem o admin do Django.
- **Campos:**
  - `email_normalizado`: único; é o `USERNAME_FIELD` e o `EMAIL_FIELD`;
  - `nome`: obrigatório, sem espaços nas pontas, entre 1 e 150 caracteres;
  - `papel`: `comprador`, `fornecedor` ou `administrador`;
  - `situacao`: `ativa`, `suspensa` ou `removida`, com padrão `ativa`;
  - `fornecedor`: chave estrangeira para `Fornecedor` com `PROTECT`, preenchida só para o papel fornecedor;
  - `criada_em`: preenchido por `agora()` (E01-03);
  - os campos de `AbstractBaseUser`.
- **`is_active`:** é uma propriedade, verdadeira quando `situacao != removida`. A conta suspensa continua ativa para autenticação, porque o comprador suspenso pode consultar listas e pedidos pagos (especificação §2).
- **E-mail no salvamento:** sempre passa por `normalizar_email`.
- **Senha inicial:** inutilizável (`set_unusable_password`). A senha é definida no cadastro por convite (E02-05) ou pela recuperação de acesso (E02-02).
- **Remoção:** a conta nunca é apagada pela aplicação. A remoção é uma mudança de situação (E02-08).

**Restrições no banco (Postgres):**

| Nome sugerido | Regra |
|---|---|
| `conta_email_unico` | `UNIQUE (email_normalizado)` |
| `conta_email_ja_normalizado` | `CHECK (email_normalizado = lower(btrim(email_normalizado)) AND email_normalizado <> '')` |
| `conta_papel_valido` | `papel IN ('comprador','fornecedor','administrador')` |
| `conta_situacao_valida` | `situacao IN ('ativa','suspensa','removida')` |
| `conta_fornecedor_vinculado` | `(papel = 'fornecedor') = (fornecedor_id IS NOT NULL)` |
| `conta_administrador_unico` | índice único parcial sobre `papel` onde `papel = 'administrador'` |
| `conta_administrador_ativo` | `papel <> 'administrador' OR situacao = 'ativa'` |

A aplicação verifica a unicidade antes de gravar, para dar mensagem clara (`EmailEmUso`). A restrição do banco resolve as corridas.

**E-mail banido:**

- **Modelo:** `EmailBanido(RegistroSoInsercao)`, com a trigger da E01-04 instalada na tabela.
- **Campos:**
  - `email_normalizado`: único, com o mesmo `CHECK` de normalização da conta;
  - `banido_em`: preenchido por `agora()`;
  - `banido_por`: chave estrangeira para `Conta` com `PROTECT`. O administrador nunca é removido.
- **Banimento definitivo:** a tabela não aceita alteração nem exclusão.
- **Consulta:** `email_banido(texto: str) -> bool` normaliza a entrada e consulta a tabela. Um texto que não é e-mail válido devolve `False`, sem exceção, para não interromper fluxos de recusa.

**Fornecedor (mínimo):** `Fornecedor` tem só `nome`, obrigatório, entre 1 e 150 caracteres. Não há telas nem regras de negócio nesta fatia.

**Comando `criar_administrador --email <e-mail> --nome <nome>`:**

- Cria a conta com papel `administrador`, situação `ativa` e senha inutilizável.
- Cria também o `EmailAddress` do django-allauth verificado e primário, mas só depois que o allauth estiver instalado (E02-02). Nesta fatia, o comando só cria a conta. A E02-02 acrescenta esse passo e o teste correspondente.
- Recusa com mensagem e código de saída diferente de zero, sem criar nada, quando:
  - já existe administrador;
  - o e-mail é inválido;
  - o e-mail já está em uso;
  - o e-mail está banido.
- Registra a auditoria `conta.criar_administrador`, com autor `SISTEMA` e alterações `{"conta": <id>}`.
- Não recebe senha por argumento nem por variável de ambiente.

**Erros:** `EmailInvalido` e `EmailEmUso` ficam em `apps.contas`, com mensagens em português que não repetem o e-mail.

## Compatibilidade

- **Testes da E01-04:** usam `get_user_model().objects.create_user(username=...)`, que deixa de existir com o novo modelo. O implementador troca **só a criação do usuário** desses testes (`tests/tecnicos/test_nucleo_auditoria.py`, linhas 22 e 167) por `ContaFactory`, sem alterar nenhuma asserção. A troca é autorizada por esta especificação e precisa ser citada no `review.md`.
- **Auditoria:** `apps/nucleo/auditoria.py` usa `get_user_model()` e continua funcionando sem alteração.
- **Banco local:** a troca do `AUTH_USER_MODEL` exige um banco local novo. O CI e o banco de testes já são criados do zero. O `README.md` ganha a instrução `docker compose down -v` seguida de `docker compose up -d db` e `migrate`.

## Interfaces

- `apps/contas/emails.py`: `normalizar_email`, `EmailInvalido`, `email_banido`.
- `apps/contas/models.py`: `Conta`, `EmailBanido`, `Papel` e `Situacao` (`TextChoices`), `EmailEmUso`.
- `apps/fornecedores/models.py`: `Fornecedor`.
- `apps/contas/management/commands/criar_administrador.py`.
- `tests/fabricas.py`: `ContaFactory` (comprador por padrão, com `fornecedor`, `administrador` e `suspensa` como *traits*) e `FornecedorFactory`.

## Invariantes

- Nenhum e-mail é gravado em `Conta` ou `EmailBanido` sem estar normalizado. O `CHECK` do banco garante isso, inclusive por SQL direto.
- Existe no máximo um administrador, e ele está sempre ativo.
- Conta de fornecedor sempre tem fornecedor vinculado, e as demais nunca têm.
- `EmailBanido` nunca é alterado nem apagado.

## Casos-limite e concorrência

- Dois cadastros simultâneos com o mesmo e-mail normalizado e papéis diferentes: um sucesso e uma recusa pela restrição `UNIQUE`, testado com `executar_em_paralelo` (E01-05). É a parte de banco do T-34. O fluxo completo por convite fica na E02-05.
- Normalização de e-mail com espaços internos: o validador recusa, porque espaço interno não é removido.
- E-mail com maiúsculas no domínio e no usuário: tudo fica em minúsculas, como manda a especificação, que não distingue as duas partes.

## Dependências e decisões em aberto

- Depende de E01 (aprovada).
- Sem decisões em aberto.
