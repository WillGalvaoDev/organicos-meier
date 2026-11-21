# E16-06 — Registro do implementador

Agente 2.

## Red (observado antes do código de produção)

`uv run pytest -q tests/tecnicos/test_regras_de_funcionamento.py`: **5 failed, 3 passed**. Falharam A-1 (só a seção "Retirada", `<h1>` "Regras e retirada"), A-2 (parágrafos ausentes), A-4 (valores fixos do template), A-5 (a retirada fixa em "sete dias") e A-8 (link "Regras e retirada"). Passaram de primeira, como guardas: A-3 (a seção "Retirada" não mudou), A-6 (a página nunca mostrou rodada nem pessoas) e A-7 (o acesso é o da E14-03).

## Green

- `templates/pedidos/regras.html`: `<h1>` e `<title>` "Regras de funcionamento", as sete seções novas com os parágrafos exatos da regra 2 e a seção "Retirada" no fim, com o texto e o endereço da E14-03.
- `apps/pedidos/retirada_views.py`: `_valores_das_regras()` lê, a cada requisição, `calculo.TAXA_DE_SERVICO`, `fechamento.HORAS_DO_FECHAMENTO`, `prazos.HORAS_DO_PRAZO_DE_PAGAMENTO`, `prazos.HORAS_DA_MARGEM` e `liberacao_da_retirada.PRAZO_DE_RETIRADA`. A página muda junto com as constantes. Nenhuma constante precisou ser extraída (todas já tinham nome).
- `templates/inicio.html`: o link passou a "Regras de funcionamento" (a rota é a mesma).

## Desvios e pontos para o revisor e o especificador

1. **Conflito entre a regra 5 e o A-3 da E16-06.** O A-3 diz que "os testes da E14-03 continuam passando sem alteração", mas a regra 5 manda trocar o texto do link da página inicial, e o A-9 da E14-03 (`test_o_link_das_regras_na_pagina_inicial`) confere o texto antigo "Regras e retirada". Segui a regra 5 e troquei, nesse teste, só a string esperada (três asserções, nenhuma removida; a negativa para o fornecedor continua). Evidência: sem a troca, `test_endereco_de_retirada_telas.py::test_o_link_das_regras_na_pagina_inicial` falha com o texto "Regras de funcionamento" na página. Os demais testes da E14-03 não mudaram.
2. **"24 horas" depois do prazo (Pagamento).** A margem existente é `HORAS_DA_MARGEM = 48` contados de T0. O texto "aprovado até {24} horas depois do fim dele" usa `HORAS_DA_MARGEM - HORAS_DO_PRAZO_DE_PAGAMENTO` (24 com os valores atuais), que é o que o servidor aplica.
3. **Prazo de retirada por extenso:** 1 a 9 dias saem por extenso ("sete dias", como no texto da E14-03) e 10 ou mais em algarismos ("10 dias", como o A-5 pede).
4. **A-4:** o teste troca a taxa para 7%, o prazo de pagamento para 36 h, a margem para 60 h (resultando em 24 h depois do prazo) e o fechamento para 36 h, por `monkeypatch` nas constantes.
5. O texto do convite "válido por 24 horas" (Participação) é fixo na spec; não há constante de 24 h para ele com nome próprio nesta fatia e a spec só lista a taxa, o prazo de pagamento, o de fechamento e a retirada como valores configuráveis.

## Verificação

`uv run pytest -q tests/tecnicos/test_regras_de_funcionamento.py tests/tecnicos/test_endereco_de_retirada_telas.py tests/tecnicos/test_portal_do_fornecedor.py`: **36 passed**. `ruff` e `mypy` (548 arquivos) limpos. Suíte completa no fim da E16. Sem push, PR nem merge.


---

## Revisão independente — agente 3 — 2026-11-17

Base avaliada: `52f8745870ebfa007ad6a94edf7f968ae472d04e`, branch
`e16-especificacoes`, diff contra `02f8e91`. Requisitos lidos antes do código:
AGENTS.md, especificação funcional v1.7, infraestrutura v1.8 e as oito specs e
acceptances da E16. Registros do implementador acima preservados integralmente.
A evidência global de execução está no parecer da E16-08 abaixo.

**Veredito da fatia: APROVADO.** A E16 completa não está aprovada.

A-1 a A-8 confrontados com spec, template, view e testes: oito seções e redação
aprovada, endereço preservado, valores derivados das constantes de taxa/prazos,
retirada por extenso, link atualizado e acesso de comprador/administrador com recusa
do fornecedor. Conferida a diferença `48 - 24` para a margem contada depois do prazo.

A mudança das três strings no teste antigo do link é consequência direta da regra 5,
foi registrada e não removeu a negativa de autorização. A leitura literal de
“sem alteração” do A-3 não deve impedir a mudança de texto expressamente exigida.
Não há decisão comercial nova nem afrouxamento de comportamento. Registros Red/Green
conferidos, com guardas existentes identificadas. Sem achado novo nesta fatia.


## Revalidação independente — 2026-11-18 — commit 5f12d21

Revalidação de regressão: implementação desta fatia não foi alterada pelas correções; suíte completa passou. Mantido o parecer anterior, sem novo achado. Evidências globais na E16-08.
