# E15-06 — Registro do implementador

Agente 2.

## Red

- Commit do Red: `uv run pytest tests/tecnicos/test_historico_de_acoes.py` → **17 falhas e 1 passando** (a rota não existe; o que passou é a guarda "a leitura não grava", A-12).

## Green

- `apps/operacao/historico.py` (consulta, filtros, paginação e o texto das linhas), a view `historico` em `apps/operacao/views.py` (`somente_administrador`, `require_GET`), a rota `historico_acoes`, o template `templates/administracao/historico.html` e o link "Histórico de ações" na navegação do painel.
- Resultado: `18 passed`; com o painel, `43 passed`.

## Desvios e pontos para o revisor

1. **ADM2 (especificação inviável).** Como nas E15-02 e E15-04, o banco admite um administrador só. ADM1 é o administrador; ADM2 é uma conta de comprador com esse nome, autora de e3. Por isso o A-9 usa `autor=sistema` para obter "Nenhuma ação encontrada." (a spec usa `autor=<ADM2>`, que aqui seria um filtro inválido, já que a regra 3 só aceita "sistema" ou administrador). O A-10 testa `autor=<comprador>` como inválido.
2. **Intervalo ao contrário** (`de` maior que `ate`): a mensagem é "Filtro inválido ignorado: de." e os dois filtros de data são ignorados, para o resultado ser as três linhas que o A-10 pede.
3. **Marcação própria.** Cada linha é `<tr class="entrada">` com a ação em `<td class="acao">`; os testes leem essa marcação. As alterações são uma linha "chave: valor" por chave, em JSON compacto, escapada pelo template.
4. **A-4:** o arranjo não conta as entradas de autenticação (a passkey não grava auditoria neste arranjo), e o teste lê o total do banco.

## Ajuste do especificador (commit e8c967a)

A-6 ganhou a conferência da lista de autores (só "Sistema" e ADM1) e A-10 o autor comprador chamado ADM2. Acrescentei as duas asserções e `test_autor_comprador_com_nome_de_administrador_e_invalido` (guardas: passaram de primeira, o código já filtrava por papel de administrador).
