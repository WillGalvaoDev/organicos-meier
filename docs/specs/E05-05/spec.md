# E05-05 — Carrinho e formulários de interesse

Fatia 5 de 7 da milestone **E05 — Interesses, reservas e progresso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

Esta fatia dá ao comprador as telas sobre os serviços da E05-01 a E05-04:

- o carrinho, agrupado por fornecedor, com reservas e pendências separadas, totais, progresso e caixas;
- o formulário de quantidade no catálogo e no carrinho;
- a remoção de pendentes.

Toda regra fica nos serviços. As rotas só convertem a entrada, chamam o serviço e escolhem a resposta.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | Comprador ativo gerencia interesses e vê reservado e pendente separados. Suspenso consulta listas e não adiciona interesses. Restrições verificadas no servidor, inclusive em chamadas diretas. |
| Especificação §5 | O carrinho agrega fornecedores diferentes, mas separa visualmente rodadas, etapas, prazos e totais. Itens no carrinho são interesse, não compra paga. O excedente de estoque é recusado claramente, sem sucesso falso. |
| Especificação §5.2 | O comprador vê reservado e pendente separados, inclusive sem estoque, e pode remover pendentes. |
| Especificação §6.2 | Comprador vê seu pedido, o progresso agregado do fornecedor e, em produtos com múltiplo, o total agregado, as caixas completas, as unidades faltantes, as suas unidades em caixas e as suas excedentes. Sem nomes nem pedidos de outros compradores. |
| Especificação §13 | Carrinho agrupado por rodada, com reservas, excedentes, etapas e prazos. Reservado e pendente separados, e pendentes removíveis. Catálogo com progresso monetário elegível. |
| Cenários §16 | 96 (tela), 99 (pela rota), 63, 85 e 109 (pela rota). |
| Infraestrutura 4.10 | A consulta do carrinho devolve reservado e pendente em campos separados, por parcela e por produto, inclusive com estoque zero. Cada comprador vê só as próprias parcelas. |
| Infraestrutura 8 | T-25 (rotas de carrinho recusadas à conta de fornecedor), T-42. |
| E02-10 | Políticas `comprador` e `comprador_ativo`, com a varredura de rotas. |
| E03-03 D-1 | "Produto indisponível" explícito junto à descrição, também no carrinho. |
| E03-08 | Catálogo do comprador em `/catalogo/` e `/catalogo/<id do fornecedor>/`. |
| E05-01 a E05-04 | Serviços, fila, remoção de pendentes e progresso. |

## Escopo

**Dentro:**

- A rota `GET /carrinho/` e o link "Carrinho" na navegação dos compradores.
- As rotas `POST /interesses/` e `POST /interesses/pendentes/remover/`.
- O bloco de interesse e de progresso na página do fornecedor no catálogo.

**Fora:**

- O prazo do fechamento no carrinho. A rodada ainda não tem prazo, e a E06 acrescenta o prazo ao grupo.
- O pedido congelado e o pagamento (E08).
- O endereço de retirada no carrinho (§11, E14).
- O portal do fornecedor (E13).

## Decisões técnicas

- **Quantidade desejada:** o formulário envia o total reservado desejado do produto, e a rota chama `definir_interesse` (E05-01). O botão "Remover" envia `quantidade=0`. Reenviar o mesmo formulário não cria parcela nova. Com pendência própria, valem também os campos de estado da correção E05-R02, no fim desta spec.
- **Agrupamento por fornecedor:**
  - a parcela não tem vínculo com a rodada (E05-01), e um fornecedor tem no máximo uma rodada ativa;
  - cada grupo mostra a rodada ativa do fornecedor, quando ela existe;
  - pendentes de um fornecedor sem rodada ativa aparecem num grupo com "Sem rodada ativa.".
- **Respostas** (lição das correções E03-R03, R04 e R05):
  - toda página de erro é montada com o estado relido do banco depois da transação do serviço;
  - um 409 nunca oferece formulário para o produto recusado;
  - o texto recusado volta só no formulário do produto enviado;
  - ids só são usados depois de validados pelo formulário.
