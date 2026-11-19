# E16-10 — Alinhamento dos critérios das melhorias M-3 e M-8

Fatia 10 da milestone **E16 — Homologação e encerramento da fase 1**. Ela foi aberta pela revisão das melhorias (E16-08, regra 10), com a decisão do responsável de 2026-11-18. Agente 1 (especificador).

## Versões dos documentos-base

Como na E16-01: especificação v1.7 e infraestrutura v1.8. Gate de especificação: como na E16-01.

## Contexto e objetivo

Dois critérios de aceitação aprovados têm redação que contradiz regras superiores. A implementação e os testes seguem as regras superiores, e por isso o revisor classificou os dois casos como melhoria e não como defeito.

- **M-3** (E08-R07): na E08-02, o A-12 pede 409 para o administrador numa rota de comprador ativo, mas a política recusa antes. O A-21 pede que não haja aviso de preço também quando o preço muda antes do congelamento, o que contraria o §5.1 e a E05-06.
- **M-8** (E09-08): o A-3 usa o literal `1.000,00`, embora a spec recuse o separador de milhar. O teste e o formulário usam `1000,00`.

O responsável decidiu tratar as duas antes do encerramento, numa fatia só de documentação. Esta fatia corrige a redação, para que o relatório final e a matriz citem critérios coerentes com o comportamento aprovado.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| `docs/melhorias.md`, M-3 | "Alinhar a redação à recusa pela política e ao aviso devido antes da abertura, sem alterar permissões nem o comportamento de notificações." |
| `docs/melhorias.md`, M-8 | "Alinhar o literal à regra de entrada aprovada, mantendo os negativos de separador de milhar." |
| Funcional §5.1 e E05-06 | Uma mudança de preço durante interesse e fechamento atinge os interesses e avisa os compradores afetados. Um pedido que já entrou em pagamento preserva o preço. |
| E02-10 | A política `comprador_ativo` recusa o administrador antes de qualquer regra da etapa. |
| E09-08, spec | "Valores com separador de milhar ou mais de duas casas: recusados no formulário." |
| E16-08, regra 10 | Uma melhoria a tratar antes do encerramento vira fatia própria. |

## Escopo

**Dentro:**
- a redação do A-12 e do A-21 em `docs/specs/E08-02/acceptance.md`;
- a redação do A-3 em `docs/specs/E09-08/acceptance.md`;
- um teste novo de caracterização para a recusa do administrador (regra 2-A, complemento de 2026-11-19 para o achado E16-R08).

Os dois textos novos estão abaixo e foram aplicados pelo especificador neste mesmo commit. Cada linha tem a marca "(redação corrigida na E16-10)", e o texto anterior fica preservado abaixo da tabela.

**Fora:**
- mudar produção, permissões, notificações ou a regra de entrada de valores;
- reescrever ou afrouxar os testes existentes. A única adição permitida é a caracterização da regra 2-A.

## Regras

1. **Redação nova:**
   - **E08-02 A-12, "Então":** "nenhuma rota de edição de pedido, item, `T0` ou frete; os `POST` de interesse de A recebem 409 com a mensagem da etapa; o `POST` do administrador é recusado pela política `comprador_ativo` (E02-10), antes da regra da etapa e sem a mensagem dela; os pedidos não mudam".
   - **E08-02 A-21, "Então":** "quando o preço vem antes, os itens de `P1` têm 11,00, e A e B recebem `preco_alterado`, porque as parcelas ainda estavam ativas (§5.1, E05-06); quando vem depois, os itens têm 10,00, o preço do produto é 11,00 e nenhum `preco_alterado` é gerado para A nem para B".
   - **E09-08 A-3, "Quando":** "`POST financeiro_aporte` com `1000,00`, `sim-mov-1` e "Aporte inicial"". Os negativos com separador de milhar (`1.000,00`) continuam recusados, como na spec da E09-08.
2. **Correspondência com os testes:** o implementador confere, lendo o corpo, que os testes ligados a esses critérios já conferem a redação nova, sem alterá-los:
   - `tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409`;
   - os dois testes de ordem do A-21 em `tests/tecnicos/test_pedidos_concorrencia.py`;
   - `tests/tecnicos/test_financeiro_telas.py::test_aporte_com_passkey_recente_entra_na_reserva_e_no_historico`.

   Ele executa esses testes e registra o comando e o resultado no `review.md`. Se algum teste não conferir a redação nova, o implementador para e devolve ao especificador, sem mudar o teste por conta própria.
2-A. **Complemento da prova do administrador** (achado E16-R08, revisão de 2026-11-18 sobre 3e8b4ff).
   - **A devolução:** o registro do implementador reconheceu que nenhum dos testes citados afirma a ausência da mensagem da etapa na resposta ao administrador. O revisor apontou que isso devia ter sido devolvido. O especificador recebe a devolução aqui.
   - **Busca de prova existente:** o especificador procurou nos testes a mensagem `MENSAGEM_INTERESSES` ("Os interesses deste fornecedor não podem ser alterados nesta etapa."). Ela só é afirmada como presente, nas respostas ao comprador (`test_pedidos_abertura_tela.py` e a constante `BLOQUEADO` de `test_interesses_carrinho.py`). Nenhum teste afirma a ausência dela para o administrador. `test_quem_pode_ver_e_quem_pode_gravar` (E05-05 A-14) confere o 403 sem ler o corpo.
   - **Caracterização:** entra `tests/tecnicos/test_pedidos_abertura_tela.py::test_administrador_e_recusado_pela_politica_sem_a_mensagem_da_etapa`, que:
     - usa o arranjo do A-12 (`abrir(arranjo)`, com os interesses do fornecedor bloqueados) e o administrador autenticado como no E05-05 A-14;
     - faz `POST /interesses/` com `produto=<P1>` e `quantidade=7`;
     - confere `status_code == 403`, exatamente;
     - confere que `MENSAGEM_INTERESSES` não está no corpo da resposta;
     - confere que pedidos, itens e parcelas de interesse ficam iguais por conteúdo, lidos antes do `POST`.
   - **O que não muda:** o teste existente `test_interesse_depois_da_abertura_e_recusado_com_409` continua como está, com a tolerância `in (302, 403)`. A política `comprador_ativo` (E02-10) e a produção também não mudam.
   - **Se a caracterização falhar:** se o 403 ou a ausência da mensagem não se confirmarem, o implementador para e devolve, com a resposta obtida. Não muda a produção nem o teste.

3. **Encerramento das melhorias:** depois da aprovação do revisor, M-3 e M-8 passam para "Encerradas" em `docs/melhorias.md`, com a entrega E16-10 e o commit.

## Invariantes

- Nenhum código de produção muda, e nenhum teste existente muda. Só entra o teste da regra 2-A.
- O texto anterior dos critérios fica preservado.

## TDD

Não há comportamento novo, e a fatia é só de documentação. É uma exceção técnica justificada pelo AGENTS.md §3: não há Red possível, porque o comportamento já é o da redação nova. A evidência é a execução dos testes da regra 2.

O teste da regra 2-A é uma caracterização de comportamento existente. Se passar na primeira execução, o `review.md` registra isso como caracterização, sem um Red inventado.

## Dependências e decisões em aberto

- Depende da E08-02, da E09-08 e da decisão do responsável de 2026-11-18.
- Nenhuma dependência nova.
- Nenhuma decisão em aberto.
