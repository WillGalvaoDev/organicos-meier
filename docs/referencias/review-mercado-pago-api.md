# Revisão independente — referência da API do Mercado Pago

**Veredito: REPROVADO.** Quatro achados **importantes**, abertos. O documento ainda precisa de correções para servir de referência técnica à E10 e à tradução da fase 2a. Este parecer não reprova novamente a E09 nem demonstra defeito no código de produção: o objeto auditado é o material de apoio.

Revisor: agente 3. Data: **2026-10-29**. Pasta: `om-docs-mp`. Branch: `docs-referencia-mercado-pago`. Base: `ae9bf21272f57fa4d1f9452f3485b7582b3ea157`; commits examinados: `0c88c6b` e `4163af6faf84e47597542b6cfa8c4487abf7256c`. As linhas abaixo referem-se a `docs/referencias/mercado-pago-api.md` em `4163af6`.

## Escopo e método

Leitura integral do documento, AGENTS.md, trechos pertinentes da especificação funcional v1.6 e da infraestrutura v1.7, e contratos E07-01, E07-05, E08-03 e E09-02. Conferência independente da documentação pública oficial do Mercado Pago em 2026-10-29, incluindo páginas adicionais às fontes listadas no documento. Não se usa a implementação como autoridade de negócio.

A revisão distingue: comportamento descrito pela documentação pública, confirmação empírica ainda pendente no sandbox e escolha de tradução interna. Manter L-1 a L-13 abertas é correto; isso não dispensa registrar um comportamento já descrito publicamente nem permite apresentar uma solução ainda não especificada como decisão vigente.

O commit `4163af6` somente renumera a melhoria de desempenho da E09-08 de M-5 para M-9 e registra o identificador histórico. A descrição e o encaminhamento foram preservados; não há achado nessa renumeração.

## Achados

### MP-R01 — Importante — adaptação do vencimento apresentada como regra já definida

**Local:** §4, linha 100; contraste com §10, linha 241. **Referências internas:** AGENTS.md §2; infraestrutura 4.5 e L-1; E08-03, operação `criar_cobranca`, linha 128.

A faixa de 30 minutos a 30 dias e o padrão de 24 horas têm respaldo na [documentação oficial de Pix](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/integration-configuration/integrate-pix). Entretanto, a linha 100 determina que a tradução da fase 2a usa `max(T0 + 24h, emissão + 30 min)`. A infraestrutura ainda exige `date_of_expiration = T0 + 24h`, sujeita à validação L-1; a E08-03 transmite exatamente esse vencimento. O próprio §10 trata a adaptação como possível alinhamento dependente de especificação.

**Evidência reproduzível:** emissão em `T0 + 23h50min` produz vencimento em `T0 + 24h20min` pela fórmula, vinte minutos além do valor exigido atualmente. A faixa publicada comprova a incompatibilidade a tratar; não comprova aprovação dessa solução. A recusa de novas tentativas e a aceitação de pagamentos iniciados no prazo durante a margem não alteram, por si, o contrato do vencimento externo.

**Impacto:** um documento subordinado passa a orientar uma implementação diferente da fonte de verdade, sem que o leitor perceba que a escolha ainda depende de especificação.

**Correção necessária:** manter o limite publicado e o conflito rastreável, mas apresentar a fórmula apenas como proposta, sem instrução de implementação vigente. Eventual adoção deve ser formalizada nos documentos competentes pelo especificador. Não é necessário decidir essa alternativa para corrigir a referência; o revisor não a aprova nem a proíbe comercialmente neste parecer.

### MP-R02 — Importante — reembolso Pix em processamento é omitido embora já documentado

**Local:** §7, linhas 131–145, especialmente 135 e 144. **Referências internas:** especificação §9.2 e §9.5; infraestrutura 4.7; AGENTS.md §6 (nenhuma devolução duplicada e recuperação após falha).

O resumo mostra apenas `approved` como exemplo e relega os estados intermediários a algo ainda não confirmado. A [página oficial de reembolso Pix](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/payment-management/cancellations-and-refunds/refund-pix) descreve contingência em processamento que, por padrão, pode retornar HTTP 400. Com `X-Render-In-Process-Refunds: true`, o caso é exposto como HTTP 201 e `status=in_process`; o cabeçalho também se aplica à consulta individual e à listagem de reembolsos. A referência oferece [consulta individual](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/get-refund/get), ausente do resumo.

**Evidência reproduzível:** comparar os parágrafos iniciais de “Reembolsos de transações com Pix” com a linha 144. O cenário documentado é: solicitação recebida, dificuldade no processamento, resposta HTTP 400, reembolso ainda em andamento. Trata-se de informação pública já disponível, e não de uma possibilidade inventada pelo simulador.

