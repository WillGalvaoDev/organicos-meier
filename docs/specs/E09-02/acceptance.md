# E09-02 — Critérios de aceitação

Agente 1 (especificador). Cada critério precisa permitir um teste automatizado que falhe antes da implementação.

**Arranjo comum:** o simulador reiniciado e o relógio controlado em `T0`. A cobrança C tem R$ 125,00, Pix, criada pelo provedor (`obter_provedor().criar_cobranca`).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 3.2, simulador | positivo | `definir_tarifa("pix", percentual=Decimal("0.99"), fixa=Decimal("0.00"))` e `definir_liberacao("pix", horas=24)` | aprovar C às `T0 + 1h`; `consultar_pagamento` | `tarifa = 1.24` (125,00 × 0,99% = 1,2375, arredondado para cima), `liberado_em = T0 + 25h` em UTC |
| A-2 | Infra 3.4 | positivo | C pendente | `consultar_pagamento` | `tarifa` e `liberado_em` são `None` |
| A-3 | Infra 3.4 | positivo | o A-1 aprovado | `consultar_saldo()` às `T0 + 2h` e às `T0 + 25h` | às `T0 + 2h`: liberado 0,00 e a liberar 123,76; às `T0 + 25h`: liberado 123,76 e a liberar 0,00 (com o limite inclusivo) |
| A-4 | Infra 3.5 | positivo | o A-1 aprovado; `depositar(Decimal("1000.00"))` e `registrar_saida(Decimal("50.00"), descricao="repasse")` às `T0 + 3h` | `listar_movimentos(T0, T0 + 4h)` | quatro movimentos em ordem: `pagamento` +125,00 com o `id_externo` de C; `tarifa` −1,24 com o mesmo `id_externo`; `deposito` +1000,00; `saida` −50,00; os ids são estáveis entre consultas |
| A-5 | Interface | negativo | o arranjo | `listar_movimentos` com instante sem fuso; com `desde > ate`; `depositar(0)`, `depositar(-1)` e `depositar(1.0)` | `InstanteSemFuso`; `ValueError`; `ValueError` nos três |
| A-6 | E07-01 | negativo | `indisponivel()` | `consultar_saldo()` e `listar_movimentos(...)`; depois `normalizar()` e as mesmas chamadas | `ProvedorIndisponivel` nas duas; depois, as respostas normais |
| A-7 | E07-01 | negativo | `falhar_proximas(1, operacao="consultar_saldo")` | duas chamadas a `consultar_saldo()` | a primeira levanta `ProvedorIndisponivel` e a segunda responde |
| A-8 | E07-03, cenário 37 | positivo | o A-1 aprovado | sincronizar C | `PagamentoNoProvedor.tarifa = 1.24` e `liberado_no_provedor_em = T0 + 25h`; a `ConsultaDoPagamento` sem divergência |
| A-9 | E07-03 | negativo | o A-8 sincronizado; a sincronização de uma resposta montada com `tarifa = 2.00` | sincronizar | a tarifa gravada continua 1,24; a consulta registrada com a divergência `tarifa`; um log `warning` |
| A-10 | E07-03 | positivo | C aprovado, mas a resposta montada sem `tarifa` e sem `liberado_em`; depois uma resposta com os dois | duas sincronizações | depois da primeira, os dois campos nulos; depois da segunda, preenchidos, sem divergência |
| A-11 | Simulador | positivo | o A-1 aprovado | `ajustar_saldo(Decimal("-0.50"))`; `consultar_saldo()` às `T0 + 25h` | um movimento `ajuste` −0,50 na lista; liberado 123,26 |
| A-12 | E08-07 | positivo e negativo | um administrador e o simulador configurado | `POST` nos formulários "Depositar na conta" (R$ 1.000,00) e "Registrar saída da conta" (R$ 50,00, "repasse"); depois com valor `1.000,00` e com `-5` | dois movimentos novos; nos inválidos, a mensagem de erro do formulário e nenhum movimento; comprador e fornecedor recebem 403, e sem o simulador configurado, 404 |
| A-13 | E08-07 A-9 | positivo | as rotas de `config/urls.py` | o teste de fronteira | as rotas de `apps.simulador_pagamentos` são exatamente as sete; as de `apps.pagamentos` continuam `{"pagamentos_avisos"}` |
| A-14 | E07-01 | concorrência | C pendente, com a tarifa do A-1 | duas aprovações de C em paralelo pelo controle | um único movimento `pagamento` e um único `tarifa` |
| A-16 | Coerência com o Mercado Pago | positivo | o simulador às `T0 + 2h` | `consultar_saldo()` | `referente_a == consultado_em == T0 + 2h`; nenhum movimento do simulador tem o tipo `outro` |
| A-17 | L-11, decisão de 2026-10-22 | positivo | um dublê do provedor que guarda os argumentos de `verificar_aviso` | `POST /pagamentos/avisos/?data.id=123&type=payment` com um corpo válido | o dublê recebe os parâmetros `{"data.id": "123", "type": "payment"}`, o corpo e os cabeçalhos; o resultado é o da E07-05 |
| A-18 | E07-05 | negativo | o simulador configurado | os avisos da E07-05 (válido, repetido, assinatura errada, corpo grande), agora com uma query string qualquer | os mesmos códigos e registros da E07-05; nenhum log leva a query string |
| A-15 | Interface | positivo | `reiniciar()` depois do A-4 | `listar_movimentos` e `consultar_saldo` | lista vazia e saldo zero; os planos de tarifa e liberação de volta a zero |

## Mapeamento para testes

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-7, A-11, A-14 a A-16 | `tests/tecnicos/test_pagamentos_simulador.py` |
| A-8 a A-10 | `tests/tecnicos/test_pagamentos_sincronizacao.py` |
| A-12 | `tests/tecnicos/test_simulador_pagamentos_tela.py` |
| A-17 e A-18 | `tests/tecnicos/test_pagamentos_avisos.py` |
| A-13 | `tests/tecnicos/test_pagamentos_fronteiras.py` |
