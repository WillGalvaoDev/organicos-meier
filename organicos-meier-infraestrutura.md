# Orgânicos Méier — Recomendação de infraestrutura e fases de implementação

Versão 1.7 · 14 de outubro de 2026
Base: `organicos-meier-especificacao-funcional.md` (v1.6)

### Histórico de versões

| Versão | Alterações |
|---|---|
| 1.0 | Primeira versão. |
| 1.1 | Incorpora A1 (reserva), A2 (prazo e margem) e A3 (pagamentos só pela plataforma). Remove o modo de pagamento manual. Abre as pendências P-1 a P-8. |
| 1.2 | Incorpora as decisões aprovadas P-1 a P-8 e a nova redação de A1 a A3. Pagamentos aprovados até `T0 + 48h` passam a ser aceitos. Cria a devolução excepcional (P-5). Detalha o livro-razão por destinação. Os critérios R1 a R14 viram cenários da especificação (§16) e testes técnicos (seção 8). Separa as limitações técnicas a validar (L-1 a L-12). |
| 1.3 | Ajustes pontuais. **Devolução excepcional:** feita pelo admin diretamente ao comprador, fora da integração. A plataforma só registra a confirmação administrativa e a baixa da obrigação, sem exigir saída da conta do provedor. **Frete no retorno ao interesse:** todos os valores recebidos são devolvidos e não há frete efetivo. Seções 3.1, 3.5, 3.6, 4.2, 4.7, 8, 9.2 e 11. |
| 1.4 | Reflete as decisões 17.2 e 17.3 da especificação v1.3: cancelamento da rodada inteira com ou sem reembolso integral (nova seção 4.8) e pedido congelado imutável com ocorrências de entrega (nova seção 4.9). Seções 3.2, 4.2, 4.4, 5, 7, 8, 9 e 11. |
| 1.5 | Reflete as decisões 17.4 a 17.11 da especificação v1.4, com 17.2 e 17.3 reconfirmados sem mudança. Novas seções 4.10 a 4.14: interesses, reservas e condições da rodada; contas e banimento; medidas decimais; visibilidade do fornecedor; envio do pedido formal. Seção 4 renomeada para "Pagamentos e fluxos críticos". Testes T-20 a T-29 e limitação L-13. Seções 4, 5, 7, 8, 9 e 11. |
| 1.6 | Reflete Q-1 a Q-4 e R-1 a R-4 da especificação v1.5: fila de pendentes com a rotina `alocar_pendentes`, e-mail normalizado único e invalidação de sessões, quantidades fracionárias em qualquer unidade com subtotal `ROUND_HALF_UP`, compatibilidade múltiplo/incremento, reenvio manual também depois de sucesso. Seções 4.10, 4.11, 4.12, 4.14, 5, 7, 8, 9 e 11. Testes T-30 a T-41. L-13 mantida. Novas questões Q-5 a Q-7. |
| 1.7 | Reflete Q-5 a Q-7 e R-5 a R-8 da especificação v1.6: remoção de pendentes pelo comprador, prioridade e isolamento da fila, pendentes fora do mínimo, alteração transacional do incremento, reembolso parcial proporcional ao subtotal com controle acumulado, bloqueio do reenvio durante o ciclo automático, validação de incrementos inteiros e fracionários. Seções 4.9, 4.10, 4.12, 4.14, 7, 8, 9 e 11. Testes T-42 a T-55. Nenhuma questão de implementação aberta. |

### Convenção de classificação

- **[A1–A3] / [P-1–P-8]**: decisão de negócio aprovada pelo responsável pelo projeto. O texto completo está na especificação funcional, na seção indicada.
- **[Derivado]**: requisito técnico necessário para cumprir uma decisão aprovada. Não cria regra comercial.
- **[Validar L-n]**: comportamento do provedor ainda não comprovado. Precisa de prova de conceito ou confirmação na documentação (seção 9.2) e não pode ser tratado como funcionalidade garantida.
- **Q-n**: ambiguidade de negócio que impede ou condiciona a implementação. Listada na especificação §17 e não resolvida por inferência.

As escolhas de stack e provedores são recomendações técnicas e não recebem marcação.

## 1. Premissas

- Escala inicial: 100 compradores e 50 fornecedores cadastrados, um administrador. Pouca concorrência real, com picos na abertura e no fim do prazo de pagamento.
- Prioridades: **segurança e integridade financeira** primeiro, **custo de implantação e manutenção** em seguida.
- Manutenção por um desenvolvedor solo. Evitar complexidade que não se paga nessa escala.
- Meios de pagamento: Pix, cartão de crédito e cartão de débito, **exclusivamente pelo provedor integrado** [A3].
- O Mercado Pago **não** é presumido como oferecendo segregação nativa de saldo, nem como garantindo a aprovação de cobranças depois do vencimento. A segregação é feita pelo livro-razão [P-2]. Os comportamentos de vencimento estão em validação (L-1 a L-5).

## 2. Stack recomendada

| Camada | Escolha | Justificativa |
|---|---|---|
| Aplicação | **Django 5** com templates no servidor e **HTMX**, num único deploy | Sem front separado, sem tokens no navegador e sem CORS. Autorização verificada no servidor em toda view e consulta. Regras financeiras em Python, testáveis. |
| Autenticação | **django-allauth** | Senha, link ou código por e-mail, Google, MFA (TOTP e passkeys) e nova autenticação antes de ações sensíveis. Um adaptador próprio recusa cadastros sem convite válido ou com e-mail banido, inclusive pelo Google. Admin: passkey obrigatória e nova autenticação antes de autorizar apuração, estornos, devoluções excepcionais, repasses, aportes e movimentações entre destinações. |
| Banco | **Neon Postgres**, região São Paulo (`aws-sa-east-1`) | Restauração a qualquer momento (PITR) incluída no plano pago, branches para desenvolvimento e homologação, dados no Brasil. |
| Hospedagem | **Fly.io**, região `gru` (São Paulo) | Uma instância web e uma worker, com custo previsível. Segredos via `fly secrets`. Homologação num app separado que desliga sozinho sem uso. |
| Tarefas e prazos | **Procrastinate** (fila dentro do Postgres) | Sem Redis. Tarefas periódicas, retomáveis e com travas no banco. Processa chamadas pendentes ao provedor, bloqueio em `T0 + 24h`, conciliação da margem e conciliação diária. |
| Pagamentos | **Mercado Pago**: Pix e cartão via **Checkout Pro** | Um único provedor, uma conciliação e um saldo. Checkout Pro é a opção com menor exposição a dados de cartão. |
| E-mail | **Amazon SES** (região São Paulo) | Custo baixo por mensagem e sem limite diário que atrapalhe os comunicados. Exige saída do modo sandbox. |
| WhatsApp | **Meta WhatsApp Cloud API**, direto | Templates *utility* com opt-in registrado. Fase 3. |
| Arquivos e backup externo | **Cloudflare R2** | Avatares, comprovantes de devoluções excepcionais e aportes, e `pg_dump` diário criptografado, num provedor diferente do banco. |
| Observabilidade | **Sentry** (sem envio de dados pessoais) e **Better Stack** (monitor de disponibilidade) | Mais os alertas da seção 3.6. |
| DNS e proteção | **Cloudflare** (plano grátis) | DNS, proteção contra negação de serviço e limite de requisições nas rotas de login e convite. |

As decisões A1 a A3 e P-1 a P-8 não exigem nenhuma tecnologia ou provedor novo. Os comprovantes ficam no R2, que já estava na stack.

### Alternativas descartadas

- **Supabase + Vercel:** a restauração a qualquer momento é um adicional caro, as regras críticas ficariam divididas entre RLS, funções SQL e o front, e o custo da Vercel Pro (a partir de US$ 20) cresce com o uso. O plano Hobby da Vercel não permite uso comercial.
- **VPS própria:** transfere atualizações, firewall, backup e restauração para o desenvolvedor. Vai contra a prioridade de segurança.
- **AWS ou GCP completos:** custo maior sem ganho nesta escala.
- **Stripe:** o Pix passa pela EBANX e, para empresas fora do Brasil, incide IOF de 3,5%.

## 3. Arquitetura financeira

Especificação funcional: §9.3 a §9.5.

### 3.1 Livro-razão e destinações [A1, P-1, P-2]

Todo valor tem uma destinação. Todo movimento é um lançamento que só aceita inserção, com autor (usuário ou regra do sistema), momento, justificativa e vínculo com a origem: pedido, ciclo, pagamento, devolução, repasse, aporte ou movimentação.

| Destinação | Granularidade | Contém |
|---|---|---|
| **Custódia das rodadas** | rodada, ciclo e comprador, por componente (produtos, frete, serviço) | Valores pagos antes da apuração final |
| **Obrigações com fornecedores** | fornecedor e rodada | Produtos devidos ao fornecedor depois da apuração final |
| **Frete** | rodada | Frete arrecadado, frete efetivo e déficit, registrados separadamente [P-1] |
| **Obrigações com compradores** | parcela de devolução | Devoluções devidas e ainda não liquidadas |
| **Receita de serviço** | rodada | Taxa de serviço de pedidos válidos, menos as devoluções proporcionais de serviço |
| **Reserva** | única | Aportes do admin, menos as utilizações [A1, P-3, P-4] |
| **Despesas** | por tipo | Tarifas do provedor, déficits de frete, outros prejuízos operacionais |

- **Frete efetivo**: só existe quando a compra ao fornecedor é realizada. Corresponde ao frete `F` informado pelo admin na abertura do pagamento. Quando a rodada volta para interesse por insuficiência de pagamentos, todos os valores recebidos são devolvidos e não há frete efetivo (especificação §8.2 e §9.3).
- **Déficit de frete** = frete efetivo − frete arrecadado líquido de devoluções. Inclui a parcela dos inadimplentes (§8.2) e as devoluções proporcionais de frete (§9.2). É responsabilidade do admin [P-1], sem cobrança adicional retroativa a compradores [P-1].

