# E15-05 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

- **Arranjos:**
  - **AP-I:** fornecedor G em `interesse`, mínimo R$ 200,00, produto Q de R$ 10,00 por unidade com múltiplo 12 e 18 unidades em interesse. Pelo §6.1: elegível R$ 120,00, 6 aguardando, faltam 6.
  - **AP-I2:** o AP-I com o mínimo de G reduzido a R$ 100,00 antes do interesse (mínimo atingido).
  - **AE**, **AE-recebido** e **AE-liberada:** os da E14-01 (fornecedor F; X de A e Y de B; produtos R$ 170,00; frete R$ 22,00), com `simulador_pagamentos.definir_liberacao("pix", horas=0)`.
  - Os prazos e etapas de fechamento e de pagamento vêm dos apoios das E06, E08 e E11.
- **Página:** `GET /administracao/` como ADM1 autenticado com passkey. As seções são localizadas pelos títulos `<h2>`.
- **Instantes:** como nos arranjos. Datas em Brasília.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Ordem das seções | positivo | sem rodada nem alerta | GET | 200; os títulos "Alertas abertos", "Ações necessárias", "Rodadas", "Prazos encerrados" e "Tarefas periódicas", nessa ordem; "Nenhum alerta aberto.", "Nenhuma ação pendente.", "Nenhuma rodada em andamento." e "Nenhum prazo encerrado aguardando.". **Red esperado:** as seções não existem |
| A-2 | Regra 1 | positivo | `invariante_violado` (crítico) aberto depois de `tarefa_atrasada` e de `chamada_ao_provedor_falhou` | GET | os três, com o crítico primeiro; a gravidade, o título, o corpo, "aberto em" e o link "Ver" de cada um; o formulário "Dar ciência" só no `chamada_ao_provedor_falhou`, com `action` para `/administracao/alertas/<pk>/ciencia/` e CSRF |
| A-3 | Regras 3 e 6 | positivo | AP-I | GET | na linha de G: "Interesse"; "R$ 120,00 de R$ 200,00 (60%)"; "Q: 6 unidade aguardando, faltam 6 para a próxima caixa"; prazo "—"; o link "Abrir"; nenhuma ação de G |
| A-4 | Regra 3 | positivo | AP-I2 | GET | a ação "Mínimo atingido: o fechamento pode ser iniciado." de G, com o link de `rodadas_estoque` |
| A-5 | Regras 6 e 8 | positivo | AP-I2 com o fechamento iniciado, prazo `P` | GET antes de `P`; depois em `P + 1min` sem encerrar | antes: "Fecha em <P>"; a coluna de caixas preenchida; sem prazo encerrado. Depois: o prazo encerrado "<G>: fechamento vencido em <P>, aguardando o encerramento automático." |
| A-6 | Regras 3, 6 e 8 | positivo | o A-5 com `encerrar_fechamentos_vencidos()` (mínimo mantido) | GET | etapa "Fechamento com prazo encerrado"; "Encerrado em <P>"; a coluna de caixas "—"; a ação "Fechamento encerrado: aguarda a abertura do pagamento."; o prazo encerrado "<G>: fechamento encerrado em <P>." |
| A-7 | Regras 3, 6 e 8 | positivo | rodada em `pagamento` com `T0` | GET em `T0 + 1h` e em `T0 + 48h` | em `T0 + 1h`: "Pagamento até <T0+24h>; margem até <T0+48h>"; sem ação de apuração. Em `T0 + 48h`: "Apta para a apuração final desde <T0+48h>."; o prazo encerrado "margem encerrada em <T0+48h>" |
| A-8 | Regra 3 | positivo | o A-7 com a apuração válida feita e não aprovada | GET | "Apuração feita: aguarda a aprovação do resultado."; nenhuma ação de "Apta para a apuração"; nenhuma linha de margem encerrada |
| A-9 | Regra 3 | positivo | AE com o pedido formal em `concluido_com_falhas` (três falhas, E13-02) | GET; reenvio manual (E13-04) com o e-mail falhando; GET; reenvio manual aceito; GET | "O pedido formal não foi enviado depois das três tentativas: reenvie.", com o link de `rodadas_pedido_formal`; depois do reenvio que falhou, a ação continua; depois do reenvio aceito, a ação some (a situação do ciclo continua `concluido_com_falhas`) |
| A-10 | Regra 3 | positivo | AE com P1 recebido 11 e P2 nada | GET | "Recebimento: 1 produto(s) a resolver." |
| A-11 | Regra 3 | positivo | AE-recebido sem endereço registrado; depois com endereço | GET nos dois estados | "Recebimento resolvido: a retirada pode ser liberada. Registre antes o endereço de retirada."; depois, sem a segunda frase |
| A-12 | Regra 3 | positivo | AE depois da aprovação, com a liberação do simulador em 0 horas | GET; depois o repasse de R$ 170,00 e o frete de R$ 22,00 pela tela da E13-06; GET | "Repasse ao fornecedor liberado: R$ 170,00." e "Pagamento do frete liberado: R$ 22,00."; depois, nenhuma das duas |
| A-13 | Regras 3, 5, 6 e 8 | positivo | AE-liberada com o relógio em `L + 8 dias` e nenhum descarte | GET | etapa "Disponível para retirada"; "Retirada até 12/11/2026 10:00"; a ação "Prazo de retirada encerrado: 4 item(ns) pendente(s) de decisão."; o prazo encerrado com o link de `rodadas_retiradas` |
| A-14 | Regra 5 | positivo | AE-liberada com todos os saldos retirados ou descartados | GET | a rodada fora da tabela; nenhuma ação dela |
| A-15 | Regra 5 | negativo | rodada cancelada (E12) com pedidos | GET | a rodada fora da tabela e dos prazos encerrados |
| A-16 | Regra 3, globais | positivo | AE com a ocorrência `faltante` de 2 em X-P1 (obrigação de R$ 23,59, devida) | GET | "Devoluções a autorizar: 1 (R$ 23,59)." com o link de `financeiro_devolucoes`; depois da autorização (E10), a ação some |
| A-17 | Regra 3, globais | positivo | AE-recebido com o repasse total e uma ocorrência depois dele (E14-08 A-4: R$ 10,00 de produtos sem cobertura) | GET | "Itens sem cobertura: 2 (R$ 11,29)." com o link de `financeiro_reserva`. Os dois itens de `itens_sem_cobertura()`: a obrigação com R$ 10,00 de produtos sem cobertura e a despesa de déficit de frete de R$ 1,29, nascida quando a devolução tirou o frete da rodada já apurada (`registrar_obrigacao`, E09) |
| A-18 | Regra 3, ordem | positivo | AP-I2 (G) e AE (F), com ações nas duas e uma devolução devida | GET | as ações dos dois fornecedores na ordem alfabética dos nomes (o teste dá nomes que tornam a ordem diferente da ordem dos pk) e a global por último |
| A-19 | Regras 9 e 10 | positivo | `processar_envios_pendentes` atrasada com falha `RuntimeError`; as demais em dia; `verificar_operacao` sem registro; `ConciliacaoDiaria` de 19/11/2026 sem divergência | GET | onze linhas; "Atrasada desde <data>" e "Última falha em <data>: RuntimeError" em Envio de notificações; "Sem registro de execução" em Verificação operacional; "Última conciliação: 19/11/2026 (Sem divergência)" |
| A-20 | Regra 10 | positivo | nenhuma conciliação | GET | "Nenhuma conciliação registrada." |
| A-21 | Regra 11 | positivo | um `Envio` em `falhou` | GET | "Olá, <nome>.", os links "Envios" e "Financeiro", "Envios com falha: 1", o botão "Sair" e os links de Fornecedores, Usuários, Convites, Comunicados e Endereço de retirada (os testes atuais de `test_notificacoes_administracao.py` e `test_financeiro_telas.py` continuam passando sem alteração) |
| A-22 | Acesso | negativo | AE | GET como comprador A e como a conta do fornecedor F; GET anônimo | 403, 403 e o fluxo de login atual (`test_admin_area_restrita.py` sem alteração) |
| A-23 | Regra 12 | negativo | AE-liberada com a ocorrência e AP-I | GET | nenhum nome ou e-mail dos compradores A, B e C no HTML |
| A-24 | Invariante | negativo | os estados do A-6, A-12 e A-13 | GET e comparar o banco | nenhuma escrita (contagem das tabelas de domínio e de alertas igual) |
| A-25 | Regra 13 | positivo | 5 rodadas: interesse, fechamento, pagamento, aguardando fornecedor e disponível para retirada | GET | 200; as 5 linhas na ordem das etapas |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-25 | `tests/tecnicos/test_painel_administrativo.py` |
