# E15-05 — Painel do administrador

Fatia 5 de 7 da milestone **E15 — Painel administrativo e alertas operacionais**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E15-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E15-01.

## Contexto e objetivo

A §13 pede um "dashboard de rodadas, mínimos, caixas pendentes, prazos encerrados e ações necessárias". Hoje a página `administracao/` (E02-03) só tem links para envios e financeiro. As rodadas que já saíram da etapa ativa (`aguardando_fornecedor`, `disponivel_para_retirada`) nem aparecem na página do fornecedor.

Esta fatia transforma `administracao/` no painel que integra o que as etapas anteriores criaram:
- os alertas abertos;
- as ações que esperam o administrador;
- as rodadas em andamento, com mínimo, caixas e prazos;
- os prazos encerrados;
- as tarefas periódicas.

Tudo é calculado na leitura da página. O painel não cria regra de negócio: cada ação aponta para a tela que já a executa.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, administrador | Dashboard de rodadas, mínimos, caixas pendentes, prazos encerrados e ações necessárias. |
| Especificação §6.1, §6.2 | Progresso elegível e caixas: completas, excedentes aguardando caixa, faltantes para a próxima. |
| Especificação §7 | Etapas, prazos e o que espera autorização do administrador. |
| Especificação §9.2, §10, §11 | Autorização de estornos; repasse; recebimento, liberação, vencidos. |
| Infraestrutura 3.6 | Alertas ao admin. |
| Milestone 15, herdados E06, E09 e E14 | Prazos encerrados; alertas financeiros e a última conciliação; recebimento a resolver, vencidos e obrigações sem cobertura. |

## Escopo

**Dentro:** a página `administracao/` (rota e nome atuais, `painel_administracao`) e as funções de leitura que a montam.

**Fora:**
- escrever qualquer coisa, salvo a ciência (E15-04), que é um formulário que aponta para a rota dela;
- telas de detalhe novas.

## Regras

**Acesso:** como hoje (`somente_administrador` e passkey, E02-03). Comprador e fornecedor recebem 403. Instantes em Brasília, `dd/mm/aaaa hh:mm`. `instante = agora()` é lido uma vez por carregamento.

**Ordem das seções:** 1 Alertas abertos, 2 Ações necessárias, 3 Rodadas, 4 Prazos encerrados, 5 Tarefas periódicas, 6 Navegação. Cada seção tem um título `<h2>` com o nome dado abaixo.

### 1. "Alertas abertos"

1. `alertas_abertos()`, na ordem dela (críticos primeiro). Por alerta:
   - a gravidade ("Crítico" ou "Aviso");
   - o título e o corpo (os financeiros com os textos da E09-03, os operacionais com os das E15-02 a E15-04);
   - "aberto em <data>";
   - o link "Ver" (`link_do_alerta`, E15-02);
   - nos de natureza `fato`, o formulário "Dar ciência" (POST para `alertas_ciencia`, com CSRF).
2. Sem alerta aberto: "Nenhum alerta aberto.".

### 2. "Ações necessárias"

3. `acoes_necessarias(instante)` devolve uma lista de `AcaoNecessaria(rodada | None, fornecedor | None, texto, link)`. Primeiro vêm as ações das rodadas, ordenadas pelo nome do fornecedor e depois pelo pk da rodada, na ordem da tabela abaixo. Depois vêm as globais. Por rodada:

