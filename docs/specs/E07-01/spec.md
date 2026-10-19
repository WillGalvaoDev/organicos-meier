# E07-01 — Interface do provedor de pagamentos e simulador

Fatia 1 de 6 da milestone **E07 — Simulador de pagamentos e integração**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Todo pagamento de comprador passa pelo provedor integrado (A3). Na fase 1, o único provedor é um simulador, sem dinheiro real. O Mercado Pago entra na fase 2a, depois da prova de conceito (L-1 a L-11).

Para que o Mercado Pago entre depois sem mudar as regras, o sistema fala com o provedor só por uma interface interna. Esta fatia entrega:

- a interface, com os tipos de dados e os erros;
- o simulador determinístico, que guarda o "lado do provedor" em tabelas próprias;
- os controles que os testes usam para reproduzir o pagador e o provedor: aprovação, recusa, expiração, avisos atrasados, repetidos, fora de ordem ou perdidos, falhas, indisponibilidade e atraso de consistência.

Nenhum serviço de negócio usa a interface ainda. Os pedidos e as cobranças são da E08.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §8.1 | Pagamentos só pela plataforma integrada. Considerar confirmações assíncronas, expiração e estornos; não presumir confirmação imediata. |
| Especificação §15 | Integridade: idempotência em webhooks e estornos; validação de autenticidade dos eventos. Tempo: separar o tempo do evento financeiro, o do recebimento do webhook e o prazo comercial. |
| Infraestrutura 4.1 | Fase 1 só com o simulador. Cada pagamento registra o provedor e o ambiente. |
| Infraestrutura 4.2 | O provedor é a fonte da verdade; chave de idempotência gravada antes da chamada e reaproveitada nas novas tentativas; `external_reference` com pedido e ciclo; instantes do provedor normalizados em UTC [L-4]; mais de um pagamento aprovado para o mesmo pedido é possível. |
| Infraestrutura 4.3 e 4.5 | Vencimento da cobrança, cancelamento ativo das tentativas pendentes [L-2], aprovação depois do vencimento não presumida possível nem impossível [L-3]. |
| Infraestrutura 4.4 | Atraso de consistência do provedor [L-6]. |
| Infraestrutura 7, fase 1 | "Pagamento fica atrás de uma interface interna (criar cobrança, consultar, buscar por referência, cancelar tentativa, estornar, consultar saldo e movimentos, receber evento)." O simulador reproduz webhooks atrasados, repetidos e fora de ordem, aprovações em qualquer instante, dois pagamentos aprovados para o mesmo pedido, cancelamento coincidindo com o pagamento e API fora do ar. |
| Infraestrutura 9.2 | L-1 a L-11: nenhum comportamento do Mercado Pago é presumido. |
| AGENTS.md §6 e §7 | Interfaces substituíveis, simulação determinística, tratamento explícito de falhas. Não implementar fases posteriores. |
| E04-04 | Precedente do simulador de WhatsApp: interface `Protocol`, implementação escolhida por configuração, plano de falhas no processo, fixture que reinicia o simulador. |

## Escopo

**Dentro:**

- O app `apps.pagamentos`, com a interface (`apps/pagamentos/provedor.py`).
- O app `apps.simulador_pagamentos`, com o simulador e os controles.
- As operações `criar_cobranca`, `consultar_pagamento`, `buscar_por_referencia`, `cancelar_cobranca` e `verificar_aviso`.
- `obter_provedor()`.

**Fora:**

- `estornar` (E10) e `consultar_saldo_e_movimentos` (E09). Elas entram na interface e no simulador junto com as etapas que as usam, com especificação própria. Também ficam para lá a falha definitiva de estorno, o saldo insuficiente, as datas de liberação por meio de pagamento, o aporte e a contestação.
- O registro dos pagamentos no sistema (E07-03), as chamadas pendentes (E07-04), a rota dos avisos (E07-05) e a consulta antes das decisões (E07-06).
- A configuração por ambiente e a recusa em produção (E07-02). Nesta fatia, `obter_provedor()` sempre devolve o simulador.
- Meios de pagamento além de Pix. O cartão é da fase 2b.
- Uma tela para operar o simulador em desenvolvimento. Ela só tem uso quando houver cobranças de verdade (E08).

## Decisões técnicas

