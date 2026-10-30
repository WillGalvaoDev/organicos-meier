# Orgânicos Méier — Especificação funcional

Versão 1.7 · 29 de outubro de 2026

| Versão | Alterações |
|---|---|
| 1.0 | Primeira versão. |
| 1.1 | Incorpora as decisões A1 a A3 e P-1 a P-8, aprovadas depois da auditoria da infraestrutura: pagamentos exclusivamente pelo provedor integrado, prazo de pagamento improrrogável, margem operacional, aceitação de pagamentos aprovados até `T0 + 48h`, segregação financeira, reserva, devolução excepcional. Seções alteradas: 1, 2, 7, 8, 9, 10, 12, 13, 14, 15, 16 e 17. Escolhas técnicas e limitações a validar estão em `organicos-meier-infraestrutura.md` (v1.2). |
| 1.2 | Ajustes pontuais. Devolução excepcional feita pelo administrador fora da integração, com a plataforma registrando só a confirmação e a baixa. Retorno ao interesse por insuficiência de pagamentos devolve todos os valores recebidos, sem frete efetivo. Seções 8.2, 9.3, 9.5, 13, 14 e 16. Corresponde a `organicos-meier-infraestrutura.md` v1.3. |
| 1.3 | Resolve os pontos 17.2 (cancelamento administrativo da rodada inteira, com ou sem reembolso integral, sem motivo obrigatório) e 17.3 (pedido congelado imutável, ocorrências de entrega com reembolso pontual). Seções 2, 5, 7 (novas 7.1 e 7.2), 8.3, 9.1, 10, 12, 13, 14, 16 e 17. Corresponde a `organicos-meier-infraestrutura.md` v1.4. |
| 1.4 | Resolve os pontos 17.4 a 17.11 e reconfirma 17.2 e 17.3 sem alteração de regra: restauração de interesses depois de caixa invalidada, estoque no retorno ao interesse, banimento por e-mail, contas independentes de comprador e fornecedor, medidas fracionárias, visibilidade do fornecedor, falhas no envio do pedido formal, congelamento das condições da rodada. Seções 2, 3, 4, 5, 6.2, 8.2, 10, 12, 13, 14, 16 e 17. Questões de implementação Q-1 a Q-4 separadas em 17. Corresponde a `organicos-meier-infraestrutura.md` v1.5. |
| 1.5 | Incorpora as decisões Q-1 a Q-4 e os requisitos derivados aprovados R-1 a R-4: fila de interesses pendentes, e-mail exclusivo por conta, reenvio do pedido formal também depois de sucesso, quantidades fracionárias em qualquer unidade, arredondamento monetário, compatibilidade entre múltiplo e incremento, normalização de e-mails, tentativas de envio. Nova seção 5.2. Seções 2, 3, 4.2, 4.4, 5, 8.2, 9, 9.2, 10, 12, 13, 14, 16 e 17. Novas questões Q-5 a Q-7. Corresponde a `organicos-meier-infraestrutura.md` v1.6. |
| 1.6 | Incorpora as decisões Q-5 a Q-7 e os requisitos aprovados R-5 a R-8: visualização e remoção de quantidades pendentes pelo comprador, alteração do incremento só na fase de interesse e com validação integral, reembolso parcial proporcional ao subtotal registrado com controle acumulado, prioridade dos pendentes, pendentes fora do mínimo, bloqueio de reenvio durante o ciclo automático, validação de incrementos inteiros e fracionários. Seções 2, 4.2, 4.4, 5.2, 9.2, 10, 13, 14, 16 e 17. Nenhuma questão de implementação aberta. Corresponde a `organicos-meier-infraestrutura.md` v1.7. |
| 1.7 | Incorpora a decisão Q-8, aprovada pelo responsável em 2026-10-29: perda por contestação (cartão) ou por devolução forçada do Pix (MED) depois da aprovação do pagamento. O fornecedor recebe integralmente, inclusive antes do repasse; a perda é coberta pela receita de serviço da rodada, depois pela reserva e, se faltar, por novo aporte; o comprador é suspenso para análise do administrador, sem banimento automático. Nova seção 9.6 e linha Q-8 na seção 17. Corresponde a `organicos-meier-infraestrutura.md` v1.8. |

## 1. Finalidade e escopo

Sistema real de compras coletivas de produtos, com acesso por convite, destinado inicialmente a **100 compradores cadastrados no total e 50 fornecedores**. Esses números não representam acessos simultâneos. Há um único administrador. O projeto também será apresentado em portfólio, mas precisa atender uma operação de produção.

O administrador cadastra fornecedores, produtos, preços, estoque e condições. Compradores registram interesses. Cada fornecedor reúne sua própria rodada de compras, sujeita a mínimo monetário e, quando aplicável, múltiplos de compra. O administrador conduz o fechamento e a cobrança. Recebe os pagamentos em sua conta **exclusivamente pela plataforma de pagamentos integrada**, transfere manualmente ao fornecedor e recebe os produtos em sua casa. Compradores retiram os produtos nesse endereço. O administrador mantém também uma reserva financeira constituída com capital próprio (seção 9.4).

Este documento define o comportamento esperado, sem escolher stack, hospedagem, plataforma de pagamentos ou provedor de mensagens. O agente de infraestrutura deve justificar essas escolhas e sua compatibilidade com as regras abaixo. As escolhas estão em `organicos-meier-infraestrutura.md`.

### Classificação das regras

- **Regra definida:** decisão explícita do responsável pelo projeto, descrita como comportamento obrigatório.
- **Requisito derivado:** proteção técnica necessária para cumprir as regras, sem alterar a operação comercial.
- **Ponto a validar:** decisão ainda não fechada; aparece na seção 17 e não deve ser silenciosamente tratada como aprovada.

## 2. Perfis e permissões

| Perfil | Permissões |
|---|---|
| Administrador | Único responsável por convites, cadastros, preços, estoque, etapas, prazos, cancelamento de rodadas, ocorrências de entrega, repasses, recebimento, estornos, devoluções excepcionais, aportes e controle da reserva financeira, movimentações entre destinações financeiras, retiradas, descarte, comunicados e moderação de usuários. |
| Comprador ativo | Consulta catálogo, regras, endereço e progresso agregado; gerencia interesses nas etapas permitidas; vê separadamente suas quantidades reservadas e pendentes e pode remover quantidades pendentes (seção 5.2); paga seus pedidos; consulta seu histórico e notificações; edita dados opcionais. |
| Comprador suspenso | Pode consultar listas e seus pedidos pagos; não pode adicionar interesses. Interesses e pedidos não pagos são removidos/cancelados. Suspensão reversível pelo administrador. |
| Comprador removido | Acesso bloqueado definitivamente: o e-mail fica banido para login e para novos cadastros por convite. Histórico, inclusive financeiro, preservado para o administrador. Pedidos pagos não são apagados. |
| Fornecedor | Consulta somente o fornecedor previamente vinculado à sua conta: seus produtos, quantidades, preços unitários, valores totais dos produtos, andamento da rodada, pedido formal e previsão de entrega. Não vê pagamentos individuais, dados pessoais dos compradores, taxa de serviço, reserva financeira nem informações de outros fornecedores. Não altera cadastro, produtos, preços ou etapas e não realiza compras. |

Restrições devem ser verificadas no servidor, inclusive em chamadas diretas e exportações. Ocultar controles na interface não é suficiente.

**Contas de comprador e fornecedor:** são independentes. Uma mesma pessoa pode ter as duas, cada uma com login e permissões próprios, e as duas exigem convite. A conta de fornecedor não compra: para comprar, a pessoa usa sua conta de comprador. Uma conta com dois perfis não substitui as duas contas independentes, e não há permissões nem dados cruzados entre elas.

**E-mail exclusivo por conta:** cada conta tem um e-mail exclusivo na plataforma. O mesmo endereço não pode estar associado a duas contas, qualquer que seja o papel, inclusive no login com Google. Quem tem conta de comprador e de fornecedor usa e-mails diferentes. A unicidade é garantida no banco de dados e na aplicação, com a normalização abaixo.

**Normalização de e-mails:** ignora diferenças entre maiúsculas e minúsculas e remove espaços no início e no fim. Não há equivalência automática entre aliases: `usuario@gmail.com` e `usuario+teste@gmail.com` são endereços distintos. A mesma normalização vale no cadastro, no convite, no login, na verificação de unicidade e no banimento.

**Suspensão e remoção:** a suspensão é reversível. A remoção é definitiva e bane o e-mail. O bloqueio é exclusivamente por endereço de e-mail, sem bloqueio por IP, dispositivo, telefone ou outra identificação. O banimento afeta só o endereço banido e não bloqueia automaticamente outras contas da mesma pessoa. Ao banir, as sessões ativas daquele e-mail são invalidadas e novos acessos são impedidos. Históricos comerciais, operacionais e financeiros são preservados.

## 3. Convites, autenticação e cadastro

### 3.1 Convites

- Somente o administrador emite convites.
- Convite individual, de uso único, vinculado a um e-mail e com validade fixa de 24 horas a partir da emissão.
- Convite expirado não permite cadastro; o interessado precisa solicitar outro ao administrador.
- O convite define o perfil: comprador ou fornecedor. O usuário não escolhe nem altera esse perfil durante o cadastro.
- Convite de fornecedor fica vinculado ao fornecedor previamente cadastrado pelo administrador.
- Após concluir o cadastro, comprador não precisa de novos convites para novas rodadas.
- E-mail banido não pode se cadastrar, mesmo com novo convite, nem fazer login por nenhum método.
- Contas de comprador e de fornecedor exigem convites próprios (seção 2).
- Convite para um e-mail já associado a outra conta, qualquer que seja o papel, não permite cadastro. A comparação usa o e-mail normalizado (seção 2).
- Requisito derivado: tokens imprevisíveis, expiração e consumo único validados no servidor, inclusive diante de duas tentativas simultâneas.

### 3.2 Acesso e perfil

- Oferecer e-mail e senha, link de acesso por e-mail e conta Google.
- Todos os métodos devem respeitar a identidade de e-mail autorizada e o bloqueio da conta. Login por Google não pode criar uma conta fora do fluxo de convite, e o e-mail do Google só acessa a conta com o mesmo e-mail normalizado.
- Cadastro inicial exige nome e e-mail.
- Telefone/WhatsApp e avatar são opcionais e podem ser adicionados posteriormente.
- Recebimento de mensagens por WhatsApp exige número cadastrado e aceitação opcional do usuário.
- Requisito derivado: evitar contas duplicadas e associação insegura entre métodos de login; definir recuperação de acesso e comprovação de controle do e-mail.

## 4. Fornecedores, produtos e rodadas

### 4.1 Fornecedor

Dados funcionais necessários: identificação/nome, e-mail para envio do pedido formal, mínimo monetário de produtos, prazo padrão de entrega, informações de frete e vínculo com a conta de consulta quando existir.

O mínimo monetário só pode ser alterado durante a fase de interesse da rodada ativa (seção 4.4).

O prazo padrão é editável pelo administrador; a previsão pode ser ajustada após os pagamentos. O frete pode constar do cadastro, mas seu valor efetivo é informado manualmente pelo administrador ao abrir o pagamento de cada rodada.