| Etapa e condição | Texto | Link |
|---|---|---|
| `interesse` com o mínimo elegível atingido (`progresso_da_rodada(r).atingido`) | "Mínimo atingido: o fechamento pode ser iniciado." | `rodadas_estoque` |
| `fechamento_encerrado` | "Fechamento encerrado: aguarda a abertura do pagamento." | `rodadas_estoque` |
| `pagamento`, `pode_iniciar_apuracao(abertura, instante)` e sem `ApuracaoFinal` do ciclo | "Apta para a apuração final desde <fim da margem>." | `rodadas_estoque` |
| `pagamento` com `ApuracaoFinal` válida sem `AprovacaoDoResultado` | "Apuração feita: aguarda a aprovação do resultado." | `rodadas_estoque` |
| `aguardando_fornecedor` com `EnvioDoPedidoFormal` em `concluido_com_falhas` e nenhuma `TentativaDeEnvioDoPedidoFormal` do pedido formal com resultado `sucesso` | "O pedido formal não foi enviado depois das três tentativas: reenvie." | `rodadas_pedido_formal` |
| `aguardando_fornecedor` e `recebimento_resolvido(r)` falso | "Recebimento: <n> produto(s) a resolver." (n = linhas de `situacao_do_recebimento` com `a_resolver > 0`) | `rodadas_recebimento` |
| `aguardando_fornecedor` e `recebimento_resolvido(r)` verdadeiro | "Recebimento resolvido: a retirada pode ser liberada." e, sem `endereco_vigente()`, mais " Registre antes o endereço de retirada." | `rodadas_recebimento` |
| `aguardando_fornecedor` ou `disponivel_para_retirada`, com `liquidez` da obrigação com o fornecedor da rodada (E13-06) com `liberado > 0` | "Repasse ao fornecedor liberado: <valor>." | `rodadas_saidas` |
| `aguardando_fornecedor` ou `disponivel_para_retirada`, com `liquidez` da conta de frete da rodada com `liberado > 0` | "Pagamento do frete liberado: <valor>." | `rodadas_saidas` |
| `disponivel_para_retirada`, prazo final da retirada encerrado e itens vencidos (`situacao_da_retirada(r).vencidos` não vazia) | "Prazo de retirada encerrado: <n> item(ns) pendente(s) de decisão." | `rodadas_retiradas` |

   **Globais**, ao final:
   - **Devoluções a autorizar:** obrigações com comprador cuja `situacao_da_devolucao` é `devida` e cujo valor devido é maior que zero. Texto: "Devoluções a autorizar: <n> (<soma>)." Link: `financeiro_devolucoes`.
   - **Obrigações sem cobertura:** quando `itens_sem_cobertura()` não está vazio. Texto: "Itens sem cobertura: <n> (<soma dos valores>)." Link: `financeiro_reserva`.
4. Sem ação: "Nenhuma ação pendente.".

### 3. "Rodadas"

5. **Rodadas exibidas:**
   - em `ETAPAS_ATIVAS` e em `aguardando_fornecedor`;
   - em `disponivel_para_retirada` enquanto algum item de `situacao_da_retirada` tem saldo maior que zero.

   Não aparecem as canceladas nem as liberadas sem saldo. A ordem segue a ordem de `Etapa` e, dentro da etapa, o nome do fornecedor.
6. **Colunas:**
   - **Fornecedor.**
   - **Etapa:** o rótulo de `Etapa`.
   - **Mínimo:** só em `interesse`, `fechamento` e `fechamento_encerrado`, como "<valor elegível> de <mínimo> (<percentual>%)", a partir de `progresso_da_rodada`. Nas demais etapas, "—".
   - **Caixas pendentes:** só em `interesse` e `fechamento`. Para cada produto com múltiplo e `excedente > 0`: "<produto>: <excedente> aguardando, faltam <faltam_para_proxima_caixa> para a próxima caixa", com as quantidades formatadas e a unidade. Sem nenhum produto assim, ou nas demais etapas, "—".
   - **Prazo:**
     - `fechamento`: "Fecha em <prazo_do_fechamento>";
     - `fechamento_encerrado`: "Encerrado em <prazo_do_fechamento>";
     - `pagamento`: "Pagamento até <prazo_de_pagamento>; margem até <fim_da_margem>";
     - `disponivel_para_retirada`: "Retirada até <prazo_final>";
     - as demais etapas: "—".
   - **Link** "Abrir", para `rodadas_estoque`.
7. Sem rodada: "Nenhuma rodada em andamento.".

### 4. "Prazos encerrados"

8. Uma linha por rodada cujo prazo terminou e que espera o administrador ou uma tarefa:
   - `fechamento` com `prazo_do_fechamento ≤ instante`: "<fornecedor>: fechamento vencido em <prazo>, aguardando o encerramento automático.";
   - `fechamento_encerrado`: "<fornecedor>: fechamento encerrado em <prazo>.";
   - `pagamento` sem `ApuracaoFinal` e com `fim_da_margem ≤ instante`: "<fornecedor>: margem encerrada em <fim da margem>.";
   - `disponivel_para_retirada` com `prazo_final ≤ instante` e vencidos: "<fornecedor>: retirada encerrada em <prazo_final>, com itens pendentes."

   Cada linha tem o link `rodadas_estoque` ou, na retirada, `rodadas_retiradas`. Sem nenhuma: "Nenhum prazo encerrado aguardando.".