- **Dois apps.** `apps.pagamentos` é o lado do sistema: interface, registros e regras. `apps.simulador_pagamentos` faz o papel do provedor. Fora de `obter_provedor()` e dos testes, nenhum módulo importa o simulador, e um teste confere isso. Na fase 2a, o Mercado Pago entra como outra implementação da mesma interface.
- **Estado do simulador no banco.** As cobranças e os avisos simulados ficam em tabelas do simulador. Uma cobrança criada pela tarefa (worker) precisa ser vista por outra conexão ou processo, ao contrário das mensagens do WhatsApp simulado (E04-04). O plano de falhas fica no processo, como no WhatsApp, porque só os testes o usam.
- **Determinístico.** O simulador não usa aleatoriedade, rede nem relógio próprio: os instantes vêm de `agora()` (E01-03) ou do argumento `em` dos controles. Uma cobrança nunca muda de situação sozinha, nem quando passa do vencimento. Os identificadores são sequenciais.
- **Cobrança é o pagamento.** Criar uma cobrança cria, no provedor, um pagamento pendente com identificador externo próprio, como no Pix. Uma nova tentativa para o mesmo pedido é outra cobrança, com outra chave de idempotência e o mesmo `referencia_externa`.
- **Vocabulário interno.** As situações e os campos da interface são do sistema, e não do Mercado Pago. A implementação da fase 2a traduz o que o provedor responde, inclusive os horários para UTC (L-4).
- **Assinatura dos avisos do simulador:** HMAC-SHA256 do corpo, com o segredo `SEGREDO_AVISOS_SIMULADOR`, no cabeçalho `X-Simulador-Assinatura: sha256=<hex>`, conferida com `hmac.compare_digest`. O esquema real é a L-11 e fica para a fase 2a. Por isso a verificação é um método da interface, e não código da rota.

## Regras

### Interface (`apps/pagamentos/provedor.py`)

**Tipos** (dataclasses congeladas):

- `SituacaoNoProvedor`, um `StrEnum`: `pendente`, `aprovado`, `recusado`, `cancelado`, `expirado`. Só `pendente` não é terminal.
- `NovaCobranca`:
  - `chave_idempotencia`: texto de 1 a 64 caracteres;
  - `referencia_externa`: texto de 1 a 64 caracteres;
  - `valor`: `Decimal` maior que zero, com duas casas;
  - `descricao`: texto de até 120 caracteres, sem dados pessoais;
  - `expira_em`: instante com fuso;
  - `meio`: só `"pix"` na fase 1.

  A validação local recusa com `ValueError` antes de chamar o provedor. `float` em `valor` é recusado (R-1).
- `PagamentoConsultado`:
  - `provedor`, o nome da implementação (`"simulador"`);
  - `id_externo`, `referencia_externa`, `valor` e `situacao`;
  - `criado_em`: a criação no provedor;
  - `aprovado_em`: a aprovação no provedor (`date_approved`), ou `None`;
  - `expira_em`;
  - `consultado_em`: o instante de `agora()` em que a resposta foi obtida.

  Todos os instantes em UTC, com fuso.
- `CobrancaCriada`: `pagamento` (`PagamentoConsultado`) e `dados_para_pagar` (dicionário de textos, como o código Pix). Os dados para pagar não são gravados em log.
- `AvisoDoProvedor`: `id_evento`, `tipo` (por exemplo, `"pagamento"`) e `id_externo`. O aviso não traz situação: quem quiser saber consulta (E07-03, E07-05).

**Erros:**

| Erro | Quando | Natureza |
|---|---|---|
| `ProvedorIndisponivel` | rede, tempo esgotado, erro interno do provedor | temporária: pode tentar de novo com a mesma chave |
| `RecusaDoProvedor(codigo)` | o provedor recusou o pedido (dados inválidos, chave reutilizada com outros dados) | definitiva |
| `PagamentoNaoEncontrado` | o identificador não existe no provedor | à parte: pode ser atraso de consistência (L-6); quem chama decide (E07-04) |
| `AvisoInvalido` | assinatura ausente ou errada, corpo malformado | o aviso é descartado (E07-05) |

As mensagens dos erros não levam dados pessoais nem o corpo do aviso.

**Protocolo `Provedor`:**

