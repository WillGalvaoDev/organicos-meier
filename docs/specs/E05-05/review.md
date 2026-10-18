# E05-05 — Revisão independente

## Revisão independente — 2026-10-18

Commit auditado: `32b05a24fb38aa7bcaef2d67c5917fdef59bc2c5` (`main`, PR #65). Parecer global da E05: **REPROVADO**.

Fontes: especificação funcional v1.6 (§§2, 4.4, 5, 5.1, 5.2 e 6), infraestrutura v1.7 (§§4.10–4.12), AGENTS.md e os sete pares `spec.md`/`acceptance.md` da E05, incluindo a decisão D-1 da E05-07. Código e testes foram confrontados com esses contratos. A revisão não altera regras, código de produção ou testes versionados.

Validação independente no PostgreSQL local:

- `uv run pytest -q`: **1619 passed em 161,01 s**.
- `uv run ruff check .`: passou.
- `uv run ruff format --check .`: **217 arquivos** conformes.
- `uv run mypy .`: **251 arquivos**, sem erros.
- `uv run python manage.py makemigrations --check --dry-run`: nenhuma alteração pendente.
- Provas adicionais do revisor: **8 failed, 8 passed em 4,71 s**, conforme reprodução integral em [E05-01/review.md](../E05-01/review.md). As falhas são deliberadamente asserções do contrato contra o commit auditado; não são falhas da suíte versionada.

Os registros Red/Green do implementador são preservados abaixo. Eles documentam os testes funcionais e os comandos; o revisor não afirma ter presenciado as execuções históricas. A ausência confessada de Red nos testes de concorrência é tratada em R04. Nenhum teste foi afrouxado nesta revisão. As duas mudanças nos testes da E03-08 estão autorizadas pela E05-05; a suíte de regressão inteira passou.

### Parecer da fatia: REPROVADO

A-1 a A-20 passaram nos cenários versionados, incluindo privacidade, políticas de acesso, erros e consultas. R02 demonstra falha adicional no contrato de A-6: POST de remoção com pendência própria retorna 302 nas duas origens, deixando 4 reservados. O reenvio também altera estado novamente. Corrigir somente após explicitar a combinação com FIFO obrigatório; ver [parecer consolidado](../E05-01/review.md).

---

## Registro original do implementador (preservado como evidência)

# E05-05 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

Fontes lidas antes de editar: especificação funcional v1.6, infraestrutura v1.7, `spec.md` e `acceptance.md` da fatia, E03-08 e E05-01 a E05-04.

## Arquivos

- `apps/interesses/forms.py`, `views.py` (`carrinho`, `definir`, `remover_pendentes`), `apresentacao.py` (contexto do carrinho e do catálogo, `Retorno`) e, em `consultas.py`, `carrinho_do_comprador`.
- `apps/catalogo/views.py` e `templates/catalogo/comprador_fornecedor.html`: progresso, "Seu interesse", caixas e formulário de quantidade.
- `templates/interesses/` (`carrinho.html`, `_quantidade.html`, `_caixas.html`, `_progresso.html`), `templates/base.html` (link "Carrinho" para compradores) e `config/urls.py` (`carrinho`, `interesses_definir`, `interesses_remover_pendentes`).
- Testes: `tests/tecnicos/test_interesses_carrinho.py` (A-1 a A-16, A-18, A-19; o A-17 é o 405 deste arquivo mais a varredura de políticas existente) e os dois ajustes autorizados em `tests/tecnicos/test_catalogo_comprador.py` (A-20). Nenhuma migração.

## Ciclo TDD

**Andaime sem comportamento (exceção técnica):** rotas e URLs devolvendo corpo vazio, formulário e importações.

**Red.** `uv run pytest tests/tecnicos/test_interesses_carrinho.py -q`: **28 failed, 1 passed**, por asserção (páginas vazias: `assert 'Reservado: 6' in ''`, `(200, None) == (302, '/carrinho/')`, `assert 200 == 409`, `0 == 1` em formulários). Passou já no Red o 405 do GET nas rotas de gravação (A-17), porque `require_POST` estava no andaime. Antes disso corrigi, nos testes, detalhes de forma (uso de `.get("Location")`, asserções antes de desempacotar listas), sem alterar garantias.

**Green.** Mesmo arquivo: **29 passed**. Suíte completa: **1594 passed** (eram 1565). `ruff check`, `ruff format --check`, `mypy .` e `makemigrations --check --dry-run` sem erros. Dois ajustes de teste ao longo do Green, por erro meu: o cliente do administrador precisa ser logado **antes** de criar a rodada (há um único administrador), e o parcial `_caixas.html` precisava do `{% load catalogo %}`.

## Ajustes autorizados em `test_catalogo_comprador.py` (A-20)

Justificativa: seção "Relação com a E03-08" do `spec.md` da E05-05. O diff do arquivo contém **só** estes dois ajustes e os auxiliares que eles exigem.

1. `test_campos_internos_e_dados_de_compradores_nao_aparecem`: as asserções `"reservad" not in html.lower()` e `"pendente" not in html.lower()` foram trocadas por: a página contém "Seu interesse: reservado 0, pendente 0" e não contém "reservado 2" nem "pendente 1". Todas as demais (mínimo `987,65` e `987.65`, nomes, e-mails) ficaram iguais.
2. `test_numero_de_consultas_nao_cresce_com_os_produtos`: o teto passou de **8 para 10**. Medição: o comprador da sessão agora tem uma parcela em cada produto, e a página faz **10 consultas** com 1 produto e com 20 produtos (com teto 9 os dois casos falham; com 10, 11 e 12 passam). Para manter a asserção "7 kg disponível" intacta, a reserva dos outros compradores caiu de 3 para 2 e a da sessão é 1 (total 3). Foi preciso o auxiliar `_reservar_para` e importar `Conta`.

## Decisões técnicas

- **Vírgula decimal.** O texto de `quantidade` vai ao serviço só com a vírgula trocada por ponto (`"2,5"` vira `"2.5"`), porque os valores exibidos têm vírgula e o usuário tende a digitar assim. O serviço continua sendo quem converte e valida; o texto digitado volta intacto no `value` do formulário. O campo do formulário vem preenchido com ponto decimal, para o reenvio ser aceito.
- **Botão "Remover".** É um botão `name="quantidade" value="0"` dentro do mesmo formulário: ao clicar, o último valor de `quantidade` é `0`. Evita um segundo formulário por produto.
- **Produto inválido** (id que não passa no formulário): 200 com "Produto inválido." na página do carrinho, mesmo com `origem=catalogo`, porque sem produto não há fornecedor.
- **A-11, segundo caso** (fornecedor sem rodada ativa, `origem=catalogo`): 409 na página do carrinho com a mensagem do serviço para esse caso ("Os interesses deste fornecedor não podem ser alterados nesta etapa."); a frase "Este produto não está disponível para interesse agora." vale para o produto fora da rodada (primeiro caso). Registro como leitura da spec, porque o texto do critério é ambíguo.
- **`quantidade` ausente ou com mais de 30 caracteres** com produto válido: 200 no formulário do produto com "Informe a quantidade." e o texto cortado em 30 caracteres.
- O 403 de `PermissionDenied` do serviço (A-15) é o tratamento padrão do Django; a transação do serviço já desfez tudo.

## Mapeamento dos critérios

| Critério | Teste |
|---|---|
| A-1 | `test_carrinho_agrupa_por_fornecedor_e_nao_mostra_o_minimo` |
| A-2 | `test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado` (`acceptance`, cenário 96) |
| A-3 | `test_pendente_sem_rodada_ativa` |
| A-4 | `test_caixas_so_com_as_unidades_do_proprio_comprador` |
| A-5 | `test_produto_indisponivel_no_carrinho_e_no_catalogo` |
| A-6 | `test_definir_e_idempotente_e_zero_remove` |
| A-7 | `test_origem_catalogo_volta_para_o_catalogo` |
| A-8 | `test_quantidade_recusada_volta_no_formulario_do_produto` (seis textos) |
| A-9 | `test_produto_invalido_nao_derruba`, `test_produto_inexistente_da_404` |
| A-10 | `test_etapa_mudou_entre_a_pagina_e_o_envio` (carrinho e catálogo) |
| A-11 | `test_produto_fora_da_rodada_e_rodada_inexistente` |
| A-12 | `test_remover_pendentes_pela_rota` (`acceptance`, cenário 97) |
| A-13 | `test_remocao_de_pendentes_recusada_e_campos_extras_ignorados` (`acceptance`, cenários 98 e 99) |
| A-14 | `test_quem_pode_ver_e_quem_pode_gravar` |
| A-15 | `test_suspensao_entre_a_politica_e_a_trava` |
| A-16 | `test_numero_de_consultas_do_carrinho` (1 produto = 10 produtos × 4 parcelas; 3 fornecedores − 2 = 2 − 1, no máximo 6) |
| A-17 | `test_get_nas_rotas_de_gravacao_responde_405` + varredura `test_permissoes_politica_rotas.py` (sem alteração) |
| A-18 | `test_link_do_carrinho_so_para_comprador` |
| A-19 | `test_so_o_percentual_do_minimo_chega_ao_comprador` |
| A-20 | `tests/tecnicos/test_catalogo_comprador.py` (seção acima) |

## Limites da verificação

Cliente HTTP do Django, sem navegador (nenhum comportamento de HTMX; as rotas respondem página inteira ou redirecionamento). O prazo do fechamento no carrinho é da E06; o pedido e o pagamento, da E08.
