# E14-07 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_retirada_comprador.py tests/tecnicos/test_portal_do_fornecedor.py` (arquivos inteiros, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | `test_retirada_comprador.py`: **7 failed, 6 passed**. Falham A-1 a A-6 e A-8 (as seções não existiam). Passam por ausência, como guardas de regressão: A-7 (antes da liberação sem seção de retirada, com a previsão), A-9 (nenhum formulário a mais), A-10 (404 de outro comprador), A-11 (403 do comprador nas rotas da E14-06, que já existiam) e A-12 (as rotas do comprador não criam registro). Os acréscimos do portal (A-13 e A-14, 2 testes) também **já passavam**: o portal não muda e as rotas da E14-06 já recusam o fornecedor |
| Green | `test_retirada_comprador.py`: **13 passed**; `test_portal_do_fornecedor.py`: **20 passed**; `test_pedidos_telas_comprador.py` verde; `mypy apps tests/apoio` e `ruff` limpos |

## O que foi feito
- `apps/pedidos/entrega_do_comprador.py` (`ocorrencias_do_pedido`, `retirada_do_pedido`), usados em `apps/pedidos/views.py` e em `templates/pedidos/detalhe.html`: seção "Ocorrências de entrega" (data, produto, tipo, quantidade, "Reembolso de R$ ..." e a situação: Devida, rótulo da parcela ou "Sem valor a devolver") e seção "Retirada" (liberação, prazo, endereço da liberação e a tabela Pedido/Reembolsado/Retirado/Descartado/A retirar, com o aviso de prazo encerrado quando há saldo). Sem formulário e sem o nome do administrador.
- A-13 e A-14 acrescentados a `tests/tecnicos/test_portal_do_fornecedor.py` (recusas do fornecedor nas rotas da E14 e conjunto de chaves do portal sem dado de recebimento, ocorrência, retirada, descarte ou endereço; nada disso no HTML nem no CSV).

## Decisões técnicas
- A linha da ocorrência traz data e hora de Brasília (a spec diz "data"); o teste confere os dois.
- "Reembolsado" na tabela de retirada soma o da apuração e o das ocorrências (spec, E14-07 regra 2).


---

## Revisão independente — agente 3 — 2026-11-16

**Objeto:** `5b00c56`, branch `e14-especificacoes`, comparação com `bc35037` (main após E13). Fontes: especificação funcional v1.7, infraestrutura v1.8, AGENTS.md e as oito especificações e matrizes da E14. Histórico do implementador acima preservado.

A execução independente e o parecer consolidado estão em [E14-08/review.md](../E14-08/review.md), incluindo o código das contraprovas. A revisão não alterou código de produção nem os testes do implementador.

**Parecer da fatia: REPROVADO — E14-R02 (importante).**

| Critérios | Verificação |
|---|---|
| A-1 e A-2 | Ocorrência e estado real da devolução, inclusive conclusão no simulador. |
| A-3 a A-8 | Retirada, endereço fixado, saldo, vencimento sem descarte automático, faltas, previsão anterior e suspenso. |
| A-9 a A-12 | Sem novos formulários do comprador, isolamento entre compradores e POSTs recusados/sem escrita operacional. |
| A-13 e A-14 | Fornecedor recusado nas rotas E14; portal/CSV e conjunto fechado de campos preservados. |

Os critérios automatizados passam, mas a regra 5 não recebeu um cenário com ocorrência anterior e cancelamento posterior.

### E14-R02 — seção de ocorrência permanece após cancelamento

- **Requisito:** E14-07, regra 5: pedido não válido (cancelado ou de rodada que voltou ao interesse), **sem as seções desta fatia**; funcional §7.2 determina cancelamento da rodada inteira.
- **Local:** `apps/pedidos/entrega_do_comprador.py:42-46`, chamado incondicionalmente por `apps/pedidos/views.py:57`; `templates/pedidos/detalhe.html` renderiza a lista sempre que não vazia.
- **Reprodução:** AE, falta de 2 em X-P1, cancelamento administrativo sem reembolso, GET `/pedidos/<X>/` autenticado como A.
- **Evidência independente:** HTTP 200 ainda contém `<h2>Ocorrências de entrega</h2>` e a linha de R$ 23,59, estado Devida. `test_cancelada_sem_secao_de_ocorrencias` falha na ausência exigida. A situação quitada e o `PedidoApurado` históricos não devem ser confundidos com validade operacional depois de cancelar a rodada.
- **Correção esperada:** aplicar a regra de exibição ao pedido/rodada atuais e testar cancelamento posterior à ocorrência. **Preservar** o registro e a obrigação financeira; ocultar esta seção não autoriza apagar a ocorrência ou o acompanhamento de estornos existente.

TDD: `7836b63` antes de `d01cb27`. As guardas já existentes de comprador/fornecedor são testes de regressão; a seção nova tem Red próprio. A falha encontrada está fora dos exemplos A-1 a A-14, mas dentro da regra explícita 5.


---

## Correção do implementador — reprovação de 2026-11-16

**E14-R02 (A-15 e A-16).**
- Red \`e69bedc\`: \`uv run pytest tests/tecnicos/test_retirada_comprador.py\` → 2 falhas: `<h2>Ocorrências de entrega</h2>` presente depois do cancelamento, sem e com reembolso.
- Green: `pedido_valido` em `apps/pedidos/entrega_do_comprador.py` (no pedido formal da rodada e sem `CancelamentoDaRodada`, a cada carregamento); `ocorrencias_do_pedido` devolve vazio para o pedido não válido. Ocorrência, reembolso e obrigações não são tocados; a seção "Estornos" segue como está. Arquivo: 15 passed.


---

## Revalidação independente das correções — agente 3 — 2026-11-16

**Commit revisado: `eb317b4`**, branch `e14-especificacoes`. Comparação com o parecer `e462a61`; especificação complementar `f530028`; testes Red `e69bedc`. Fontes e requisitos-base permanecem os da revisão anterior. O histórico acima continua válido como registro daquela revisão; o resultado atual é o desta seção.

**APROVADO. E14-R02 encerrado.**

Conferida a regra 5 corrigida e A-15/A-16. `pedido_valido` consulta o cancelamento atual e a participação na apuração do ciclo do pedido formal antes de montar as ocorrências. A guarda afeta apenas a apresentação: nenhuma escrita em ocorrência, reembolso ou obrigação foi acrescentada. A seção de retirada já depende da etapa liberada e do pedido válido, e a liberação continua não cancelável.

A contraprova original de cancelamento sem reembolso passou. Os novos testes cobrem também cancelamento com reembolso e a preservação da seção Estornos com 23,59 e 70,76; os testes anteriores preservam a exibição de ocorrências em pedidos válidos, o comprador suspenso e o isolamento do fornecedor. A revisão do diff confirma ausência de alteração financeira.

TDD: dois testes Red em `e69bedc` antes da guarda em `eb317b4`, sem afrouxamento dos testes anteriores. Resultados e comandos em E14-08. Sem achado residual nesta fatia.