- **Sem HTMX obrigatório.** As rotas respondem com página inteira ou redirecionamento.
- **Progresso em percentual.** A E03-08 classificou o mínimo do fornecedor como campo nunca exibido ao comprador, e o teste dela verifica isso. Mostrar o valor elegível e o mínimo em reais, ou o valor elegível junto com o percentual, revelaria o mínimo. O comprador vê o progresso do mínimo em percentual e o aviso "Mínimo atingido.". Isso cumpre a §6.2 ("progresso agregado do fornecedor") e a §13 ("progresso monetário elegível"), porque o percentual é calculado sobre o valor monetário elegível. Os valores em reais ficam com o administrador (E05-04).

**Formato dos textos:** `R$ <valor>` indica o resultado do filtro `reais`, que já inclui o prefixo `R$ ` (E05-04).

## Relação com a E03-08

A E03-08 entregou o catálogo só de leitura e deixou para a E05 os controles, o progresso e as caixas. Três frases da spec dela mudam de alcance com esta fatia, e a mudança vem de requisitos de precedência maior:

| E03-08 | A partir desta fatia | Fundamento |
|---|---|---|
| "quantidades reservadas e pendentes individuais" nunca exibidas | as do **próprio** comprador da sessão são exibidas; as de outros compradores continuam nunca exibidas | §5.2 e §13: o comprador vê separadamente o reservado e o pendente dele |
| "O total reservado não é exibido, só o estoque livre." | em produto **com múltiplo**, o total agregado é exibido; sem múltiplo, continua não exibido | §6.2: em produtos com múltiplo, o comprador vê o total agregado em interesse |
| mínimo do fornecedor nunca exibido | **sem mudança**: o comprador vê só o percentual | E03-08 |

**Ajustes autorizados nos testes da E03-08** (`tests/tecnicos/test_catalogo_comprador.py`). Registre os dois no `review.md`, com esta seção como justificativa:

1. Em `test_campos_internos_e_dados_de_compradores_nao_aparecem` (E03-08 A-9), as duas asserções `"reservad" not in html.lower()` e `"pendente" not in html.lower()` são substituídas.
   - O teste passa a exigir que a página contenha "Seu interesse: reservado 0, pendente 0", porque o comprador da sessão não tem parcelas.
   - Também passa a exigir que ela não contenha "reservado 2" nem "pendente 1", que são as quantidades de Ana e Bia no teste.
   - Todas as outras asserções continuam iguais, inclusive as do mínimo (`987,65` e `987.65`) e as de nomes e e-mails.
2. Em `test_numero_de_consultas_nao_cresce_com_os_produtos` (E03-08 A-10), o teto de 8 consultas pode subir para um novo valor fixo. Esse valor é medido com o bloco de interesse e progresso desta fatia e com o comprador da sessão tendo uma parcela em cada produto.
   - A propriedade não muda: o mesmo teto vale com 1 e com 20 produtos.
   - O novo valor e a medição ficam registrados no `review.md`.

Nenhum outro teste existente pode ser alterado por esta fatia.

## Regras

**Carrinho** (`GET /carrinho/`, política `comprador`):

- **Grupos:** só aparecem as parcelas do comprador da sessão com situação `ativa` ou `pendente`. Os grupos são por fornecedor, em ordem de nome e id.
- **Cabeçalho de cada grupo:**
  - o nome do fornecedor;
  - com rodada ativa:
    - "Etapa: <rótulo da etapa>";
    - "Progresso do mínimo: <percentual>%" e, quando `atingido` é verdadeiro, "Mínimo atingido.". Os dados vêm de `progresso_da_rodada(rodada, comprador)` (E05-04). O mínimo, o valor elegível e o que falta, em reais, nunca aparecem para o comprador (ver "Relação com a E03-08");
  - sem rodada ativa: "Sem rodada ativa.".
- **Linhas:** uma por produto em que o comprador tem reservado ou pendente maior que zero, em ordem de nome. Cada linha mostra:
  - o nome do produto e, quando `disponivel` é falso, "Produto indisponível" junto ao nome;
  - o preço e a unidade;
  - "Reservado: <x>" e "Pendente: <y>", sempre os dois, mesmo com zero, e mesmo quando o estoque está zerado (cenário 96);
  - "Subtotal: R$ <subtotal do reservado>", calculado com o preço vigente;
  - em produto com múltiplo e com rodada ativa:
    - "Total agregado: <total reservado de todos os compradores>";
    - "Caixas completas: <n>";
    - "Faltam <f> para a próxima caixa";
    - "Suas unidades em caixas: <a>";
    - "Suas unidades excedentes: <b>".