### 4.2 Produto

Cada produto pertence a um fornecedor. O administrador cadastra e atualiza descrição, preço, medida de venda, disponibilidade, estoque limitado quando aplicável e múltiplo de compra quando exigido.

São aceitas diversas medidas: unidade, pacote, peso, volume e caixa, conforme o produto. A quantidade/peso e o preço devidos precisam estar determinados antes do pagamento; não há ajuste posterior por pesagem nesta versão.

**Unidades e incrementos:**

- O administrador define, por produto, a unidade de medida e o incremento permitido.
- Quantidades fracionárias são permitidas em qualquer unidade de medida configurada, não só peso. Exemplos: 0,25 kg, 0,5 litro, 1 unidade.
- **Validação do incremento:**
  - O incremento é definido individualmente por produto e pode ser inteiro ou fracionário. Não é obrigatório que os produtos usem incremento fracionário, e produtos vendidos por unidade, caixa ou outras medidas indivisíveis não são fracionados.
  - O incremento é maior que zero e tem no máximo três casas decimais.
  - A quantidade solicitada é múltipla exata do incremento.
  - O múltiplo do fornecedor é divisível exatamente pelo incremento.
  - Não se usa ponto flutuante binário para validar quantidades.
  - Exemplos válidos:

    | Produto | Unidade | Incremento |
    |---|---|---|
    | Ovos | unidade | 1 |
    | Maçãs | unidade | 2 |
    | Banana | kg | 0,25 |
    | Leite | litro | 0,5 |
    | Caixa de produtos | caixa | 1 |
- O comprador só pode selecionar quantidades múltiplas do incremento do produto.
- O preço é calculado conforme a quantidade selecionada (seção 9, arredondamento).
- Quantidade e preço são determinados antes do pagamento e ficam congelados na abertura da etapa de pagamento. Não há ajuste posterior por pesagem ou medição.
- Aritmética decimal exata, sem cálculo monetário em ponto flutuante binário, e validação no servidor.
- **Compatibilidade entre múltiplo e incremento:** o múltiplo de compra exigido pelo fornecedor precisa ser divisível exatamente pelo incremento. Exemplo válido: múltiplo de 1 kg com incremento de 0,25 kg. O servidor rejeita configurações incompatíveis no cadastro e em qualquer alteração permitida na fase de interesse (seção 4.4).
- **Alteração do incremento:** o administrador pode alterar o incremento de um produto somente na fase de interesse (seção 4.4). A alteração só é aceita se:
  - o novo incremento for válido;
  - todas as quantidades reservadas e pendentes existentes daquele produto continuarem múltiplas dele;
  - o múltiplo de compra do fornecedor continuar divisível exatamente por ele.

  Se qualquer condição falhar, a alteração é rejeitada integralmente, sem modificar interesses existentes.

O múltiplo de compra só pode ser alterado durante a fase de interesse da rodada ativa (seção 4.4).

Separar a medida vendida ao comprador do múltiplo exigido pelo fornecedor. Exemplo: comprador compra unidades; fornecedor exige grupos de 12 unidades. Não confundir isso com um produto cuja unidade de venda já seja uma caixa inteira.

### 4.3 Rodada ou lista

Uma rodada reúne interesses e pedidos de um único fornecedor. Fornecedores diferentes têm andamento independente, mesmo quando seus produtos aparecem no mesmo carrinho.

- Apenas uma rodada ativa por fornecedor.
- A rodada deixa de impedir outra quando os produtos são recebidos e liberados para retirada, não quando todas as retiradas terminam.
- Pedidos antigos e seus controles de retirada continuam existindo após a abertura de nova rodada.
- Estoque é definido por rodada; não presumir reposição ou reaproveitamento automático do estoque da rodada anterior.
- Rodada em interesse pode permanecer aberta indefinidamente se nunca atingir o mínimo.

### 4.4 Alterações nas condições da rodada

- Mínimo monetário, múltiplos de compra, incremento e estoque só podem ser alterados pelo administrador durante a fase de interesse.
- Alterações de estoque respeitam as reservas existentes: o estoque não pode ficar abaixo da quantidade já reservada.
- A partir do início do fechamento, essas condições ficam congeladas, inclusive para o administrador.
- Se a rodada voltar para interesse, essas condições podem ser alteradas de novo, sem modificar registros históricos ou financeiros dos ciclos anteriores.
- A regra de atualização de preços durante interesse e fechamento (seção 5.1) continua valendo. O congelamento acima não se aplica a preços.
- Requisito derivado: cada ciclo registra os valores de mínimo, múltiplos, incremento e estoque vigentes no início do seu fechamento.
- Alterações de múltiplo ou de incremento na fase de interesse seguem as validações da seção 4.2.

## 5. Carrinho, reservas e prioridade

O carrinho agrega produtos de diferentes fornecedores, mas deve separar visualmente suas rodadas, etapas, prazos e totais. Itens no carrinho representam interesse, não compra paga.

- Adicionar quantidade reserva estoque disponível daquela rodada.
- Não permitir reservas acima do estoque limitado. A quantidade excedente deve ser recusada claramente, sem apresentar sucesso falso.
- Reservas podem permanecer enquanto o interesse existir; não há expiração periódica de reserva definida.
- Remoção, redução, cancelamento ou perda de itens por inadimplência libera a reserva correspondente quando a rodada continuar utilizável.
- Cada acréscimo de quantidade recebe posição própria na fila, preservando a ordem de adição.
- Ao reduzir quantidade, remover primeiro as parcelas mais recentes daquele comprador.
- Quantidades seguem a unidade de medida e o incremento do produto (seção 4.2).
- Parcelas restauradas (seção 5.2) mantêm sua posição original na fila. A restauração não cria parcela, reserva ou posição nova.
- Requisito derivado: reserva, alteração e alocação devem suportar concorrência sem sobrevendagem e usar desempate determinístico.

Durante interesse e fechamento, o comprador pode adicionar, reduzir ou remover itens. Após o prazo de fechamento, alterações ficam bloqueadas até decisão administrativa. Na fase de pagamento, o pedido é congelado; só é possível pagar ou não pagar. A partir daí, a composição do pedido é definitiva (seção 7.1).

### 5.1 Atualização de preços

Atualizações do administrador atingem interesses existentes durante interesse e fechamento, mesmo com mínimo, múltiplos e estoque congelados no fechamento (seção 4.4). Compradores afetados recebem notificação no perfil do site. Recalcular totais e progresso após a alteração.

Pedidos que já entraram em pagamento preservam o preço congelado. Mudança de catálogo não pode alterar uma cobrança existente. Se uma redução de preço derrubar o total elegível abaixo do mínimo ao término do fechamento, retornar para interesse.

### 5.2 Fila de interesses pendentes

- Quando uma caixa é invalidada por inadimplência, as unidades dos compradores adimplentes afetados voltam automaticamente para uma **fila de interesses pendentes do mesmo fornecedor**.
- Cada parcela mantém sua prioridade FIFO original.
- Essas unidades não reservam de novo o estoque da rodada já apurada.
- Na próxima rodada em fase de interesse, o sistema tenta reservar as unidades pendentes pela prioridade original e pelo estoque disponível.
- Unidades que não puderem ser reservadas continuam pendentes, sem reserva fictícia.
- A restauração não modifica a composição de pedidos congelados e não depende da conclusão dos reembolsos.
- Parcelas, reservas e restaurações não são duplicadas, inclusive em execuções concorrentes.
- Compradores inadimplentes perdem todos os interesses daquele fornecedor e não entram na fila de pendentes.
- Interesse pendente não é reserva de estoque.
- Unidades reservadas a partir da fila passam a ser interesses comuns da rodada, com a posição original.

**Prioridade dos pendentes:**

- Sempre que houver estoque disponível para alocação, os interesses pendentes são atendidos primeiro, pela prioridade FIFO original. Só depois são consideradas novas reservas. Isso vale na abertura da fase de interesse e sempre que estoque é liberado ou aumentado.
- A fila de um fornecedor só é atendida pelas rodadas desse fornecedor.
- A integridade das reservas é garantida em operações concorrentes, sem reservas fictícias nem parcelas duplicadas.
- A fila vale quando a rodada anterior continua viável. Quando a rodada volta para interesse, as reservas dos adimplentes permanecem na própria rodada (seção 8.2, regra 17.5).

**Pendentes e mínimo:**

- Quantidades pendentes sem reserva não entram no cálculo do mínimo monetário do fornecedor. Só contam as quantidades elegíveis e reservadas, conforme as regras de apuração (seção 6).
- Pendentes sem estoque continuam na fila para rodadas futuras e não entram antecipadamente em pedidos formais nem em cobranças.

**Visibilidade e remoção pelo comprador:**

- O comprador vê separadamente suas quantidades reservadas e pendentes, inclusive quando não há estoque disponível.
- O comprador pode remover, voluntariamente, parte ou a totalidade das suas quantidades pendentes.
- A remoção atualiza só a quantidade pendente. Não modifica reservas válidas, posições FIFO de outras parcelas, registros financeiros anteriores, pedidos congelados nem reembolsos já devidos.
- A remoção de pendentes não pode ser usada para editar pedidos congelados.
- Requisito derivado: a quantidade removida é múltipla do incremento e não passa da quantidade pendente. Quando o comprador tem mais de uma parcela pendente do mesmo produto, a remoção parcial começa pelas parcelas mais recentes, como na redução de interesses da seção 5.
- Requisito derivado: a remoção de pendentes vale em qualquer fase, porque as quantidades pendentes não fazem parte de nenhum ciclo. Quantidades já reservadas seguem as regras de alteração da seção 5.

## 6. Mínimo monetário e múltiplos de compra

### 6.1 Progresso elegível

O mínimo do fornecedor é sempre monetário e considera **somente produtos**. Excluir frete e taxa de serviço.

Para produto sem restrição de múltiplo, toda quantidade em interesse contribui para o mínimo. Para produto com múltiplo `m`, apenas `floor(quantidade total / m) × m` unidades contribuem. A regra é por produto; não misturar produtos para completar uma caixa sem nova decisão de negócio.

Exemplo: 18 unidades de R$ 10,00 com múltiplo 12 representam R$ 180,00 de interesse bruto, mas apenas R$ 120,00 elegíveis para o mínimo. Há uma caixa completa e seis unidades aguardando; faltam seis para outra caixa.

### 6.2 Exibição

Comprador vê seu pedido, o progresso agregado do fornecedor e, em produtos com múltiplo:

- total agregado em interesse;
- número de caixas completas;
- unidades faltantes para a próxima caixa;
- quantas de suas unidades estão em caixas completas;
- quantas de suas unidades estão excedentes aguardando outra caixa.

Não exibir nomes ou pedidos individuais de outros compradores. Fornecedor vê quantidades agregadas, caixas completas, excedentes, preços unitários, valores totais dos produtos e andamento, sem identidades dos compradores (seção 2).

### 6.3 Fechamento das caixas