```
nome: str
criar_cobranca(nova: NovaCobranca) -> CobrancaCriada
consultar_pagamento(id_externo: str) -> PagamentoConsultado
buscar_por_referencia(referencia_externa: str) -> list[PagamentoConsultado]
cancelar_cobranca(id_externo: str) -> PagamentoConsultado
verificar_aviso(corpo: bytes, cabecalhos: Mapping[str, str]) -> AvisoDoProvedor
```

- `buscar_por_referencia` devolve os pagamentos em ordem de criação no provedor. A lista pode vir vazia.
- `cancelar_cobranca` devolve a situação depois do pedido de cancelamento, que é o que o provedor registrou. Pode ser `aprovado`, se o pagador concluiu ao mesmo tempo (L-2).
- Nenhum método escreve nas tabelas de `apps.pagamentos`. Registrar o que voltou é papel de quem chama (E07-03).

**`obter_provedor() -> Provedor`:** devolve a implementação configurada. Quem usa o provedor nunca importa uma implementação diretamente. Nesta fatia, é sempre o simulador; a E07-02 acrescenta a configuração e a recusa em produção.

### Simulador (`apps.simulador_pagamentos`)

**Tabelas:**

- `CobrancaSimulada`:
  - `id_externo`: `"sim-<n>"`, sequencial e único;
  - `chave_idempotencia`: única;
  - `referencia_externa`, `valor`, `descricao`, `meio`, `situacao`, `criado_em`, `aprovado_em` (nulo) e `expira_em`.
- `AvisoSimulado`:
  - `id_evento`: `"sim-ev-<n>"`, sequencial e único;
  - `tipo` (`"pagamento"`), `id_externo`, `criado_em`;
  - `entregas`: quantas vezes foi entregue;
  - `descartado`: booleano.

**Operações da interface:**

| Operação | Comportamento |
|---|---|
| `criar_cobranca` | Chave nova: cria a cobrança `pendente`, com `criado_em = agora()`, e devolve `dados_para_pagar = {"pix_copia_e_cola": "SIMULADO-<id_externo>"}`. Chave existente com os mesmos dados: devolve a cobrança existente, sem criar outra. Chave existente com outros dados: `RecusaDoProvedor("chave_reutilizada")`. `expira_em` não posterior a `agora()`: `RecusaDoProvedor("expiracao_invalida")`. A criação não gera aviso. |
| `consultar_pagamento` | Devolve o estado gravado. Identificador desconhecido: `PagamentoNaoEncontrado`. |
| `buscar_por_referencia` | Todas as cobranças com a referência, por `criado_em` e `id_externo`. |
| `cancelar_cobranca` | `pendente` passa a `cancelado` e gera um aviso. Nas outras situações, nada muda e a situação atual é devolvida. Identificador desconhecido: `PagamentoNaoEncontrado`. |
| `verificar_aviso` | Confere a assinatura e lê o corpo JSON `{"id_evento", "tipo", "id_externo"}`. Qualquer falha: `AvisoInvalido`. |

**Controles** (`apps/simulador_pagamentos/controle.py`), usados pelos testes e, mais tarde, pela tela de desenvolvimento:

- `aprovar(id_externo, *, em=None)`: a cobrança passa a `aprovado`, com `aprovado_em = em` ou `agora()`. Vale a partir de `pendente`, `cancelado` ou `expirado`, porque a aprovação depois do vencimento ou do cancelamento não é presumida impossível (L-2, L-3). `em` anterior a `criado_em`, ou a cobrança já `aprovado` ou `recusado`: `ValueError`. Um `em` no passado representa uma aprovação que o provedor informa depois.
- `recusar(id_externo)` e `expirar(id_externo)`: só a partir de `pendente`. Caso contrário, `ValueError`.
- `aprovar_no_cancelamento(id_externo, *, em=None)`: o próximo `cancelar_cobranca` dessa cobrança aprova em vez de cancelar e devolve `aprovado`. Representa o pagador concluindo no mesmo instante do cancelamento (infraestrutura 4.3).
- Toda mudança de situação, por controle ou por `cancelar_cobranca`, cria um `AvisoSimulado` não entregue.
- `reemitir_aviso(id_externo) -> AvisoSimulado`: cria outro aviso para a mesma cobrança, com novo `id_evento`, sem mudar a situação. Representa o provedor mandando mais de um evento para o mesmo pagamento.
- `avisos_pendentes() -> list[AvisoSimulado]`: os não entregues e não descartados, em ordem de criação.
- `entregar_avisos(avisos=None, *, vezes=1) -> list[int]`: entrega os avisos indicados, na ordem da lista (por padrão, os pendentes), cada um `vezes` vezes. Cada entrega monta o corpo, assina e chama a mesma função que a rota de avisos chama (E07-05), e devolve os códigos HTTP. Com isso, os testes produzem avisos atrasados (não entregar ainda), repetidos (`vezes`), fora de ordem (a ordem da lista) e perdidos (`descartar(aviso)`). Até a E07-05 existir, a função de recebimento é injetável, e os testes desta fatia usam um receptor de teste.
- `corpo_e_cabecalhos(aviso) -> tuple[bytes, dict[str, str]]`: o corpo e a assinatura, para os testes da rota (E07-05) enviarem por HTTP.