### 3.2 Regras de movimentação

| Evento | Lançamento | Classificação |
|---|---|---|
| Pagamento aprovado e aceito | Entrada na custódia da rodada, por componente | Derivado |
| Tarifa do provedor sobre um pagamento | Despesa coberta pela receita de serviço | P-1 |
| Apuração final aprovada | Custódia → obrigações com fornecedores (produtos), frete arrecadado (frete), receita de serviço (serviço) | Derivado |
| Devolução devida antes do repasse | Obrigação com comprador financiada pela custódia ou pela obrigação daquela mesma rodada | P-2 (ressalva das devoluções devidas) |
| Devolução devida depois do repasse | Obrigação com comprador financiada por receita de serviço, reserva ou novo aporte | P-2, P-3 |
| Pagamento aprovado depois de `T0 + 48h` ou em duplicidade | Obrigação de devolução integral, financiada pelo próprio pagamento | P-6, Derivado |
| Déficit de frete | Despesa financiada por receita de serviço, reserva ou novo aporte | P-1, P-2, P-3 |
| Aporte | Entrada na reserva | A1, P-4 |
| Cancelamento da rodada com reembolso | Uma obrigação de devolução integral por comprador que pagou (valor pago menos devoluções concluídas ou pendentes), financiada como as demais devoluções (antes ou depois do repasse) | 17.2, P-2 |
| Cancelamento da rodada sem reembolso | Nenhum lançamento novo. Obrigações existentes mantidas. Valores continuam nas destinações em que estavam, e qualquer movimentação posterior segue P-2. | 17.2, P-2 |
| Ocorrência de entrega com reembolso pontual | Obrigação de devolução dos itens afetados, com serviço e frete proporcionais (§9.2), financiada como as demais devoluções | 17.3, P-2 |
| Repasse manual ao fornecedor | Baixa da obrigação com aquele fornecedor | A3, P-2 |
| Retirada da receita de serviço pelo admin | Baixa da receita de serviço | Derivado |

- **Movimentação entre destinações** [P-2]: explícita, com justificativa, rastreável e auditável.
  - Lançamentos cuja origem já está fixada por uma regra aprovada (por exemplo, tarifa coberta pela receita de serviço) são gerados pelo sistema, citando a regra como justificativa.
  - Lançamentos em que há escolha de origem (receita de serviço, reserva ou novo aporte) exigem autorização do admin com nova autenticação [Derivado].
- **Proibições** [P-2]: recursos de um fornecedor nunca financiam tarifas, déficits, prejuízos ou obrigações de outro fornecedor, nem despesas da plataforma. O sistema recusa no servidor qualquer lançamento com esse efeito.
- **Tarifa sem receita de serviço suficiente:** por exemplo, numa rodada que volta para interesse e devolve o serviço. A tarifa fica como despesa pendente de cobertura, e o admin escolhe a origem entre receita de serviço acumulada, reserva ou novo aporte [P-2, P-3].

### 3.3 Reserva [A1, P-3, P-4]

- Aporte inicial de R$ 1.000,00 de capital próprio. Não é receita.
- Pode cobrir estornos, tarifas, déficits de frete e outros prejuízos ou despesas operacionais [P-3].
- Não limita a responsabilidade por estornos e não autoriza utilizar recursos de fornecedores [A1].
- **Saldo comprometido** [Derivado]: quando o admin designa a reserva para cobrir uma obrigação, o valor fica separado para aquela obrigação. Ele não pode ser usado para outra despesa até a obrigação ser liquidada ou a designação ser desfeita com justificativa. Isso cumpre "não comprometer recursos reservados para obrigações existentes" [P-3].
- **Saldo livre** = saldo − saldo comprometido. Nenhuma utilização é aceita acima do saldo livre, e nenhuma utilização reduz valores devidos a fornecedores ou compradores [P-3].
- **Sem recomposição automática** até R$ 1.000,00 [P-4]. O painel mostra saldo, comprometido, livre, histórico de aportes e utilizações, e um alerta de insuficiência quando as obrigações sem cobertura superam o saldo livre.
- **Onde fica o dinheiro** [Derivado]: o aporte é depositado **na conta do provedor**, porque o Mercado Pago só estorna com saldo disponível. O depósito é recurso próprio do admin, não pagamento de comprador, e não conflita com A3. Como esse depósito aparece no extrato e na API: [Validar L-9].

### 3.4 Liquidez e saldo único

O provedor tem um saldo único. A segregação é contábil, garantida pelo livro-razão [P-2].

- **Liquidez por destinação** [Derivado]: cada lançamento de entrada registra a data de liberação do dinheiro no provedor, separando valor liberado de valor a liberar [Validar L-10]. Datas de liberação variam por meio de pagamento.
- **Repasse ao fornecedor** [Derivado de P-2]: limitado à parte **liberada** da obrigação com aquele fornecedor. Pagar o fornecedor A com dinheiro liberado que pertence ao fornecedor B seria financiar a obrigação de A com recursos de B, o que P-2 proíbe.
- **Invariante** [Derivado]: saldo do provedor (liberado + a liberar) ≥ custódia + obrigações com fornecedores + frete arrecadado não pago + obrigações com compradores. A diferença positiva corresponde aos recursos da plataforma (receita de serviço não retirada + reserva). Uma violação gera alerta crítico e bloqueia novas utilizações da reserva e retiradas de receita.

### 3.5 Conciliação

- **Diária:** compara o livro-razão com o saldo e os movimentos do provedor [Validar L-9]. Divergência gera alerta.
- Toda saída da conta do provedor é registrada no livro-razão: repasse, retirada de receita, devolução pela plataforma.
- Devoluções excepcionais são registradas como liquidadas fora do provedor. A conciliação não espera saída correspondente na conta e não as aponta como divergência (seção 4.7).

### 3.6 Alertas

Gerados por tarefas agendadas e enviados ao admin:

- violação do invariante;
- insuficiência da reserva;
- pagamento sem conciliação;
- pagamento aprovado depois de `T0 + 48h`;
- pagamento em duplicidade;
- devolução com falha ou em falha definitiva;
- devolução elegível para devolução excepcional, aguardando confirmação do admin;
- tarefa atrasada;
- falha de mensagem;
- divergência na conciliação diária.

## 4. Pagamentos e fluxos críticos

Especificação funcional: §2 a §10. Seções 4.1 a 4.7: pagamentos e devoluções. Seções 4.8 a 4.14: cancelamento, pedido congelado, interesses, contas, medidas, visibilidade do fornecedor e pedido formal.

### 4.1 Exclusividade do provedor [A3]

- Todos os pagamentos de compradores ocorrem exclusivamente pelo provedor integrado. É proibido recebê-los por Pix direto, transferência ou qualquer mecanismo externo.
- A fase 1 usa só o simulador, sem dinheiro real. A operação real começa na fase 2a.
- A aplicação não inicia em produção com o simulador habilitado.
- Os repasses manuais aos fornecedores continuam permitidos.
- A devolução excepcional (seção 4.7) **não** é exceção à proibição de recebimentos externos.

**Requisitos derivados:**

- Não existe tela nem rota que permita registrar como recebido um pagamento de comprador fora do provedor.
- Cada pagamento registra o provedor e o ambiente.
- A verificação de inicialização compara ambiente e implementação de pagamento configurada, e encerra o processo se produção estiver com o simulador.

### 4.2 Princípios de integração [Derivado]

- **O provedor é a fonte da verdade.** O webhook só avisa: o sistema verifica a assinatura [Validar L-11], registra o evento com chave única e uma tarefa consulta `GET /v1/payments/{id}` antes de aplicar qualquer estado.
- **Consulta obrigatória antes de decisões irreversíveis:** apuração final, aprovação do resultado da cobrança, envio do pedido formal, autorização ou nova tentativa de devolução, confirmação de devolução excepcional, registro de repasse, cancelamento da rodada com reembolso. Se a consulta falhar, a ação fica bloqueada.
- **Chave de idempotência (`X-Idempotency-Key`):** gravada no banco **antes** da chamada, uma por pedido, ciclo e tentativa, ou por parcela de devolução, e reaproveitada nas novas tentativas.
- **`external_reference`** com o pedido e o ciclo de cobrança, para que um pagamento antigo nunca quite um pedido novo.
- **Chamadas pendentes:** toda chamada ao provedor é registrada numa tabela na mesma transação que muda o estado, e executada por uma tarefa.
- **Instantes registrados separadamente:** criação da tentativa no provedor, **aprovação no provedor** (`date_approved`), recebimento do webhook e consulta. Os horários do provedor são normalizados para UTC [Validar L-4].
- **Reconhecimento único:** cada pagamento do provedor é reconhecido uma única vez (restrição `UNIQUE` no identificador externo). Se houver mais de um pagamento aprovado e aceito para o mesmo pedido, só um quita o pedido e os demais geram obrigação de devolução integral.
- **Concorrência:** webhook, bloqueio por prazo, conciliação e autorização do admin atualizam o pedido sob trava de linha (`select_for_update`), sempre reconsultando o estado dentro da transação. A decisão sobre aceitar um pagamento depende só do `date_approved` do provedor, então a ordem de chegada dos eventos não altera o resultado.

### 4.3 Linha do tempo da cobrança [A2, P-6, P-7, P-8]

`T0` = instante em que o admin autoriza a abertura do pagamento, gravado pelo servidor em UTC.

