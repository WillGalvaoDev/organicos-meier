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