Ao terminar as 24 horas de fechamento, remover unidades que não completam caixas, respeitando prioridade por adição. É permitido reduzir parcialmente o pedido de um comprador. Informar a redução ao afetado e recalcular o mínimo.

Não abrir espera adicional para completar caixas. Se o mínimo deixar de ser atendido, retornar para interesse conforme as regras da rodada.

Ao abrir pagamento, congelar a composição das caixas e registrar quais parcelas de cada comprador pertencem a cada caixa. Não redistribuir compradores entre caixas em razão de inadimplência.

## 7. Ciclo da rodada e autorizações

Os nomes abaixo separam estados operacionais de bloqueios por prazo. São nomes funcionais, não imposição de enum ou estrutura de banco.

| Estado/situação | Comportamento e saída |
|---|---|
| Interesse | Aceita alterações e reserva estoque. Pode durar indefinidamente. Atingir o mínimo apenas habilita o administrador a iniciar fechamento. |
| Fechamento | Inicia por ação administrativa quando mínimo elegível é atendido. Prazo de 24h a partir da autorização. Aceita alterações e novos compradores. |
| Fechamento com prazo encerrado | Bloqueia alterações automaticamente, remove excedentes de caixas e verifica mínimo. Se insuficiente, volta para interesse; se suficiente, aguarda autorização para pagamento. |
| Pagamento | Inicia por ação administrativa, no instante `T0`, com frete informado e pedidos congelados. Prazo oficial de exatamente 24h, improrrogável, inclusive pelo administrador. Não aceita novos compradores nem alterações de pedidos. |
| Margem operacional | De `T0 + 24h` a `T0 + 48h`. Novas tentativas de pagamento ficam bloqueadas automaticamente em `T0 + 24h`. Serve apenas para confirmar e conciliar pagamentos já iniciados. Não reabre compras, não altera pedidos e não autoriza novas cobranças. Não prorroga o prazo oficial de pagamento. |
| Apta para apuração final | A partir de `T0 + 48h`. A apuração de pagamentos, inadimplência, caixas inválidas e mínimo remanescente começa somente por autorização administrativa. Não pode ser antecipada, mesmo que todos os compradores tenham pago. O avanço ou a execução dos estornos aguarda decisão administrativa. |
| Aguardando fornecedor | Resultado válido da cobrança é aprovado pelo administrador. Pedido formal é enviado automaticamente por e-mail. Administrador paga fornecedor e registra repasse manualmente. Aguarda recebimento dos produtos. |
| Disponível para retirada | Administrador confirma recebimento/libera retirada. Rodada é encerrada para permitir nova rodada do fornecedor. Pedidos mantêm acompanhamento individual de retirada e eventual descarte. |
| Cancelada | Administrador cancela a rodada inteira por decisão própria, sem informar motivo, e indica se existe reembolso devido (seção 7.2). Interesses são removidos. Valores pagos exigem tratamento financeiro, nunca simples exclusão. |

O encerramento automático dos prazos não autoriza automaticamente uma nova etapa. O retorno por mínimo insuficiente é uma regra de falha, não uma autorização para nova cobrança.

Se o mínimo cair durante o fechamento, preservar o prazo original: aguardar até seu término. **Não há contador adicional de observação de 24h nem cancelamento automático por esse motivo.**

O administrador pode prorrogar o prazo de fechamento e os demais prazos conforme as regras existentes e cancelar rodadas (seção 7.2). Pedidos congelados não podem ser corrigidos (seção 7.1). O prazo de pagamento de 24h é definitivo e não pode ser prorrogado nem pelo administrador. Requisito derivado: a margem operacional também não é prorrogável, porque o critério de aceitação de pagamentos (seção 8.3) é fixo em `T0 + 48h`. O administrador pode iniciar a apuração depois de `T0 + 48h`, mas isso não amplia esse critério. Toda intervenção deve ser auditada. Nenhuma intervenção pode reescrever pagamentos concluídos, apagar histórico ou cobrar valor adicional.

### 7.1 Imutabilidade do pedido congelado

- Após a abertura da etapa de pagamento, a composição do pedido (produtos e quantidades) é definitiva.
- Nem compradores nem administrador podem adicionar, remover ou alterar produtos e quantidades de pedidos congelados. Não há funcionalidade de edição ou correção de pedidos congelados.
- O pedido original permanece preservado como registro histórico.
- A imutabilidade é do **pedido comercial**. Continuam permitidas as mudanças legítimas de **estado financeiro e operacional**, registradas separadamente e sem alterar a composição: pagamento, cancelamento por inadimplência ou caixa inválida (seção 8.2), cancelamento da rodada (seção 7.2), devolução, ocorrência de entrega (seção 10), retirada e descarte.
- Pagamentos comunicados tardiamente pelo provedor não autorizam editar pedidos já apurados (seção 8.3).

### 7.2 Cancelamento administrativo da rodada

- Somente o administrador pode cancelar uma rodada, por decisão própria.
- O cancelamento afeta todos os compradores daquela rodada, nunca apenas compradores selecionados. Não há cancelamento individual.
- Não é necessário informar ao sistema o motivo do cancelamento nem o que aconteceu com o fornecedor.
- Ao cancelar, o administrador informa se existe reembolso devido:
  - **Com reembolso:** devolução integral para todos os compradores que efetivamente pagaram.
  - **Sem reembolso:** o cancelamento não inicia novas devoluções.
- Obrigações de devolução já existentes não são apagadas nem consideradas liquidadas porque o administrador escolheu "sem reembolso".
- Pagamentos, repasses, devoluções e demais registros financeiros anteriores permanecem preservados.
- Os reembolsos seguem os mecanismos já definidos: plataforma de pagamentos integrada como via principal e devolução excepcional confirmada pelo administrador quando necessária (seções 9.2 e 9.5).
- Requisito derivado: "integral" corresponde ao valor pago pelo comprador (produtos, serviço e frete), descontadas as devoluções já concluídas ou pendentes, para que o total devolvido nunca ultrapasse o valor pago (seção 9.2).
- Requisito derivado: a indicação "com reembolso" no cancelamento já é a autorização administrativa das devoluções geradas. Não há etapa de aprovação adicional.
- Requisito derivado: ao cancelar, novas tentativas de pagamento ficam bloqueadas. Um pagamento aprovado depois do cancelamento é registrado e tratado financeiramente com auditoria, como em 8.3, sem alterar pedidos.
- O cancelamento é distinto das ocorrências de entrega (seção 10): ocorrências não cancelam a rodada, e o cancelamento não é feito por produto ou comprador.

## 8. Pagamento, inadimplência e retorno ao interesse

### 8.1 Abertura

Antes de autorizar pagamento, validar mínimo e caixas, informar frete e calcular pedidos individuais. Gerar uma obrigação de pagamento por comprador e por rodada de fornecedor; não consolidar fornecedores diferentes em uma cobrança.

Todos os pagamentos de compradores ocorrem exclusivamente pela plataforma de pagamentos integrada. É proibido receber pagamentos de compradores por Pix direto, transferência ou qualquer mecanismo externo. A devolução excepcional da seção 9.5 não é exceção a essa proibição.

Oferecer os meios suportados pela plataforma escolhida que sejam compatíveis com a operação e seus prazos. A seleção precisa considerar confirmações assíncronas, expiração e estornos; não presumir que todos os meios tenham confirmação imediata.

### 8.2 Margem operacional e apuração final

1. Em `T0 + 24h`, bloquear novas tentativas de pagamento.
2. Entre `T0 + 24h` e `T0 + 48h` (margem operacional), confirmar e conciliar pagamentos já iniciados. Pedidos não pagos ainda não são cancelados nesse intervalo.
3. A partir de `T0 + 48h`, e somente por autorização administrativa, iniciar a apuração final:
   1. Identificar os pagamentos aceitos conforme a seção 8.3 e os pedidos não pagos.
   2. Cancelar pedidos não pagos. Compradores inadimplentes perdem todos os itens daquele fornecedor no carrinho, inclusive suas reservas e posições na fila.
   3. Invalidar caixas que ficaram incompletas por inadimplência, sem reorganizar suas unidades.
   4. Apurar estorno proporcional de unidades pagas em caixas invalidadas. Quando a rodada segue viável, essas unidades vão para a fila de interesses pendentes do fornecedor (seção 5.2), com a prioridade original de cada parcela, sem reservar de novo o estoque desta rodada e sem esperar a conclusão financeira do reembolso. Quando a rodada volta para interesse, valem as regras de retorno ao interesse abaixo. Os itens válidos do ciclo original não são alterados. A restauração não duplica reservas, parcelas de interesse nem posições na fila.
   5. Recalcular mínimo considerando somente produtos pagos que ainda podem ser pedidos.
   6. Se o mínimo permanecer atendido, apresentar resultado ao administrador para avanço e autorizações financeiras necessárias.
   7. Se não for atendido, retornar a rodada para interesse e apresentar ao administrador, para autorização, a devolução de todos os valores recebidos. Como nenhuma compra ao fornecedor foi realizada, não há frete efetivo nesse fluxo.

A apuração final não pode ser antecipada, mesmo que todos os compradores tenham pago antes de `T0 + 48h`.

Se o mínimo permanecer válido, o administrador assume o frete atribuído aos inadimplentes como déficit de frete (seção 9.3). Não aumentar o frete de quem já pagou.

Quando a rodada volta para interesse por insuficiência de pagamentos:

- Interesses e reservas de quem pagou são preservados ou restaurados, conforme o caso, com a prioridade original.
- Pedidos de quem não pagou são removidos, e suas reservas liberadas.
- O estoque cadastrado permanece inalterado. Não há reposição automática, redefinição de estoque nem duplicação de reservas.
- Reembolsos pendentes não impedem a continuidade da rodada.
- Os registros financeiros anteriores permanecem separados. É permitido iniciar novo fechamento mesmo com estornos anteriores pendentes.
- Mínimo, múltiplos e estoque voltam a ser alteráveis (seção 4.4).

Requisito derivado: distinguir tentativas/ciclos financeiros de uma mesma rodada. Um pagamento antigo ou webhook atrasado não pode quitar um pedido novo nem duplicar reservas ou interesses.

### 8.3 Pagamentos tardios e concorrência

- O prazo oficial para o comprador pagar é de 24h, de `T0` a `T0 + 24h`. A partir de `T0 + 24h`, não são permitidas novas tentativas de pagamento.
- Pagamentos já iniciados dentro do prazo e efetivamente aprovados até `T0 + 48h` são aceitos e quitam o pedido.
- O critério de aceitação é o horário efetivo de aprovação registrado pelo provedor, não o horário de recebimento da notificação. Uma aprovação feita até `T0 + 48h` e notificada depois disso é aceita, desde que identificada na apuração.
- Pagamentos aprovados depois de `T0 + 48h` não quitam o pedido e geram obrigação de devolução, pela plataforma de pagamentos ou, quando necessário, pela devolução excepcional (seção 9.5).
- A margem operacional não reabre compras, não altera pedidos e não autoriza novas cobranças.
- Nunca ignorar dinheiro recebido nem autorizar pedido duplicado por repetição de evento.
- Pagamentos comunicados tardiamente pelo provedor não autorizam editar pedidos já apurados. São registrados e tratados financeiramente, com auditoria e sem alterar o pedido original.
- Requisito derivado: cada pagamento do provedor é reconhecido uma única vez. Se um pedido tiver mais de um pagamento aceito, apenas um quita o pedido e os demais geram obrigação de devolução integral.
- Requisito derivado: a compatibilidade do vencimento configurado no provedor com essas regras precisa ser validada tecnicamente antes da operação real. O comportamento do provedor não é presumido (documento de infraestrutura, seção 9.2).