| Instante ou intervalo | Regra | Origem |
|---|---|---|
| `T0 ≤ t < T0 + 24h` | Comprador pode criar tentativas e pagar | A2 |
| `t ≥ T0 + 24h` | Novas tentativas recusadas no servidor. Prazo improrrogável, inclusive pelo admin. | A2, P-7 |
| `T0 + 24h ≤ t ≤ T0 + 48h` | Margem operacional: só confirmação e conciliação de pagamentos já iniciados. Não reabre compras, não altera pedidos, não autoriza novas cobranças. | A2, P-6 |
| `date_approved ≤ T0 + 48h` | Pagamento iniciado no prazo e aprovado até aqui é **aceito** e quita o pedido, qualquer que seja o horário do webhook | P-6 |
| `date_approved > T0 + 48h` | Não quita o pedido. Gera obrigação de devolução integral. | P-6 |
| `t ≥ T0 + 48h` | Apuração final pode começar, só com autorização do admin. Nunca antes, mesmo com todos os pedidos pagos. | A2, P-8 |

**Requisitos derivados:**

- **Margem também improrrogável.** O critério de aceitação de P-6 é fixo em `T0 + 48h`. O admin pode iniciar a apuração depois de `T0 + 48h`, mas isso não amplia a janela de aceitação.
- **"Pagamento já iniciado"** = tentativa com criação no provedor antes de `T0 + 24h`. O servidor já impede criar tentativas depois disso. Mesmo assim, uma tentativa com criação registrada em `T0 + 24h` ou depois, por qualquer anomalia, não é aceita e gera obrigação de devolução.
- **Bloqueio ativo em `T0 + 24h`:** a tarefa agendada cancela no provedor as tentativas ainda pendentes [Validar L-2]. Se o pagador concluir no mesmo instante em que o cancelamento é enviado, vale o que o provedor registrar: aprovado com `date_approved ≤ T0 + 48h` é aceito, conforme P-6.
- **Durante a margem**, uma tarefa reconsulta todas as tentativas do ciclo e busca pagamentos pelo `external_reference` [Validar L-6]. O painel mostra a situação de cada pedido: aprovado no prazo, aprovado na margem, pendente, não pago, sem resposta do provedor. Pedidos não pagos não são cancelados durante a margem.
- **Apuração final:** recusada no servidor antes de `T0 + 48h`. Quando autorizada, executa nesta ordem:
  1. reconsulta todas as tentativas e faz a busca por `external_reference`;
  2. cancela no provedor tentativas ainda não terminais;
  3. aplica P-6 pelo `date_approved`;
  4. segue os passos de §8.2 da especificação.

  Se o provedor estiver indisponível, a apuração fica bloqueada.
- **Fronteiras:** comparação com precisão de milissegundos em UTC. `T0 + 24h` exato já é bloqueado. `date_approved = T0 + 48h` exato é aceito.

### 4.4 Pagamentos tardios [P-6]

- Aprovados entre `T0 + 24h` e `T0 + 48h` (tentativa iniciada no prazo): aceitos, quitam o pedido e geram a notificação "Pagamento confirmado".
- Aprovados depois de `T0 + 48h`: registrados, nunca ignorados, não quitam o pedido. Geram obrigação de devolução integral, executada pelo provedor ou, se comprovadamente inviável, pela devolução excepcional.
- **Risco residual** [Validar L-6]: o provedor pode informar, só **depois** da apuração, uma aprovação com `date_approved ≤ T0 + 48h` (atraso de consistência do provedor). P-6 manda aceitar, mas a apuração já cancelou o pedido. As mitigações são a reconsulta e a busca por `external_reference` na apuração, mais a nova consulta antes da autorização de avanço. Se mesmo assim ocorrer, o pagamento é registrado, gera alerta crítico e recebe tratamento financeiro auditado pelos mecanismos existentes, **sem editar o pedido apurado** (especificação §7.1 e §8.3). A prova de conceito deve medir se esse atraso existe na prática.

### 4.5 Pix

- `date_of_expiration` = `T0 + 24h` [Validar L-1].
- Cancelamento ativo das cobranças pendentes em `T0 + 24h` [Validar L-2].
- Aprovação depois do vencimento: não presumida possível nem impossível [Validar L-3].
- **Se a prova de conceito mostrar um intervalo mínimo entre a criação e o vencimento do Pix** (por exemplo, um Pix gerado a poucos minutos de `T0 + 24h` não poder vencer exatamente em `T0 + 24h`), o cancelamento ativo em `T0 + 24h` passa a ser o mecanismo principal. Se o cancelamento também não for viável, a incompatibilidade volta ao responsável pelo projeto como decisão de negócio. A implementação não pode encurtar o prazo do comprador nem estender a janela de pagamento por conta própria.
- Estorno parcial e integral pela API [Validar L-7].

### 4.6 Cartão de crédito e débito (fase 2b)

- **Checkout Pro** com:
  - `binary_mode: true`;
  - `installments: 1`;
  - boleto e outros meios lentos excluídos (`excluded_payment_types`);
  - `expiration_date_to` = `T0 + 24h` [Validar L-5].
- Nenhuma preferência nova é criada a partir de `T0 + 24h`. Um pagamento iniciado antes e aprovado até `T0 + 48h` é aceito, conforme P-6.
- Limite de tentativas por pedido e por usuário, contra testes de cartão.
- Contestações e mediações: eventos recebidos pelo webhook e confirmados na API, registrados como lançamentos novos. Se o repasse já ocorreu, a perda é coberta por receita de serviço, reserva ou novo aporte, nunca por recursos de fornecedores [P-2, P-3].
- Captura adiada: fora da v1. A margem de 48 horas mais a decisão do admin podem ultrapassar o prazo de autorização do cartão.

### 4.7 Devoluções [P-5]

**Estados por parcela de devolução:**

```
devida → solicitada ao provedor → concluída
                ↓
        falha temporária → nova tentativa (mesma chave de idempotência)
                ↓
   falha definitiva comprovada → elegível para devolução excepcional
                ↓
   confirmação administrativa de devolução realizada fora da integração → concluída (baixa da obrigação)
```

- **Via principal:** o provedor integrado [P-5].
- **"Comprovadamente inviável"** [Derivado]: resposta do provedor que caracterize falha definitiva, como prazo de estorno vencido ou meio que não permite estorno [Validar L-7], guardada como evidência. Antes de passar a "elegível", o sistema reconsulta o pagamento e as devoluções no provedor e confirma que não há nenhuma em processamento ou concluída para a parcela.
- **Execução fora da plataforma** [P-5]: o admin faz a devolução diretamente ao comprador, por Pix ou transferência, fora da integração. A plataforma não executa a devolução, não tem integração para ela e não exige que o dinheiro saia da conta do provedor.
- **Confirmação administrativa** [P-5]: é a única ação da plataforma nesse fluxo. É explícita e exige nova autenticação. Registra pedido, comprador, valor, justificativa, identificação da transferência e comprovante (guardado no R2), e dá baixa na obrigação financeira. Até a confirmação, a obrigação continua integral.
- **Conciliação:** como o dinheiro não sai necessariamente da conta do provedor, a baixa não tem saída correspondente no saldo. A conciliação diária trata o lançamento como liquidado fora do provedor (seção 3.5).
- **Proteção contra duplicidade** [P-5]: a confirmação é recusada enquanto houver devolução em processamento no provedor para a mesma parcela. Depois da confirmação, novas tentativas no provedor ficam bloqueadas e uma segunda confirmação da mesma parcela é recusada. Somadas, as devoluções concluídas nunca passam do valor pago.
- **Risco residual:** o provedor concluir tardiamente uma devolução já declarada como falha definitiva. Detectado pela conciliação, gera alerta crítico. A reconsulta antes de declarar a falha definitiva reduz o risco [Validar L-7].
- A exceção vale só para devoluções, nunca para receber pagamentos [P-5, A3].
- **Origens de uma devolução:** caixa inválida, mínimo não atingido, pagamento depois de `T0 + 48h`, duplicidade, ocorrência de entrega e cancelamento com reembolso. Todas usam os mesmos estados e a mesma proteção contra duplicidade.

### 4.8 Cancelamento da rodada [17.2]

- **Uma ação, uma rodada:** a ação recebe só a rodada e a indicação de reembolso devido (sim ou não). Não aceita lista de compradores, motivo obrigatório nem informação sobre o fornecedor. A mensagem aos compradores é opcional.
- **Permissão:** só o perfil de admin, verificado no servidor, com nova autenticação, como as demais operações financeiras. A nova autenticação é proteção de acesso, não etapa de aprovação.
- **Execução** [Derivado], numa única transação com a rodada travada:
  1. registra o cancelamento (autor, momento, indicação de reembolso) na auditoria;
  2. remove interesses e libera reservas;
  3. bloqueia novas tentativas de pagamento;
  4. com reembolso: gera as obrigações de devolução integral (seção 3.2), já autorizadas pela própria indicação;
  5. sem reembolso: não gera obrigações.

  As chamadas ao provedor (cancelar tentativas pendentes [Validar L-2], solicitar as devoluções) entram na tabela de chamadas pendentes.
- **Idempotência:** cancelar uma rodada já cancelada é recusado. A geração de obrigações usa uma chave por rodada e comprador, então uma nova execução não duplica devoluções.
- **"Integral" sem duplicar:** para cada comprador, a obrigação é o valor pago menos as devoluções concluídas e as pendentes da mesma parcela. Obrigações pendentes continuam no seu fluxo e não são substituídas.
- **Pagamento aprovado depois do cancelamento:** registrado, gera alerta e recebe tratamento financeiro auditado pelos mecanismos existentes, sem alterar pedidos (especificação §7.2 e §8.3).
- Registros anteriores (pagamentos, repasses, devoluções, lançamentos) não são alterados.

### 4.9 Pedido congelado e ocorrências de entrega [17.3]

- **Imutabilidade no banco** [Derivado]: a partir da abertura do pagamento, os itens do pedido ficam protegidos contra `UPDATE` e `DELETE` por uma trigger no Postgres, além de não haver rotas de edição. Uma tentativa de alteração é recusada e registrada.
- **Estado separado da composição:** o estado financeiro e operacional (pago, cancelado, devolvido, retirado, descartado) fica em registros próprios, que referenciam o pedido sem alterá-lo.
- **Ocorrências de entrega:** registros que só aceitam inserção, com item do pedido, quantidade, tipo (faltante, incorreto, não entregue), autor e momento. A soma das quantidades por item não pode passar da quantidade paga, o que é verificado sob trava de linha. Cada ocorrência gera no máximo uma obrigação de reembolso pontual, com chave de idempotência própria.
- **Cálculo:** produtos afetados + serviço proporcional + frete proporcional (§9.2), pela rotina de reembolso parcial da seção 4.12 (Q-7).
- Só o admin registra ocorrências. Não há rota de comprador para isso.