### 5. "Tarefas periódicas"

9. `situacao_das_tarefas(instante)` (E15-01, com a tarefa de verificação da E15-02). Uma linha por tarefa:
   - a descrição;
   - a última conclusão (ou "—");
   - a situação: "Em dia", "Atrasada desde <atrasada_desde>" ou "Sem registro de execução";
   - quando há falha, "Última falha em <data>: <ultimo_erro>".
10. Em seguida, "Última conciliação: <data dd/mm/aaaa> (<rótulo do resultado>)", da `ConciliacaoDiaria` mais recente, ou "Nenhuma conciliação registrada." (herdado E09).

### 6. Navegação

11. Os elementos atuais continuam:
    - "Olá, <nome>.";
    - os links "Envios" e "Financeiro";
    - a linha "Envios com falha: <n> · ver falhas";
    - o botão "Sair".

    Entram os links para "Fornecedores" (`fornecedores_lista`), "Usuários" (`usuarios_administracao`), "Convites" (`convites_administracao`), "Comunicados" (`comunicados_administracao`), "Endereço de retirada" (`retirada_endereco`) e "Histórico de ações" (`historico_acoes`, E15-06). Até a E15-06 existir, o último link fica de fora. O teste deste item entra na E15-06.

### Privacidade e desempenho

12. O painel não mostra nome, e-mail nem WhatsApp de comprador. Rodadas e ações são por fornecedor; os valores são agregados.
13. O número de consultas ao banco não cresce com o número de pedidos de uma rodada além do que as funções de leitura reaproveitadas já fazem. O teste confere que a página carrega com 5 rodadas em etapas diferentes. Otimizações ficam para `docs/melhorias.md` se o revisor apontar.

## Interface

```python
@dataclass(frozen=True)
class AcaoNecessaria:
    rodada: int | None
    fornecedor: str | None
    texto: str
    link: str

def acoes_necessarias(instante: datetime) -> list[AcaoNecessaria]: ...
def rodadas_do_painel(instante: datetime) -> list[LinhaDaRodada]: ...
def prazos_encerrados(instante: datetime) -> list[PrazoEncerrado]: ...
```

## Decisões técnicas

- **Cálculo na leitura.** Quando o worker parou, o painel é a única forma de ver isso (E15-01, "Limitação"). Ler as fontes na hora evita um segundo estado que poderia divergir.
- **"Caixas pendentes" = excedentes aguardando caixa.** É o termo da §6.2 para as unidades que ainda não completam uma caixa. Depois do fechamento, os excedentes são removidos (§6.3), por isso a coluna só existe em `interesse` e `fechamento`.
- **Repasse e frete como ações.** A §10 deixa o pagamento ao fornecedor e o registro do repasse ao administrador. O valor liberado é o que ele já pode pagar (E13-06).
- **Pedido formal: a ação some com o primeiro envio aceito.** O reenvio manual (E13-04) grava uma `TentativaDeEnvioDoPedidoFormal` com sucesso, mas não muda a situação do ciclo automático, que continua `concluido_com_falhas`. A ação pede "reenvie". Quando uma tentativa já teve sucesso, não há mais o que reenviar. Um reenvio manual que falhou mantém a ação. Correção apontada pela E15-07 (A-3).
- **Parcelas elegíveis à devolução excepcional ficam nos alertas.** Elas já têm o alerta `devolucao_elegivel_excepcional` da E10, e repeti-las nas ações duplicaria a informação.

## Invariantes

- A página não escreve nada.
- Cada ação e cada linha apontam para uma tela existente que executa ou detalha o assunto.

## Dependências e decisões em aberto

- Depende das E15-01 a E15-04, das E05 e E06 (progresso e prazos), das E08 e E11 (prazos e apuração), das E09 e E10 (devoluções e cobertura), da E13 (pedido formal e saídas) e da E14 (recebimento, endereço e retirada).
- Nenhuma decisão em aberto.