- **Formulários de cada linha:**
  - **Quantidade:** um formulário `POST /interesses/` com `produto`, `quantidade` (preenchida com o reservado atual) e `origem=carrinho`, e os botões "Atualizar" e "Remover" (`quantidade=0`). Ele só aparece quando `interesses_editaveis(fornecedor)` é verdadeiro, o produto está no estoque da rodada ativa e a conta é `ativa`.
  - **Pendentes:** com pendente maior que zero e conta `ativa`, um formulário `POST /interesses/pendentes/remover/` com `produto` e `quantidade`, e o botão "Remover pendentes". Ele aparece em qualquer etapa.
- **Rodapé do grupo:** "Total reservado: R$ <soma dos subtotais das linhas>". Esse valor é o interesse com o preço vigente. Não é um valor de cobrança: não inclui taxa nem frete.
- **Carrinho vazio:** "Seu carrinho está vazio." e um link para `/catalogo/`.
- **Aviso:** "Os itens do carrinho são interesses, não compras pagas." (§5).

**Catálogo do fornecedor** (`GET /catalogo/<id>/`, E03-08, política `comprador`):

- No topo, a mesma linha de progresso do cabeçalho do carrinho.
- Em cada produto, para o comprador da sessão:
  - "Seu interesse: reservado <x>, pendente <y>";
  - com múltiplo, as mesmas linhas de caixa do carrinho;
  - quando a conta é `ativa` e `interesses_editaveis`, o formulário de quantidade com `origem=catalogo`, o botão "Atualizar interesse" e o campo preenchido com o reservado atual.
- Conta suspensa: nenhum formulário.

**`POST /interesses/`** (política `comprador_ativo`):

- **Formulário:**
  - `produto`: `IntegerField(min_value=1, max_value=9223372036854775807)`;
  - `quantidade`: `CharField(max_length=30)`, convertido só pelo serviço;
  - `origem`: `carrinho` ou `catalogo`, e qualquer outro valor vale como `carrinho`.
- Qualquer outro campo é ignorado, inclusive ids de parcela ou de item de pedido (cenário 99).
- **Respostas:**

| Situação | Resposta |
|---|---|
| sucesso | 302 para `/carrinho/` ou para `/catalogo/<fornecedor do produto>/`, conforme `origem`, com a mensagem "Interesse atualizado: <produto>, reservado <x>." |
| `produto` inválido no formulário | 200 com a página de origem e "Produto inválido." no topo, sem valor preservado |
| produto inexistente | 404 |
| `QuantidadeInvalida`, `EstoqueInsuficiente` ou `ReducaoAcimaDoReservado` | 200 com a página de origem; dentro do `<form>` desse produto, o texto enviado no `value` (escapado) e a mensagem do serviço; os outros formulários com os valores do banco |
| `InteressesBloqueados` ou `ProdutoForaDaRodada` | 409 com a página de origem, a mensagem do serviço no topo e o estado relido, sem formulário de quantidade para esse produto |
| `PermissionDenied` do serviço (conta suspensa entre a política e a trava) | 403 |

- **Página de origem:** quando `origem=catalogo` e o fornecedor não tem mais rodada ativa, a página de origem passa a ser o carrinho.

**`POST /interesses/pendentes/remover/`** (política `comprador_ativo`):

- Usa o mesmo formulário, sem `origem`, e chama `remover_pendente` (E05-03).
- Em caso de sucesso, responde 302 para `/carrinho/` com a mensagem "Pendência removida: <produto>, pendente <y>.".
- `QuantidadeInvalida` e `RemocaoAcimaDoPendente` seguem a linha de 200 da tabela, com o texto e a mensagem no formulário de pendentes do produto.
- Os demais casos seguem a tabela.

**Navegação:** `base.html` mostra o link "Carrinho" (`/carrinho/`) para contas de papel comprador.

**Consultas:** o número de consultas do carrinho não depende do número de produtos nem de parcelas. Ele pode crescer uma quantidade fixa por fornecedor do carrinho.

## Interfaces

- `apps/interesses/views.py`: `carrinho`, `definir` e `remover_pendentes`.
- `apps/interesses/forms.py`.
- `config/urls.py`: rotas `carrinho`, `interesses_definir` e `interesses_remover_pendentes`.
- `apps/interesses/consultas.py`: `carrinho_do_comprador(comprador)`, que monta os grupos.
- Templates `templates/interesses/carrinho.html` e o bloco do produto no catálogo.