**Plano de falhas** (no processo, com trava):

- `indisponivel()`: toda operação da interface levanta `ProvedorIndisponivel`, até `normalizar()`.
- `falhar_proximas(n, *, operacao=None, depois_de_executar=False)`: as próximas `n` chamadas (de uma operação, ou de qualquer uma) levantam `ProvedorIndisponivel`. Com `depois_de_executar=True`, a operação é feita e gravada no simulador antes da exceção. Isso representa o tempo esgotado depois de o provedor aceitar.
- `atrasar_consistencia(id_externo, consultas)`: as próximas consultas e buscas que envolvem esse pagamento devolvem a situação anterior à última mudança. Representa a L-6.
- `normalizar()` e `reiniciar()`. A fixture `simulador_pagamentos` de `tests/apoio` chama `reiniciar()` antes e depois de cada teste que a usa.

**Log:** `"Simulador de pagamentos: <operação> <id_externo>"`, sem valor, descrição, referência nem dados para pagar.

## Interfaces

- `apps/pagamentos/provedor.py`: os tipos, os erros, `Provedor` e `obter_provedor`.
- `apps/simulador_pagamentos/`: `models.py` (as duas tabelas e a migração), `provedor.py` (`ProvedorSimulado`) e `controle.py`.
- `config/settings/base.py`: os dois apps em `INSTALLED_APPS`; `SEGREDO_AVISOS_SIMULADOR` lido do ambiente, com valor padrão só em `dev.py` e `test.py` (em `prod.py`, a E07-02 decide).
- `tests/apoio`: a fixture `simulador_pagamentos`.

## Invariantes

- O simulador nunca usa rede nem aleatoriedade, e nada nele muda de situação sem um controle ou uma operação.
- Uma chave de idempotência corresponde a no máximo uma cobrança.
- Nenhuma operação da interface grava em `apps.pagamentos`.
- Nenhum log nem mensagem de erro leva valor, descrição, dados para pagar ou o corpo de um aviso.

## Casos-limite e concorrência

- **Mesma chave em duas conexões ao mesmo tempo:** uma cria e a outra recebe a cobrança criada. A restrição `UNIQUE` da chave decide, e a segunda lê a existente depois do conflito. Nunca há duas cobranças.
- **Tempo esgotado depois de criar:** `falhar_proximas(1, operacao="criar_cobranca", depois_de_executar=True)`. A repetição com a mesma chave devolve a mesma cobrança.
- **Cancelamento e pagamento juntos:** com `aprovar_no_cancelamento`, `cancelar_cobranca` devolve `aprovado` e gera um aviso só.
- **Aprovação depois do vencimento:** `aprovar` sobre uma cobrança `expirado` é aceito, com o `em` informado.
- **Dois pagamentos aprovados para a mesma referência:** duas cobranças com chaves diferentes e a mesma referência, as duas aprovadas, e `buscar_por_referencia` devolve as duas.

## Dependências e decisões em aberto

- Depende de E01 (tempo, decimais, auditoria, CI).
- Nenhuma dependência nova: `hmac`, `hashlib` e `json` são da biblioteca padrão.
- Sem decisões em aberto. O formato real dos avisos, a assinatura, os horários e as situações do Mercado Pago (L-1 a L-11) ficam para a fase 2a, com a interface preservada.