### 4.10 Interesses, reservas e condições da rodada [17.4, 17.5, 17.11, Q-1, Q-5, Q-6, R-2, R-5, R-6]

- **Parcela com identidade estável** [Derivado]: cada parcela de interesse tem identificador e número de sequência imutáveis, gerados por sequência do banco, que definem a posição FIFO. A parcela registra situação (ativa, em pedido, pendente, removida), quantidade reservada e quantidade pendente sem reserva. Restaurar ou reservar a partir da fila muda só esses campos. Não cria parcela, número de sequência ou reserva nova.
- **Restauração depois de caixa invalidada (17.4, Q-1):**
  - executada na apuração final, na mesma transação que invalida a caixa, sem esperar o estorno;
  - em rodada que segue viável, as unidades afetadas dos adimplentes passam para "pendente" na **fila de pendentes do fornecedor**, com quantidade reservada zero na rodada apurada;
  - idempotência pela chave única (parcela, caixa invalidada): uma reexecução não restaura de novo.
  - Em rodada que volta para interesse, vale o retorno ao interesse abaixo (seção 11).
- **Reserva a partir da fila (Q-1, R-5):** uma rotina única, `alocar_pendentes(fornecedor)`, faz o seguinte numa transação, com trava de linha do estoque de cada produto:
  1. percorre as parcelas pendentes em ordem de sequência;
  2. reserva para cada uma o mínimo entre a quantidade pendente e o estoque livre, sempre em múltiplos do incremento;
  3. atualiza quantidade reservada e quantidade pendente.

  Ela roda na abertura da fase de interesse da rodada seguinte e antes de qualquer nova reserva, sempre que estoque é liberado (remoção, redução, inadimplência) ou aumentado. A adição de um interesse novo chama a rotina antes de reservar para si, o que preserva a FIFO entre pendentes e novos (especificação §5.2). Execuções concorrentes se serializam pela trava, e o resultado não depende da ordem. A rotina só lê parcelas pendentes do próprio fornecedor e só reserva estoque da rodada ativa desse fornecedor (isolamento de R-5).
- **Invariantes verificadas em teste e por restrição:** total reservado ≤ estoque. Quantidade reservada + pendente ≤ quantidade original da parcela. Nenhuma reserva fictícia: parcela pendente sem estoque fica com reserva zero.
- **Pendentes fora do ciclo (R-6):** o cálculo do mínimo, a formação de caixas, a abertura do pagamento, o pedido formal e as cobranças leem só a quantidade reservada. A quantidade pendente sem reserva nunca entra nessas consultas. Quando a rodada sai da fase de interesse, ela continua pendente para a rodada seguinte.
- **Inadimplentes:** perdem todas as parcelas daquele fornecedor (situação "removida"), inclusive as pendentes, com a liberação das reservas na mesma transação. A liberação aciona `alocar_pendentes` quando a rodada está em interesse.
- **Retorno ao interesse (17.5):** o estoque não é tocado. As reservas de quem pagou são mantidas ou reativadas com o mesmo número de sequência, e as dos inadimplentes são liberadas. A invariante "total reservado ≤ estoque" é verificada sob trava de linha do estoque do produto. Estornos pendentes seguem no seu fluxo, sem bloquear a rodada.
- **Condições congeladas (17.11, Q-6):** mínimo, múltiplo, incremento e estoque só podem ser alterados quando a rodada ativa do fornecedor está em interesse. O servidor recusa a alteração em qualquer outra etapa, inclusive para o admin. Uma redução de estoque abaixo do total reservado é recusada sob trava. Toda alteração de múltiplo também passa pela validação de compatibilidade com o incremento (seção 4.12, R-2). No início do fechamento, os valores vigentes são gravados no ciclo, e os ciclos anteriores nunca são reescritos. Alterações de preço seguem a especificação §5.1, fora desse bloqueio.
- **Ciclos:** parcelas que entram em um novo ciclo geram um pedido novo, com snapshot próprio. Pagamentos e estornos do ciclo anterior continuam vinculados ao ciclo anterior pelo `external_reference` (seção 4.2).
- **Consulta do comprador (Q-5):** a consulta do carrinho e do histórico devolve, por parcela e por produto, a quantidade reservada e a quantidade pendente em campos separados, inclusive com estoque zerado. Cada comprador vê só as próprias parcelas.
- **Remoção de pendentes (Q-5):** uma rota própria, `remover_pendente(comprador, produto, quantidade)`, numa transação com trava das parcelas do comprador naquele produto:
  1. aceita só quantidade múltipla do incremento e até o total pendente do comprador;
  2. reduz a quantidade pendente das parcelas a partir da mais recente (especificação §5.2);
  3. não altera a quantidade reservada nem a sequência de nenhuma parcela;
  4. marca a parcela como removida quando reservado e pendente ficam zero.

  A rota só atua sobre o campo de quantidade pendente. Não aceita identificadores de itens de pedido nem de parcelas na situação "em pedido". A trigger de imutabilidade da seção 4.9 continua protegendo os pedidos congelados. Por usar a mesma trava de `alocar_pendentes`, a quantidade removida nunca vira reserva.

### 4.11 Contas, acesso e banimento [17.6, 17.7, Q-2, R-3]

- **Uma conta, um papel:** cada conta é comprador ou fornecedor, definido pelo convite. Não há conta com dois papéis. As rotas de compra exigem o papel de comprador, e as de fornecedor exigem o vínculo com o fornecedor, sempre verificado no servidor.
- **Normalização única (R-3):** uma única função, `normalizar_email`, remove espaços nas pontas e converte para minúsculas, sem tratar aliases (`+`, pontos). Ela é usada em cadastro, convite, login (senha, link, Google), verificação de unicidade e banimento. Testes garantem que nenhum desses fluxos compara e-mails sem passar por ela.
- **E-mail exclusivo (Q-2):** coluna `email_normalizado` com restrição `UNIQUE` no banco, cobrindo todas as contas, de qualquer papel. A aplicação verifica antes, para dar mensagem clara, e a restrição do banco resolve corridas: dois cadastros simultâneos com o mesmo e-mail resultam em um sucesso e uma recusa.
  - A emissão e o consumo de convite para e-mail já associado a uma conta são recusados.
  - No login com Google, o adaptador do django-allauth associa o login somente à conta com o mesmo `email_normalizado`. Nunca cria uma segunda conta, e só cria a primeira com convite válido.
- **Banimento por e-mail:** tabela própria, com `email_normalizado` único. A verificação ocorre no adaptador do django-allauth para todos os métodos e no consumo do convite. O banimento atinge só o endereço banido. Outras contas da mesma pessoa, com outros e-mails, não são afetadas.
- **Invalidação de sessões (R-3):** ao banir, na mesma transação, a conta é marcada como banida e todas as sessões ativas dela são apagadas. Um middleware também recusa qualquer requisição autenticada de conta banida, para cobrir sessões em cache ou criadas durante a corrida.
- **Suspensão:** é um estado da conta, reversível, e não entra na tabela de banimento.

### 4.12 Medidas e valores decimais [17.8, Q-4, Q-6, Q-7, R-1, R-2, R-8]

- **Quantidades:** `Decimal` no Python e `NUMERIC(12,3)` no Postgres, para qualquer unidade (kg, L, unidade, caixa e outras) [Derivado].
- **Incremento (R-8):** obrigatório por produto, `NUMERIC(12,3)`, inteiro ou fracionário, maior que zero e com no máximo 3 casas decimais. Valores como 1, 2, 0,25 e 0,5 são válidos, e não há fracionamento obrigatório. A entrada é recebida como texto decimal e convertida para `Decimal`. Números em ponto flutuante na API são recusados, e a validação usa só `Decimal`.
- **Validação de quantidade:** o servidor valida `quantidade % incremento == 0` em toda adição ou alteração, inclusive pela API.
- **Compatibilidade (R-2):** o servidor exige `múltiplo % incremento == 0` no cadastro e em toda alteração de múltiplo permitida na fase de interesse. Configuração incompatível é recusada.
- **Preços e subtotais (R-1):**
  - preço unitário em `NUMERIC(12,2)`;
  - subtotal do item = `(preço × quantidade).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`, calculado uma única vez;
  - `P` = soma dos subtotais arredondados;
  - preço unitário, quantidade e subtotal cobrado gravados no snapshot do pedido.
- **Sem ponto flutuante binário:** nenhum `float` em valores monetários ou quantidades. Uma verificação estática e testes de tipo garantem isso.
- **Reembolsos:** leem os valores do snapshot do ciclo original e nunca o preço atual do catálogo. O reembolso do item inteiro usa o subtotal registrado.
- **Reembolso parcial (Q-7):** a rotina `reembolso_parcial(item, quantidade)` roda numa transação com trava do item do pedido e de seu acumulador de reembolsos. O item tem subtotal `S`, quantidade `Q`, valor já reembolsado `R` e quantidade já reembolsada `q_r`.
  1. Recusa se `q_r + quantidade > Q` ou se a quantidade não é múltipla do incremento registrado.
  2. Se `q_r + quantidade == Q`: valor = `S − R` (devolução integral exata).
  3. Senão: valor = `min((S × quantidade / Q).quantize(0.01, ROUND_HALF_UP), S − R)`.
  4. Grava um registro de devolução novo (só aceita inserção) e atualiza o acumulador. O pedido congelado não é tocado.

  Serviço e frete usam o mesmo esquema por componente, sobre os valores registrados do pedido, com acumulador próprio e devolução integral exata do saldo [Derivado, especificação §9.2]. A mesma rotina atende ocorrências de entrega, caixas invalidadas e o reembolso integral do cancelamento, que passa a quantidade restante. Assim, toda devolução de um item passa pelo mesmo acumulador e o resultado é determinístico.
