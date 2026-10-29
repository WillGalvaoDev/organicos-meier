# E10-07 — Avisos de estorno, telas do administrador e do comprador

Fatia 7 de 7 da milestone **E10 — Devoluções**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.7
- Infraestrutura: v1.8
- Gate de especificação: como na E10-01.

## Contexto e objetivo

As fatias E10-02 a E10-06 entregam o cálculo, a execução e a confirmação excepcional como serviços. Esta fatia os torna visíveis e operáveis:
- **O administrador** vê as devoluções por estado, autoriza, pede nova tentativa e confirma a devolução excepcional com o comprovante.
- **O comprador** vê os estornos dos seus pedidos, com o valor, o motivo e o estado real do processamento.
- **O aviso `estorno`** (E04) é emitido nos momentos em que o estado real muda para o comprador.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §9.2 | O administrador autoriza estornos no dashboard. Exibir solicitados, pendentes, concluídos e falhos, com retentativa segura. Autorização não é dinheiro devolvido. |
| Especificação §9.5 | Confirmação administrativa com registro da transferência, comprovante e baixa da obrigação. |
| Especificação §12 | Evento "Estorno": valor, motivo (inclusive pagamento aprovado depois de `T0 + 48h` ou em duplicidade) e estado real do processamento, inclusive quando for devolução excepcional. |
| Especificação §13 | Comprador: histórico de pedidos, pagamentos e estornos. Administrador: autorização e acompanhamento de estornos; devolução excepcional com as parcelas elegíveis e a confirmação. |
| Infraestrutura 4.2 e 4.7 | Ações financeiras com nova autenticação. |
| Herdado da E04 | Emitir com `emitir_evento`, dentro da transação do fato, com a chave derivada do fato, e redigir título, corpo e link do aviso `estorno`. |
| Herdado da E08 | O aviso `estorno` ao comprador é emitido pela E10. |
| Cenários §16 | 35 e 36, pelo fluxo da tela |

## Escopo

**Dentro:**
- As rotas e telas do administrador em `/financeiro/devolucoes/`.
- A seção de estornos no detalhe do pedido do comprador.
- A emissão do aviso `estorno`.
- O download do comprovante.

**Fora:**
- O painel geral de alertas (E15).
- As telas de ocorrência, de caixa e de cancelamento, que criam reembolsos (E11, E12 e E14).

## Regras

**Telas do administrador** (só o administrador, `somente_administrador`; as ações com `exige_reautenticacao_por_passkey`):

| Rota | Método | Conteúdo ou efeito |
|---|---|---|
| `financeiro/devolucoes/` | GET | lista paginada das obrigações com comprador, nos grupos **pendentes de autorização** (devida), **solicitadas**, **em processamento**, **falhas** (`falha_temporaria`, `falha_definitiva`), **elegíveis para devolução excepcional** e **concluídas** (pela plataforma ou fora dela). Cada linha mostra o valor, o motivo, o pedido e o comprador (ou "pagamento sem pedido"), o pagamento, a situação e, nas falhas, o código, as tentativas e a próxima tentativa. O texto "Autorização não é dinheiro devolvido" aparece no topo |
| `financeiro/devolucoes/<obrigacao>/` | GET | o detalhe: a obrigação com componentes, o financiado e o sem cobertura, a parcela, o histórico, a evidência da falha definitiva e a confirmação excepcional |
| `financeiro/devolucoes/<obrigacao>/autorizar/` | POST, reautenticado | `autorizar_devolucao(obrigacao, autor=ADM)`. Recusa: a mensagem do serviço e o status 409; provedor fora do ar: "Não foi possível consultar o provedor; tente de novo", com o status 503. Sucesso: redireciona ao detalhe, com a mensagem "Devolução solicitada ao provedor" |
| `financeiro/devolucoes/<obrigacao>/tentar-de-novo/` | POST, reautenticado | `tentar_devolucao_de_novo`, com o mesmo tratamento de erro |
| `financeiro/devolucoes/<obrigacao>/excepcional/` | GET e POST, reautenticado | o formulário de confirmação, com meio, identificação, justificativa e comprovante (`multipart/form-data`), e `confirmar_devolucao_excepcional`. Só aparece para parcela `elegivel_excepcional`; para outra situação, o GET responde 409 com a mensagem da E10-06 |
| `financeiro/devolucoes/<obrigacao>/comprovante/` | GET | o arquivo do comprovante, com `Content-Disposition: attachment` e o tipo gravado. Só para o administrador; para qualquer outro perfil, 403 (ou o redirecionamento ao login, para quem não está autenticado) |