## 9. Cálculos financeiros e estornos

Para cada comprador, no momento de abrir pagamento:

- `P` = subtotal de produtos elegíveis do comprador.
- `T` = soma de subtotais elegíveis de todos os compradores da rodada.
- `F` = frete total informado pelo administrador.
- Serviço do comprador = `5% × P`.
- Frete do comprador = `F × P / T`.
- Total a pagar = produtos + serviço + frete.

Usar representação monetária exata e regra determinística de arredondamento. A soma das parcelas de frete deve ser exatamente o frete informado, inclusive quando houver centavos residuais. Registrar valores congelados e componentes separadamente.

**Arredondamento dos produtos:**

- Preços unitários são cadastrados com duas casas decimais.
- O subtotal de cada item é preço unitário × quantidade, calculado com precisão decimal exata e arredondado **uma única vez** para duas casas, com `ROUND_HALF_UP`.
- O total dos produtos (`P`) é a soma dos subtotais já arredondados.
- Os valores efetivamente cobrados são registrados.
- Exemplo: R$ 7,99/kg × 0,25 kg = R$ 1,9975, e o subtotal cobrável é R$ 2,00.
- As regras de taxa de serviço, frete, segregação financeira e reembolso proporcional continuam as mesmas, aplicadas sobre os subtotais registrados.

### 9.1 Motivos previstos de estorno

- Mínimo não alcançado após apuração dos pagamentos.
- Unidades pagas em caixa que ficou incompleta por inadimplência.
- Ocorrências de entrega: itens faltantes, incorretos ou não entregues (reembolso pontual, seção 10).
- Cancelamento administrativo da rodada com reembolso (devolução integral, seção 7.2).
- Pagamento aprovado depois de `T0 + 48h` (devolução integral, seção 8.3).
- Pagamento em duplicidade para o mesmo pedido (devolução integral do excedente, seção 8.3).

Após pagar, o comprador não dispõe de cancelamento voluntário no fluxo definido. Exceções obrigatórias, disputas e requisitos do provedor precisam ser avaliados para produção; a regra de interface não elimina obrigações externas.

### 9.2 Estorno proporcional

Estornar produtos afetados, serviço correspondente e frete proporcional. Exemplo: comprador pagou R$ 100,00 em produtos, R$ 5,00 de serviço e R$ 20,00 de frete. Se faltar R$ 25,00 em produtos, estorno de R$ 25,00 + R$ 1,25 + R$ 5,00 = R$ 31,25.

O administrador autoriza estornos manualmente no dashboard; a plataforma de pagamentos executa a devolução, que é a via principal. A devolução excepcional (seção 9.5) só se aplica quando a via principal for comprovadamente inviável. Exibir estados solicitados, pendentes, concluídos e falhos, com possibilidade segura de retentativa. Autorização não equivale a dinheiro devolvido.

Estornos sucessivos não podem ultrapassar o valor efetivamente pago ou devolver duas vezes a mesma parcela. Estorno integral deve completar exatamente o saldo restante, evitando resíduos de arredondamento.

Reembolsos usam os valores registrados no ciclo financeiro original, sem recalcular com preços atuais. Reembolsos do item inteiro usam o subtotal registrado.

**Reembolso parcial de item:**

- Quando parte da quantidade de um item não é entregue, o valor de produtos do reembolso é proporcional ao subtotal cobrado e registrado: `subtotal registrado × (quantidade reembolsada ÷ quantidade do item)`, arredondado a centavos com `ROUND_HALF_UP`.
- O preço atual do produto nunca é usado.
- Os reembolsos acumulados são controlados por item, e a soma nunca ultrapassa o subtotal originalmente cobrado. Se o cálculo levaria a soma além do subtotal, o reembolso é limitado ao saldo restante do item.
- Quando a quantidade reembolsada acumulada completa a quantidade do item, o último reembolso é exatamente o saldo restante, e a soma devolvida é exatamente o subtotal cobrado.
- Taxa de serviço e frete seguem a regra proporcional desta seção.
- Cada devolução é registrada separadamente, sem alterar a composição do pedido congelado.
- O cálculo é determinístico, inclusive com vários reembolsos parciais do mesmo item.
- Requisito derivado: o mesmo cálculo vale para todo reembolso de parte de um item, inclusive unidades em caixa invalidada (seção 8.2) e ocorrências de entrega (seção 10).
- Requisito derivado: serviço e frete de cada reembolso parcial são calculados sobre os valores registrados do pedido, com `ROUND_HALF_UP`, e o mesmo controle acumulado por componente. Uma devolução integral do pedido completa exatamente o saldo restante de cada componente.

Taxas cobradas pela plataforma de pagamentos, custo de WhatsApp e outros custos operacionais não são repassados ao comprador, nem por cobrança adicional retroativa. Tarifas do provedor de pagamentos são despesas operacionais cobertas pela receita da taxa de serviço (seção 9.3).

### 9.3 Segregação financeira

- O livro-razão separa:
  - custódia das rodadas;
  - obrigações com fornecedores;
  - receita de serviço;
  - reserva;
  - despesas.

  Registra também as obrigações financeiras com compradores (devoluções devidas) e, separadamente, frete arrecadado, frete efetivo e déficits de frete.
- Recursos destinados a um fornecedor são exclusivos para o pagamento desse fornecedor, ressalvadas as devoluções legitimamente devidas aos compradores antes do repasse.
- Esses recursos nunca podem financiar tarifas, déficits, prejuízos ou obrigações de outros fornecedores.
- Tarifas do provedor de pagamentos são despesas operacionais cobertas pela receita da taxa de serviço.
- Déficits de frete são responsabilidade financeira do administrador.
- Despesas e prejuízos da plataforma são cobertos pela taxa de serviço, pelo aporte inicial ou por novos aportes.
- Não há cobrança adicional retroativa aos compradores.
- Toda movimentação entre destinações financeiras é explícita, justificada, rastreável e auditável.
- A segregação é garantida pelo livro-razão, mesmo que o provedor apresente saldo financeiro único.
- Frete efetivo só existe quando a compra ao fornecedor é realizada. Quando a rodada volta para interesse por insuficiência de pagamentos, todos os valores recebidos são devolvidos e não há frete efetivo.
- Requisito derivado: déficit de frete é a diferença entre o frete efetivo e o frete arrecadado, já descontadas as devoluções.

### 9.4 Reserva financeira

- O administrador faz um aporte inicial de R$ 1.000,00 de capital próprio. O aporte não é receita da plataforma.
- A reserva pode cobrir estornos, tarifas, déficits de frete e outros prejuízos ou despesas operacionais.
- A reserva não limita a responsabilidade por estornos e não autoriza utilizar recursos de fornecedores.
- Sua utilização não pode comprometer recursos reservados para obrigações financeiras existentes, nem reduzir indevidamente valores devidos a fornecedores ou compradores.
- Não há recomposição automática obrigatória até R$ 1.000,00. O administrador pode realizar novos aportes conforme a necessidade.
- O sistema apresenta o saldo da reserva e alertas de insuficiência.
- Aportes, utilizações, saldos e obrigações são registrados no livro-razão.

### 9.5 Devolução excepcional

- A devolução pela plataforma de pagamentos integrada é a via principal.
- Quando ela for comprovadamente inviável, é permitida devolução excepcional por Pix ou transferência bancária ao comprador.
- O administrador realiza a devolução excepcional diretamente ao comprador, fora da integração. A plataforma não executa essa devolução, não tem integração para ela e não exige que o dinheiro saia da conta do provedor.
- A plataforma permite somente a confirmação administrativa explícita de que a devolução foi realizada. Essa confirmação registra pedido, comprador, valor, justificativa, identificação da transferência e comprovante, e dá baixa na obrigação financeira.
- Impedir devolução duplicada: a confirmação não é aceita enquanto houver operação pendente na plataforma de pagamentos para a mesma parcela, nem duas vezes para a mesma parcela. Depois dela, novas tentativas na plataforma ficam bloqueadas.
- A obrigação financeira permanece integralmente registrada enquanto não for liquidada.
- A exceção aplica-se exclusivamente a devoluções, nunca ao recebimento de pagamentos de compradores.

### 9.6 Contestação e devolução forçada (Q-8)

Contestação é a disputa aberta pelo comprador no cartão (fase 2b). Devolução forçada é a devolução de um Pix imposta pelo banco do pagador (MED, fase 2a). Nas duas, o provedor debita o valor da conta depois da aprovação do pagamento, sem uma devolução autorizada pela plataforma.

- O fornecedor recebe integralmente, antes ou depois do repasse. Os recursos destinados a ele não cobrem a perda (P-2).
- A perda é coberta primeiro pela receita de serviço da rodada do pedido, depois pela reserva e, se faltar, por novo aporte (P-1, P-3).
- O comprador do pagamento contestado é suspenso (seção 2) para análise do administrador. Não há banimento automático. A reversão da suspensão segue a seção 2.
- O débito e cada cobertura são lançamentos explícitos, auditáveis e justificados no livro-razão (seção 9.3).
- Fase 1: o simulador reproduz o débito, e a conciliação diária o aponta como divergência. Os lançamentos e a suspensão automáticos entram com o meio de pagamento real que os produz (fase 2a para o Pix, fase 2b para o cartão).

## 10. Pedido formal, repasse e recebimento

- Fornecedor consulta somente os dados permitidos na seção 2.
- Após aprovação do resultado válido da etapa de pagamento, enviar automaticamente pedido formal ao e-mail do fornecedor.
- **Falhas no envio:**
  - O envio automático inicial tem até três tentativas no total, incluindo a primeira.
  - Depois de três falhas, o sistema notifica o administrador e disponibiliza o botão **Reenviar pedido**.
  - O botão também fica disponível depois de um envio bem-sucedido.
  - Cada acionamento do botão executa uma única tentativa. Tentativas manuais não iniciam outro ciclo de três tentativas automáticas.
  - O reenvio usa o mesmo pedido formal, sem gerar outro pedido nem alterar produtos, quantidades ou valores.
  - Todas as tentativas e seus resultados são registrados e auditáveis.
  - Há proteção contra duplicação por concorrência ou acionamentos repetidos, sem impedir reenvios manuais legítimos.
  - Enquanto o ciclo automático estiver em andamento (antes de um sucesso ou da terceira falha), o administrador não pode executar reenvio manual. Concluído o ciclo, o reenvio fica disponível, inclusive se o envio automático tiver sido bem-sucedido.
  - Aceitação do e-mail pelo serviço de envio não comprova entrega ao fornecedor (documento de infraestrutura, L-13).