- Caixas e remoção de excedentes usam a mesma aritmética decimal. Com R-2, nenhuma parcela fica com quantidade fora do incremento.
- **Alteração do incremento (Q-6):** a rotina `alterar_incremento(produto, novo)` roda numa transação com trava da linha do produto e das parcelas do produto:
  1. recusa se a rodada ativa do fornecedor não está em interesse;
  2. recusa se o novo valor é inválido (R-8);
  3. recusa se alguma quantidade reservada ou pendente de qualquer parcela do produto não é múltipla do novo valor, incluindo as pendentes na fila do fornecedor;
  4. recusa se `múltiplo % novo != 0`.

  Qualquer recusa reverte a transação inteira, sem escrita. A adição de interesse também trava a linha do produto, então adições e alterações de incremento se serializam e a validação sempre usa o incremento vigente. Os ciclos anteriores mantêm o incremento registrado no seu snapshot.

### 4.13 Visibilidade do fornecedor [17.9]

- As consultas do fornecedor usam serializadores próprios com **lista de campos permitidos**: produtos, quantidades agregadas, preços unitários, valores totais dos produtos, andamento, pedido formal e previsão de entrega. Qualquer campo fora da lista não é exposto.
- O filtro pelo fornecedor vinculado é aplicado no conjunto de consulta (queryset), não só na tela. Isso vale para exportações e downloads.
- Testes de autorização cobrem acesso direto por identificador a pagamentos, compradores, taxa de serviço, reserva e dados de outro fornecedor.

### 4.14 Envio do pedido formal [17.10, Q-3, R-4]

- **Pedido formal único:** gerado uma vez por ciclo aprovado, com identificador e conteúdo congelados (snapshot). Todo envio, automático ou manual, usa esse mesmo snapshot.
- **Ciclo automático:**
  - no máximo três tentativas no total, incluindo a primeira, pela tabela de chamadas pendentes, com intervalos crescentes definidos na implementação;
  - "falha" é a recusa ou o erro na chamada ao Amazon SES [Validar L-13];
  - o ciclo termina no primeiro sucesso ou na terceira falha;
  - cada tentativa registra tipo (automática ou manual), número, horário, resultado, resposta e, quando manual, o admin.
- **Esgotadas as três:** alerta ao admin (especificação §12) e botão **Reenviar pedido** disponível.
- **Depois de sucesso (Q-3):** botão **Reenviar pedido** também disponível.
- **Durante o ciclo automático (R-7):** enquanto houver tentativa automática agendada ou em execução, o reenvio manual é recusado no servidor. O estado do ciclo (em andamento, concluído com sucesso, concluído com três falhas) é gravado no pedido formal e lido sob a mesma trava usada pelos envios, então uma tentativa automática e um acionamento manual nunca correm juntos.
- **Reenvio manual (R-4):**
  - cada acionamento executa exatamente uma tentativa e nunca inicia novo ciclo automático;
  - cada acionamento carrega um token de requisição único, gravado com restrição `UNIQUE`: requisições repetidas com o mesmo token (duplo clique, reenvio do formulário) geram um único envio, e um acionamento novo gera uma tentativa nova;
  - um envio em andamento para o mesmo pedido formal fica sob trava, então duas tentativas não saem ao mesmo tempo.
- O reenvio não altera o pedido formal nem gera outro. A aceitação pelo SES não comprova entrega (L-13, mantida em aberto).

## 5. Integridade, segurança e dados

- `transaction.atomic` e `select_for_update` em estoque, fila, caixas, congelamento dos pedidos, reconhecimento de pagamentos, parcelas de devolução e lançamentos do livro-razão.
- Restrições `UNIQUE` em convites, eventos de webhook, identificadores externos de pagamento, chaves de idempotência e designações de reserva.
- Histórico financeiro, livro-razão e auditoria só aceitam inserção. Ajustes financeiros entram como lançamentos novos.
- Itens de pedido congelado protegidos contra alteração no banco (seção 4.9). Ocorrências de entrega só aceitam inserção.
- Restrições `UNIQUE` na sequência das parcelas de interesse, no `email_normalizado` das contas, na tabela de banimento, na chave (parcela, caixa invalidada) da restauração e no token de reenvio do pedido formal (seções 4.10, 4.11 e 4.14). Trava de linha no estoque por produto em reserva, restauração e alteração de estoque (seção 4.10).
- Prazos checados nas tarefas agendadas **e** em cada ação. Instantes em UTC, exibidos em America/Sao_Paulo. Relógio do servidor sincronizado por NTP. Possível diferença entre o relógio do provedor e o do servidor: [Validar L-4].
- Ambientes separados, cada um com credenciais próprias. O simulador nunca é ativado em produção.
- Segredos só em variáveis do provedor. Nenhum dado pessoal em logs nem no Sentry. Comprovantes no R2 com acesso restrito ao admin.
- Dados principais no Brasil (Neon e Fly.io em São Paulo). SES, Sentry e Cloudflare processam parte dos dados fora do país: minimizar o que é enviado e registrar isso na avaliação de LGPD.

## 6. Backup e recuperação

| Camada | Mecanismo | Perda máxima de dados (RPO) |
|---|---|---|
| Principal | Restauração a qualquer momento do Neon | minutos, dentro da janela do plano |
| Externa | `pg_dump` diário criptografado no Cloudflare R2 | 24h |
| Financeira | Conciliação com a API do provedor depois de restaurar | ~0 para o que o provedor registra |

- Procedimento depois de uma restauração: congelar as rodadas, conciliar pagamentos, devoluções e saldo, conferir o livro-razão e o estoque, e avisar quem foi afetado.
- Aportes, repasses, retiradas de receita e devoluções excepcionais registrados depois do último ponto recuperado são reconferidos com o extrato e os comprovantes.
- Prazos `T0 + 24h` e `T0 + 48h` vencidos durante a indisponibilidade continuam valendo: o critério de aceitação usa o `date_approved` do provedor, não o horário de processamento.
- O tempo de recuperação (RTO) só é definido depois de um **teste de restauração cronometrado**, repetido todo trimestre.

## 7. Fases de implementação

Nenhum pagamento de comprador é recebido fora do provedor integrado, em nenhuma fase [A3].

### Fase 0: preparação (paralela ao início da fase 1)

- **Prova de conceito no sandbox do Mercado Pago** cobrindo L-1 a L-12 (seção 9.2), com as respostas registradas. Os resultados ajustam a interface interna de pagamento antes da fase 2a.
- Contador: pessoa física ou CNPJ (MEI), tratamento contábil do aporte, das destinações e das devoluções excepcionais.
- Domínio, Cloudflare, contas no Neon, Fly.io, R2, SES e Sentry.

### Fase 1: plataforma completa com simulador

**Escopo:** toda a especificação v1.6, incluindo o livro-razão por destinação, a reserva, a linha do tempo `T0`/`T0 + 24h`/`T0 + 48h`, o fluxo de devoluções com a excepcional, o cancelamento da rodada, as ocorrências de entrega e as regras das seções 4.10 a 4.14, inclusive remoção de pendentes, alteração de incremento e reembolso parcial.

**Pagamento:** fica atrás de uma interface interna (criar cobrança, consultar, buscar por referência, cancelar tentativa, estornar, consultar saldo e movimentos, receber evento). A única implementação na fase 1 é o **simulador**, sem dinheiro real [A3]. Ele reproduz:

- webhooks atrasados, repetidos e fora de ordem;
- aprovação antes de `T0 + 24h`, entre `T0 + 24h` e `T0 + 48h`, exatamente em `T0 + 48h` e depois;
- webhook de aprovação feita na margem chegando só depois de `T0 + 48h`;
- dois pagamentos aprovados para o mesmo pedido;
- cancelamento de tentativa coincidindo com o pagamento;
- estorno parcial, falha temporária, falha definitiva, saldo insuficiente;
- datas de liberação diferentes por meio de pagamento;
- aporte e saídas da conta;
- contestação;
- cancelamento da rodada durante a margem e depois do repasse, com pagamento chegando depois do cancelamento;
- API fora do ar.

**Ambientes:** desenvolvimento e homologação. Sem operação em produção.

**Critério de saída:**

- cenários 1 a 119 da especificação (§16) passando contra o simulador;
- testes técnicos T-1 a T-55 (seção 8) passando, com evidência do ciclo Red → Green → Refactor conforme o `AGENTS.md`;
- teste de restauração realizado.

### Fase 2a: Mercado Pago com Pix — início da operação real

**Pré-requisitos:**

- L-1 a L-4 e L-6 a L-11 validadas, com os resultados incorporados à implementação. Se L-1 ou L-2 revelarem incompatibilidade com A2 ou P-6, a fase não começa sem decisão do responsável (seção 4.5).
- Aporte inicial de R$ 1.000,00 depositado na conta do provedor e registrado no livro-razão.

**Escopo:** implementação do Mercado Pago na interface, com Pix.

**Critério de saída:**

- cenários e testes técnicos passando no sandbox;
- transações reais de valor baixo em produção, incluindo uma devolução parcial;
- conciliação diária validada.

### Fase 2b: cartão de crédito e débito

**Decisões de negócio que continuam abertas e precisam estar fechadas antes:**

- taxa de serviço igual para todos os meios ou diferente para cartão. Com P-1, as tarifas do cartão saem da receita de serviço, então essa decisão afeta diretamente a margem;
- prazo de liberação no Mercado Pago, que limita o repasse (seção 3.4).

**Pré-requisito técnico:** L-5 validada.

**Escopo:** Checkout Pro (seção 4.6), contestações no livro-razão, liquidez por data de liberação.

