# E09-08 — Telas financeiras do administrador

Fatia 8 de 8 da milestone **E09 — Livro-razão, reserva e conciliação**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação: como na E09-01.

## Contexto e objetivo

O administrador precisa ver e operar o livro-razão:

- os saldos por destinação, com o liberado e o a liberar;
- os movimentos com a justificativa;
- a reserva, com o saldo, o comprometido, o livre, os aportes e as utilizações;
- as despesas pendentes, as obrigações sem cobertura, os alertas abertos e as conciliações.

Também precisa registrar aportes, coberturas, designações e retiradas. Esta fatia entrega essas telas sobre os serviços das fatias anteriores. Toda ação que move dinheiro ou escolhe uma origem exige nova autenticação por passkey.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §13, administrador | Livro-razão por destinação, com movimentações justificadas, e reserva financeira (aportes, utilizações, saldo e alertas de insuficiência). Apuração, déficit de frete e acompanhamento de estornos. |
| Especificação §9.4 | O sistema apresenta o saldo da reserva e os alertas de insuficiência. |
| Infraestrutura 2 | Admin com passkey obrigatória e nova autenticação antes de aportes e movimentações entre destinações. |
| Infraestrutura 3.3 | O painel mostra saldo, comprometido, livre, histórico de aportes e utilizações e o alerta de insuficiência. |
| Especificação §2 e 17.9 | O fornecedor não vê taxa de serviço nem reserva. O comprador não vê nada financeiro de outros. |
| E02-10 | Toda view declara uma política. |

## Escopo

**Dentro:** as rotas da tabela abaixo, os formulários e as mensagens.

**Fora:**

- A tela do repasse (E13).
- As telas das devoluções (E10).
- O painel consolidado (E15).
- Exportações.

## Regras

**Rotas** (prefixo `/administracao/financeiro/`):

| Nome | Caminho | Métodos | Política |
|---|---|---|---|
| `financeiro_resumo` | `` | GET | `somente_administrador` |
| `financeiro_movimentos` | `movimentos/` | GET (filtros `destinacao`, `rodada`) | `somente_administrador` |
| `financeiro_reserva` | `reserva/` | GET | `somente_administrador` |
| `financeiro_aporte` | `reserva/aporte/` | GET e POST | `exige_reautenticacao_por_passkey` |
| `financeiro_designar` | `obrigacoes/<id>/designar/` | POST | `exige_reautenticacao_por_passkey` |
| `financeiro_desfazer_designacao` | `designacoes/<id>/desfazer/` | POST | `exige_reautenticacao_por_passkey` |
| `financeiro_cobrir_obrigacao` | `obrigacoes/<id>/cobrir/` | POST | `exige_reautenticacao_por_passkey` |
| `financeiro_cobrir_despesa` | `despesas/<id>/cobrir/` | POST | `exige_reautenticacao_por_passkey` |
| `financeiro_retirada` | `retirada/` | GET e POST | `exige_reautenticacao_por_passkey` |
| `financeiro_conciliacoes` | `conciliacoes/` | GET | `somente_administrador` |

**Conteúdo do resumo:**

| Bloco | Mostra |
|---|---|
| Alertas abertos | `alertas_abertos()`, com os críticos em destaque |
| Por destinação | custódia por rodada e ciclo (soma dos compradores); obrigações com fornecedores por fornecedor e rodada, com liberado e a liberar; frete por rodada, com efetivo, arrecadado, devolvido, déficit e déficit coberto (`frete_do_ciclo`); receita de serviço por rodada, com liberado; obrigações com compradores com devido, financiado, designado, liquidado e sem cobertura; despesas a cobrir |
| Reserva | saldo, comprometido e livre, e o aviso "Reserva insuficiente: obrigações sem cobertura de R$ X para um saldo livre de R$ Y." enquanto o alerta estiver aberto |
| Pendências | despesas pendentes e obrigações sem cobertura, cada uma com as ações de cobrir, designar ou desfazer |
| Conciliação | a última `ConciliacaoDiaria`, com o resultado |

**Movimentos:** os mais recentes primeiro, em páginas de 50. Cada um mostra:

- o tipo;
- o momento, no horário de Brasília;
- o autor ("Sistema" ou o nome da conta);
- a justificativa;
- a origem;
- as transferências, de e para, com o valor em reais.

O filtro por destinação e rodada mostra só os movimentos que tocam essas contas.

**Reserva:** o histórico de aportes (data, valor, identificação, autor e justificativa), as utilizações e designações (alvo, valor, situação, autor e justificativa) e os desfazeres.

**Formulários:**

| Formulário | Campos | Serviço |
|---|---|---|
| Aporte | valor (vírgula ou ponto, `ler_decimal_digitado`), identificação do depósito no provedor, justificativa | `registrar_aporte` |
| Designar reserva | valor, justificativa | `designar_reserva` |
| Desfazer designação | justificativa | `desfazer_designacao` |
| Cobrir obrigação | rodada da receita (lista das rodadas com saldo de receita), valor, justificativa | `cobrir_obrigacao_com_receita` |
| Cobrir despesa | fonte (reserva ou a receita de uma rodada), valor, justificativa | `cobrir_despesa` |
| Retirada da receita | rodada (com o liberado ao lado), valor, identificação da saída no provedor, justificativa | `registrar_saida(tipo="retirada_de_receita")` |

- **Recusa:** cada recusa de serviço vira uma mensagem no formulário, com status 400 ou 409 conforme o caso e sem escrita. A mensagem diz o motivo e os valores relevantes. Por exemplo: "O valor passa do saldo livre da reserva (R$ 20,00)." ou "Só R$ 30,00 da receita desta rodada estão liberados no provedor.".
- **Sucesso:** a página redireciona com uma mensagem de confirmação (PRG).
- **Sem passkey recente:** as rotas de ação levam para a nova autenticação e voltam depois.

**Links:** o link dos avisos `alerta_financeiro` (E09-03) passa a apontar para `financeiro_resumo`. O menu do administrador ganha "Financeiro".

## Interfaces

As rotas acima, com os templates em `templates/financeiro/`.

## Invariantes

- Nenhuma view escreve no livro-razão sem passar pelos serviços das fatias anteriores.
- Nenhuma rota financeira responde a comprador ou fornecedor: ambos recebem 403, sem dados.
- Valores sempre em `Decimal`, exibidos com o filtro `reais` existente.

## Casos-limite e concorrência

- **Duplo clique no aporte:** a identificação única recusa o segundo, com a mensagem de aporte já registrado.
- **Valores com separador de milhar ou mais de duas casas:** recusados no formulário.
- **Rodada ou obrigação inexistente na URL:** 404.

## Dependências e decisões em aberto

Depende de E09-01 a E09-07. Nenhuma decisão em aberto.