- **Botões por situação:** "Autorizar devolução" só na devida, "Tentar de novo" só em `falha_temporaria` e "Confirmar devolução feita fora da plataforma" só em `elegivel_excepcional`. O servidor recusa a ação mesmo que o botão seja forjado.
- O link "Devoluções" entra no menu financeiro do administrador (E09-08).

**Seção "Estornos" no detalhe do pedido do comprador** (`pedidos/<pk>/`, só o dono, como já é a rota):
- uma linha por obrigação do pedido, inclusive as dos pagamentos que não quitaram, com o valor, o motivo em texto e o estado real;
- os estados mostrados ao comprador:

| Situação interna | Texto ao comprador |
|---|---|
| devida | "Estorno registrado, aguardando processamento" |
| `solicitada` ou `falha_temporaria` | "Estorno solicitado à plataforma de pagamento" |
| `em_processamento` | "Estorno em processamento na plataforma de pagamento" |
| `falha_definitiva` ou `elegivel_excepcional` | "A plataforma não conseguiu devolver; o administrador fará a devolução diretamente" |
| `concluida` | "Estorno concluído pela plataforma de pagamento" |
| `concluida_fora_da_plataforma` | "Devolução feita pelo administrador por Pix ou transferência" |

- O comprador não vê códigos de falha, evidências, comprovante, identificação da transferência nem dados de outros compradores.

**Textos dos motivos:**

| Motivo | Texto |
|---|---|
| `minimo_nao_atingido` | Mínimo não atingido |
| `caixa_invalidada` | Caixa incompleta |
| `ocorrencia_de_entrega` | Ocorrência na entrega |
| `cancelamento_da_rodada` | Cancelamento da rodada |
| `aprovado_apos_a_margem` | Pagamento aprovado depois do prazo |
| `duplicidade` | Pagamento em duplicidade |
| `iniciado_fora_do_prazo` | Pagamento iniciado fora do prazo |
| `pedido_cancelado` | Pedido cancelado |
| `valor_divergente` | Valor diferente do pedido |

**Aviso `estorno`**, emitido ao comprador da obrigação com `emitir_evento(Evento.ESTORNO, comprador, ...)`, dentro da transação que muda a situação, com a chave `estorno:<parcela.pk>:<situacao>:<conta.pk>`:

| Momento | Situação nova | Título | Corpo (sempre com o valor e o motivo) |
|---|---|---|---|
| autorização | `solicitada` | "Estorno solicitado" | "Solicitamos à plataforma de pagamento a devolução de R$ X (motivo)." |
| conclusão pelo provedor | `concluida` | "Estorno concluído" | "A plataforma de pagamento concluiu a devolução de R$ X (motivo)." |
| elegível | `elegivel_excepcional` | "Estorno em andamento" | "A plataforma de pagamento não conseguiu devolver R$ X (motivo). O administrador fará a devolução diretamente por Pix ou transferência." |
| confirmação excepcional | `concluida_fora_da_plataforma` | "Devolução realizada" | "O administrador devolveu R$ X (motivo) por <Pix/transferência>." |

- O link de todos os avisos é o detalhe do pedido.
- `falha_temporaria`, `em_processamento` e `falha_definitiva` não geram aviso, porque são estados intermediários. O comprador os vê na tela.
- Obrigação sem comprador (`sem_pedido`) não gera aviso.
- O aviso não leva código de falha, identificação da transferência nem dado bancário.

## Decisões técnicas

- **Os avisos ficam nos serviços das fatias E10-04 e E10-06.** A emissão é acrescentada dentro deles, na mesma transação do fato, e não em receptores à parte. Assim, uma transação desfeita não deixa aviso. A chave de idempotência evita a duplicação nas repetições.
- **A falha temporária não avisa o comprador.** Ela é resolvida pela própria plataforma e não muda o que ele precisa fazer. O administrador a vê no alerta (E10-04).

## Invariantes

- Cada mudança de situação com aviso gera no máximo um aviso por comprador.
- Nenhuma rota de devolução aceita perfil que não seja administrador. As ações exigem passkey recente.
- O comprador só vê obrigações dos próprios pedidos.

## Casos-limite

- **Autorização com o provedor fora do ar:** a tela mostra o erro, e nada muda (E10-04 A-4).
- **Duplo envio do formulário de autorização:** uma parcela e um aviso.
- **Comprovante inválido:** o formulário volta com a mensagem e o status 400, sem gravar.
- **Formulário excepcional aberto e a parcela concluída pelo provedor antes do envio:** o POST recusa com 409 ("já devolvida pela plataforma").

## Dependências e decisões em aberto

Depende de E10-02 a E10-06, E04 (avisos), E09-08 (menu e padrões das telas financeiras) e E08 (detalhe do pedido). Nenhuma decisão em aberto.