**Impacto:** a E10 pode ser especificada sem o cenário em que erro HTTP não significa recusa definitiva, prejudicando a reconciliação de resposta incerta e a proteção contra devolução excepcional enquanto houver operação pendente. Não se afirma que o documento ordena uma segunda devolução; o problema é omitir o comportamento crítico para impedi-la.

**Correção necessária:** resumir esse cenário, cabeçalho e consultas de acompanhamento; distinguir erro de transporte/status HTTP de estado da devolução. Explicitar que o enquadramento de códigos como falha definitiva depende da situação e da reconsulta exigida pelas fontes internas. Manter L-7 aberta para prova empírica. A [introdução oficial a reembolsos](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/payment-management/cancellations-and-refunds/introduction) também documenta saldo disponível suficiente e prazo de 180 dias após aprovação: registrar esses limites como informação publicada, separadamente da validação por meio/conta. Não apresentar saldo insuficiente como inviabilidade definitiva.

### MP-R03 — Importante — tradução mistura os esquemas de Liberações e Dinheiro em conta

**Local:** §9, linhas 199–225, especialmente 221 e 223. **Referências internas:** infraestrutura 3.1–3.5, L-8/L-9; E09-02, contrato de movimentos e saldo.

A linha 221 aplica `MP_FEE_AMOUNT` tanto a `payment` quanto a `SETTLEMENT`. Esse campo pertence ao [glossário de Liberações](https://www.mercadopago.com.br/developers/en/docs/reports/released-money/report-fields). O [glossário de Dinheiro em conta](https://www.mercadopago.com.br/developers/pt/docs/reports/account-money/report-fields) usa `TRANSACTION_AMOUNT`, `FEE_AMOUNT`, `SETTLEMENT_NET_AMOUNT` e `SETTLEMENT_DATE`. `FEE_AMOUNT` agrega categorias de encargos e não pode ser tratado silenciosamente como o mesmo campo/semântica do outro relatório.

Além disso, o [guia de uso de Dinheiro em conta](https://www.mercadopago.com.br/developers/pt/docs/reports/account-money/how-to-use) diferencia `WITHDRAWAL` (DOC/TED) de `PAYOUT` (Pix). O mapeamento de saída traz `payout / WITHDRAWAL`, omitindo o `PAYOUT` desse segundo esquema; a regra residual de “outros” pode classificá-lo incorretamente.

**Evidência reproduzível:** procurar `MP_FEE_AMOUNT` no glossário de Dinheiro em conta e comparar com a entrada `FEE_AMOUNT`; depois comparar a linha 223 com as entradas `WITHDRAWAL` e `PAYOUT` no guia. Um parser que siga literalmente a linha 221 exige um campo que não é o documentado para `SETTLEMENT`.

**Impacto:** perda/duplicação de encargos ou falha de leitura na conciliação, e tratamento de saída Pix reconhecível como movimento desconhecido. É uma falha de tradução proposta, não uma divergência financeira observada em produção.

**Correção necessária:** separar os dois esquemas, com campos, datas e tipos próprios; incluir a saída `PAYOUT`. Explicitar o que é demonstrado pela fonte e o que ainda depende de amostras/L-8/L-9, sem presumir equivalência entre encargos agregados e tarifa do pagamento. Preservar o contrato interno de valores exatos e movimentos rastreáveis. A consulta dos relatórios deve continuar sujeita à validação de completude, liberação e instante de referência.

### MP-R04 — Importante — instrução de assinatura amplia indevidamente a omissão de campos

**Local:** §8, linhas 164–175. **Referências internas:** infraestrutura 4.2 e L-11; especificação §15; E07-05 (autenticidade antes de processar).

A linha 172 permite retirar qualquer valor ausente do modelo, que inclui `ts`. A [versão Markdown oficial de Webhooks, seção “Without SDKs”](https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks.md) delimita a retirada aos campos `data.id` e `x-request-id`. Ela também determina normalizar identificadores alfanuméricos para minúsculas antes de montar o manifesto, regra omitida pelo documento.

**Evidência reproduzível:** comparar a lista explícita de campos opcionais na fonte com “um dos valores do modelo” na linha 172. Para um ID alfanumérico como `ORDABC`, a fonte usa `ordabc` no manifesto; copiar literalmente o valor recebido produz outra entrada de HMAC. IDs numéricos de Payments não sofrem essa diferença.

**Impacto:** uma tradução literal pode aceitar um formato sem timestamp não respaldado pela documentação ou rejeitar notificações válidas com ID alfanumérico. Não foi demonstrada exploração nem falha do simulador: ele usa outro contrato de assinatura, corretamente registrado no §10.

**Correção necessária:** delimitar quais segmentos podem ser omitidos, não autorizar ausência de `ts`/assinatura e registrar a normalização e seu alcance. Manter L-11 para validar amostras e tolerância temporal; o caráter “a confirmar” não deve transformar uma receita incompleta em algoritmo autorizado.

## Cobertura e pontos sem achado impeditivo adicional

| Área | Resultado da conferência |
|---|---|
| Papel do documento e fases | A declaração de apoio, precedência e manutenção das limitações está correta; MP-R01 é a exceção material encontrada. Não é autorização de produção. |
| Autenticação/idempotência | Bearer e chave obrigatória são sustentados por [Criar pagamento](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/create-payment/post) e [Criar reembolso](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/create-refund/post). Repetir a mesma operação com a mesma chave é coerente com infraestrutura 4.2. Não foi validada retenção temporal da chave no sandbox. |
| Estados de pagamento | Os principais pares da tabela correspondem às [mensagens oficiais](https://www.mercadopago.com.br/developers/pt/docs/checkout-api-payments/response-handling/collection-results/introduction). A conservação do fato de aprovação é tradução interna, não afirmação de que o status externo não muda. |
| Pix | QR, dados de pagamento e faixa de vencimento conferidos; a solução do conflito de prazo é MP-R01. |
| Busca | Endpoint, filtros e paginação conferidos na [referência de busca](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/search-payments/get). “Todos” deve ser lido como contrato interno de completude dentro do recorte: a API descreve últimos doze meses e erro 9062 para intervalo de 365 dias ou mais. Não houve teste de atraso real. |
| Cancelamento | `status=cancelled` e erro 2018 para estados diferentes de pending/in_process/authorized constam da [referência específica](https://www.mercadopago.com.br/developers/pt/reference/online-payments/checkout-api-payments/create-cancellation/put). Transformar esse erro em consulta é decisão da interface, não resposta nativa da API. A corrida continua L-2. |
| Webhooks | Corpo de exemplo, resposta 200/201, espera de 22 segundos e reenvios com intervalo ampliado após a terceira tentativa conferidos na [documentação oficial](https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks). O tratamento interno rápido e idempotente corresponde à E07-05. Ressalva MP-R04. |
| Relatórios | A [geração via API](https://www.mercadopago.com.br/developers/pt/docs/reports/account-money/api) documenta `/v1/account/settlement_report`, listagem e download. O endpoint pode ser identificado documentalmente mesmo sem validar a conta no sandbox. Não foi estabelecida prova de inexistência universal de API de saldo; a conclusão deve permanecer limitada às referências consultadas e a L-9 aberta. Ressalva MP-R03. |
| Diferenças do simulador | Separar vocabulário/formato interno da tradução externa é coerente com E07/E09. Controles determinísticos de falha/atraso não comprovam frequência ou garantia de comportamento do provedor real. |

## Verificações executadas e limites

- `git status --short`: árvore limpa no início.
- `git branch --show-current`, `git log -4 --oneline`, `git rev-parse HEAD` e `git merge-base HEAD ae9bf21`: branch, commits e base conferidos.
- `git diff ae9bf21..4163af6 --stat` e diff de `docs/melhorias.md`: somente os dois documentos previstos; nenhuma implementação nessa entrega.
- Leitura UTF-8 e buscas `rg` por requisitos, limitações, prazos, reembolsos e contratos internos.
- Abertura e comparação das fontes oficiais linkadas neste parecer. A página de listagem de reembolsos retornou erro ao navegador de pesquisa; sua existência e o uso do cabeçalho são documentados pela página de reembolso Pix. O link de assinatura sem domínio nacional falhou; a versão oficial `.com.br` e sua versão Markdown foram consultadas. Não se tratam falhas de obtenção de página como ausência de recurso da API.
- `git diff --check`: sem erro no parecer.

Não houve chamada autenticada, pagamento, reembolso, sandbox, acesso a segredos ou push. Não foram executados pytest/lint/mypy: a entrega contém somente documentação; esses testes não verificariam a fidelidade da API. TDD de produção não se aplica a esta alteração documental. As evidências são leitura comparativa e referências reproduzíveis, não resultados de integração.

Nenhuma correção foi feita em `mercado-pago-api.md`, nas fontes de verdade, em código ou em testes. Não foi criada melhoria não impeditiva; os quatro achados são importantes e devem ser corrigidos antes do aceite. Próximo gate: autor/especificador corrige MP-R01 a MP-R04 e devolve o documento para revalidação independente. L-n permanecem abertas até suas validações próprias.