## Invariantes

- Nenhuma página mostra nome, e-mail ou quantidade individual de outro comprador.
- Nenhuma página do comprador mostra o mínimo do fornecedor, o valor elegível nem o que falta em reais.
- Toda alteração passa por `definir_interesse` ou `remover_pendente`.
- Nenhuma resposta 409 por `InteressesBloqueados` ou `ProdutoForaDaRodada` tem formulário de quantidade para o produto recusado. O 409 por `InteresseDesatualizado` (correção E05-R02) mostra o formulário com os valores atuais.

## Casos-limite e concorrência

- **Cenário 96:** A tem 6 reservados e 4 pendentes, com o estoque do produto zerado. O carrinho mostra "Reservado: 6" e "Pendente: 4".
- **Duplo envio:** o mesmo `POST /interesses/` com `quantidade=6`, duas vezes, cria uma parcela só.
- **Etapa mudou entre a página e o envio:** a rodada passa a `fechamento_encerrado`. O envio responde 409, sem formulário de quantidade, e mostra "Etapa: Fechamento com prazo encerrado".
- **Conta de fornecedor ou administrador** chamando as rotas: recusada pela política (T-25).
- **Visitante anônimo:** redirecionado para `/entrar/`.
- **`quantidade` com `"><b>x</b>`:** aparece escapada no `value`.

## Correção E05-R02 — formulários com pendência própria (2026-10-18)

O diagnóstico e a decisão estão na correção E05-R02 da E05-01. Esta seção define o que muda nas rotas e nas telas. O revisor reproduziu o defeito pelas duas origens: um `POST /interesses/` com `quantidade=0`, de A com 6 reservados e 4 pendentes, responde 302 e deixa 4 reservados.

**Campos novos** nos dois formulários (quantidade e pendentes), no carrinho e no catálogo:

- `reservado_atual` e `pendente_atual`, ocultos (`type="hidden"`);
- preenchidos com o `ResumoDoInteresse` do comprador no produto, lido para montar a página, no formato de `formatar_quantidade`.

**Conversão na rota** (`FormularioInteresse`):

- Os dois campos são `CharField(max_length=30, required=False)` e são convertidos por `quantidade()`, que aceita vírgula.
- Os dois ausentes ou vazios: `esperado=None`. É o caso de clientes que não são a página.
- Os dois presentes, cada um convertível e maior ou igual a zero: `esperado=ResumoDoInteresse(reservado, pendente)`.
- Qualquer outro caso, como só um dos dois, texto inválido ou negativo, tem a mesma resposta de `InteresseDesatualizado`. O serviço não é chamado.

**Chamadas:** `definir_interesse(conta, produto, valor, esperado=esperado)` e `remover_pendente(conta, produto, valor, esperado=esperado)`.

**Respostas:**

| Situação | Resposta |
|---|---|
| `InteresseDesatualizado`, ou campos de estado inválidos | 409 com a página de origem relida. A mensagem do serviço fica dentro do `<form>` do produto, que aparece com os valores atuais do banco: `quantidade`, `reservado_atual` e `pendente_atual`. Nada é gravado. |
| sucesso de `definir_interesse` | 302, como antes, com a mensagem montada pelas três regras abaixo |

Mensagem de sucesso de `definir_interesse`:

- com pendente final zero: "Interesse atualizado: <produto>, reservado <x>.", sem mudança;
- com pendente final maior que zero: "Interesse atualizado: <produto>, reservado <x>, pendente <y>.";
- com `total > 0` e reservado final diferente de `total`, a frase " As pendências da fila, inclusive as suas, são atendidas primeiro." é acrescentada ao final.

A mensagem de `remover_pendente` não muda.

**Botão "Remover"** (`quantidade=0`): pela correção E05-R02, remove o item inteiro, com as pendências e o reservado do comprador no produto. O texto do botão continua "Remover".

**Testes existentes:** nenhum precisa mudar. Os envios sem os campos novos caem em `esperado=None`, e os critérios A-1 a A-20 continuam valendo. No A-6, o reenvio com o total já atingido continua não gravando nada.

## Dependências e decisões em aberto

- Depende de E05-01 a E05-04 e de E03-08.
- Sem decisões em aberto.
