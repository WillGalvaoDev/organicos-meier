# E06-07 — Telas do fechamento

Fatia 7 de 7 da milestone **E06 — Fechamento e caixas**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

As fatias E06-01 a E06-06 entregam os serviços. Esta fatia entrega as telas:

- **Para o administrador:** os botões de iniciar e prorrogar o fechamento, o prazo e o histórico de prazos.
- **Para o comprador:** o prazo do fechamento no carrinho e no catálogo.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, administrador | "Dashboard de rodadas, mínimos, caixas pendentes, prazos encerrados e ações necessárias"; "Início de etapas [...], prorrogação (exceto prazo de pagamento e margem operacional)". |
| Especificação §13, comprador | "Carrinho agrupado por rodada, com reservas, excedentes, etapas e prazos." |
| Especificação §5 | O carrinho separa visualmente rodadas, etapas, prazos e totais. |
| Especificação §15 | Datas exibidas no fuso da operação. |
| E02-10 | Política `somente_administrador` nas rotas do administrador e a varredura de políticas. |
| E05-04 | O bloco de progresso na página de estoque da rodada (`/administracao/rodadas/<id>/estoque/`). |
| E05-05 | O grupo do carrinho, o topo do catálogo e as respostas 200, 302 e 409, montadas com o estado relido. |
| Milestone E06, herdado da E05 | Mostrar o prazo do fechamento no grupo do carrinho. |
| E06-01, E06-03, E06-04 | `iniciar_fechamento`, `aceita_interesses`, `prazo_do_fechamento`, `prorrogar_fechamento` e `TransicaoRecusada`. |

## Escopo

**Dentro:**

- O bloco "Fechamento" na página de estoque da rodada.
- As rotas de iniciar e de prorrogar o fechamento.
- O prazo no detalhe do fornecedor, no carrinho e no catálogo.

**Fora:**

- O painel administrativo geral e os alertas (E15).
- O botão de abrir o pagamento (E08).
- O portal do fornecedor (E13).

## Decisões técnicas

- **O bloco fica junto do progresso.** A decisão de iniciar o fechamento depende do progresso elegível. Por isso as ações ficam na página de estoque da rodada, que já mostra esse progresso (E05-04).
- **Formato das datas.** O formato é `dd/mm/aaaa HH:MM` no fuso da operação, seguido de "(horário de Brasília)". O valor sai de `no_fuso_da_operacao` (E01-03), ou do filtro `date` com `TIME_ZONE` igual a America/Sao_Paulo, como nas telas existentes.
- **Campo do novo prazo.** O novo prazo é um `<input type="datetime-local">` com o formato `AAAA-MM-DDTHH:MM`. O valor é interpretado em America/Sao_Paulo e convertido em instante com fuso antes de chamar o serviço. Os segundos são zero.
- **Respostas no padrão da E05-05:**
  - sucesso: 302 com mensagem;
  - recusa de transição: 409, com a página relida e a mensagem no topo;
  - formulário inválido: 200, com a mensagem junto ao campo.

## Regras

**Bloco "Fechamento"** em `/administracao/rodadas/<id>/estoque/` (política `somente_administrador`), abaixo do bloco de progresso:

| Situação da rodada | O que aparece |
|---|---|
| `interesse` com `atingido` verdadeiro | o botão "Iniciar fechamento" (`POST /administracao/rodadas/<id>/fechamento/iniciar/`) e o texto "O prazo será de 24 horas a partir do início." |
| `interesse` com `atingido` falso | "O fechamento pode ser iniciado quando o mínimo elegível for atingido.", sem botão |
| `fechamento` com prazo não encerrado | "Prazo do fechamento: <data e hora> (horário de Brasília)" e o formulário "Prorrogar fechamento" (`POST /administracao/rodadas/<id>/fechamento/prorrogar/`), com o campo `termino` preenchido com o prazo atual |
| `fechamento` com prazo encerrado (a tarefa ainda não rodou) | "Prazo do fechamento encerrado em <data e hora>. O encerramento será processado automaticamente.", sem formulário |
| `fechamento_encerrado` | "Fechamento encerrado em <data e hora>. Aguardando a autorização do pagamento." |
| demais etapas | nenhum bloco |

**Histórico de prazos:** com um ciclo vigente, a página lista as linhas de `PrazoDoFechamento` do ciclo, em ordem de registro. Cada linha mostra:

- a origem ("Início" ou "Prorrogação");
- o prazo definido;
- quando foi registrado.

O autor não aparece: é sempre o administrador.

**`POST /administracao/rodadas/<id>/fechamento/iniciar/`** (política `somente_administrador`; `GET` responde 405):

| Situação | Resposta |
|---|---|
| rodada inexistente | 404 |
| sucesso | 302 para a página de estoque, com a mensagem "Fechamento iniciado. Prazo: <data> às <hora> (horário de Brasília)." |
| `TransicaoRecusada` | 409 com a página de estoque relida e a mensagem do serviço no topo |

**`POST /administracao/rodadas/<id>/fechamento/prorrogar/`** (política `somente_administrador`; `GET` responde 405):

- Formulário com `termino`, um `DateTimeField` com o formato de entrada `%Y-%m-%dT%H:%M`, convertido em instante com fuso em America/Sao_Paulo.

| Situação | Resposta |
|---|---|
| rodada inexistente | 404 |
| `termino` vazio ou inválido | 200 com a página de estoque e "Informe a data e a hora do novo prazo." junto ao campo, com o texto enviado escapado; nada gravado |
| sucesso | 302 para a página de estoque, com a mensagem "Prazo do fechamento prorrogado para <data> às <hora> (horário de Brasília)." |
| `TransicaoRecusada` | 409 com a página relida e a mensagem do serviço no topo |

