# E13-05 — A previsão de entrega: ajuste, aviso e exibição

Fatia 5 de 8 da milestone **E13 — Pedido formal, repasse e portal do fornecedor**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E13-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E13-01.

## Contexto e objetivo

O prazo padrão de entrega vem do fornecedor e gera a previsão inicial na emissão do pedido formal (E13-01). Depois dos pagamentos, o administrador pode ajustar a previsão (§4.3, §10). A alteração gera o aviso `previsao_de_entrega_alterada` com a nova previsão para os pedidos afetados (§12). O fornecedor consulta a previsão vigente (§2, E13-07).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §4.1, §4.3 | Prazo padrão de entrega do fornecedor; a previsão pode ser ajustada depois dos pagamentos. |
| Especificação §10 | O prazo padrão de entrega vem do fornecedor e pode ser ajustado pelo administrador depois dos pagamentos. |
| Especificação §12 | Alteração de previsão de entrega: nova previsão para os pedidos afetados. |
| Especificação §13 | Administrador: previsão de entrega. Fornecedor: consulta da previsão de entrega. |
| Especificação §2 | Comprador suspenso consulta os pedidos pagos; comprador removido tem o acesso bloqueado. |
| Herdado da E04 | Emitir o aviso com `emitir_evento` na transação do fato, com chave derivada do fato. Canais: site e e-mail (`CANAIS_POR_EVENTO`). |
| Cenários §16 | 67 (o fornecedor vê a previsão de entrega) |

## Escopo

**Dentro:**
- O serviço `ajustar_previsao_de_entrega` e a exceção `PrevisaoRecusada`.
- O aviso aos compradores.
- O bloco da previsão na página do pedido formal (E13-04) e a rota de ajuste.
- A linha da previsão na página do pedido do comprador.

**Fora:** a consulta do fornecedor (E13-07).

## Regras

`ajustar_previsao_de_entrega(autor, rodada, data) -> PrevisaoDeEntrega`:

1. **Permissão:** só o administrador ativo; senão `PermissionDenied`, sem escrita.
2. **Validação da data:** um `datetime.date` (não `datetime`); outro tipo: `PrevisaoRecusada("data_invalida")`.
3. **Transação e trava:** a `Rodada`, com `select_for_update(no_key=True)`, relida. É a mesma trava do cancelamento (E12) e dos envios (E13-02), então o ajuste e o cancelamento se serializam.
4. **Conferências sob a trava**, na ordem (a primeira que falha vale):
   - a rodada em `aguardando_fornecedor`, com pedido formal; senão `PrevisaoRecusada("fora_de_aguardando_fornecedor")`, com a mensagem "A previsão só pode ser ajustada com a rodada aguardando o fornecedor.";
   - a data não anterior a hoje no calendário de Brasília; senão `PrevisaoRecusada("data_passada")`, com "A previsão não pode ser uma data passada.";
   - a data diferente da previsão vigente; senão `PrevisaoRecusada("sem_alteracao")`, com "A data informada já é a previsão vigente."
5. **Registro:** uma `PrevisaoDeEntrega` de origem `ajuste`, com o autor e `registrada_em`. A previsão vigente passa a ser ela (E13-01). O `PedidoFormal`, as linhas e o conteúdo do e-mail não mudam: o pedido formal guarda a previsão da emissão (E13-01, regra 6), e um reenvio manda o mesmo conteúdo (Q-3).
6. **Aviso `previsao_de_entrega_alterada`**, na mesma transação:
   - **destinatários:** os compradores dos pedidos válidos do ciclo (`PedidoApurado`), um aviso por comprador;
   - **exclusão:** as contas removidas (acesso bloqueado, §2);
   - **inclusão:** as suspensas recebem, porque consultam os pedidos pagos (§2);
   - **chave:** `previsao_de_entrega_alterada:<previsão>:<conta>`;
   - **título:** `Previsão de entrega alterada: <fornecedor>`;
   - **corpo:** `A previsão de entrega do seu pedido <pk> da rodada de <fornecedor> passou de <dd/mm/aaaa> para <dd/mm/aaaa>.`;
   - **link:** `/pedidos/<pk>/`;
   - **privacidade:** o corpo não traz dado de outro comprador.
7. **Auditoria `rodada.previsao_de_entrega`:** o autor, a rodada, o ciclo, a data anterior e a nova, e quantos compradores foram avisados.

**Tela do administrador** (na página do pedido formal, E13-04):

8. **Bloco "Previsão de entrega":**
   - a previsão vigente, em `dd/mm/aaaa`;
   - o histórico das previsões (data, "Prazo padrão de <n> dias" ou "Ajuste", o administrador e o momento em Brasília);
   - com a rodada em `aguardando_fornecedor`, um formulário com um campo de data (`data`, no formato `aaaa-mm-dd` do campo de data do navegador) e o botão "Alterar previsão".
9. **Rota** `POST administracao/rodadas/<pk>/previsao/` (nome `rodadas_previsao`), `somente_administrador`; `GET` dá 405:
   - **sucesso:** redireciona para a página do pedido formal com "Previsão de entrega alterada para <dd/mm/aaaa>.";
   - **data ausente ou fora do formato:** a página com 400 e "Informe uma data válida.";
   - **`PrevisaoRecusada`:** a página com 409 e a mensagem da recusa (`data_invalida` dá 400);
   - **sem pedido formal:** 404.

**Comprador** (`pedidos/<pk>/`):

10. **Previsão no pedido:** um pedido válido de uma rodada em `aguardando_fornecedor` mostra "Previsão de entrega: <dd/mm/aaaa>.", com a previsão vigente. Nas outras etapas, e nos pedidos que não são válidos (cancelados ou só com unidades invalidadas), a linha não aparece.

## Decisões técnicas

- **Ajuste só em `aguardando_fornecedor`.** O §10 permite o ajuste depois dos pagamentos, e a previsão só existe com o pedido formal (aprovação). Na retirada liberada os produtos já chegaram (E14), e a rodada cancelada não tem entrega a prever.
- **Sem data passada.** A previsão é uma expectativa de entrega futura. Uma data passada não é previsão, e o servidor a recusa (AGENTS §6: o servidor valida prazos).
- **O pedido formal não muda.** O pedido formal congelado é o pedido feito ao fornecedor (infraestrutura 4.14). A previsão ajustada é consultada pelo fornecedor no portal (E13-07), sem gerar outro pedido formal.

## Invariantes

- A previsão vigente é sempre a de maior `pk` do ciclo.
- Nenhum ajuste altera o pedido formal ou as tentativas.
- Um aviso por ajuste e comprador.

## Casos-limite e concorrência

- **Dois ajustes em paralelo:** serializados pela trava da rodada. O segundo compara com a previsão gravada pelo primeiro: com a mesma data, recebe `sem_alteracao`; com outra, grava e avisa de novo.
- **Ajuste e cancelamento em paralelo:** se o cancelamento trava antes, o ajuste recebe `fora_de_aguardando_fornecedor`.
- **Ajuste para hoje:** aceito.

## Dependências e decisões em aberto

- Depende das E13-01 e E13-04 e da E04.
- Nenhuma decisão em aberto.