- Pedido deve identificar rodada, produtos, medidas, quantidades finais, caixas/múltiplos quando aplicáveis e condições de entrega pertinentes. Não incluir dados pessoais de compradores.
- Não enviar pedido com unidades inadimplentes, caixas inválidas ou quantidades ainda sujeitas à apuração.
- Transferência ao fornecedor é manual nesta versão; administrador registra confirmação no dashboard. O repasse manual não é pagamento de comprador e continua permitido. Ele usa somente recursos registrados como obrigação com aquele fornecedor (seção 9.3).
- Prazo padrão de entrega vem do fornecedor e pode ser ajustado pelo administrador após pagamentos.
- Não há substituição de produtos.
- Se entrega for parcial, administrador registra as ocorrências e autoriza o reembolso ou aguarda o restante antes de anunciar o recebimento. Não existe liberação automática de retirada parcial.
- **Ocorrências de entrega:** após a entrega, o administrador pode registrar, por produto e quantidade, itens faltantes, incorretos ou não entregues, conforme constatado.
  - Cada ocorrência permite reembolso pontual dos itens afetados, incluindo serviço e frete proporcionais (seção 9.2).
  - Ocorrências e reembolsos são registrados separadamente, sem modificar o pedido original (seção 7.1).
  - O comprador não pode modificar o pedido para informar faltas ou solicitar substituições.
  - Ocorrências não cancelam a rodada.
  - Requisito derivado: a quantidade somada das ocorrências de um item não pode ultrapassar a quantidade paga desse item no pedido.
- Após resolver ocorrências ou receber tudo, administrador libera retirada e encerra a rodada para novas compras do fornecedor.

## 11. Retirada e descarte

- Endereço disponível no carrinho e nas regras de funcionamento do site. Exposição fora da área autenticada não foi solicitada.
- Retirada normalmente disponível, salvo avisos de restrição publicados pelo administrador.
- Liberação de retirada gera avisos por e-mail, perfil do site e WhatsApp para quem optou pelo canal.
- Administrador registra retirada por item e quantidade, permitindo retiradas em momentos diferentes.
- Prazo de armazenamento: sete dias a partir da liberação para retirada.
- Depois do prazo, administrador registra manualmente o descarte dos itens restantes. Não marcar descarte como ocorrido apenas porque o tempo passou.
- Preservar histórico de quantidades recebidas, estornadas, retiradas e descartadas.
- A disponibilidade de nova rodada não depende da conclusão das retiradas anteriores.

## 12. Notificações e comunicados

### Canais

- Perfil do site: central de notificações do usuário.
- E-mail: avisos operacionais e pedido formal ao fornecedor.
- WhatsApp: somente com número e consentimento de recebimento; não presumir SMS.

### Eventos funcionais

| Evento | Conteúdo necessário |
|---|---|
| Convite | Link, finalidade e expiração de 24h. |
| Alteração de preço de item no carrinho | Produto afetado, preço atualizado e impacto no interesse; notificação no site explicitamente obrigatória. |
| Início do fechamento | Fornecedor, etapa e prazo; não pedir confirmação de interesse. |
| Remoção de excedentes de caixa | Produto, quantidade removida e quantidade mantida. |
| Abertura do pagamento | Pedido congelado, discriminação de valores e prazo oficial de 24h, sem prorrogação. |
| Pagamento confirmado | Estado do pagamento e referência ao pedido. |
| Cancelamento por inadimplência ou caixa incompleta | Itens afetados e consequência financeira. Para quem pagou unidades em caixa invalidada, também o retorno dessas unidades ao interesse ou à fila de interesses pendentes (seção 5.2). |
| Retorno para interesse | Motivo e situação de interesses e estornos. |
| Estorno | Valor, motivo (inclusive pagamento aprovado depois de `T0 + 48h` ou em duplicidade) e estado real do processamento, inclusive quando for devolução excepcional. |
| Alteração de previsão de entrega | Nova previsão para pedidos afetados. |
| Liberação de retirada | Endereço, disponibilidade e limite de sete dias. |
| Cancelamento administrativo | Rodada cancelada, indicação de reembolso integral ou de ausência de novas devoluções e, quando o administrador desejar, mensagem customizada. A mensagem é opcional e não é motivo obrigatório. |
| Comunicado administrativo | Mensagem para todos os usuários compradores pelos canais aplicáveis. |
| Falha no envio do pedido formal | Para o administrador, depois da terceira tentativa sem sucesso: rodada, tentativas, resultados e acesso ao botão **Reenviar pedido**. |

Além dos canais explicitamente definidos, a distribuição exata de cada evento entre e-mail e WhatsApp deve ser configurada na especificação técnica para evitar mensagens desnecessárias. Lembretes adicionais não foram definidos como regra obrigatória.

Requisitos derivados: registrar envio e falhas; permitir retentativa sem duplicação indevida; não fazer falha de mensagem alterar o estado financeiro. O estado exibido no site deve continuar correto mesmo se um canal externo falhar.

## 13. Telas e capacidades mínimas

### Comprador

- Aceite de convite, cadastro, login e recuperação de acesso.
- Catálogo por fornecedor, medidas, incrementos, preços, disponibilidade e múltiplos.
- Progresso monetário elegível de cada fornecedor.
- Carrinho agrupado por rodada, com reservas, excedentes, etapas e prazos. Quantidades reservadas e pendentes aparecem separadas, e as pendentes podem ser removidas (seção 5.2).
- Pedido congelado com produtos, taxa de 5%, frete e pagamento.
- Histórico de pedidos, pagamentos, estornos e retirada por item.
- Notificações, regras, endereço e comunicados.
- Perfil com nome, avatar, WhatsApp e preferência de recebimento.

### Administrador

- Dashboard de rodadas, mínimos, caixas pendentes, prazos encerrados e ações necessárias.
- Gestão de fornecedores, produtos, preços, medidas, incrementos, múltiplos e estoque por rodada. Mínimo, múltiplos, incremento e estoque só são editáveis na fase de interesse.
- Emissão e consulta de convites, inclusive vínculo ao fornecedor.
- Gestão de usuários, suspensão/reversão e remoção com banimento de e-mail.
- Início de etapas, definição de frete, prorrogação (exceto prazo de pagamento e margem operacional) e cancelamento da rodada inteira, com indicação de reembolso devido. Sem edição de pedidos congelados.
- Apuração de pagamentos, caixas inválidas, déficit de frete e autorização/acompanhamento de estornos.
- Situação dos pagamentos durante a margem operacional, incluindo pagamentos aprovados depois de `T0 + 48h` e em duplicidade.
- Devolução excepcional: parcelas elegíveis e confirmação administrativa da devolução feita fora da integração, com registro da transferência, comprovante e baixa da obrigação.
- Livro-razão por destinação, com movimentações justificadas, e reserva financeira (aportes, utilizações, saldo e alertas de insuficiência).
- Visualização do pedido consolidado, envio formal, tentativas registradas (automáticas e manuais), falhas de comunicação e botão **Reenviar pedido**, disponível depois de três falhas ou de um envio bem-sucedido.
- Registro de repasse, previsão de entrega, ocorrências de entrega (faltantes, incorretos, não entregues) com reembolso pontual, e liberação de retirada.
- Controle de retirada por item, itens vencidos e registro de descarte.
- Comunicados gerais e histórico de ações relevantes.

### Fornecedor

- Cadastro por convite e login.
- Consulta de seus produtos e rodadas com quantidades agregadas, caixas, excedentes, preços unitários, valores totais dos produtos, progresso e etapa.
- Consulta do pedido formal e da previsão de entrega, sem dados individuais dos compradores, pagamentos individuais, taxa de serviço, reserva ou dados de outros fornecedores.
- Sem acesso a compras: a pessoa usa sua conta de comprador, se tiver uma.

## 14. Modelo conceitual de informação

Não impõe tabelas, mas a solução deve representar sem perda de histórico:

| Conceito | Responsabilidade |
|---|---|
| Conta e perfil | Identidade, e-mail normalizado exclusivo na plataforma, papel único por conta (comprador ou fornecedor), status de acesso e preferências. Contas de comprador e fornecedor da mesma pessoa são independentes e usam e-mails diferentes. |
| E-mail banido | Endereço normalizado banido, autor e momento. Bloqueia login e cadastro e invalida as sessões ativas daquele e-mail. |
| Convite | E-mail, papel, fornecedor vinculado, emissão, expiração e consumo. |
| Fornecedor e produto | Cadastro e condições correntes de catálogo, incluindo unidade de medida, incremento permitido e preço unitário com duas casas decimais. |
| Rodada | Fornecedor, etapa, mínimo, prazos, frete e condições aplicáveis. Valores de mínimo, múltiplos e estoque congelados por ciclo a partir do fechamento. Quando cancelada: autor, momento e indicação de reembolso devido. |
| Estoque da rodada | Limite, reservas e disponibilidade. |
| Parcela de interesse | Comprador, produto, quantidade decimal exata, posição de adição, situação (ativa, em pedido, pendente, removida), quantidade reservada e quantidade pendente sem reserva. A restauração e a reserva a partir da fila mantêm a mesma parcela e posição. |
| Caixa/lote e alocação | Composição congelada das unidades por parcela e validade após pagamento. |
| Pedido e itens | Snapshot comercial por comprador, rodada e ciclo de cobrança, com preço unitário, quantidade e subtotal cobrado registrados por item. Composição imutável após a abertura do pagamento. Estados financeiros e operacionais registrados à parte. |
| Pagamento e eventos | Tentativas, identificadores externos, horário de aprovação no provedor, horário de recebimento da notificação e conciliação. |
| Estorno e parcelas | Motivo, autorização, componentes, valores reembolsados acumulados por item e por componente, processamento externo e, quando aplicável, devolução excepcional com transferência, comprovante, confirmação administrativa e baixa. |
| Livro-razão e destinações | Custódia das rodadas, obrigações com fornecedores e compradores, receita de serviço, reserva, despesas e frete (arrecadado, efetivo e déficit). Movimentações justificadas e auditáveis. |
| Reserva e aportes | Aportes, utilizações, saldo e alertas de insuficiência. |
| Pedido ao fornecedor e repasse | Quantidades finais, pedido formal único por ciclo, tentativas de envio (automáticas e manuais) com resultados, e registro manual de transferência. |
| Recebimento e retirada | Quantidades recebidas, faltantes, retiradas, descartadas e datas. |
| Ocorrência de entrega | Item do pedido, quantidade, tipo (faltante, incorreto, não entregue), autor, momento e reembolso associado, sem alterar o pedido. |
| Notificação e comunicado | Destinatários, canais, conteúdo e resultado de entrega. |
| Auditoria | Autor, ação, momento, motivo quando exigido e alterações relevantes. O cancelamento de rodada não exige motivo. |

Estados de rodada, pedido, pagamento, estorno e retirada são independentes. Por exemplo, rodada pode estar em novo fechamento enquanto estorno do ciclo anterior ainda está pendente.

## 15. Requisitos de produção para o agente de infraestrutura

A proposta deve dimensionar os 100 compradores totais e 50 fornecedores sem presumir carga simultânea igual ao cadastro. Considerar concentração de acessos nos avisos de pagamento e um possível crescimento posterior. Evitar complexidade sem necessidade, preservando integridade financeira.

