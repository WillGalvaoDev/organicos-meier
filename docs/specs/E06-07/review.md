# E06-07 — Revisão independente — 2026-10-19

**Veredito desta fatia: REPROVADO. Veredito global da E06: REPROVADO.**

Base: `main`, commit `2fbf143d082b37a1e8333a0736a310008e10e9ad`. A-1 a A-14 examinados. R01 (bloqueador): carrinho e catálogo falham com retorno ao interesse entre leituras. R02 (importante): formulário aceita data sem hora, segundos não zero e offset explícito, contrariando o formato local especificado. Permissões e demais respostas passaram na suíte existente.

O [parecer consolidado em E06-01](../E06-01/review.md) registra fontes, matriz das sete fatias, classificação, referências, passos de reprodução, limites e código completo das provas independentes. Suíte completa: **1772 passed**. Provas adicionais: **7 failed, 8 passed** (as falhas confirmam R01 a R04). Ruff, formatação, mypy e verificação de migrações passaram. Não houve alteração de produção nem de testes versionados pelo revisor.

Os registros do implementador abaixo são preservados como evidência histórica; não substituem o veredito independente acima. As correções e o gate de processo R05 exigem nova avaliação antes do encerramento da E06.

---

## Registro anterior preservado

# E06-07 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6 (§§5, 13, 15), infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E02-10, E05-04, E05-05 e E06-01 a E06-06.

## Arquivos

- `apps/rodadas/views.py`, `config/urls.py` e `apps/rodadas/forms.py`: `fechamento_iniciar`, `fechamento_prorrogar` e `FormularioProrrogacao`; o bloco "Fechamento" e o histórico de prazos em `_pagina_do_estoque`.
- `templates/rodadas/estoque.html`, `templates/fornecedores/detalhe.html`, `apps/fornecedores/views.py`: bloco, histórico e prazo no detalhe do fornecedor.
- `apps/interesses/apresentacao.py` (`prazo_da_rodada`, `linha_do_prazo`), `templates/interesses/carrinho.html` e `templates/catalogo/comprador_fornecedor.html`: o prazo para o comprador.
- Testes: `tests/tecnicos/test_rodadas_fechamento_telas.py` (A-1 a A-9, A-12 e A-14) e, em `test_interesses_carrinho.py`, A-10, A-11 e A-13. Nenhuma migração.

## Ciclo TDD

**Andaime (exceção técnica):** as duas rotas e as URLs devolvendo corpo vazio.

**Red.** `uv run pytest tests/tecnicos/test_rodadas_fechamento_telas.py -q`: **13 failed, 4 passed**, por asserção (`assert 'action="/administracao/rodadas/1/fechamento/iniciar/"' in '...'`, `assert 302 == 200`, `assert 200 == 409`, `assert 200 == 404`, `'Informe a data e a hora do novo prazo.' in ''`). Nos acréscimos do carrinho: **2 failed, 1 passed** (`AssertionError: /carrinho/`, o prazo ausente). Passaram já no Red os testes que dependem de ausência ou do que o andaime já fazia (GET 405, recusa de comprador e fornecedor pela política).

**Green.** Telas e carrinho: **71 passed**. Suíte completa: **1772 passed** (eram 1752). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros.
- A tela não decide transição: as rotas chamam `iniciar_fechamento` e `prorrogar_fechamento` e traduzem `TransicaoRecusada` em 409 com a página relida.
- `termino` é um `DateTimeField` de formato `%Y-%m-%dT%H:%M`; como `TIME_ZONE` é America/Sao_Paulo, o valor limpo já é instante com fuso. Quando a rodada não desenha o formulário de prorrogação, a mensagem de campo inválido vai para o topo (mesma lição da E05-R05).

## Diferenças em relação ao texto dos critérios (por conflito ou por medição)

1. **A-10, "nenhum 100,00".** O estado do A-5 tem A com 10 reservados a R$ 10,00, então "Subtotal" e "Total reservado" legitimamente mostram R$ 100,00 ao comprador: a asserção literal não pode valer. Para testar a **mesma propriedade** (o mínimo do fornecedor não aparece), o teste define o mínimo em R$ 87,65, que não coincide com nenhum valor da página, e exige a ausência de "87,65" e "87.65". Registro como conflito do critério para o especificador.
2. **A-13, limite de consultas.** A spec fala em "no máximo uma constante por fornecedor" sem o valor. Medido: com a rodada em `fechamento` a página faz **6 consultas a mais por fornecedor** (leitura do prazo para o aviso e para a decisão de editar), igual com 1 e com 10 produtos. O teste exige a igualdade entre 1 e 10 produtos e o acréscimo máximo de 6 por fornecedor (18 para 3).
3. **Sessão do administrador nos testes.** Como os testes avançam o relógio para depois do prazo, a sessão do administrador precisa nascer no instante dos testes; o fixture `admin_client` congela o relógio em `T0` antes do login.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_com_o_minimo_atingido_oferece_iniciar` |
| A-2 | `test_sem_o_minimo_nao_oferece_iniciar` |
| A-3 | `test_iniciar_pela_tela` |
| A-4 | `test_iniciar_recusado_volta_409_com_a_mensagem` |
| A-5 | `test_fechamento_em_andamento_mostra_prazo_formulario_e_historico` |
| A-6 | `test_prorrogar_pela_tela` |
| A-7 | `test_termino_invalido_volta_200_sem_gravar`, `test_termino_anterior_ao_prazo_volta_409` |
| A-8 | `test_prazo_vencido_sem_a_tarefa_nao_oferece_prorrogar` |
| A-9 | `test_fechamento_encerrado_mostra_o_estado_e_o_detalhe_do_fornecedor` |
| A-10 | `test_o_prazo_do_fechamento_aparece_no_carrinho_e_no_catalogo` |
| A-11 | `test_depois_do_prazo_o_aviso_muda_e_os_formularios_somem` |
| A-12 | `test_so_o_administrador_usa_as_rotas`, `test_get_nas_rotas_responde_405` e a varredura `test_permissoes_politica_rotas.py` (sem alteração) |
| A-13 | `test_numero_de_consultas_com_fornecedores_em_fechamento` |
| A-14 | `test_rodada_inexistente_da_404` |

## Limites da verificação

Cliente HTTP do Django, sem navegador (o campo `datetime-local` não foi exercitado num navegador). O painel geral e os alertas (E15), o pagamento (E08) e o portal do fornecedor (E13) são de outras fatias. Nenhuma mutação foi aplicada nesta fatia.
