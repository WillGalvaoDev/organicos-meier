# E13-08 — Ponta a ponta: pedido formal, repasse e fornecedor com o simulador

Fatia 8 de 8 da milestone **E13 — Pedido formal, repasse e portal do fornecedor**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E13-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E13-01.

## Contexto e objetivo

Esta fatia não cria comportamento novo. Ela exercita, pelo caminho real, os cenários e os testes técnicos da etapa:
- as telas, os serviços, a tarefa de envio e o serviço de e-mail simulado;
- o simulador de pagamentos, com a liberação do dinheiro e as chamadas processadas pelo executor real;
- o invariante financeiro conferido ao fim de cada cenário.

Ela também entrega o cenário herdado da E12, "cancelamento depois do repasse" (infraestrutura 7).

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Infraestrutura 7, fase 1 | O simulador reproduz o cancelamento da rodada depois do repasse, com pagamento chegando depois do cancelamento. Critério de saída: os cenários 1 a 119 e T-1 a T-55 contra o simulador. |
| Infraestrutura 3.2 | Devolução devida depois do repasse: obrigação com comprador financiada por receita de serviço, reserva ou novo aporte. |
| Infraestrutura 3.4 | O invariante de liquidez; o repasse limitado ao liberado. |
| Herdado da E12 | O cenário "cancelamento depois do repasse", com a devolução financiada depois do repasse; a rodada cancelada não envia nem reenvia o pedido formal. |
| Especificação §16 | Cenários 21, 40, 67 a 70, 92 a 95, 118 e 119. |
| Infraestrutura 8 | T-11 (segunda metade), T-25, T-27, T-28, T-29, T-41, T-54 e T-55. |

## Escopo

**Dentro:** os cenários de ponta a ponta abaixo.

**Fora:**
- A retirada e as ocorrências de entrega (E14).
- A decisão sobre cancelar uma rodada `disponivel_para_retirada` (herdada para a E14).

## Cenários de ponta a ponta

1. **Do resultado aprovado ao pedido aceito** (cenários 67 e 68):
   - **ação:** a aprovação pela tela (E11-07); o serviço de e-mail falha na primeira tentativa e aceita na segunda; a tarefa roda nos instantes do ciclo;
   - **esperado:**
     - duas tentativas, um envio aceito, nenhum aviso ao administrador;
     - o e-mail igual ao snapshot;
     - o fornecedor vê o pedido formal e a previsão no portal.
2. **Três falhas e reenvio** (cenários 69, 92, 93 e 94; T-28, T-41 e T-54):
   - **ação:** três falhas automáticas; durante o ciclo, o reenvio pela tela é recusado; depois da terceira, o aviso ao administrador e o reenvio pelo link do aviso;
   - **esperado:** a primeira tentativa manual falha, e a segunda é aceita, sem ciclo automático novo; o snapshot e o identificador iguais do começo ao fim.
3. **Duplo clique e acionamentos concorrentes** (cenários 70, 95, 118 e 119; T-29 e T-55):
   - **ação:** pela rota HTTP, com transações reais:
     - dois POST com o mesmo token;
     - dois POST com tokens distintos ao mesmo tempo;
     - um POST durante uma tentativa automática em execução;
   - **esperado:** os resultados da E13-03 A-15 a A-17.
4. **Ajuste da previsão** (cenário 67):
   - **ação:** o ajuste pela tela;
   - **esperado:** o aviso aos compradores dos pedidos válidos; a nova previsão no portal do fornecedor e no pedido do comprador; o pedido formal e o reenvio seguinte com o conteúdo original.
5. **Repasse limitado ao liberado** (cenário 40; T-11):
   - **arranjo:** a liberação do Pix em 72 h no simulador;
   - **ação:** um repasse pela tela antes da liberação, recusado; o relógio avançado; o repasse parcial e depois o total;
   - **esperado:**
     - cada repasse só baixa a obrigação com aquele fornecedor;
     - a conciliação do dia não aponta divergência, com as saídas também registradas no simulador (`registrar_saida` do controle do simulador);
     - o invariante sem violação.
6. **Cancelamento depois do repasse** (herdado da E12; infraestrutura 3.2 e 7):
   - **arranjo:** AF aprovada, com o pedido formal aceito e o repasse total registrado (no livro e no simulador);
   - **ação:** o cancelamento com reembolso pela tela (E12-06);
   - **esperado:**
     - a parte de produtos das devoluções fica sem cobertura, porque a obrigação com o fornecedor já foi repassada;
     - o serviço e o frete são financiados pela receita de serviço e pelo frete da rodada, pela regra da E09-06;
     - o administrador cobre a falta com a reserva (P-3) e, se ela não bastar, com um novo aporte;
     - a tarefa de autorização (E12-03) autoriza, os estornos concluem no simulador e o invariante fica sem violação;
     - o pedido formal e as tentativas ficam intactos, e o reenvio é recusado (`rodada_cancelada`);
     - o repasse registrado continua no livro, sem mudança (§7.2).
7. **Pagamento depois do cancelamento, com repasse feito** (infraestrutura 7; E12-04):
   - **arranjo:** o cenário 6;
   - **ação:** uma cobrança pendente aprovada no simulador depois do cancelamento;
   - **esperado:** a devolução integral pelo próprio pagamento e o alerta crítico (E12-04); nenhuma mudança no repasse nem na obrigação com o fornecedor.
8. **Visibilidade do fornecedor de ponta a ponta** (cenários 21 e 67; T-25 e T-27):
   - **ação:** em cada etapa dos cenários 1 a 6, a conta do fornecedor consulta o portal e tenta as rotas proibidas;
   - **esperado:** os campos e as recusas da E13-07.

## Regras

- Cada cenário roda contra o simulador de pagamentos, sem dublê do provedor, salvo o controle explícito de falhas dele (`falhar_proximas`) e da liberação (`definir_liberacao`).
- O serviço de e-mail é o backend de teste (`locmem` e `tests/apoio/email_falho.py`), e "aceito" é o retorno sem exceção de `enviar_email` (L-13).
- Ao fim de cada cenário: `verificar_invariante_agora()` sem alerta `invariante_violado`. Esta é a última asserção de cada teste.
- Para cada pedido formal: o assunto e o corpo de todo e-mail enviado são iguais aos gravados, e existe um único `PedidoFormal` por ciclo.

## Dependências e decisões em aberto

- Depende das E13-01 a E13-07 e das E09 a E12.
- Nenhuma decisão em aberto.
- **Herdado para a E14:** o encerramento da rodada (`disponivel_para_retirada`) com o pedido formal; a decisão do responsável sobre cancelar uma rodada nessa etapa (milestone 14).