**Critério de saída:** cenários de cartão no sandbox (aprovado, recusado, aprovado na margem, estorno parcial, contestação depois do repasse), transações reais de valor baixo.

### Fase 3: WhatsApp

- Conta comercial aprovada na Meta, templates *utility*, opt-in registrado.
- Falha no WhatsApp nunca altera estado financeiro nem a notificação no site (cenário 24).

## 8. Critérios de aceitação e testes

Os critérios de negócio estão na especificação funcional, §16 (cenários 1 a 95). O cenário 12 foi reescrito, os cenários 25 a 40 cobrem A1 a A3 e P-1 a P-8, os cenários 41 a 52 cobrem 17.2 e 17.3, os cenários 53 a 73 cobrem 17.4 a 17.11, os cenários 74 a 95 cobrem Q-1 a Q-4 e R-1 a R-4, e os cenários 96 a 119 cobrem Q-5 a Q-7 e R-5 a R-8. Os critérios R1 a R14 da versão 1.1 foram incorporados a esses cenários.

Testes técnicos complementares, automatizados contra o simulador:

| ID | Teste | Regra |
|---|---|---|
| T-1 | Tentativa criada em `T0 + 24h − 1 ms` é aceita. Em `T0 + 24h` e `T0 + 24h + 1 ms` é recusada, com a tarefa de bloqueio parada. | A2 |
| T-2 | `date_approved = T0 + 48h` é aceito. `T0 + 48h + 1 ms` gera obrigação de devolução. | P-6 |
| T-3 | Aprovação em `T0 + 47h59` com webhook chegando em `T0 + 50h` quita o pedido, se a apuração ainda não ocorreu. | P-6 |
| T-4 | Apuração recusada em `T0 + 48h − 1 ms`, mesmo com 100% pago. Em `T0 + 48h` exige autorização. | P-8 |
| T-5 | Nenhuma rota permite alterar `T0` ou o prazo de pagamento, nem com perfil de admin. | P-7 |
| T-6 | Webhook repetido 5 vezes, em paralelo, reconhece o pagamento uma única vez. | Derivado |
| T-7 | Webhook, bloqueio de `T0 + 24h` e apuração concorrendo sobre o mesmo pedido produzem o mesmo resultado em qualquer ordem. | Derivado |
| T-8 | Devolução com falha temporária repetida reaproveita a chave de idempotência e não devolve duas vezes. | Derivado |
| T-9 | Confirmação de devolução excepcional recusada enquanto houver devolução em processamento no provedor. Nova tentativa no provedor recusada depois da confirmação. Segunda confirmação da mesma parcela recusada. | P-5 |
| T-10 | Utilização da reserva acima do saldo livre recusada. Obrigação sem cobertura mantida integral, com alerta de insuficiência. | P-3, P-4 |
| T-11 | Lançamento que use recursos do fornecedor A para tarifa, déficit ou obrigação do fornecedor B recusado. Repasse a A limitado ao valor liberado de A. | P-2 |
| T-12 | Aplicação configurada com o simulador em produção encerra na inicialização. | A3 |
| T-13 | Cancelamento com reembolso executado duas vezes em paralelo: um é recusado e nenhuma devolução é duplicada. | 17.2 |
| T-14 | Cancelamento com reembolso com devolução parcial pendente: a nova obrigação cobre só o saldo restante, e o total nunca passa do valor pago. | 17.2 |
| T-15 | Cancelamento sem reembolso com obrigação existente: nenhuma obrigação nova, e a existente continua pendente e não é baixada. | 17.2 |
| T-16 | Rota de cancelamento recusa lista de compradores e aceita requisição sem motivo. Comprador e fornecedor recebem recusa. | 17.2 |
| T-17 | `UPDATE` ou `DELETE` direto no banco sobre item de pedido congelado é recusado pela trigger. Nenhuma rota permite edição. | 17.3 |
| T-18 | Ocorrências concorrentes sobre o mesmo item não ultrapassam a quantidade paga. Cada ocorrência gera um único reembolso, com o valor de §9.2. | 17.3 |
| T-19 | Pagamento informado pelo provedor depois da apuração ou do cancelamento fica registrado com alerta e não altera o pedido. | 17.3, 17.2 |
| T-20 | Apuração com caixa invalidada executada duas vezes: parcelas restauradas uma única vez, mesmo número de sequência, sem reserva duplicada. | 17.4 |
| T-21 | Restauração concorrendo com adição de outro comprador ao mesmo produto: ordem FIFO pela sequência original e total reservado ≤ estoque. | 17.4, 17.5 |
| T-22 | Retorno ao interesse com inadimplentes e pagantes: estoque cadastrado inalterado, reservas de inadimplentes liberadas, reservas de pagantes com sequência original. | 17.5 |
| T-23 | Alteração de mínimo, múltiplo e estoque recusada pelo servidor em fechamento, pagamento, margem e etapas seguintes, inclusive pelo admin. Preço aceito no fechamento. Redução de estoque abaixo do reservado recusada. | 17.11 |
| T-24 | Login por senha, link e Google com e-mail banido (variando maiúsculas e espaços) recusado. Alias com `+` não bloqueado. Sessão aberta encerrada no banimento. | 17.6 |
| T-25 | Conta de fornecedor chamando rotas de carrinho e pagamento recebe recusa. Conta de comprador chamando rotas de fornecedor recebe recusa. | 17.7 |
| T-26 | Quantidade fora do incremento recusada pela API. `0,35 × 12,99` resulta em 455 centavos. Múltiplo que não é múltiplo do incremento recusado no cadastro. | 17.8 |
| T-27 | Fornecedor consultando por identificador direto pagamentos, compradores, taxa de serviço, reserva ou produto de outro fornecedor recebe recusa. A exportação só contém campos permitidos. | 17.9 |
| T-28 | SES simulado falhando três vezes: exatamente três tentativas, alerta ao admin e botão disponível. Falha seguida de sucesso: nenhuma tentativa a mais. | 17.10 |
| T-29 | Duas requisições de reenvio com o mesmo token geram um envio. Tokens distintos geram duas tentativas registradas. O conteúdo enviado é idêntico ao snapshot. | 17.10 |
| T-30 | `alocar_pendentes` com estoque menor que o total pendente: reserva por ordem de sequência, a última parcela atendida parcialmente, o restante pendente com reserva zero e total reservado = estoque. | Q-1 |
| T-31 | `alocar_pendentes` executada em paralelo com a adição de um interesse novo no mesmo produto: pendentes atendidos primeiro, nenhuma reserva acima do estoque, resultado idêntico em qualquer ordem. | Q-1 |
| T-32 | Apuração reexecutada sobre a mesma caixa invalidada: a chave (parcela, caixa) impede segunda restauração, sem nova parcela nem nova sequência. | Q-1 |
| T-33 | Parcela pendente sem reserva fora de mínimo, caixas e pedido na abertura do pagamento. Continua pendente na rodada seguinte. Inadimplente sem parcelas pendentes. | Q-1 |
| T-34 | Dois cadastros simultâneos com o mesmo e-mail normalizado (`Ana@x.com` e ` ana@x.com `), um por convite de comprador e outro de fornecedor: um sucesso e uma recusa pela restrição `UNIQUE`. | Q-2, R-3 |
| T-35 | Login com Google com e-mail igual ao de uma conta, mas com maiúsculas diferentes: entra nessa conta e não cria outra. Google com e-mail sem conta e sem convite: nada criado. | Q-2, R-3 |
| T-36 | Banimento com sessões ativas em dois navegadores: sessões apagadas e a próxima requisição de cada uma é recusada pelo middleware. A outra conta da mesma pessoa, com outro e-mail, continua acessível. | Q-2, R-3 |
| T-37 | `normalizar_email` usado em todos os pontos de comparação (cadastro, convite, login, unicidade, banimento): teste de propriedade com variações de maiúsculas e espaços. Aliases com `+` continuam distintos. | R-3 |
| T-38 | Quantidades em L, kg e unidade validadas contra o incremento do produto. Incremento zero, negativo ou com mais de 3 casas recusado. Múltiplo incompatível recusado no cadastro e na alteração em interesse. | Q-4, R-2 |
| T-39 | Tabela de arredondamento: 7,99 × 0,25 = 2,00; 2,50 × 0,25 = 0,63; 12,99 × 0,35 = 4,55. `P` é a soma dos subtotais arredondados. A verificação estática não encontra `float` em código monetário. | R-1 |
| T-40 | Reembolso do item inteiro depois de mudança de preço no catálogo usa o subtotal do snapshot. A soma da devolução integral bate com os valores cobrados registrados. | R-1 |
| T-41 | Reenvio manual: recusado durante o ciclo automático, aceito depois da terceira falha e depois de sucesso, uma tentativa por acionamento, nenhum ciclo automático novo, snapshot e identificador do pedido formal inalterados. | Q-3, R-4 |
| T-42 | Consulta do comprador devolve reservado e pendente em campos separados, inclusive com estoque zero. Outro comprador não vê essas parcelas. | Q-5 |
| T-43 | `remover_pendente` parcial e total: só a quantidade pendente muda, sequências e reservas inalteradas, parcelas mais recentes reduzidas primeiro. Quantidade fora do incremento ou acima do pendente recusada sem escrita. | Q-5 |
| T-44 | `remover_pendente` com identificador de item de pedido congelado ou de parcela "em pedido" recusada. Pedido, trigger e registros financeiros inalterados. | Q-5, 17.3 |
| T-45 | `remover_pendente` em paralelo com `alocar_pendentes` sobre o mesmo produto: em qualquer ordem, reservado + pendente ≤ original, total reservado ≤ estoque e a quantidade removida nunca reservada. | Q-5, R-5 |
| T-46 | Liberação de estoque em paralelo com nova reserva: pendentes atendidos primeiro pela sequência. Pendentes do fornecedor X nunca alocados em rodada do fornecedor Y. | R-5 |
| T-47 | Cálculo do mínimo, formação de caixas, abertura de pagamento, pedido formal e cobrança ignoram quantidade pendente. A quantidade pendente continua na fila depois da abertura do pagamento. | R-6 |
| T-48 | `alterar_incremento`: valor compatível aceito na fase de interesse; incompatível com reservado, pendente ou múltiplo recusado sem nenhuma escrita; qualquer valor recusado a partir do fechamento. | Q-6 |
| T-49 | `alterar_incremento` em paralelo com adição de interesse no mesmo produto: operações serializadas pela trava do produto, nenhuma parcela fora do incremento vigente ao final. | Q-6 |
| T-50 | Validação R-8 com a tabela da especificação (1, 2, 0,25, 0,5, 1) e inválidos (0, -1, 0,0001). Quantidades inteiras e fracionárias validadas com `Decimal`. Número em ponto flutuante na API recusado. | R-8 |
| T-51 | `reembolso_parcial`: 7,99 × 0,25/1 = 2,00; sequência 2,00 / 2,00 / 2,00 / 1,99; caso de R$ 0,09 com limite ao saldo. Mudança do preço de catálogo não altera nenhum valor. | Q-7 |
| T-52 | Reembolso acima da quantidade paga recusado. Devolução integral depois de parciais completa exatamente o saldo. Acumulado de serviço e frete nunca passa do registrado. | Q-7 |
| T-53 | Dois `reembolso_parcial` concorrentes sobre o mesmo item: serializados pela trava, soma ≤ subtotal, nenhum registro duplicado. | Q-7 |
| T-54 | Reenvio manual recusado com tentativa automática agendada ou em execução. Aceito depois do sucesso e depois da terceira falha, com uma tentativa por acionamento. | R-7 |
| T-55 | Tentativa automática e acionamento manual concorrentes: o manual é recusado. Dois manuais distintos depois do ciclo: executados em sequência, nunca ao mesmo tempo. Snapshot inalterado. | R-7, R-4 |

