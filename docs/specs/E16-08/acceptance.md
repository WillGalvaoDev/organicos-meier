# E16-08 — Critérios de aceitação

Agente 1 (especificador). Esta fatia é de operação e documentação. Os critérios dos documentos (A-1 a A-4) têm teste automatizado, que falha antes de os documentos existirem. Os de execução (A-5 a A-15) são conferidos pelo revisor nas evidências do `review.md`: comandos, saídas, capturas, datas e horas. Ele os reexecuta quando o acesso permitir. Como na E15-07, não há Red de comportamento novo.

| ID | Origem | Tipo | Dado | Quando | Então |
|---|---|---|---|---|---|
| A-1 | Regra 1 | positivo | `docs/operacao/homologacao.md` | ler | as seis seções da regra 1, na ordem; em "Variáveis e segredos", todas as variáveis obrigatórias de `prod.py` (conferido contra a lista extraída do código); nenhum valor que pareça segredo (sem `sk_`, `age1` seguido de mais de 20 caracteres, `postgres://` com senha ou `AKIA`). **Red esperado:** o arquivo não existe |
| A-2 | Regra 11 | positivo | `docs/relatorio-fase1.md` | ler | as nove seções da regra 11, na ordem; a seção "Critério de saída" com as três linhas da infraestrutura 7; o link para `docs/rastreabilidade-fase1.md` e para `docs/operacao/restauracao.md` |
| A-3 | Regras 6 e 11 | positivo | `docs/operacao/restauracao.md` | ler | a tabela "Registro dos testes" com pelo menos duas linhas (caminhos A e B), todas as colunas preenchidas; a seção "RTO e RPO" com um RTO numérico em horas |
| A-4 | Regra 10 | positivo | `docs/melhorias.md` | ler | nenhuma melhoria pendente sem decisão: cada pendente tem a fase indicada ("fase 2a" ou posterior), e cada descartada está em "Encerradas" com o motivo |
| A-5 | Regra 2 | positivo | o app de homologação | `fly releases` e `fly status` | a versão implantada corresponde ao commit da `main` com as E16-01 a E16-07; processos `web` e `worker` rodando em `gru` |
| A-6 | Regra 3.1 e 3.2 | positivo | a homologação | `curl -i https://<app>.fly.dev/saude/`; abrir `/entrar/` | 200 com `ok`; a página com os estáticos; o monitor do Better Stack verde |
| A-7 | Regra 3.3 | negativo | um erro provocado com um e-mail conhecido no texto | abrir o evento no Sentry | o ambiente `homologacao`; o e-mail trocado por `[removido]`; sem cookies, corpo ou query string |
| A-8 | Regra 3.4 e 3.5 | positivo | o worker parado por 20 minutos | acompanhar o Sentry e a caixa de e-mail | os check-ins `ok` antes da parada; o aviso de check-in perdido de `verificar-operacao` por e-mail; a normalização depois da volta |
| A-9 | Regra 3.6 | negativo | um avatar enviado na homologação | abrir a URL do objeto no R2 sem assinatura | acesso negado; o avatar abre pela view da aplicação |
| A-10 | Regra 3.7 | positivo | a homologação depois das 03:00 | listar o bucket de backups; abrir o painel | o objeto do dia com a chave da E16-04; a linha "Último backup externo" no painel |
| A-11 | Regra 3.8 | positivo | um convite para um endereço verificado no SES | emitir | o e-mail recebido, com o link para o domínio da homologação |
| A-12 | Regras 4 e 5 | positivo | o roteiro executado | ler o `review.md` | cada passo da regra 4 com data, hora e resultado; as recusas de isolamento da regra 5 |
| A-13 | Regra 6 | positivo | os dois testes de restauração | ler o registro e as saídas de `conferir_restauracao` | código de saída 0 nas duas; o dado criado depois de `R` ausente; o estado conhecido presente; a duração medida |
| A-14 | Regra 7 | positivo | o commit final da `main`; o branch de testes do Neon | ler o resultado do CI e da execução no Neon | a suíte verde nos dois, com o número de testes e a duração |
| A-15 | Regras 12 e 13 | positivo | o PR da fatia | ler o README e o relatório | a Parte 1 atualizada nas duas línguas com os mesmos fatos; a fase marcada como encerrada só se não houver bloqueador nem achado importante aberto |

| Critério | Arquivo de teste |
|---|---|
| A-1 a A-4 | `tests/ambiente/test_artefatos_de_implantacao.py` |
| A-5 a A-15 | evidências no `docs/specs/E16-08/review.md`, conferidas pelo revisor |