### Integridade e segurança

- Transações ou mecanismo equivalente para estoque, fila, caixas e congelamento de pedidos.
- Idempotência em ações críticas, webhooks, pedidos formais e estornos.
- Validação de autenticidade de eventos da plataforma de pagamentos e conciliação recuperável.
- Nenhum dado sensível de cartão tratado diretamente pela aplicação quando o provedor puder hospedá-lo.
- Autorização por perfil, usuário e fornecedor em toda leitura/escrita.
- Proteção reforçada para conta administrativa e operações financeiras; propor método de autenticação adequado.
- Segredos fora do código e dos logs; proteção e retenção apropriadas para dados pessoais.
- Histórico financeiro imutável ou auditável; remoção de conta não apaga fatos operacionais.
- Pagamentos de compradores exclusivamente pelo provedor integrado. A aplicação não pode iniciar em produção com o simulador de pagamentos habilitado.
- Livro-razão que garanta a segregação da seção 9.3, independentemente de o provedor oferecer segregação nativa de saldo.
- Nenhuma dupla devolução nem reconhecimento duplicado de pagamento, inclusive com webhooks, expiração, conciliação e autorização administrativa concorrentes.

### Tempo e processamento externo

- Prazos calculados no servidor: 24 horas decorridas, inclusive de madrugada.
- Datas exibidas no fuso da operação, inicialmente America/Sao_Paulo; armazenar instantes de forma inequívoca.
- Bloqueios por prazo devem valer mesmo se um job atrasar: validar prazo também nas ações do usuário.
- Processamento retomável após interrupção, sem aplicar transição ou estorno duas vezes.
- Separar tempo do evento financeiro, tempo de recebimento do webhook e prazo comercial. A aceitação de pagamentos usa o horário de aprovação registrado pelo provedor (seção 8.3).
- Não presumir que o provedor garanta a aprovação de cobranças depois do vencimento, nem que ofereça segregação nativa de saldo.

### Operação

- Ambientes separados de desenvolvimento, testes e produção; pagamentos de teste nunca confundidos com reais. A primeira fase usa apenas simulador, sem dinheiro real. A operação financeira real começa com a integração do provedor.
- Backup e restauração verificável, com proposta de objetivos de recuperação.
- Logs e alertas para pagamentos sem conciliação, estornos falhos, tarefas atrasadas e falhas de comunicação.
- Controle de custo de hospedagem, autenticação, banco, e-mail, WhatsApp, armazenamento e pagamentos.
- Documentar limitações e custos de cada meio de pagamento, reembolso e mensagem, com fontes atuais na pesquisa de infraestrutura.
- Definir procedimentos de suporte, incidentes, atualização e recuperação antes do lançamento.
- Avaliar requisitos aplicáveis de privacidade, retenção, consumo e operação financeira no Brasil; não considerar este documento parecer jurídico ou fiscal.

## 16. Cenários mínimos de aceitação

