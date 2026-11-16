# E14-03 — Registro da implementação (agente 2, 2026-11-16)

Comando: `uv run pytest tests/tecnicos/test_endereco_de_retirada.py tests/tecnicos/test_endereco_de_retirada_telas.py` (arquivos inteiros, sem `-k`).

| Etapa | Resultado |
|---|---|
| Red | **13 failed**: `apps.pedidos.endereco_de_retirada` e `EnderecoDeRetirada` inexistentes; rotas `regras/` e `administracao/retirada/endereco/` em 404; carrinho e início sem os textos |
| Green | **13 passed**; também verdes `test_permissoes_politica_rotas.py`, `test_pedidos_abertura_tela.py` (lista de rotas sem mudança), `test_interesses_carrinho.py`, `test_permissoes_papeis.py`, `test_catalogo_permissoes.py`; `mypy apps config` e `ruff` limpos |

## O que foi feito
- `EnderecoDeRetirada` (só inserção, migração `0018`), `definir_endereco_de_retirada`, `endereco_vigente`, `EnderecoRecusado` em `apps/pedidos/endereco_de_retirada.py`; auditoria `retirada.definir_endereco` (anterior e novo).
- `apps/pedidos/retirada_views.py`: `retirada_endereco` (`somente_administrador`, GET/POST) e `regras`; templates `pedidos/endereco_de_retirada.html` e `pedidos/regras.html`; rotas em `config/urls.py`.
- Carrinho: linha "Retirada: ..." em cada grupo (`contexto_do_carrinho` + `interesses/carrinho.html`); início: "Regras e retirada" para comprador e administrador.

## Decisões técnicas
- **Política de `regras/`:** `exige_login` (autenticada) com a recusa do fornecedor dentro da view (403), em vez de uma política nova, para não alterar o enum de políticas nem o teste que varre as rotas. Anônimo vai ao login pelo decorador.
- **Tela do administrador sem formulário de `acionamento`:** a E14-03 não o pede; a duplicidade do envio é tratada por `sem_alteracao` (mesmo texto).
- **Quebras de linha:** `linebreaksbr` (escapa o HTML antes de trocar `\n` por `<br>`).


---

## Revisão independente — agente 3 — 2026-11-16

**Objeto:** `5b00c56`, branch `e14-especificacoes`, comparação com `bc35037` (main após E13). Fontes: especificação funcional v1.7, infraestrutura v1.8, AGENTS.md e as oito especificações e matrizes da E14. Histórico do implementador acima preservado.

A execução independente e o parecer consolidado estão em [E14-08/review.md](../E14-08/review.md), incluindo o código das contraprovas. A revisão não alterou código de produção nem os testes do implementador.

**Parecer da fatia: APROVADO.**

| Critérios | Verificação |
|---|---|
| A-1 a A-4 | Endereço vigente por maior pk, histórico/auditoria, normalização, limites de texto e permissão. |
| A-5 a A-9 | Carrinho e regras autenticados, ausência de endereço, fornecedor/anônimo recusados, link por perfil. |
| A-10 a A-13 | Administração, recusas, escape HTML/quebras de linha e proteção de atualização/exclusão no banco. |

Código confrontado: `endereco_de_retirada.py`, `retirada_views.py`, migração 0018 e templates/carrinho. Os dois arquivos `test_endereco_de_retirada*` foram incluídos na suíte independente. Sem achado nesta fatia.

TDD: `8bac5e3` contém somente testes, antes da implementação `d1b1a49`; evidências registradas de Red/Green compatíveis com o histórico.