## 9. Pendências e validações

### 9.1 Decisões resolvidas

| ID | Decisão aprovada | Especificação | Este documento |
|---|---|---|---|
| A1 | Aporte inicial de R$ 1.000,00, livro-razão segregado, reserva sem limite de responsabilidade | §9.3, §9.4 | 3.1, 3.3 |
| A2 | 24h para pagar, margem de 24h, apuração a partir de `T0 + 48h` com autorização | §7, §8.2 | 4.3 |
| A3 | Pagamentos só pelo provedor, simulador na fase 1, sem simulador em produção | §1, §8.1, §15 | 4.1, 7 |
| P-1 | Tarifas cobertas pela receita de serviço, déficit de frete do admin, sem cobrança retroativa | §9, §9.3 | 3.1, 3.2 |
| P-2 | Recursos de fornecedor exclusivos, movimentações explícitas e auditáveis | §9.3, §10 | 3.2, 3.4 |
| P-3 | Usos permitidos da reserva, sem comprometer obrigações existentes | §9.4 | 3.3 |
| P-4 | Sem recomposição automática, novos aportes conforme necessidade, alertas | §9.4 | 3.3 |
| P-5 | Devolução excepcional por Pix ou transferência, só quando inviável pelo provedor | §9.5 | 4.7 |
| P-6 | Aceitação por `date_approved ≤ T0 + 48h`, devolução depois disso | §8.3 | 4.3, 4.4 |
| P-7 | Prazo de pagamento improrrogável, inclusive pelo admin | §7 | 4.3 |
| P-8 | Apuração nunca antecipada | §7, §8.2 | 4.3 |
| 17.2 | Cancelamento da rodada inteira, só pelo admin, sem motivo, com ou sem reembolso integral | §7.2 | 3.2, 4.8 |
| 17.3 | Pedido congelado imutável, ocorrências de entrega com reembolso pontual | §7.1, §10 | 3.2, 4.9 |
| 17.4 | Unidades pagas em caixa invalidada voltam ao interesse com prioridade original | §5, §8.2 | 4.10 |
| 17.5 | Estoque inalterado e reservas preservadas ou liberadas no retorno ao interesse | §8.2 | 4.10 |
| 17.6 | Banimento só por e-mail, para login e cadastro | §2, §3.1 | 4.11 |
| 17.7 | Contas de comprador e fornecedor independentes | §2, §3.1 | 4.11 |
| 17.8 | Incremento por produto (peso), decimal exato | §4.2, §5 | 4.12 |
| 17.9 | Lista fechada do que o fornecedor vê | §2, §6.2, §13 | 4.13 |
| 17.10 | Três tentativas automáticas e reenvio manual do mesmo pedido formal | §10, §12 | 4.14 |
| 17.11 | Condições alteráveis só em interesse, preços conforme §5.1 | §4.4 | 4.10 |
| Q-1 | Fila de pendentes do fornecedor, FIFO original, reserva só com estoque | §5.2, §8.2 | 4.10 |
| Q-2 | E-mail exclusivo por conta, inclusive no Google | §2, §3 | 4.11 |
| Q-3 | Reenvio do pedido formal também depois de sucesso | §10 | 4.14 |
| Q-4 | Frações em qualquer unidade, incremento por produto | §4.2 | 4.12 |
| R-1 | Subtotal por item com `ROUND_HALF_UP`, reembolso pelo valor registrado | §9, §9.2 | 4.12 |
| R-2 | Múltiplo divisível pelo incremento | §4.2, §4.4 | 4.10, 4.12 |
| R-3 | Normalização de e-mail e invalidação de sessões | §2, §3 | 4.11 |
| R-4 | Três tentativas automáticas, reenvio manual de uma tentativa por acionamento | §10 | 4.14 |
| Q-5 | Comprador vê reservado e pendente e remove pendentes | §5.2, §13 | 4.10 |
| Q-6 | Incremento alterável só em interesse, com validação integral | §4.2, §4.4 | 4.10, 4.12 |
| Q-7 | Reembolso parcial proporcional ao subtotal registrado, com acumulado por item | §9.2 | 4.12 |
| R-5 | Pendentes antes de novas reservas, isolados por fornecedor | §5.2 | 4.10 |
| R-6 | Pendentes sem reserva fora do mínimo, dos pedidos e das cobranças | §5.2 | 4.10 |
| R-7 | Reenvio manual bloqueado durante o ciclo automático | §10 | 4.14 |
| R-8 | Incremento inteiro ou fracionário, > 0, até 3 casas | §4.2 | 4.12 |

### 9.2 Limitações técnicas a validar (prova de conceito ou documentação)

| ID | O que validar | Impacto se não confirmar | Necessária para |
|---|---|---|---|
| L-1 | Se o `date_of_expiration` do Pix aceita qualquer instante (inclusive `T0 + 24h` para Pix gerado perto do prazo) ou exige intervalo mínimo ou máximo | Mecanismo principal passa a ser L-2. Se L-2 também falhar, decisão do responsável (seção 4.5). | Fase 2a |
| L-2 | Se é possível cancelar pela API um Pix ou pagamento pendente, e o resultado quando o pagador conclui ao mesmo tempo | Bloqueio em `T0 + 24h` depende só do vencimento | Fase 2a |
| L-3 | Se um Pix pode ser aprovado depois do `date_of_expiration`, e como isso é informado | Afeta a frequência de casos P-6 | Fase 2a |
| L-4 | Presença, precisão, fuso e estabilidade do `date_approved`, e diferença de relógio em relação ao servidor | Critério de P-6 precisa de outra fonte de horário | Fase 2a |
| L-5 | Se o `expiration_date_to` do Checkout Pro impede novos pagamentos, e o que acontece com pagamentos de cartão em andamento | Ajustar o bloqueio do cartão | Fase 2b |
| L-6 | Busca de pagamentos por `external_reference` e atraso de consistência da API | Risco residual da seção 4.4 maior | Fase 2a |
| L-7 | Estorno parcial por meio de pagamento, prazo máximo de estorno, exigência de saldo, devolução de tarifa e códigos de falha definitiva | Critério de "comprovadamente inviável" (P-5) e custo das tarifas (P-1) | Fase 2a |
| L-8 | Se saídas por Pix ou transferência da conta (repasse, retirada) aparecem na API ou no extrato exportável | Conciliação dessas saídas feita por conferência manual | Fase 2a |
| L-9 | API de saldo (liberado e a liberar) e de movimentos, e como aparece um depósito de recursos próprios (aporte) | Conciliação diária e registro do aporte manuais | Fase 2a |
| L-10 | Data de liberação (`money_release_date`) por meio de pagamento | Liquidez por destinação estimada | Fase 2a (Pix), 2b (cartão) |
| L-11 | Esquema de assinatura dos webhooks e política de reenvio | Verificação de autenticidade | Fase 2a |
| L-12 | Segregação nativa de saldo no provedor (presumida inexistente) | Nenhum. O livro-razão já cobre (P-2). | Informativo |
| L-13 | Amazon SES: a aceitação da mensagem pela API não garante entrega. Falhas posteriores (bounce) não são detectadas sem integração adicional, que não foi incluída. | Pedido aceito pelo SES e não entregue não aciona as tentativas. O admin depende de contato do fornecedor. | Fase 1 (registro), informativo |

Também a validar, sem relação com pagamentos:

- Neon: região São Paulo e janela de restauração do plano.
- Amazon SES: saída do modo sandbox.
- Meta: tarifas em reais para mensagens *utility*.

### 9.3 Outras questões abertas

Q-1 a Q-7 estão resolvidas (seção 9.1). Não há questão de implementação aberta. Nenhum ponto já resolvido foi reaberto.

- A parte de 17.12 que é validação técnica (coberta por L-7).
- Decisões de negócio da fase 2b: taxa por meio de pagamento e prazo de liberação.
- Orientação do contador (seção 7, fase 0).

## 10. Custos estimados

