# E01-02 — Critérios de aceitação

Cada critério precisa de um teste automatizado escrito antes do código, com falha observada (Red).

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Infra 4.12 | positivo | a entrada `"7.99"` | converto para dinheiro | obtenho `Decimal("7.99")` |
| A-2 | Infra 4.12 | positivo | a entrada `"8"` | converto para dinheiro | obtenho `Decimal("8.00")` |
| A-3 | Spec §9 (R-1) | negativo | a entrada `"7.999"` | converto para dinheiro | `ValorInvalido` por excesso de casas |
| A-4 | Infra 4.12, T-50 | negativo | a entrada `7.99` como `float` | converto para dinheiro ou quantidade | `ValorInvalido` por tipo |
| A-5 | Infra 4.12 | negativo | entradas `""`, `"abc"`, `"NaN"`, `"Infinity"`, `"1,5"`, `"1.000,00"`, `True`, `8` (int) | converto para dinheiro | `ValorInvalido` em cada caso |
| A-6 | Spec §4.2 (R-8) | positivo | a entrada `"0.25"` e a entrada `"2"` | converto para quantidade | obtenho `Decimal("0.25")` e `Decimal("2")` |
| A-7 | Spec §4.2 (R-8), T-50 | negativo | a entrada `"0.0001"` | converto para quantidade | `ValorInvalido` por excesso de casas |
| A-8 | Spec cenário 88, T-39 | positivo | `Decimal("7.99") * Decimal("0.25")` | arredondo a centavos | `Decimal("2.00")` |
| A-9 | Spec cenário 89, T-39 | positivo | `Decimal("2.50") * Decimal("0.25")` | arredondo a centavos | `Decimal("0.63")` |
| A-10 | Spec cenário 64, T-26 | positivo | `Decimal("12.99") * Decimal("0.35")` | arredondo a centavos | `Decimal("4.55")` |
| A-11 | Infra 4.12 | positivo | `Decimal("0.015")` | arredondo a centavos duas vezes | `Decimal("0.02")` nas duas vezes (idempotência) |
| A-12 | Infra 4.12 | negativo | um `float` | chamo `arredondar_centavos` | `ValorInvalido` por tipo |
| A-13 | Spec §4.2 | positivo | pares `(1.25, 0.25)`, `(0, 0.25)`, `(4, 2)` | verifico múltiplo exato | verdadeiro em todos |
| A-14 | Spec §4.2 | negativo | pares `(1.2, 0.5)`, `(3, 2)` | verifico múltiplo exato | falso em todos |
| A-15 | Spec §4.2 (R-8) | negativo | passo `0` ou `-0.25` | verifico múltiplo exato | `ValorInvalido` |
| A-16 | Infra 4.12 | positivo | um modelo de teste com campo de dinheiro e de quantidade | gravo `9999999999.99` e `999999999.999` no Postgres e releio | os valores voltam idênticos |
| A-17 | Infra 4.12 | negativo | o mesmo modelo de teste | valido (`full_clean`) com valor acima da precisão | erro de validação |
| A-18 | Infra 4.12 | positivo | `Decimal("1E+2")` | converto para dinheiro | `Decimal("100.00")` |
| A-19 | Infra 4.12, T-50 | negativo | o mesmo modelo de teste, com `7.99` como `float` no campo de dinheiro e `0.25` como `float` no de quantidade | valido (`full_clean`) | erro de validação nos dois campos |
| A-20 | Spec da fatia | negativo | `config/settings/base.py` e `config/settings/prod.py` | inspeciono `INSTALLED_APPS` com as configurações de produção | o app `apoio_testes` não aparece |

O modelo de teste de A-16, A-17 e A-19 fica no app `tests/apoio` e não gera migração da aplicação.

## Mapeamento para testes

| Critério | Arquivo e função de teste |
|---|---|
| A-1 a A-7, A-18 | `tests/tecnicos/test_nucleo_valores.py::test_conversao_*` |
| A-8 a A-12 | `tests/tecnicos/test_nucleo_valores.py::test_arredondamento_*` |
| A-13 a A-15 | `tests/tecnicos/test_nucleo_valores.py::test_multiplo_*` |
| A-16, A-17, A-19 | `tests/tecnicos/test_nucleo_campos_decimais.py` (requer `django_db`) |
| A-20 | `tests/tecnicos/test_nucleo_campos_decimais.py::test_app_de_testes_fora_da_producao` |