1. Convite com mais de 24h, já consumido ou usado com outro e-mail não cadastra usuário. Convite de fornecedor não permite escolher outro fornecedor.
2. Login por Google ou link não contorna convite, suspensão ou banimento.
3. Duas reservas simultâneas para a última unidade não podem ambas ser aceitas.
4. Interesse abaixo do mínimo permanece aberto indefinidamente. Atingir mínimo não inicia fechamento sozinho.
5. Administrador inicia fechamento e o término ocorre 24h depois. Queda temporária do mínimo não reinicia nem estende o relógio.
6. Produto de R$ 10,00, múltiplo 12 e 18 unidades gera R$ 120,00 elegíveis, não R$ 180,00.
7. Comprador A adiciona 8 unidades; B adiciona 10: primeira caixa contém 8 de A e 4 de B; B vê 6 excedentes. No fim do fechamento, essas 6 são removidas.
8. A aumenta posteriormente sua quantidade: o acréscimo fica depois das adições anteriores de B. Redução de A remove primeiro seu acréscimo mais recente.
9. Fechamento encerrado com mínimo insuficiente volta para interesse. Com mínimo suficiente, fica bloqueado aguardando autorização de pagamento.
10. Produtos de R$ 100,00 e R$ 300,00, frete de R$ 40,00: compradores pagam respectivamente R$ 115,00 e R$ 345,00, incluindo serviço e frete.
11. Na etapa de pagamento, nenhuma alteração de carrinho, novo comprador ou preço de catálogo modifica pedidos congelados.
12. Com pagamento aberto em `T0`, tentativas são aceitas antes de `T0 + 24h` e recusadas a partir de `T0 + 24h`, mesmo que a tarefa agendada atrase. Durante a margem operacional não é possível comprar, alterar pedidos nem criar cobranças. A rodada aguarda `T0 + 48h` e decisão administrativa.
13. Inadimplência em uma caixa invalida a caixa inteira; compradores pagos nela recebem estorno proporcional sem realocação para outra caixa.
14. Se produtos válidos pagos mantêm o mínimo, a diferença de frete de inadimplentes fica com o administrador e não altera cobranças concluídas.
15. Se produtos válidos pagos ficam abaixo do mínimo, a rodada retorna para interesse; pagos mantêm interesses e têm estornos autorizáveis; não pagos perdem itens.
16. Novo fechamento pode começar com estorno antigo pendente, sem misturar cobranças ou duplicar estoque.
17. Webhook repetido não duplica pagamento, pedido, mensagem formal ou estorno.
18. Falta de R$ 25,00 em pedido de R$ 100,00 de produtos, R$ 5,00 de serviço e R$ 20,00 de frete gera R$ 31,25 de estorno.
19. Suspensão esvazia interesses e cancela pedidos não pagos; pedidos pagos continuam disponíveis para retirada. Reversão não restaura automaticamente interesses antigos sem regra específica.
20. Remoção bloqueia acesso e novo cadastro com o e-mail, mas mantém histórico e pedidos pagos para controle administrativo.
21. Fornecedor não consegue consultar compradores ou dados de outro fornecedor, inclusive por acesso direto à API.
22. Liberação de retirada permite nova rodada imediatamente. Retiradas antigas continuam registráveis por item.
23. Após sete dias, itens restantes aparecem como pendentes de decisão/descarte; somente ação administrativa registra descarte efetivo.
24. Falha no WhatsApp não desfaz pagamento nem impede que a notificação e o estado correto apareçam no site.
25. Pagamento iniciado antes de `T0 + 24h` e aprovado pelo provedor em `T0 + 30h` quita o pedido, mesmo que a notificação chegue depois de `T0 + 48h`, desde que identificado na apuração.
26. Pagamento aprovado depois de `T0 + 48h` não quita o pedido e gera obrigação de devolução integral, pela plataforma ou pela devolução excepcional.
27. A apuração final não começa antes de `T0 + 48h`, mesmo com todos os pedidos pagos. A partir de `T0 + 48h`, só começa com autorização do administrador.
28. O administrador não consegue prorrogar o prazo de pagamento nem a margem operacional. Continua podendo prorrogar o fechamento conforme as regras existentes.
29. O aporte inicial de R$ 1.000,00 entra na reserva e não altera a receita de serviço nem outra destinação.
30. A tarifa do provedor sobre um pagamento é registrada como despesa coberta pela receita de serviço, sem alterar obrigações com fornecedores nem valores cobrados de compradores.
31. Déficit de frete por inadimplência ou devolução é registrado separadamente (frete arrecadado, frete efetivo, déficit) e coberto pela taxa de serviço, pela reserva ou por novo aporte, sem cobrança adicional retroativa a compradores.
32. Recursos do fornecedor A nunca cobrem tarifa, déficit, prejuízo ou obrigação do fornecedor B, mesmo com saldo único no provedor. Movimentação com esse efeito é recusada.
33. Devolução devida antes do repasse é financiada pelos recursos da própria rodada. Devolução depois do repasse é coberta pela taxa de serviço, pela reserva ou por novo aporte.
34. Com reserva insuficiente, a obrigação permanece integralmente registrada e o sistema alerta. Depois de novo aporte, a devolução é concluída sem duplicidade.
35. Quando a devolução pela plataforma é comprovadamente inviável, o administrador devolve diretamente ao comprador, e a plataforma registra apenas a confirmação administrativa, com registro completo e baixa da obrigação. Até a confirmação, a obrigação permanece integral.
36. A confirmação de devolução excepcional é recusada enquanto houver devolução pendente na plataforma para a mesma parcela, e não pode ser feita duas vezes para a mesma parcela.
37. Não existe forma de registrar pagamento de comprador recebido fora da plataforma integrada.
38. A aplicação não inicia em produção com o simulador de pagamentos habilitado.
39. Pedido com dois pagamentos aceitos: apenas um quita o pedido, e o outro gera obrigação de devolução integral.
40. O repasse manual ao fornecedor continua registrável e consome apenas a obrigação com aquele fornecedor.
41. O cancelamento administrativo afeta todos os compradores da rodada. Não existe forma de cancelar a rodada para compradores selecionados.
42. Somente o administrador consegue cancelar a rodada; compradores e fornecedores são recusados, inclusive por acesso direto à API. O cancelamento é aceito sem motivo e sem informação sobre o fornecedor.
43. Cancelamento com reembolso: cada comprador que pagou recebe devolução integral (produtos, serviço e frete), descontado o que já foi devolvido ou está pendente. O total devolvido nunca ultrapassa o valor pago, e quem não pagou não recebe devolução.
44. Cancelamento sem reembolso não gera nenhuma devolução nova. Uma obrigação de devolução já existente (por exemplo, pagamento aprovado depois de `T0 + 48h`) continua pendente até ser liquidada.
45. Depois do cancelamento, pagamentos, repasses, devoluções e demais registros financeiros anteriores continuam consultáveis e inalterados.
46. Reembolsos do cancelamento usam a plataforma de pagamentos e, se ela for comprovadamente inviável, a devolução excepcional confirmada pelo administrador, sem duplicar devoluções pendentes.
47. A partir da abertura do pagamento, nenhuma tela ou rota permite a comprador ou administrador adicionar, remover ou alterar produtos ou quantidades do pedido.
48. Ocorrência de 2 unidades faltantes de um produto de R$ 10,00 em pedido de R$ 100,00 de produtos, R$ 5,00 de serviço e R$ 20,00 de frete gera reembolso pontual de R$ 20,00 + R$ 1,00 + R$ 4,00 = R$ 25,00. O pedido original continua igual, e ocorrência e reembolso ficam registrados à parte.
49. A soma das ocorrências de um item não pode ultrapassar a quantidade paga desse item. Uma ocorrência que ultrapasse é recusada.
50. O comprador não consegue registrar falta nem pedir substituição alterando o pedido.
51. Pagamento comunicado pelo provedor depois da apuração ou do cancelamento é registrado e tratado financeiramente com auditoria, sem editar o pedido.
52. Registrar uma ocorrência de entrega não cancela a rodada, e cancelar a rodada não registra ocorrências.
53. Caixa invalidada por inadimplência de B: as unidades que A pagou nessa caixa recebem estorno proporcional e voltam ao interesse com a posição original, mesmo antes da conclusão do estorno. Os itens válidos de A no ciclo não mudam.
54. O inadimplente B perde todos os itens daquele fornecedor no carrinho, inclusive reservas e posições na fila. Itens de B de outros fornecedores não são afetados.
55. A restauração processada duas vezes, ou em paralelo com novas adições, não duplica parcela, reserva ou posição. Uma parcela adicionada depois da adição original da parcela restaurada fica atrás dela.
56. Rodada que volta para interesse por insuficiência de pagamentos mantém o estoque cadastrado. Reservas de quem pagou continuam com a ordem original, e as dos inadimplentes são liberadas e ficam disponíveis. Estornos pendentes não impedem novas adições nem novo fechamento.
57. Depois do retorno ao interesse, o total reservado de cada produto nunca passa do estoque, e nenhuma reserva aparece duplicada.
58. E-mail de conta removida é recusado no login por senha, por link e pelo Google, e um novo convite para esse e-mail não permite cadastro. O histórico, inclusive financeiro, continua consultável pelo administrador.
59. O banimento vale para o mesmo endereço escrito com maiúsculas diferentes, mas não para aliases (por exemplo, com `+` ou pontos). IP, dispositivo e telefone não são bloqueados.
60. Suspensão continua reversível e não bane o e-mail.
61. Pessoa com conta de comprador e conta de fornecedor: cada login vê só as permissões e os dados da sua conta. A conta de fornecedor é recusada ao tentar comprar, inclusive pela API.
62. Conta de fornecedor só é criada por convite de fornecedor, e conta de comprador não é convertida em conta de fornecedor nem ganha esse perfil.
63. Produto por peso a R$ 12,00/kg com incremento de 0,5 kg: 1,5 kg é aceito por R$ 18,00, e 1,2 kg é recusado pelo servidor, inclusive pela API.
64. Produto por peso a R$ 12,99/kg com incremento de 0,05 kg: 0,35 kg resulta em R$ 4,5465, arredondado uma única vez para R$ 4,55 (seção 9).
65. Quantidade e preço de produto por peso ficam congelados na abertura do pagamento, sem ajuste posterior por pesagem.
66. Cadastro de produto por peso com múltiplo de compra que não seja múltiplo do incremento é recusado.
67. O fornecedor vê seus produtos, quantidades, preços unitários, valores totais dos produtos, andamento, pedido formal e previsão de entrega. Consulta ou exportação de pagamentos individuais, dados de compradores, taxa de serviço, reserva ou dados de outro fornecedor é recusada pelo servidor.
68. Envio do pedido formal falha na primeira tentativa e funciona na segunda: duas tentativas registradas, um envio, sem aviso ao administrador.
69. Três tentativas falham: não há quarta tentativa automática, o administrador é notificado e o botão **Reenviar pedido** fica disponível. O reenvio usa o mesmo pedido formal, com os mesmos produtos, quantidades e valores.
70. Duplo clique em **Reenviar pedido** gera um único envio. Um novo clique feito depois gera uma nova tentativa registrada, e nenhum dos dois cria um pedido novo.
71. Na fase de interesse, o administrador altera mínimo, múltiplo e estoque. Uma redução de estoque abaixo da quantidade reservada é recusada.
72. Do início do fechamento em diante, alterar mínimo, múltiplo ou estoque é recusado, inclusive para o administrador e pela API. Alterar preço continua permitido no fechamento e atinge os interesses (seção 5.1).
73. Quando a rodada volta para interesse, as condições voltam a ser editáveis, e os registros do ciclo anterior continuam com os valores originais.
74. Caixa invalidada por inadimplência em rodada que segue viável: as unidades pagas por A nessa caixa vão para a fila de interesses pendentes do fornecedor, sem reservar estoque da rodada apurada e antes da conclusão do estorno. O pedido congelado e os itens válidos de A não mudam.
75. Na próxima rodada em interesse, com estoque de 10 unidades e pendentes A (6 unidades, posição mais antiga) e C (8 unidades): A recebe 6 reservadas, C recebe 4 reservadas e 4 continuam pendentes sem reserva. O total reservado é 10.
76. Na mesma rodada, D adiciona 3 unidades depois da abertura, sem estoque livre: a adição é recusada ou fica limitada, conforme a seção 5. Se depois for liberado ou aumentado estoque, as 4 unidades pendentes de C são atendidas antes de qualquer nova reserva de D.
77. Unidades pendentes sem reserva não contam para o mínimo e não entram em pedido quando a rodada abre pagamento. Continuam na fila para a rodada seguinte.
78. Apuração reexecutada, ou tentativa de reserva da fila executada duas vezes ou em paralelo com novas adições, não duplica parcela, restauração ou reserva. O total reservado nunca passa do estoque, e a ordem segue a posição original.
79. O inadimplente B não tem nenhuma unidade daquele fornecedor na fila de pendentes.
80. Convite ou cadastro para um e-mail já usado por outra conta, de qualquer papel, é recusado, inclusive quando escrito com maiúsculas ou espaços diferentes (por exemplo, `  Ana@Exemplo.com ` contra `ana@exemplo.com`).
81. A mesma pessoa tem conta de comprador com `ana@exemplo.com` e conta de fornecedor com `ana.fornecedor@exemplo.com`: as duas funcionam de forma independente. Banir `ana@exemplo.com` não bloqueia `ana.fornecedor@exemplo.com`.
82. Login com Google cujo e-mail normalizado pertence a uma conta acessa somente essa conta e nunca cria uma segunda. Google com e-mail sem conta nem convite válido não cria conta.
83. Banimento de um e-mail com duas sessões abertas: as duas são invalidadas e a próxima requisição de cada uma é recusada. Novo login por qualquer método é recusado. Históricos são preservados.
84. `usuario@gmail.com` e `usuario+teste@gmail.com` podem pertencer a contas distintas. Banir um não afeta o outro.
85. Produto em litros com incremento de 0,5 L: 1,5 L é aceito e 1,2 L é recusado. Produto em unidades com incremento 1: 2 é aceito e 2,5 é recusado. Produto em kg com incremento de 0,25 kg: 0,75 kg é aceito. Todas as validações ocorrem no servidor, inclusive pela API.
86. Incremento igual a zero ou negativo é recusado no cadastro do produto.
87. Múltiplo de 1 kg com incremento de 0,25 kg é aceito, e múltiplo de 1 kg com incremento de 0,3 kg é recusado. Na fase de interesse, uma alteração que torne o múltiplo incompatível (por exemplo, 0,9 kg com incremento de 0,25 kg) é recusada. A partir do fechamento, qualquer alteração de múltiplo é recusada (seção 4.4).
88. R$ 7,99/kg × 0,25 kg = R$ 1,9975, e o subtotal cobrado é R$ 2,00.
89. Meio centavo: R$ 2,50/kg × 0,25 kg = R$ 0,625, arredondado para R$ 0,63. Dois itens de R$ 0,625 cada somam `P` = R$ 1,26 (soma dos subtotais arredondados), não R$ 1,25.
90. Depois de cobrar R$ 2,00 por 0,25 kg a R$ 7,99/kg, o preço do produto muda para R$ 8,99/kg. Uma ocorrência da quantidade inteira desse item reembolsa R$ 2,00 de produtos, mais serviço e frete proporcionais sobre os valores registrados, sem recalcular com o preço atual.
91. A devolução integral de um cancelamento com reembolso soma exatamente os valores cobrados registrados (produtos, serviço e frete), descontadas as devoluções já concluídas ou pendentes.
92. Depois de um envio bem-sucedido do pedido formal, o botão **Reenviar pedido** está disponível. O acionamento gera uma única tentativa, com o mesmo pedido formal e o mesmo conteúdo, sem tentativas automáticas adicionais.
93. Reenvio manual que falha: a falha é registrada, nenhuma tentativa automática é iniciada e o botão continua disponível.
94. Enquanto o ciclo automático não termina (depois da primeira falha e antes da terceira), o reenvio manual é recusado.
95. Dois acionamentos concorrentes da mesma solicitação de reenvio geram um único envio. Dois acionamentos distintos geram duas tentativas registradas. Em nenhum caso há segundo pedido formal ou mudança no conteúdo original.
96. Comprador A tem 6 unidades reservadas e 4 pendentes de um produto. O carrinho e o histórico mostram separadamente "reservado: 6" e "pendente: 4", inclusive quando o estoque do produto está zerado.
97. A remove 2 das 4 unidades pendentes: a pendência cai para 2, e as reservas de A e de outros compradores, as posições FIFO de outras parcelas e o reembolso já devido a A não mudam. Ao remover as 2 restantes, a pendência zera e a parcela sai da fila.
98. Remoção de quantidade pendente maior que a existente, ou fora do incremento do produto, é recusada sem alteração.
99. Tentativa de usar a remoção de pendentes sobre item de pedido congelado (por exemplo, enviando o identificador do item do pedido) é recusada pelo servidor. Pedido e registros financeiros não mudam.
100. Remoção de pendentes em paralelo com a alocação da fila: ao final, reservado + pendente nunca passa da quantidade original da parcela, nenhuma reserva passa do estoque, e a quantidade removida nunca vira reserva.
101. D remove 3 unidades reservadas e há pendente de C com 4 unidades: C recebe as 3 antes de qualquer nova reserva. Um interesse novo de E feito ao mesmo tempo recebe só o que sobrar.
102. Pendentes do fornecedor X nunca são alocados em rodada do fornecedor Y.
103. Rodada que volta para interesse por insuficiência de pagamentos: as reservas dos adimplentes ficam na própria rodada e não passam pela fila de pendentes.
104. Produto de R$ 10,00, mínimo de R$ 100,00, A com 8 unidades reservadas e C com 5 pendentes sem reserva: o progresso elegível é R$ 80,00, e o fechamento não pode ser iniciado por causa das pendentes de C. Se a rodada chegar ao pagamento, as pendentes de C não entram em pedido nem cobrança e continuam na fila.
105. Na fase de interesse, produto com incremento de 0,5 kg, parcelas reservadas de 1,0 kg e 1,5 kg, pendente de 2,0 kg e múltiplo de 3 kg: a alteração do incremento para 0,25 kg é aceita, e nenhum interesse muda.
106. No mesmo produto, a alteração para 1 kg é recusada (1,5 kg reservado deixa de ser múltiplo), e a alteração para 2 kg é recusada (o múltiplo de 3 kg não é divisível por 2). Em ambos os casos, nada é alterado.
107. A partir do início do fechamento, qualquer alteração de incremento é recusada, inclusive para o administrador e pela API. A alteração de preço continua permitida (seção 5.1).
108. Alteração de incremento em paralelo com uma adição de interesse no mesmo produto: ou a adição é validada contra o novo incremento, ou a alteração é recusada por incompatibilidade. Nunca fica parcela fora do incremento vigente.
109. Ovos (unidade, incremento 1): 12 é aceito e 12,5 é recusado. Maçãs (unidade, incremento 2): 4 é aceito e 3 é recusado. Banana (kg, 0,25): 1,25 é aceito. Leite (litro, 0,5): 2,5 é aceito. Caixa de produtos (caixa, 1): 3 é aceito e 1,5 é recusado.
110. Incrementos 0, -1 e 0,0001 são recusados. Incrementos 0,001 e 2 são aceitos.
111. Maçãs com incremento 2 e múltiplo 12 são aceitas. Com múltiplo 5, a configuração é recusada.
112. Item de 1,000 kg a R$ 7,99/kg, com subtotal registrado de R$ 7,99. Ocorrência de 0,25 kg: o reembolso de produtos é R$ 7,99 × 0,25 = R$ 1,9975, arredondado para R$ 2,00. Uma mudança posterior do preço do produto para R$ 9,99/kg não altera o valor.
113. No mesmo item, três ocorrências de 0,25 kg reembolsam R$ 2,00 cada. A quarta, que completa a quantidade, reembolsa R$ 1,99 (R$ 7,99 − R$ 6,00). A soma é exatamente R$ 7,99.
114. Depois de uma ocorrência parcial de R$ 2,00 no item de R$ 7,99, o cancelamento da rodada com reembolso devolve, para esse item, exatamente o saldo de R$ 5,99.
115. Item de 0,6 kg a R$ 0,15/kg, subtotal de R$ 0,09 e incremento de 0,1 kg. Cada ocorrência de 0,1 kg calcula R$ 0,015, arredondado para R$ 0,02. A quinta é limitada a R$ 0,01, o saldo restante, e a sexta reembolsa R$ 0,00. A soma nunca passa de R$ 0,09, e uma ocorrência acima da quantidade paga é recusada.
116. Pedido com R$ 100,00 de produtos, R$ 5,00 de serviço e R$ 20,00 de frete: um reembolso parcial de R$ 2,00 de produtos devolve também R$ 0,10 de serviço e R$ 0,40 de frete, e o acumulado de cada componente nunca passa do valor registrado.
117. Cada reembolso parcial é registrado separadamente, com item, quantidade e valores. O pedido congelado continua com a composição original.
118. Uma tentativa automática em execução e um acionamento manual simultâneo: o manual é recusado e nenhuma tentativa a mais é feita.
119. Depois de concluído o ciclo automático, dois acionamentos manuais com solicitações distintas feitos ao mesmo tempo são executados um depois do outro, nunca ao mesmo tempo, cada um com uma única tentativa registrada.