**Detalhe do fornecedor** (`/administracao/fornecedores/<id>/`): com a rodada em `fechamento` ou `fechamento_encerrado`, a linha "Rodada ativa" ganha:

- "Prazo do fechamento: <data e hora>";
- "Prazo encerrado." quando o prazo passou.

**Carrinho e catálogo do comprador** (E05-05), no cabeçalho do grupo do fornecedor e no topo do catálogo:

- com `fechamento` e prazo não encerrado: "Prazo do fechamento: <data> às <hora> (horário de Brasília)";
- com `fechamento` e prazo encerrado, ou com `fechamento_encerrado`: "Prazo do fechamento encerrado em <data> às <hora>.";
- sem prazo gravado: nenhuma linha de prazo. É o caso das rodadas preparadas por testes antigos em `fechamento_encerrado`.

Os formulários de quantidade seguem `aceita_interesses` (E06-03). A linha "Etapa: <rótulo>" da E05-05 não muda.

**Consultas:** o prazo de cada grupo do carrinho é lido junto com a rodada. O número de consultas continua sem crescer com os produtos (E05-05 A-16). O acréscimo é no máximo um valor fixo por fornecedor.

## Interfaces

- `apps/rodadas/views.py` e `config/urls.py`: `fechamento_iniciar` e `fechamento_prorrogar`.
- `apps/rodadas/forms.py`: `FormularioProrrogacao`.
- `templates/rodadas/estoque.html`, `templates/fornecedores/detalhe.html`, `templates/interesses/carrinho.html` e `templates/catalogo/comprador_fornecedor.html`.
- `apps/interesses/apresentacao.py` e `consultas.py`: o prazo no contexto.

## Invariantes

- Nenhuma tela do comprador mostra o mínimo, o valor elegível ou o que falta em reais (E05-05).
- Nenhuma tela oferece "Iniciar fechamento" sem o mínimo atingido, nem "Prorrogar fechamento" com o prazo encerrado.
- Toda gravação passa pelos serviços da E06. A tela não decide transição.

## Casos-limite e concorrência

- **Página antiga:** o administrador clica em "Iniciar fechamento" depois que o mínimo caiu. O serviço recusa com `minimo_nao_atingido`, e a resposta é 409 com o estado relido.
- **Prorrogação enviada depois do prazo:** 409 com "O prazo deste fechamento já terminou e não pode mais ser prorrogado.".
- **Horário digitado na madrugada:** "2026-11-04T01:30" é 2026-11-04 04:30 UTC.

## Correção E06-R02 — formato do novo prazo (2026-10-19)

### Diagnóstico

`FormularioProrrogacao` usa `forms.DateTimeField(input_formats=["%Y-%m-%dT%H:%M"])`. No Django 5.2, esse campo tenta primeiro o leitor ISO 8601 e só depois os `input_formats`, então a lista não restringe a entrada. O revisor mostrou três entradas aceitas fora do contrato:

- `2026-11-04`: só a data, lida como meia-noite;
- `2026-11-04T01:30:59`: os segundos 59 chegam ao prazo;
- `2026-11-04T01:30:00+00:00`: o fuso enviado prevalece, e o horário é lido em UTC, e não no horário de Brasília.

O serviço (E06-04) aceita qualquer instante com fuso, como especificado. Por isso, o formato precisa ser garantido no formulário.

### Regra

**Formato aceito:** exatamente `AAAA-MM-DDTHH:MM`, depois de retirados os espaços das pontas (como o Django faz com os campos de texto):

- quatro dígitos de ano, dois de mês, dois de dia, a letra `T` maiúscula, dois de hora e dois de minuto, com `-` e `:` como separadores;
- só dígitos ASCII `0`–`9`. O `\d` das expressões regulares do Python aceita dígitos de outros alfabetos e não serve sozinho; use `[0-9]` ou `re.ASCII`;
- a data e a hora precisam existir no calendário (`strptime` com `%Y-%m-%dT%H:%M`). O `strptime` sozinho também não basta: ele ignora maiúsculas e aceita `t` no lugar de `T`.

**Conversão:** o texto é sempre interpretado em America/Sao_Paulo (`ZoneInfo("America/Sao_Paulo")`, o fuso da operação), independentemente da configuração ativa do Django. O resultado é um instante com fuso, com segundos e microssegundos zero.

**Recusa:** qualquer outra entrada é inválida. A rota responde como já especificado para `termino` vazio ou inválido: 200, a página de estoque, "Informe a data e a hora do novo prazo." junto ao campo, o texto enviado escapado e nada gravado (nenhuma linha de prazo, nenhuma auditoria).

**A forma de implementar fica com o implementador**, por exemplo um campo de texto com `clean_termino` ou um campo próprio que substitua `to_python`. O nome `FormularioProrrogacao`, o campo `termino` e o valor limpo (um `datetime` com fuso) continuam os mesmos.

### O que não muda

- O serviço `prorrogar_fechamento` e as recusas dele (E06-04).
- As respostas 302 e 409 da rota e o campo preenchido com o prazo atual.
- Os critérios A-1 a A-14.

### TDD

Os critérios A-15 e A-16 seguem Red → Green → Refactor, com as regras de prevenção da correção E05-R04 (E05-01). A prova `test_formato_do_prazo_restrito_ao_contrato` do revisor de `2fbf143` (as três entradas) é o Red esperado no código atual e entra literalmente nos testes.

## Dependências e decisões em aberto

- Depende de E02-10, E05-04, E05-05 e E06-01 a E06-06.
- Sem decisões em aberto.
