# Restauração do banco

Procedimento de restauração do Orgânicos Méier (infraestrutura 6; E16-05). Vale para a homologação e, depois, para a produção (fase 2a). Escrito para o responsável pelo projeto, com o procedimento à mão.

As três camadas de recuperação:
1. restauração do Neon a um instante (Caminho A);
2. `pg_dump` diário cifrado no Cloudflare R2 (Caminho B), com perda máxima de 24 horas;
3. conciliação com o provedor de pagamentos.

## 1. Quando restaurar e quem decide

Decide o **responsável pelo projeto**. Restaura-se quando o banco está perdido ou corrompido, ou quando um dado errado precisa ser desfeito e não há outro jeito. Antes de começar, anote o motivo e o instante em que o problema começou.

## 2. Congelar

Nada pode mudar rodadas durante a restauração e a conferência. Sem o worker não há tarefas, prazos automáticos nem envios.

1. Pare o worker: `fly scale count worker=0` (no app de homologação, ou no de produção quando houver).
2. Bloqueie o tráfego público (por exemplo, `fly scale count web=0`, ou a regra de acesso do provedor).
3. Os prazos continuam valendo: o relógio não para. Depois da restauração, eles são reconferidos (seção 5).

## 3. Caminho A, Neon

Restauração a um instante, num branch novo.

1. No console do Neon, crie um branch novo a partir do projeto, no instante `R` desejado (restauração a um ponto no tempo).
2. Copie a URL de **conexão direta** do branch (sem `-pooler`), com `sslmode=require`.
3. Troque o `DATABASE_URL` da aplicação: `fly secrets set DATABASE_URL=<url do branch restaurado>`.

## 4. Caminho B, backup externo

Para perda do próprio Neon (conta, projeto ou região).

1. Localize o objeto mais recente no bucket de backups do R2 (`banco/<ambiente>/<AAAA>/<MM>/organicos-<ambiente>-<AAAAMMDD>T<HHMMSS>Z.dump.age`).
2. Baixe o objeto e decifre com a chave privada do `age`, guardada pelo responsável **fora do Fly.io**: `age --decrypt -i <chave-privada.txt> -o banco.dump <objeto>.age`.
3. Crie um banco vazio (branch novo do Neon).
4. Restaure: `pg_restore --no-owner --no-privileges --dbname "<url direta do banco vazio>" banco.dump`.
5. Troque o `DATABASE_URL` da aplicação, como no Caminho A.

## 5. Conferir

Com o `DATABASE_URL` trocado, abra um console na aplicação (`fly ssh console`) e rode:

```
python manage.py conferir_restauracao
```

O comando só lê. Ele imprime sete seções e termina com "Conferência: <n> falha(s), <m> atenção(ões)." O código de saída é 1 com alguma `FALHA`. Com `--antes-de AAAA-MM-DDTHH:MM` (horário de Brasília), a última seção mostra só os movimentos anteriores ao instante, para comparar com o extrato.

| Seção | `FALHA` ou `ATENÇÃO` | O que fazer |
|---|---|---|
| Ponto recuperado | só informa | Compare o último movimento e a última auditoria com o instante `R`; tudo que aconteceu depois está perdido. |
| Invariante financeiro | `FALHA`: diferença negativa | Não reative. O saldo do provedor não cobre o dinheiro de terceiros: investigue o livro-razão e o extrato antes de seguir. `ATENÇÃO` (provedor indisponível): repita depois. |
| Estoque | `FALHA`: reservado acima do estoque | Não reative. Corrija a rodada indicada (fornecedor e produto) antes de abrir ao público. |
| Prazos encerrados | `ATENÇÃO` | Os prazos vencidos durante a indisponibilidade continuam valendo. Confira cada rodada listada no painel. |
| Pendências com o provedor | `ATENÇÃO` | Chamadas, devoluções e envios pendentes serão retomados pelo worker ao voltar; acompanhe até zerar. |
| Conciliação | `ATENÇÃO` | O worker concilia os dias em atraso, em ordem, depois de voltar; acompanhe. |
| Reconferir com o extrato | `ATENÇÃO` | Aportes, repasses, retiradas de receita e devoluções excepcionais feitos depois do ponto recuperado não estão no banco: compare com o extrato e os comprovantes e registre o que faltar. |

## 6. Reativar

1. Traga o worker de volta: `fly scale count worker=1`.
2. Libere o tráfego: `fly scale count web=1`.
3. Acompanhe o painel do administrador (E15-05) e os alertas até todas as tarefas ficarem "Em dia" e o invariante estar em ordem.

## 7. Avisar os afetados

Quando a indisponibilidade ou a perda atingiu compradores ou fornecedores, avise por comunicado (E04): o que aconteceu, o que foi desfeito e o que eles precisam refazer.

## 8. Guarda da chave privada

- **Onde fica:** a chave privada do `age` fica só com o responsável, fora do Fly.io (cofre de senhas ou cópia offline). A aplicação só conhece a chave pública (`BACKUP_CHAVE_PUBLICA_AGE`).
- **Quem tem cópia:** o responsável e uma cópia offline guardada por ele. Registre aqui quem mais tiver acesso.
- **Se a chave se perder:** os backups antigos ficam ilegíveis. Gere um par novo (`age-keygen`), troque `BACKUP_CHAVE_PUBLICA_AGE` (`fly secrets set`) e faça um backup na hora (`python manage.py backup_externo`).

## 9. Teste cronometrado

O RTO só é definido depois de um teste de restauração cronometrado, repetido todo trimestre. Roteiro (executado em homologação, na E16-08):

1. registrar um estado conhecido, com uma rodada passando por pagamento pelo simulador e uma devolução;
2. anotar o instante `R`;
3. criar depois de `R` um dado que não deve sobreviver (por exemplo, um comunicado);
4. iniciar o cronômetro;
5. restaurar pelo Caminho A até `R`;
6. rodar `python manage.py conferir_restauracao`;
7. confirmar que o dado posterior a `R` sumiu e que o estado conhecido está presente;
8. parar o cronômetro quando a aplicação responder com os dados conferidos.

Depois, repetir pelo Caminho B com o backup mais recente.

### Registro dos testes

| Data | Caminho | Ponto recuperado | Início | Fim | Duração | Resultado da conferência | Observações |
|---|---|---|---|---|---|---|---|
| — | — | — | — | — | — | — | Nenhum teste executado ainda (E16-08). |

## 10. RTO e RPO

- **RPO:** minutos pela restauração do Neon (Caminho A) e até 24 horas pelo backup externo (Caminho B), como na infraestrutura 6.
- **RTO:** a definir depois do primeiro teste cronometrado (E16-08): a maior duração medida, arredondada para cima para a meia hora seguinte.
- **Repetição:** o teste se repete a cada trimestre.