## 17. Pontos a validar antes de implementar comportamentos ambíguos

### Decisões aprovadas após a auditoria da infraestrutura

| ID | Decisão | Seções |
|---|---|---|
| A1 | Aporte inicial de R$ 1.000,00 de capital próprio, que não é receita. Livro-razão segregado. Reserva sem limite de responsabilidade. | 9.3, 9.4 |
| A2 | 24h para pagar. Margem operacional de 24h. Apuração a partir de `T0 + 48h`, com autorização. | 7, 8.2 |
| A3 | Pagamentos só pela plataforma integrada. Simulador na primeira fase, nunca em produção. Repasse manual permitido. | 1, 8.1, 10, 15 |
| P-1 | Tarifas cobertas pela receita de serviço. Déficit de frete do administrador. Sem cobrança retroativa. | 9, 9.3 |
| P-2 | Recursos de fornecedor exclusivos. Movimentações explícitas e auditáveis. | 9.3, 10 |
| P-3 | Usos permitidos da reserva, sem comprometer obrigações existentes. | 9.4 |
| P-4 | Sem recomposição automática. Novos aportes conforme necessidade. Alertas de insuficiência. | 9.4 |
| P-5 | Devolução excepcional por Pix ou transferência, só quando a plataforma for comprovadamente inviável. | 9.2, 9.5 |
| P-6 | Aceitação pelo horário de aprovação até `T0 + 48h`. Devolução depois disso. | 8.3 |
| P-7 | Prazo de pagamento improrrogável, inclusive pelo administrador. | 7 |
| P-8 | Apuração nunca antecipada. | 7, 8.2 |
| 17.2 | Cancelamento da rodada inteira, só pelo administrador, sem motivo obrigatório, com ou sem reembolso integral. Obrigações existentes preservadas. | 7, 7.2, 12 |
| 17.3 | Pedido congelado imutável. Ocorrências de entrega com reembolso pontual, registradas à parte. Pagamentos tardios sem edição do pedido. | 5, 7.1, 8.3, 10 |
| 17.4 | Unidades pagas em caixa invalidada voltam automaticamente ao interesse, com prioridade original. Inadimplentes perdem os itens daquele fornecedor. | 5, 8.2 |
| 17.5 | No retorno ao interesse, estoque inalterado, reservas de quem pagou preservadas e dos inadimplentes liberadas. Estornos pendentes não bloqueiam. | 8.2 |
| 17.6 | Banimento exclusivamente por e-mail, para login e cadastro. Suspensão continua reversível. | 2, 3.1 |
| 17.7 | Contas de comprador e fornecedor independentes, ambas por convite. Fornecedor não compra. | 2, 3.1, 13 |
| 17.8 | Unidade por produto, incremento mínimo para produtos por peso, decimal exato, sem ajuste por pesagem. Estendido a qualquer unidade por Q-4. | 4.2, 5 |
| 17.9 | Fornecedor vê produtos, quantidades, preços unitários, totais, andamento, pedido formal e previsão. Nada além disso. | 2, 6.2, 13 |
| 17.10 | Até três tentativas automáticas de envio do pedido formal, depois aviso ao administrador e **Reenviar pedido** com o mesmo pedido. | 10, 12, 13 |
| 17.11 | Mínimo, múltiplos e estoque alteráveis só na fase de interesse. Preços seguem a seção 5.1. | 4.1, 4.2, 4.4, 5.1 |
| Q-1 | Fila de interesses pendentes do fornecedor para unidades de caixa invalidada, com FIFO original e reserva só quando houver estoque na rodada seguinte. | 5.2, 8.2 |
| Q-2 | E-mail exclusivo por conta, inclusive no login com Google. Banimento só do endereço banido. | 2, 3 |
| Q-3 | Reenvio do pedido formal também depois de envio bem-sucedido, com o mesmo pedido. | 10, 13 |
| Q-4 | Quantidades fracionárias em qualquer unidade, com incremento por produto. | 4.2, 5 |
| R-1 | Subtotal por item arredondado uma vez com `ROUND_HALF_UP`, total como soma dos subtotais, reembolsos pelos valores registrados. | 9, 9.2 |
| R-2 | Múltiplo divisível exatamente pelo incremento, validado no cadastro e nas alterações. | 4.2, 4.4 |
| R-3 | Normalização de e-mail (maiúsculas, espaços, sem aliases) em todos os fluxos. Sessões invalidadas no banimento. | 2, 3 |
| R-4 | Até três tentativas automáticas, reenvio manual de uma tentativa por acionamento, disponível depois de falha ou sucesso. | 10, 12, 13 |
| Q-5 | Comprador vê reservado e pendente separados e pode remover pendentes, parcial ou totalmente, sem afetar pedidos congelados, reservas, FIFO ou reembolsos. | 2, 5.2, 13 |
| Q-6 | Incremento alterável só na fase de interesse e só se compatível com todas as quantidades reservadas e pendentes e com o múltiplo. Caso contrário, rejeição integral. | 4.2, 4.4 |
| Q-7 | Reembolso parcial proporcional ao subtotal registrado, `ROUND_HALF_UP`, acumulado por item sem passar do subtotal, e devolução integral exata. | 9.2 |
| R-5 | Pendentes atendidos antes de novas reservas, pela FIFO original, isolados por fornecedor. A fila vale para rodada viável, e 17.5 vale no retorno ao interesse. | 5.2 |
| R-6 | Pendentes sem reserva fora do mínimo, dos pedidos e das cobranças. | 5.2, 6 |
| R-7 | Reenvio manual bloqueado durante o ciclo automático e liberado depois, inclusive após sucesso. | 10 |
| R-8 | Incremento por produto, inteiro ou fracionário, maior que zero, até três casas decimais, sem fracionamento obrigatório. | 4.2 |
| Q-8 | Contestação ou devolução forçada do Pix (MED): fornecedor recebe integralmente, inclusive antes do repasse; perda coberta pela receita de serviço da rodada, depois pela reserva e por novo aporte; comprador suspenso para análise, sem banimento automático. | 2, 9.3, 9.6 |

### Pontos ainda a validar

Estes pontos não impedem pesquisa de infraestrutura, mas precisam de solução explícita antes do lançamento:

1. **Confirmações financeiras tardias:** resolvido por A2 e P-6 (seção 8.3). Permanece apenas a validação técnica do comportamento do provedor (documento de infraestrutura, seção 9.2), sem alterar a regra de negócio.
2. **Cancelamento administrativo após pagamento:** resolvido (seção 7.2).
3. **Correções administrativas de pedidos congelados:** resolvido. Pedidos congelados são imutáveis, e problemas de entrega são tratados como ocorrências com reembolso pontual (seções 7.1 e 10).
4. **Caixa inválida com rodada ainda viável:** resolvido (seções 5.2 e 8.2).
5. **Estorno e estoque no retorno ao interesse:** resolvido (seções 4.4 e 8.2).
6. **Escopo de banimento:** resolvido (seções 2 e 3.1).
7. **Fornecedor e identidade:** resolvido (seção 2).
8. **Unidades e precisão:** resolvido (seções 4.2, 4.4 e 9).
9. **Dados exibidos ao fornecedor:** resolvido (seções 2, 6.2 e 13).
10. **E-mail formal:** resolvido (seção 10).
11. **Mudanças de configuração durante rodada:** resolvido (seção 4.4).
12. **Taxas e saldo para estornos:** a cobertura de tarifas e de diferenças de frete está resolvida por P-1 a P-4 (seções 9.3 e 9.4). Permanece como validação técnica: se o provedor devolve suas tarifas, exige saldo disponível e permite estornos parciais nos meios escolhidos.

### Questões de implementação

Q-1 a Q-8 estão resolvidas (tabela de decisões acima). Não há questão de implementação aberta nesta versão.

## 18. Entrega esperada da pesquisa de infraestrutura

O agente independente deve usar esta especificação como contrato funcional e produzir:

1. Arquitetura recomendada e alternativas proporcionais à escala inicial.
2. Escolha justificada de autenticação, banco, hospedagem, tarefas agendadas, armazenamento, e-mail, WhatsApp e pagamentos.
3. Matriz entre capacidades dos provedores e requisitos críticos, incluindo pagamentos tardios, estornos parciais e consentimento de mensagens.
4. Modelo de dados e transições que separe rodadas, ciclos financeiros, caixas e retiradas.
5. Estimativa de custos fixos e variáveis com premissas de volume explícitas.
6. Estratégia de segurança, observabilidade, backups, recuperação e implantação.
7. Plano de implementação e testes dos cenários de aceitação, com riscos e decisões pendentes destacados.

Não transformar suposições de provedores em regras de negócio nem reduzir o escopo de produção a uma demonstração visual. Recursos fora do escopo inicial incluem cadastro público, convites enviados por compradores, gestão de catálogo pelo fornecedor, repasse automático ao produtor, substituições e redistribuição de caixas após início do pagamento.
