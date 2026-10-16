# E03-08 — Registro do implementador (aguardando revisão independente)

Status: implementação concluída; **aguardando o agente 3**. Nada aqui é aprovação.

## Ciclos TDD

**Andaime (sem comportamento, justificado):** `consultas.py` com corpos triviais (`[]`), views
vazias com a política `exige_comprador`, rotas `catalogo_lista` e `catalogo_fornecedor`. Suíte
antes do Red: 1037 passando.

**Red** (`uv run pytest tests/tecnicos/test_catalogo_comprador.py tests/tecnicos/test_catalogo_permissoes.py`):
**18 falhas, 6 passando**. Falhas por asserção sobre o conteúdo (`assert 'Banana' in ''`,
`assert 'Produto indisponível' in ''`, listas e 404 que o andaime não produz, teto de consultas e
link de `/inicio/`). As 6 que passavam são guardas: a política `comprador` já declarada pelo
andaime, o comprador suspenso com 200 (o andaime já responde 200), e os testes de 403/login dos
produtos e do catálogo.

**Green:** `consultas.py` (`fornecedores_no_catalogo`, `rodada_ativa_do_catalogo`,
`produtos_da_rodada`, `produtos_do_catalogo`, estoque livre em lote), filtro `reais`, views,
templates `catalogo/comprador_lista.html` e `comprador_fornecedor.html`, link em `/inicio/`.
Resultado: arquivos da fatia 24 passando; suíte completa **1058 passando**; `ruff check`,
`ruff format`, `mypy --strict`, `makemigrations --check` limpos.

**Refactor (suíte verde):** a fórmula do estoque livre virou `calcular_livre(limite, reservado)`
em `rodadas/estoque.py` (usada por `estoque_livre` e pelo catálogo) e as situações que reservam
viraram a constante pública `SITUACOES_QUE_RESERVAM` em `interesses/consultas.py`.

**Ajustes de teste durante o Green (erros do teste, não do código):** o teste de administrador no
catálogo criava um segundo administrador (há um só, por restrição do banco); passou a autenticar o
administrador antes de criar a rodada. Linhas longas quebradas para o lint.

## Matriz de critérios

| Critério | Teste |
|---|---|
| A-1 | `test_catalogo_comprador.py::test_banana_mostra_preco_incremento_e_disponivel` |
| A-2 | `::test_maca_mostra_multiplo_e_sem_limite` |
| A-3 | `::test_estoque_zero_e_tudo_reservado_aparecem_como_esgotado` |
| A-4 (D-1) | `::test_produto_fora_da_rodada_nao_aparece_e_indisponivel_traz_a_marcacao` |
| A-5 | `::test_lista_de_fornecedores_com_rodada_e_produto` |
| A-6 | `::test_fornecedor_sem_rodada_ativa_ou_inexistente_da_404_igual` |
| A-7 | `test_catalogo_permissoes.py::test_comprador_suspenso_consulta_o_catalogo` |
| A-8 | `::test_fornecedor_e_administrador_nao_consultam_o_catalogo`, `::test_visitante_anonimo_vai_para_o_login_no_catalogo` |
| A-9 | `test_catalogo_comprador.py::test_campos_internos_e_dados_de_compradores_nao_aparecem` |
| A-10 | `::test_numero_de_consultas_nao_cresce_com_os_produtos` (1 e 20 produtos, teto de 8) |
| A-11 | `::test_rodada_sem_produto_mostra_a_mensagem` |
| A-12 | `::test_as_duas_rotas_declaram_a_politica_de_comprador` e a varredura `test_permissoes_politica_rotas.py` |
| A-13 (D-1) | `::test_marcacao_some_quando_o_produto_volta_a_ficar_disponivel` |

Extras: ordenação por nome, etapas fora de interesse, formato `R$ 1.234,56`, link em `/inicio/`.

## Decisões técnicas (derivadas, sem alterar regra de negócio)

- O fornecedor aparece em `/catalogo/` quando tem rodada em qualquer etapa ativa com ao menos
  um estoque (`EXISTS`); rodadas `disponivel_para_retirada` e `cancelada` não entram.
- Sem rodada ativa e id inexistente levantam `Http404` pelo mesmo caminho, então o corpo é
  idêntico.
- A página não mostra o total reservado nem pendências: só o estoque livre.
- Teto de 8 consultas na página do fornecedor (sessão, usuário, rodada com fornecedor, estoques com
  produtos e uma agregação das reservas); medido igual com 1 e com 20 produtos.
- A unidade exibida usa o rótulo do modelo (`unidade`, `pacote`, `caixa`, `kg`, `L`), e a
  disponibilidade fica "`<quantidade> <unidade> disponível`" (por exemplo, "4 kg disponível").

## Limitações de verificação

- Adicionar interesse, carrinho, progresso e caixas são da E05 e entram nestas telas.
- O catálogo mostra o estoque livre calculado por `total_reservado` sem filtro por rodada (a parcela
  ainda não tem vínculo com a rodada; a E05 ajusta sem mudar a assinatura).
- Telas verificadas pelo cliente de teste do Django, não por navegador.
