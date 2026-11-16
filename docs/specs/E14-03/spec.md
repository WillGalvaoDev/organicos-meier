# E14-03 — O endereço de retirada, o carrinho e a página de regras

Fatia 3 de 8 da milestone **E14 — Recebimento, ocorrências, retirada e descarte**. Agente 1 (especificador).

## Versões dos documentos-base

Como na E14-01: especificação v1.7, infraestrutura v1.8. Gate de especificação: como na E14-01.

## Contexto e objetivo

Os compradores retiram os produtos no endereço do administrador (§1). O endereço fica disponível no carrinho e nas regras de funcionamento do site, só na área autenticada (§11).

Hoje o sistema não guarda nenhum endereço; a E05-05 deixou o endereço no carrinho para a E14. O aviso de liberação (E14-04) precisa dele (§12: "Endereço, disponibilidade e limite de sete dias").

Esta fatia cria o registro do endereço, a página do administrador para mantê-lo, o endereço no carrinho e a página de regras com a seção de retirada.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §1 | O administrador recebe os produtos em casa; os compradores retiram nesse endereço. |
| Especificação §11 | Endereço no carrinho e nas regras de funcionamento do site; exposição fora da área autenticada não foi solicitada. Retirada normalmente disponível, salvo avisos de restrição publicados pelo administrador. Prazo de sete dias a partir da liberação; depois, descarte manual. |
| Especificação §13, comprador | Notificações, regras, endereço e comunicados. |
| Especificação §10 | Não há substituição de produtos; faltas são ocorrências registradas pelo administrador. |
| Especificação §2 | O fornecedor consulta só os dados da lista da §2 (17.9). |
| Herdado da E05 | O endereço de retirada no carrinho, no grupo de cada fornecedor (E05-05). |

## Escopo

**Dentro:**
- O modelo `EnderecoDeRetirada` e o serviço `definir_endereco_de_retirada`.
- A página `administracao/retirada/endereco/`.
- O endereço no carrinho e a página `regras/`, com o link na página inicial.

**Fora:**
- As demais seções de regras do site (pagamento, prazos de cobrança etc.), que nenhuma etapa especificou até aqui. O herdado para a E16 é conferir na homologação se o §13 pede mais seções.
- Os avisos de restrição: são os comunicados que já existem (E04).

## Modelo

**`EnderecoDeRetirada`** (só inserção, app `pedidos`):
- `texto`: até 500 caracteres, sem espaços no começo e no fim, com quebras de linha permitidas;
- `autor`: o administrador;
- `registrado_em`.

O endereço vigente é o de maior `pk`. Não há endereço vigente enquanto nenhum foi registrado.

## Regras

`definir_endereco_de_retirada(autor, texto) -> EnderecoDeRetirada`:

1. **Permissão:** só o administrador ativo; senão `PermissionDenied`, sem escrita.
2. **Validação:**
   - o texto é normalizado: sem espaços no começo e no fim e com `\r\n` trocado por `\n`;
   - vazio ou com mais de 500 caracteres: `EnderecoRecusado("texto_invalido")`, "Informe o endereço de retirada, com até 500 caracteres.";
   - igual ao vigente: `EnderecoRecusado("sem_alteracao")`, "O endereço informado é igual ao atual.".
3. **Gravação:** um registro novo; os anteriores ficam como histórico. Auditoria `retirada.definir_endereco`, com o texto anterior e o novo.
4. **Efeito:** o endereço vigente vale para o carrinho, para as regras e para as liberações seguintes. A liberação guarda o endereço vigente no momento dela (E14-04), então trocar o endereço depois não muda os avisos já emitidos.

**Página do administrador** `GET`/`POST administracao/retirada/endereco/` (nome `retirada_endereco`), com `somente_administrador`:

5. **GET:** o endereço vigente (ou "Nenhum endereço registrado."), o formulário com o texto atual e o histórico (data e hora em Brasília, autor, texto), do mais recente para o mais antigo.
6. **POST:**
   - sucesso: 302 para a página, com "Endereço de retirada atualizado.";
   - recusa: 400 com a mensagem da regra 2 e o formulário preenchido.

**Carrinho** (`carrinho/`, E05-05):

7. **Endereço:** em cada grupo de fornecedor, a linha "Retirada: <endereço vigente>", com as quebras de linha preservadas. Sem endereço: "Retirada: endereço ainda não informado.".

**Regras** `GET regras/` (nome `regras`):

8. **Acesso:** comprador ativo ou suspenso e administrador. O fornecedor recebe 403, porque o endereço e as regras de retirada não estão na lista da §2. O anônimo vai para o login.
9. **Conteúdo** da seção "Retirada":
   - "Endereço: <endereço vigente>" (ou "Endereço ainda não informado.");
   - "A retirada fica normalmente disponível. Restrições de dia ou horário são publicadas nos comunicados.", com o link para `comunicados/`;
   - "Você é avisado quando a retirada de um pedido é liberada. A partir da liberação, o prazo para retirar é de sete dias. Depois desse prazo, o administrador pode registrar o descarte dos itens não retirados.";
   - "Itens faltantes, incorretos ou não entregues são registrados pelo administrador como ocorrências de entrega, com o reembolso dos itens afetados. Não há substituição de produtos.".
10. **Link:** a página inicial (`inicio/`) do comprador e do administrador mostra "Regras e retirada" (para `regras/`).

## Interface

- `definir_endereco_de_retirada(autor, texto) -> EnderecoDeRetirada` e `class EnderecoRecusado(Exception)` com `codigo`.
- `endereco_vigente() -> EnderecoDeRetirada | None`.
- As rotas `retirada_endereco` e `regras`.

## Decisões técnicas

- **Um endereço só, mantido pelo administrador.** Há um único administrador, que recebe os produtos em casa (§1). O endereço é dado de operação: mudá-lo não deve exigir implantação. Como registro só de inserção, preserva o que cada liberação informou.
- **A página de regras começa pela retirada.** A §11 pede o endereço "nas regras de funcionamento do site", e nenhuma página de regras existe. Esta fatia cria a página só com o que a §11 e a §10 definem para a retirada, sem inventar regras de outras seções.
- **Fornecedor sem acesso.** A §2 fecha o que o fornecedor vê (17.9); o endereço da casa do administrador não está na lista.

## Invariantes

- Nenhuma página fora da área autenticada mostra o endereço.
- O histórico dos endereços nunca é alterado.

## Casos-limite

- Texto com 500 caracteres é aceito, e com 501 é recusado.
- Endereço com duas linhas aparece com as duas linhas no carrinho e nas regras (escapado, sem HTML).

## Dependências e decisões em aberto

- Depende da E05-05 (carrinho) e da E02 (políticas).
- Nenhuma decisão em aberto.