| Item | Valor |
|---|---|
| Fly.io (web e worker em produção, homologação desligando sozinha) | ~US$ 8–15 por mês |
| Neon (plano pago, banco pequeno) | ~US$ 5–20 por mês |
| SES, R2, Sentry, Better Stack, Cloudflare | ~US$ 0–2 por mês |
| **Infraestrutura fixa** | **~US$ 15–35 por mês** (desde a fase 1) |
| Pix (Mercado Pago) | % por transação, a confirmar. Coberto pela receita de serviço [P-1]. |
| Cartão (Mercado Pago) | % maior, conforme crédito, débito e prazo de liberação. Coberto pela receita de serviço [P-1]. |
| WhatsApp | poucos reais por mês, cobrança por mensagem em reais (fase 3) |
| **Aporte inicial da reserva** | **R$ 1.000,00, uma vez**, antes da fase 2a. Capital próprio, não é custo nem receita [A1]. |

Com P-1, a taxa de serviço precisa cobrir as tarifas do provedor, inclusive as não devolvidas em estornos [Validar L-7]. Por isso a decisão de taxa por meio de pagamento (fase 2b) deve usar a tarifa do cartão como referência.

## 11. Verificação de consistência

| Verificação | Resultado |
|---|---|
| Janela de pagamento: especificação §7 e §8.2 × seção 4.3 | Iguais: `[T0, T0 + 24h)`, margem até `T0 + 48h`, apuração a partir de `T0 + 48h` com autorização. |
| Aceitação de pagamentos tardios: §8.3 × seções 4.3 e 4.4 | Iguais: `date_approved ≤ T0 + 48h` é aceito, depois disso devolução. O estado "aguardando decisão" da v1.1 foi removido. |
| Prorrogação: §7 × seção 4.3 | Pagamento e margem improrrogáveis. Fechamento e demais prazos seguem as regras existentes. |
| Antecipação: §7 e §8.2 × seção 4.3 e T-4 | Proibida em ambos. |
| Pagamento manual e A3: v1.1 × v1.2 | Nenhuma menção a recebimento manual. A devolução excepcional está restrita a devoluções nos dois documentos. |
| v1.1 R13 ("não existe forma de marcar estorno como concluído manualmente") × P-5 | Substituído: devolução pelo provedor nunca é concluída manualmente. A excepcional só é concluída pelo fluxo da seção 4.7, com confirmação (cenário 35). |
| v1.1: Pix vencendo "alguns minutos antes" | Já removido na v1.1 e mantido removido. Vencimento em `T0 + 24h` [Validar L-1]. |
| Destinações: §9.3 × seção 3.1 | Mesmas destinações. "Obrigações com compradores" e "frete" detalham o requisito de registrar obrigações financeiras e o frete arrecadado e efetivo, sem criar regra comercial. |
| Déficit de frete: §8.2 ("administrador assume") × P-1 × seção 3.2 | Compatíveis: responsabilidade do admin, financiada por receita, reserva ou aporte. |
| Repasse: §10 × P-2 × seção 3.4 | Compatíveis. O limite à parte liberada é requisito derivado de P-2. |
| Devolução excepcional (v1.3): §9.5 × seção 4.7 | Iguais: o admin devolve fora da integração, e a plataforma só registra a confirmação e a baixa, com proteção contra duplicidade. A exigência da v1.2 de saída pela conta do provedor foi removida. |
| Frete no retorno ao interesse (v1.3): §8.2 e §9.3 × seção 3.1 | Iguais: todos os valores recebidos são devolvidos e não há frete efetivo. Nenhum cálculo ou exceção de frete para esse fluxo. |
| Cancelamento (v1.4): §7, §7.2 e §12 × seção 4.8 | Iguais. A exigência antiga de "motivo próprio" e mensagem obrigatória foi removida: a mensagem é opcional e a auditoria não exige motivo. |
| Pedido congelado (v1.4): §7 e §7.1 × seção 4.9 | Removidos "corrigir pedidos" (§7), "correções auditadas" (§13) e "limites de correção a definir" (§7). Nenhuma rota de edição de pedido congelado nos dois documentos. |
| Pagamento tardio depois da apuração: seção 4.4 × §8.3 | Iguais. A referência ao ponto 17.3 em aberto foi substituída por tratamento financeiro auditado sem editar o pedido. |
| Faltas de entrega: §9.1, §10 × seção 4.9 | "Faltas" passou a ser "ocorrências de entrega" (faltante, incorreto, não entregue). O cálculo de §9.2 não mudou: o cenário 18 continua válido. |
| Condições × preços (v1.5): §4.4 e §5.1 × seção 4.10 | Iguais. Mínimo, múltiplo e estoque congelados a partir do fechamento. Preços continuam alteráveis em interesse e fechamento. |
| Restauração × pedido congelado (v1.5): §8.2 × §7.1 | Sem conflito. A restauração muda a situação da parcela de interesse, não a composição do pedido congelado do ciclo apurado. |
| Restauração × reembolso (v1.5): §8.2 × §9.2 | Sem conflito. As unidades restauradas são reembolsadas, e a restauração não espera a conclusão do reembolso. Ciclos e pagamentos não se misturam (seção 4.2). |
| Restauração × rodada única (v1.6): §5.2 e §8.2 × §4.3 | Resolvido por Q-1: as unidades ficam na fila de pendentes do fornecedor, sem reserva na rodada apurada, e não há duas rodadas ativas. |
| Q-1 × 17.5 (v1.6): §5.2 × §8.2 | A fila de pendentes vale para a rodada que segue viável, que é o caso perguntado em Q-1. Na rodada que volta para interesse, continua valendo 17.5: as reservas de quem pagou são preservadas na própria rodada. Leitura de escopo registrada para confirmação, sem regra nova. |
| Fila de pendentes × FIFO (v1.6): §5.2 × seção 4.10 | Iguais. Os pendentes são atendidos antes de qualquer nova reserva sempre que houver estoque livre (requisito derivado da prioridade FIFO original). |
| Pendente × reserva (v1.6): §5.2 × §5 | Separados. Quantidade pendente sem reserva não conta para mínimo, caixas nem pedido. |
| E-mail único × banimento (v1.6): §2 × seção 4.11 | Iguais. Um e-mail por conta, e o banimento atinge só aquele endereço. |
| Frações × múltiplos (v1.6): §4.2 e §4.4 × seção 4.12 | Iguais. R-2 vale no cadastro e nas alterações em interesse. O congelamento de 17.11 continua a partir do fechamento. |
| Arredondamento × regras existentes (v1.6): §9 × seção 4.12 | Iguais. A taxa de serviço, a distribuição do frete e o estorno proporcional continuam aplicados sobre `P`, que agora é a soma dos subtotais arredondados. Os cenários 18 e 48 continuam válidos, porque usam valores inteiros. |
| Remoção de pendentes × pedido congelado (v1.7): §5.2 e §7.1 × seções 4.9 e 4.10 | Sem conflito. A remoção só altera quantidade pendente, que nunca faz parte de um pedido. A rota não aceita itens de pedido, e a trigger continua ativa. |
| Remoção de pendentes × reembolsos (v1.7): §5.2 × §9 | Sem conflito. O reembolso devido pela caixa invalidada é independente da pendência e não muda com a remoção. |
| Incremento × congelamento (v1.7): §4.2 e §4.4 × seções 4.10 e 4.12 | Iguais. O incremento entra na lista de condições congeladas a partir do fechamento. A regra de preços da §5.1 continua igual. |
| Reembolso parcial × regras anteriores (v1.7): §9.2 × seção 4.12 | Iguais. O cenário 18 (R$ 31,25) e o cenário 48 (R$ 25,00) continuam válidos com o cálculo proporcional, porque usam quantidades inteiras e valores exatos. |
| R-5 × 17.5 (v1.7): §5.2 × §8.2 | Iguais. A leitura de escopo registrada na v1.6 agora é regra aprovada por R-5. |
| Reenvio (v1.6): §10 × seção 4.14 | Iguais. A redação de Q-3 "padrão literal: só depois de três falhas" foi removida. L-13 continua aberta. |
| Estoque no retorno (v1.5): §8.2 × §4.4 | Iguais. Estoque inalterado no retorno, e o admin pode alterá-lo depois, respeitando as reservas. |
| Fornecedor (v1.5): §2, §6.2, §10 e §13 × seção 4.13 | Iguais. A frase antiga "fornecedor consulta somente seu andamento e quantidades agregadas" (§10) foi atualizada para remeter à lista de §2. |
| Pedido formal (v1.5): §10 × seção 4.14 | Iguais. A redação antiga do ponto 17.10 ("prever correções") foi substituída: o reenvio nunca altera o pedido, o que é coerente com §7.1. |
| Captura adiada × margem de 48h | Continua fora da v1 nos dois documentos. |
| Limitações técnicas | Todas marcadas como L-n. Nenhuma apresentada como funcionalidade comprovada. |

## 12. Fontes

- [Mercado Pago Developers](https://www.mercadopago.com.br/developers)
- [Tecnoblog — Mercado Pago Pix](https://tecnoblog.net/430997/mercado-pago-agora-oferece-pix-com-taxa-zero-para-pequenos-negocios/)
- [Stripe — Pix e IOF](https://edge-docs.stripe.com/changelog/basil/2025-08-27/pix-payments-iof-tax)
- [Meta — Preços da WhatsApp Business Platform](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing)
- [Zenvia — Regras de preço do WhatsApp em 2026](https://support.zenvia.com/kb/en/article/599963/new-whatsapp-business-pricing-rules-for-2026?q=r1p7U)
- [Supabase — Regiões](https://supabase.com/docs/guides/platform/regions)
- [Jetadmin — Preços do Supabase em 2026](https://www.jetadmin.io/blog/supabase-pricing-2026-guide-to-plans-limits-and-real-world-costs/)
- [Costbench — Plano grátis do Resend](https://costbench.com/software/email-api/resend/free-plan/)
