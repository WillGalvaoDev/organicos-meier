"""A auditoria de cada ligação da matriz (E16-07, regra 2-G).

Uma linha por ligação `(entrada, afirmação, referência)`, com o que o teste prepara, a ação
que executa, o resultado que confere e o veredito da leitura do corpo do teste:
`"íntegra"` ou `"corrigida: ..."`. `tests/rastreabilidade/test_matriz.py` confere que as chaves
são exatamente as ligações da matriz. Veja as seis perguntas (a) a (f) na regra 2-G."""

AUDITORIA: dict[tuple[int | str, str, str], dict[str, str]] = {
    (
        1,
        "Convite com mais de 24h não cadastra usuário",
        "tests/tecnicos/test_convites_cadastro.py::test_fronteira_de_24h_no_post",
    ): {
        "preparacao": "convite emitido em T; relógio em T+24h menos 1 ms, em T+24h e em T+24h mais 1 ms (3 casos do parametrize)",
        "acao": "POST de cadastro (`_cadastrar`) com o token, cliente anônimo",
        "resultado": "em T+24h e +1 ms: 410 com INVALIDO e 0 compradores; em −1 ms: 302 e 1 comprador",
        "veredito": "íntegra",
    },
    (
        1,
        "Convite já consumido não cadastra usuário",
        "tests/tecnicos/test_convites_cadastro.py::test_convite_consumido_nao_pode_ser_reutilizado",
    ): {
        "preparacao": "convite com e-mail bia@x.com já usado por um cadastro bem-sucedido",
        "acao": "outro cliente faz GET e POST de cadastro no mesmo token",
        "resultado": "GET e POST: 410 com INVALIDO; continua 1 conta com o e-mail",
        "veredito": "íntegra",
    },
    (
        1,
        "Convite usado com outro e-mail não cadastra usuário",
        "tests/tecnicos/test_contas_google_cadastro.py::test_google_com_outro_email_nao_cadastra_pelo_convite",
    ): {
        "preparacao": "convite para bia@x.com iniciado pelo cliente; contagens de contas, sociais e e-mails lidas antes",
        "acao": "retorno do Google com outro e-mail (outra@x.com)",
        "resultado": "302 para /entrar/ com a recusa; contagens iguais; convite não consumido; sem sessão",
        "veredito": "íntegra",
    },
    (
        1,
        "Convite de fornecedor não permite escolher outro fornecedor",
        "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_fornecedor",
    ): {
        "preparacao": "convite de fornecedor do F1, e-mail ze@x.com; F2 existe",
        "acao": "POST de cadastro com fornecedor=F2 e papel=comprador extras",
        "resultado": "a conta criada é fornecedor e do F1, não do F2",
        "veredito": "íntegra",
    },
    (
        2,
        "Google sem conta e sem convite não cria conta nem abre sessão",
        "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada",
    ): {
        "preparacao": "nenhuma conta nem convite; contagens lidas antes",
        "acao": "retorno do Google com nova@x.com",
        "resultado": "`_recusado`: 302 para /entrar/, mensagem de recusa, sem sessão, contagens iguais",
        "veredito": "íntegra",
    },
    (
        2,
        "Link sem conta não recebe e-mail nem abre sessão",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_email_sem_conta_tem_a_mesma_resposta_e_nao_envia",
    ): {
        "preparacao": "conta ana@x.com existe e já pediu link; outbox e links limpos",
        "acao": "pedido de link para ninguem@x.com (sem conta)",
        "resultado": "mesma resposta (status e corpo) que a conta existente; 0 links; 0 e-mails. Não confere a ausência de sessão: sessão não existe sem link",
        "veredito": "íntegra",
    },
    (
        2,
        "Google com conta suspensa abre a sessão, mas a suspensão continua: sem adição de interesse",
        "tests/aceitacao/test_cenario_02_login_nao_contorna_suspensao.py::test_google_de_conta_suspensa_entra_mas_nao_adiciona_interesse",
    ): {
        "preparacao": "conta suspensa com e-mail EMAIL; rodada em interesse com produto (limite 20) criada em `_tentar_adicionar_interesse`",
        "acao": "retorno do Google; depois POST /interesses/ quantidade 3",
        "resultado": "sessão aberta (`_auth_user_id`); POST recebe 403; (R1) nenhuma parcela da conta",
        "veredito": "corrigida: assert acrescentado (sem parcela)",
    },
    (
        2,
        "Link com conta suspensa abre a sessão, mas a suspensão continua: sem adição de interesse",
        "tests/aceitacao/test_cenario_02_login_nao_contorna_suspensao.py::test_link_de_conta_suspensa_entra_mas_nao_adiciona_interesse",
    ): {
        "preparacao": "conta ativa pede link, depois é suspensa; rodada em interesse com produto",
        "acao": "POST do token do link; depois POST /interesses/ quantidade 3",
        "resultado": "sessão aberta; POST de interesse 403; nenhuma parcela da conta (`_verificar_sem_reserva`)",
        "veredito": "íntegra",
    },
    (
        2,
        "Google com conta banida ou removida não abre a sessão",
        "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
    ): {
        "preparacao": "conta com e-mail banido (ana@x.com, com espaço e caixa) ou conta removida; contagens antes (2 casos)",
        "acao": "retorno do Google com esse e-mail",
        "resultado": "`_recusado`: 302 para /entrar/, recusa, sem sessão, contagens iguais, nos casos banido e removido",
        "veredito": "íntegra",
    },
    (
        2,
        "Link com conta banida ou removida não recebe link e não abre a sessão",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link",
    ): {
        "preparacao": "conta ana@x.com removida, ou ativa com e-mail em EmailBanido; 3 grafias do e-mail e 2 casos",
        "acao": "pedido de link com a grafia do caso",
        "resultado": "200 com a resposta padrão, 0 links, 0 e-mails; (R2) sem sessão",
        "veredito": "corrigida: assert acrescentado (sem sessão)",
    },
    (
        3,
        "Duas reservas simultâneas para a última unidade não podem ambas ser aceitas",
        "tests/tecnicos/test_interesses_concorrencia.py::test_ultima_unidade_disputada_so_uma_vence",
    ): {
        "preparacao": "produto com limite 1 na rodada; duas compradoras A e B",
        "acao": "duas threads: A adiciona 1 segurando a trava, B adiciona 1 esperando",
        "resultado": "A sem exceção; B EstoqueInsuficiente com a mensagem de esgotado; reservado total 1; 1 parcela",
        "veredito": "íntegra",
    },
    (
        4,
        "Interesse abaixo do mínimo permanece aberto indefinidamente",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_abaixo_do_minimo_a_rodada_fica_aberta_indefinidamente",
    ): {
        "preparacao": "produto a R$ 10,00, limite 30, mínimo do fornecedor 100,00; 5 reservadas (R$ 50,00, abaixo); relógio em T0",
        "acao": "30 dias passam, envios processados e a fila é alocada",
        "resultado": "etapa segue INTERESSE, nada gravado, sem prazo, valor elegível abaixo do mínimo",
        "veredito": "corrigida: caracterização nova",
    },
    (
        4,
        "Atingir mínimo não inicia fechamento sozinho",
        "tests/tecnicos/test_interesses_progresso.py::test_atingir_o_minimo_nao_muda_a_etapa_nem_grava",
    ): {
        "preparacao": "produto a R$ 10,00, mínimo 50,00, 6 unidades de uma compradora (60,00)",
        "acao": "`progresso_da_rodada` com contagem das consultas",
        "resultado": "atingido é True; etapa segue INTERESSE; nenhum INSERT nem UPDATE durante o cálculo",
        "veredito": "íntegra",
    },
    (
        4,
        "Atingir mínimo não inicia fechamento sozinho",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_atingir_o_minimo_nao_inicia_nada_sozinho",
    ): {
        "preparacao": "produto a R$ 10,00 com limite 30; 20 reservadas (R$ 200,00, mínimo atingido); relógio congelado em T0",
        "acao": "30 dias passam, envios processados e a fila é alocada",
        "resultado": "etapa segue INTERESSE, nada gravado (`nada_gravado()`), sem prazo de fechamento",
        "veredito": "íntegra",
    },
    (
        5,
        "Administrador inicia fechamento e o término ocorre 24h depois",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_inicio_registra_ciclo_prazo_de_24_horas_e_auditoria",
    ): {
        "preparacao": "produto limite 20 a R$ 10,00 com 10 reservadas (mínimo 100,00 atingido); relógio em T0",
        "acao": "administrador inicia o fechamento (`iniciar_fechamento`)",
        "resultado": "etapa FECHAMENTO; prazo de início termina em `iniciado_em + 24h` (03/11/2026 13:30 UTC); auditoria com ciclo e valores",
        "veredito": "íntegra",
    },
    (
        5,
        "Queda temporária do mínimo não reinicia o relógio",
        "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_a_queda_e_a_recuperacao_do_minimo_nao_mexem_no_prazo",
    ): {
        "preparacao": "rodada com mínimo 100,00 e A com 12 reservadas; fechamento iniciado em T0 (término T)",
        "acao": "A reduz a 12 em T−2h (cai o mínimo); B compra 12 em T−1h; encerra o fechamento em T",
        "resultado": "prazo continua T depois da queda e depois da recuperação e do encerramento; etapa final FECHAMENTO_ENCERRADO",
        "veredito": "íntegra",
    },
    (
        5,
        "Queda temporária do mínimo não estende o relógio",
        "tests/tecnicos/test_rodadas_fechamento_prorrogacao.py::test_a_queda_do_minimo_nao_prorroga",
    ): {
        "preparacao": "rodada em fechamento (`em_fechamento`) com prazo T e A com interesse",
        "acao": "A reduz o interesse em T−2h",
        "resultado": "prazo segue T e não existe PrazoDoFechamento de prorrogação",
        "veredito": "íntegra",
    },
    (
        6,
        "Produto de R$ 10,00, múltiplo 12 e 18 unidades gera R$ 120,00 elegíveis, não R$ 180,00",
        "tests/tecnicos/test_interesses_progresso.py::test_dezoito_unidades_com_multiplo_doze",
    ): {
        "preparacao": "produto a R$ 10,00 com múltiplo 12; uma compradora com 18 reservadas",
        "acao": "`progresso_da_rodada(rodada)` sem comprador",
        "resultado": "elegível 12 (1 caixa, faltam 6, excedente 6); bruto 180,00 e elegível 120,00",
        "veredito": "íntegra",
    },
    (
        7,
        "Comprador A adiciona 8 unidades",
        "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_as_ultimas_adicoes_perdem_o_excedente",
    ): {
        "preparacao": "Ovos a R$ 10,00, múltiplo 12, sem mínimo; A adiciona 8 e B adiciona 10 antes do fechamento iniciado em T0",
        "acao": "`encerrar_fechamento(rodada)` em T",
        "resultado": "A fica com 8 reservadas depois do encerramento (a adição foi aceita e não perdeu unidades)",
        "veredito": "íntegra",
    },
    (
        7,
        "B adiciona 10: a primeira caixa contém 8 unidades de A",
        "tests/tecnicos/test_interesses_progresso.py::test_caixa_formada_pela_ordem_de_adicao",
    ): {
        "preparacao": "fixture: produto com múltiplo 12, A adicionou 8 e depois B adicionou 10",
        "acao": "progresso da rodada visto por A e por B",
        "resultado": "A: reservado 8, em caixas 8, excedente 0; total 18, elegível 12, 1 caixa",
        "veredito": "íntegra",
    },
    (
        7,
        "B adiciona 10: a primeira caixa contém 4 unidades de B",
        "tests/tecnicos/test_interesses_progresso.py::test_caixa_formada_pela_ordem_de_adicao",
    ): {
        "preparacao": "fixture: produto com múltiplo 12, A adicionou 8 e depois B adicionou 10",
        "acao": "progresso da rodada visto por A e por B",
        "resultado": "B: reservado 10, em caixas 4, excedente 6; total 18 e 1 caixa",
        "veredito": "íntegra",
    },
    (
        7,
        "B vê 6 excedentes",
        "tests/tecnicos/test_interesses_carrinho.py::test_caixas_so_com_as_unidades_do_proprio_comprador",
    ): {
        "preparacao": "produto com múltiplo 12; A adiciona 8 e B adiciona 10 pelo serviço",
        "acao": "A e B abrem `GET /carrinho/`",
        "resultado": 'a página de B mostra "Suas unidades em caixas: 4" e "excedentes: 6"; nenhuma página mostra o nome ou e-mail do outro',
        "veredito": "íntegra",
    },
    (
        7,
        "No fim do fechamento, essas 6 são removidas",
        "tests/tecnicos/test_rodadas_fechamento_encerramento.py::test_as_ultimas_adicoes_perdem_o_excedente",
    ): {
        "preparacao": "Ovos a R$ 10,00, múltiplo 12, sem mínimo; A adiciona 8 e B adiciona 10 antes do fechamento iniciado em T0",
        "acao": "`encerrar_fechamento(rodada)` em T",
        "resultado": "`removidas == {p.pk: 6}`; B fica ativa com 4 reservadas; etapa FECHAMENTO_ENCERRADO",
        "veredito": "íntegra",
    },
    (
        8,
        "A aumenta depois: o acréscimo fica depois das adições anteriores de B",
        "tests/tecnicos/test_interesses_servicos.py::test_acrescimo_posterior_vai_para_o_fim_da_fila",
    ): {
        "preparacao": "A adiciona 8, B adiciona 10 e A adiciona 2 (três parcelas)",
        "acao": "A reduz 2 (`reduzir_interesse`)",
        "resultado": "sequências pa8 < pb10 < pa2; quantidades originais 8, 10 e 2",
        "veredito": "íntegra",
    },
    (
        8,
        "Redução de A remove primeiro seu acréscimo mais recente",
        "tests/tecnicos/test_interesses_servicos.py::test_acrescimo_posterior_vai_para_o_fim_da_fila",
    ): {
        "preparacao": "A adiciona 8, B adiciona 10 e A adiciona 2 (três parcelas)",
        "acao": "A reduz 2 (`reduzir_interesse`)",
        "resultado": "a parcela de 2 fica REMOVIDA e a de 8 ATIVA com 8; resumo reservado 8",
        "veredito": "íntegra",
    },
    (
        9,
        "Fechamento encerrado com mínimo insuficiente volta para interesse",
        "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_nao_atingido_volta_para_interesse",
    ): {
        "preparacao": "mínimo 150,00; A 15, B 1, C 8 (C zera no fechamento); A e B somam 16 (R$ 120,00 em caixas)",
        "acao": "`encerrar_fechamento` em T",
        "resultado": "etapa final INTERESSE; A com 12 reservadas; B removida; aviso de retorno só a A e B; auditoria do encerramento",
        "veredito": "íntegra",
    },
    (
        9,
        "Com mínimo suficiente, fica bloqueado aguardando autorização de pagamento",
        "tests/tecnicos/test_rodadas_fechamento_retorno.py::test_minimo_atingido_aguarda_o_pagamento",
    ): {
        "preparacao": "mínimo 100,00; A 12 e B 6 (múltiplo 12); fechamento em T0",
        "acao": "`encerrar_fechamento` em T",
        "resultado": "etapa FECHAMENTO_ENCERRADO; sem aviso de retorno; auditoria com elegível 120,00, mínimo 100,00 e resultado aguardando_pagamento",
        "veredito": "íntegra",
    },
    (
        10,
        "Comprador de R$ 100,00 de produtos paga R$ 115,00 com serviço e frete",
        "tests/tecnicos/test_pedidos_calculo.py::test_cobranca_rateia_o_frete_pelos_produtos",
    ): {
        "preparacao": "dois compradores com produtos de R$ 100,00 e R$ 300,00 (itens de 10 unidades) e frete de R$ 40,00",
        "acao": "`calcular_cobranca` (função pura)",
        "resultado": "comprador 1: produtos 100,00, serviço 5,00, frete 10,00, total 115,00",
        "veredito": "íntegra",
    },
    (
        10,
        "Comprador de R$ 300,00 de produtos paga R$ 345,00 com serviço e frete",
        "tests/tecnicos/test_pedidos_calculo.py::test_cobranca_rateia_o_frete_pelos_produtos",
    ): {
        "preparacao": "dois compradores com produtos de R$ 100,00 e R$ 300,00 (itens de 10 unidades) e frete de R$ 40,00",
        "acao": "`calcular_cobranca` (função pura)",
        "resultado": "comprador 2: produtos 300,00, serviço 15,00, frete 30,00, total 345,00",
        "veredito": "íntegra",
    },
    (
        11,
        "Alterar o carrinho na etapa de pagamento não modifica pedidos congelados",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409",
    ): {
        "preparacao": "pagamento aberto; A (comprador com pedido) e o administrador; pedidos e itens fotografados antes",
        "acao": "A faz POST /interesses/ com 7 e com 5 para P1 (aumenta e reduz); o administrador faz POST com 7",
        "resultado": "A recebe 409 com a mensagem da etapa nas duas alterações; pedidos e itens iguais por conteúdo ao fotografado",
        "veredito": "corrigida: religada (antes só provava o comprador novo)",
    },
    (
        11,
        "Novo comprador na etapa de pagamento não modifica pedidos congelados",
        "tests/tecnicos/test_pedidos_abertura.py::test_composicao_fica_congelada_apos_a_abertura",
    ): {
        "preparacao": "pagamento aberto (A e B com pedidos); C é um comprador novo; (R4) pedidos e itens fotografados antes da tentativa de C",
        "acao": "C adiciona interesse (serviço); o administrador muda o preço de P1 para 20,00 e de P2 para 1,00",
        "resultado": "C recebe InteressesBloqueados; (R4) itens e totais iguais ao fotografado antes da tentativa",
        "veredito": "corrigida: assert reordenado (foto antes da tentativa)",
    },
    (
        11,
        "Alterar o preço de catálogo na etapa de pagamento não modifica pedidos congelados",
        "tests/tecnicos/test_pedidos_abertura.py::test_composicao_fica_congelada_apos_a_abertura",
    ): {
        "preparacao": "pagamento aberto (A e B com pedidos); C é um comprador novo; (R4) pedidos e itens fotografados antes da tentativa de C",
        "acao": "C adiciona interesse (serviço); o administrador muda o preço de P1 para 20,00 e de P2 para 1,00",
        "resultado": "itens e totais dos pedidos iguais depois das duas mudanças de preço; nenhum `preco_alterado` para A nem B",
        "veredito": "íntegra",
    },
    (
        12,
        "Antes de T0 + 24h a tentativa de pagamento é aceita",
        "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento",
    ): {
        "preparacao": "pedido X de A com pagamento aberto em T0; relógio em T0+24h menos 1 ms, depois em T0+24h e T0+24h mais 1 ms",
        "acao": "A pede o pagamento (`pedir_pagamento`) em cada instante",
        "resultado": "em −1 ms: 1 tentativa e 1 chamada criar_cobranca; em 24h e +1 ms: PagamentoRecusado prazo_encerrado com a mensagem; continua 1 tentativa e 1 chamada",
        "veredito": "íntegra",
    },
    (
        12,
        "A partir de T0 + 24h a tentativa é recusada, mesmo com a tarefa agendada atrasada",
        "tests/tecnicos/test_pedidos_prazos.py::test_com_o_bloqueio_parado_o_servidor_recusa_a_tentativa",
    ): {
        "preparacao": "pedido X com pagamento aberto; a tarefa de bloqueio não rodou; relógio em T0+24h+5min",
        "acao": "A pede o pagamento",
        "resultado": "PagamentoRecusado prazo_encerrado; 0 tentativas gravadas",
        "veredito": "íntegra",
    },
    (
        12,
        "Na margem operacional não é possível comprar",
        "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre",
    ): {
        "preparacao": "pagamento aberto; relógio em T0+30h (margem); pedidos fotografados; C é comprador novo; (R5) etapa lida ao fim",
        "acao": "C adiciona interesse; A faz POST de 7 e de 5; A pede o pagamento",
        "resultado": "C recebe InteressesBloqueados e A recebe 409 nos dois POST; o pedido de pagamento é recusado (prazo_encerrado)",
        "veredito": "íntegra",
    },
    (
        12,
        "Na margem operacional não é possível alterar pedidos",
        "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre",
    ): {
        "preparacao": "pagamento aberto; relógio em T0+30h (margem); pedidos fotografados; C é comprador novo; (R5) etapa lida ao fim",
        "acao": "C adiciona interesse; A faz POST de 7 e de 5; A pede o pagamento",
        "resultado": "POST de A recusado com 409 e os pedidos iguais por conteúdo ao fotografado em T0+30h",
        "veredito": "íntegra",
    },
    (
        12,
        "Na margem operacional não é possível criar cobranças",
        "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre",
    ): {
        "preparacao": "pagamento aberto; relógio em T0+30h (margem); pedidos fotografados; C é comprador novo; (R5) etapa lida ao fim",
        "acao": "C adiciona interesse; A faz POST de 7 e de 5; A pede o pagamento",
        "resultado": "`pedir_pagamento` levanta prazo_encerrado e o pedido continua com 0 tentativas",
        "veredito": "íntegra",
    },
    (
        12,
        "A rodada aguarda T0 + 48h",
        "tests/tecnicos/test_pedidos_prazos.py::test_na_margem_nada_se_reabre",
    ): {
        "preparacao": "pagamento aberto; relógio em T0+30h (margem); pedidos fotografados; C é comprador novo; (R5) etapa lida ao fim",
        "acao": "C adiciona interesse; A faz POST de 7 e de 5; A pede o pagamento",
        "resultado": "em T0+30h (R5) a rodada segue na etapa PAGAMENTO, sem avançar sozinha",
        "veredito": "corrigida: religada e assert acrescentado",
    },
    (
        12,
        "A rodada aguarda a decisão administrativa depois de T0 + 48h",
        "tests/tecnicos/test_pedidos_prazos.py::test_depois_de_48_horas_nada_acontece_sozinho",
    ): {
        "preparacao": "pedidos X e Y aguardando pagamento, X com tentativa criada; relógio em T0+49h",
        "acao": "roda o bloqueio, a reconsulta da margem e as chamadas pendentes",
        "resultado": "a rodada segue em PAGAMENTO; os dois pedidos seguem aguardando pagamento; nenhuma auditoria de apuração nem de cancelamento",
        "veredito": "íntegra",
    },
    (
        13,
        "Inadimplência em uma caixa invalida a caixa inteira",
        "tests/tecnicos/test_apuracao_viavel.py::test_estorno_proporcional_das_unidades_em_caixa_invalidada",
    ): {
        "preparacao": "AP-viável: X (A) pago, Y (B) não pago; apurado em T0+48h; a caixa de P2 fica inválida",
        "acao": "`_viavel` apura; o teste lê os reembolsos do pedido X",
        "resultado": "1 reembolso parcial do item de P2 com 4,000 unidades de X (as unidades de X na caixa) e obrigação de 23,59 do comprador",
        "veredito": "íntegra",
    },
    (
        13,
        "Compradores pagos na caixa invalidada recebem estorno proporcional",
        "tests/tecnicos/test_apuracao_viavel.py::test_estorno_proporcional_das_unidades_em_caixa_invalidada",
    ): {
        "preparacao": "AP-viável: X (A) pago, Y (B) não pago; apurado em T0+48h; a caixa de P2 fica inválida",
        "acao": "`_viavel` apura; o teste lê os reembolsos do pedido X",
        "resultado": "produtos 20,00, serviço 1,00, frete 2,59 e linha de 4,000 por 20,00; chave `caixa:<apuração>:<item>`; autor Sistema",
        "veredito": "íntegra",
    },
    (
        13,
        "Compradores pagos na caixa invalidada não são realocados para outra caixa",
        "tests/tecnicos/test_apuracao_viavel.py::test_a_fila_nao_reserva_na_rodada_apurada",
    ): {
        "preparacao": "AP-viável apurado; unidades de P2 de A pendentes depois da caixa invalidada",
        "acao": "lê o reservado total de P2 e chama `alocar_pendentes` do fornecedor",
        "resultado": "reservado de P2 igual a 0,000 e alocação igual a 0,000: as unidades não vão para outra caixa",
        "veredito": "corrigida: religada (antes só provava pendente sem autorização)",
    },
    (
        14,
        "Com produtos válidos pagos mantendo o mínimo, a diferença de frete de inadimplentes fica com o administrador",
        "tests/tecnicos/test_apuracao_aprovacao.py::test_aprovar_leva_a_apuracao_ao_livro_e_avanca_a_rodada",
    ): {
        "preparacao": "AP-viável V: X pago e Y não, apurado em T0+48h, relógio em T0+49h",
        "acao": "o administrador aprova o resultado (`aprovar_resultado`)",
        "resultado": "etapa aguardando_fornecedor; frete efetivo 22,00 e arrecadado 7,76; despesa DEFICIT_DE_FRETE de 14,24; destinos 60,00/3,00/7,76",
        "veredito": "corrigida: religada (antes só a tela mostrava o déficit)",
    },
    (
        14,
        "A diferença de frete de inadimplentes não altera cobranças concluídas",
        "tests/tecnicos/test_apuracao_aprovacao.py::test_o_pedido_e_o_pagamento_nao_mudam_e_a_custodia_zera",
    ): {
        "preparacao": "AP-viável V; pedidos, quitação de X e tentativas fotografados antes da aprovação",
        "acao": "o administrador aprova o resultado",
        "resultado": "pedidos, `quitado_por_id` de X e contagem de tentativas iguais ao fotografado; custódia de A zerada",
        "veredito": "corrigida: religada (a ligação anterior não comparava o pedido)",
    },
    (
        15,
        "Com pagos abaixo do mínimo, a rodada retorna para interesse",
        "tests/tecnicos/test_apuracao_telas.py::test_minimo_nao_atendido_devolve_a_rodada_e_mostra_o_estorno_integral",
    ): {
        "preparacao": "administrador com passkey; AP com mínimo 100,00; X pago (94,35); relógio no prazo",
        "acao": "POST de iniciar a apuração e leitura da página",
        "resultado": 'etapa interesse, mensagem "Mínimo não atendido", valor R$ 94,35 e sem o botão de aprovar',
        "veredito": "íntegra",
    },
    (
        15,
        "Com pagos abaixo do mínimo, os pagos mantêm interesses",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "A segue ativa com 6 em P1 e 4 em P2; totais reservados 6 e 4; sequências iguais",
        "veredito": "íntegra",
    },
    (
        15,
        "Com pagos abaixo do mínimo, os pagos têm estornos autorizáveis",
        "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_15_o_estorno_do_pago_na_rodada_devolvida_e_autorizavel",
    ): {
        "preparacao": "AP com mínimo insuficiente; X pago e a rodada devolvida ao interesse",
        "acao": "o administrador autoriza a devolução e as chamadas são processadas",
        "resultado": "antes: nenhuma parcela de devolução; depois: parcela concluída e 1 estorno simulado concluído",
        "veredito": "íntegra",
    },
    (
        15,
        "Com pagos abaixo do mínimo, os não pagos perdem itens",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "todas as parcelas de B ficam removidas",
        "veredito": "íntegra",
    },
    (
        16,
        "Novo fechamento pode começar com estorno antigo pendente",
        "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente",
    ): {
        "preparacao": "rodada devolvida ao interesse com a obrigação de X (estorno não autorizado); C pede 5 de P1",
        "acao": "o administrador inicia um novo fechamento",
        "resultado": "etapa fechamento, ciclo 2; nenhuma parcela de devolução criada; a obrigação de X continua única",
        "veredito": "íntegra",
    },
    (
        16,
        "Novo fechamento não mistura cobranças",
        "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente",
    ): {
        "preparacao": "rodada devolvida ao interesse com a obrigação de X (estorno não autorizado); C pede 5 de P1",
        "acao": "o administrador inicia um novo fechamento",
        "resultado": "o novo ciclo não cria parcela de devolução e a obrigação do pedido X segue única (count 1)",
        "veredito": "íntegra",
    },
    (
        16,
        "Novo fechamento não duplica estoque",
        "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; C com 3 pendentes de P1; X pago",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "reservado total de P1 9 (≤ 11) e de P2 4 (≤ 12); em cada parcela reservado mais pendente não passa do original",
        "veredito": "íntegra",
    },
    (
        17,
        "Webhook repetido não duplica o pagamento",
        "tests/tecnicos/test_pagamentos_avisos.py::test_aviso_repetido_nao_repete_efeitos",
    ): {
        "preparacao": "um aviso simulado de pagamento; fixture de sinais; relógio em T",
        "acao": "o aviso é enviado e processado, e reenviado 4 vezes",
        "resultado": "1 AvisoRecebido, 1 chamada ao provedor, nada a processar, 1 auditoria de situação e 1 sinal",
        "veredito": "íntegra",
    },
    (
        17,
        "Webhook repetido não duplica o pagamento",
        "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_nao_duplica_pagamento_pedido_e_mensagem",
    ): {
        "preparacao": "cenário com pedido X de A e cobrança c.p; aprovação em T0+2h",
        "acao": "o webhook chega 1 min depois e é repetido (REPETICOES) vezes",
        "resultado": "1 aviso, 1 pagamento, 1 destino, pedido pago, 1 auditoria de quitação e 1 notificação de pagamento confirmado",
        "veredito": "íntegra",
    },
    (
        17,
        "Webhook repetido não cria outro pedido nem muda a situação dele",
        "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_nao_cria_outro_pedido_nem_muda_a_situacao",
    ): {
        "preparacao": "pagamento já recebido e processado; pedidos e situações lidos depois",
        "acao": "o aviso é reemitido e entregue REPETICOES vezes",
        "resultado": "Pedido e SituacaoDoPedido iguais por conteúdo ao lido depois do primeiro webhook",
        "veredito": "íntegra",
    },
    (
        17,
        "Webhook repetido não duplica a mensagem formal (pedido formal por e-mail ao fornecedor)",
        "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_depois_do_envio_nao_duplica_o_pedido_formal",
    ): {
        "preparacao": "AF: pedido formal já enviado ao fornecedor; linhas, tentativas e e-mails lidos antes",
        "acao": "o aviso do pagamento de X é reemitido e entregue REPETICOES vezes; as tarefas rodam de novo",
        "resultado": "1 PedidoFormal, linhas iguais, 1 tentativa de envio e os e-mails iguais depois do reenvio",
        "veredito": "íntegra",
    },
    (
        17,
        "Webhook repetido não duplica a mensagem formal (pedido formal por e-mail ao fornecedor)",
        "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_antes_da_aprovacao_gera_um_so_pedido_formal",
    ): {
        "preparacao": "AP: X e Y pagos, cada aviso repetido 2 vezes antes da apuração e da aprovação",
        "acao": "apura e aprova o resultado; o pedido formal é processado",
        "resultado": "1 PedidoFormal com P1 11 e P2 12; 1 envio; sem segundo e-mail",
        "veredito": "íntegra",
    },
    (
        17,
        "Webhook repetido não duplica o estorno",
        "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_nao_duplica_estorno",
    ): {
        "preparacao": "pagamento aprovado em T0+49h e recebido em T0+50h (tardio)",
        "acao": "devolução autorizada e processada no simulador; aviso reemitido",
        "resultado": "1 obrigação, 1 parcela de devolução e 1 estorno simulado concluído",
        "veredito": "íntegra",
    },
    (
        18,
        "Falta de R$ 25,00 gera estorno de produtos de R$ 25,00, serviço de R$ 1,25 e frete de R$ 5,00",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_18_servico_e_frete_proporcionais",
    ): {
        "preparacao": "arranjo único: item de 8 unidades a R$ 12,50 em pedido pago",
        "acao": "o administrador registra ocorrência faltante de 2 unidades",
        "resultado": "produtos 25,00, serviço 1,25 e frete 5,00 no reembolso",
        "veredito": "íntegra",
    },
    (
        18,
        "O estorno da falta de R$ 25,00 soma R$ 31,25",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_18_servico_e_frete_proporcionais",
    ): {
        "preparacao": "arranjo único: item de 8 unidades a R$ 12,50 em pedido pago",
        "acao": "o administrador registra ocorrência faltante de 2 unidades",
        "resultado": "obrigação de devolução de 31,25",
        "veredito": "íntegra",
    },
    (
        19,
        "A suspensão esvazia os interesses",
        "tests/tecnicos/test_interesses_suspensao.py::test_suspensao_esvazia_os_interesses_e_a_reversao_nao_restaura",
    ): {
        "preparacao": "A com 4 de P, 2 de Q e 3 pendentes de R; sequências e quantidades originais fotografadas",
        "acao": "suspende A, depois reverte a suspensão e A adiciona de novo",
        "resultado": "3 parcelas, todas zeradas e removidas; reservado de P e Q igual a 0; auditoria do sistema lista as parcelas",
        "veredito": "íntegra",
    },
    (
        19,
        "A suspensão cancela pedidos não pagos",
        "tests/tecnicos/test_pedidos_moderacao.py::test_suspensao_cancela_o_pedido_nao_pago",
    ): {
        "preparacao": "pedido X de A não pago e pedido Z pago; composição fotografada antes",
        "acao": "o administrador suspende A (`suspender`)",
        "resultado": "X cancelado por suspensão em T0+3h; chamada de cancelamento da cobrança; Z segue pago; auditoria do sistema; composição igual",
        "veredito": "íntegra",
    },
    (
        19,
        "Pedidos pagos continuam disponíveis para retirada",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_19_o_suspenso_retira",
    ): {
        "preparacao": "pedido recebido e liberado para retirada; A é suspensa direto no banco; login refeito",
        "acao": "A abre o pedido e registra a retirada de 4 unidades de P1",
        "resultado": 'POST de retirada 302; 1 RetiradaDeItem; página do pedido 200 com "Retirada liberada em"; invariantes do congelado',
        "veredito": "íntegra",
    },
    (
        19,
        "Reversão não restaura automaticamente interesses antigos",
        "tests/tecnicos/test_interesses_suspensao.py::test_suspensao_esvazia_os_interesses_e_a_reversao_nao_restaura",
    ): {
        "preparacao": "A com 4 de P, 2 de Q e 3 pendentes de R; sequências e quantidades originais fotografadas",
        "acao": "suspende A, depois reverte a suspensão e A adiciona de novo",
        "resultado": "depois da reversão não há parcela ativa antiga; a nova parcela tem sequência maior que todas as anteriores",
        "veredito": "íntegra",
    },
    (
        20,
        "Remoção bloqueia o acesso: login por senha, link e Google não abrem sessão",
        "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite",
    ): {
        "preparacao": "conta ana@x.com com senha, removida pelo administrador",
        "acao": "tenta login por senha, pedido de link e retorno do Google; tenta novo convite com o e-mail",
        "resultado": "sem sessão por senha; nenhum e-mail de link; Google volta a /entrar/ sem sessão",
        "veredito": "íntegra",
    },
    (
        20,
        "Remoção bloqueia novo cadastro com o e-mail",
        "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite",
    ): {
        "preparacao": "conta ana@x.com com senha, removida pelo administrador",
        "acao": "tenta login por senha, pedido de link e retorno do Google; tenta novo convite com o e-mail",
        "resultado": "o convite para o e-mail removido levanta EmailEmUso e nenhum Convite é criado",
        "veredito": "íntegra",
    },
    (
        20,
        "A remoção mantém o pedido pago",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_20_o_pedido_pago_da_conta_removida_continua_pago",
    ): {
        "preparacao": "pedido pago de A; o administrador remove a conta de A (passkey)",
        "acao": "lê a conta e a situação do pedido depois da remoção",
        "resultado": "conta removida; pedido pago com pagamento quitador; o pedido ainda existe",
        "veredito": "íntegra",
    },
    (
        20,
        "A remoção mantém o histórico consultável pelo administrador",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_20_o_administrador_consulta_o_historico_financeiro_do_removido",
    ): {
        "preparacao": "pedido pago de A e conta de A removida; administrador autenticado por passkey",
        "acao": "GET /administracao/historico/",
        "resultado": "200 e a tabela lista as ações pedido.quitar e conta.remover",
        "veredito": "íntegra",
    },
    (
        21,
        "Fornecedor não consegue consultar dados de compradores",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
    ): {
        "preparacao": "arranjo AF com a conta do fornecedor F logada; pedido X de A",
        "acao": "9 acessos diretos (GET e POST) a pedido de comprador, pagar e telas financeiras",
        "resultado": 'as 9 respostas têm status 403 e a página não traz "Comprador A" nem "8,50"',
        "veredito": "íntegra",
    },
    (
        21,
        "Fornecedor não consegue consultar dados de outro fornecedor",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_rodada_de_outro_fornecedor_ou_inexistente_da_o_mesmo_404",
    ): {
        "preparacao": "fornecedor F logado; fornecedor G com rodada em interesse",
        "acao": "GET da rodada de G, do CSV do pedido formal de G e de uma rodada inexistente",
        "resultado": "as 3 respostas são 404 e têm o mesmo corpo",
        "veredito": "íntegra",
    },
    (
        21,
        "O fornecedor também é recusado por acesso direto à rota",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
    ): {
        "preparacao": "arranjo AF com a conta do fornecedor F logada; pedido X de A",
        "acao": "9 acessos diretos (GET e POST) a pedido de comprador, pagar e telas financeiras",
        "resultado": "as 9 rotas chamadas direto (inclui o POST de pagar) respondem 403",
        "veredito": "íntegra",
    },
    (
        22,
        "Liberação de retirada permite nova rodada imediatamente",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_22_nova_rodada_e_retirada_antiga",
    ): {
        "preparacao": "recebimento e liberação da retirada da rodada de A; nova rodada aberta por `_com_nova_rodada`; estado inicial fotografado",
        "acao": "retirada registrada depois da nova rodada",
        "resultado": "a nova rodada tem pk diferente e existe depois da liberação; invariantes do congelado e financeiro",
        "veredito": "íntegra",
    },
    (
        22,
        "A nova rodada não herda a reserva da anterior",
        "tests/tecnicos/test_liberacao_da_retirada.py::test_cenario_22_a_nova_rodada_nao_herda_a_reserva",
    ): {
        "preparacao": "rodada de A recebida e liberada; nova rodada com P1 limite 11; C é um comprador novo",
        "acao": "C define interesse de 11 em P1",
        "resultado": "a nova rodada está em interesse e C reserva as 11 unidades inteiras do limite",
        "veredito": "íntegra",
    },
    (
        22,
        "Retiradas antigas continuam registráveis por item",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_22_nova_rodada_e_retirada_antiga",
    ): {
        "preparacao": "recebimento e liberação da retirada da rodada de A; nova rodada aberta por `_com_nova_rodada`; estado inicial fotografado",
        "acao": "retirada registrada depois da nova rodada",
        "resultado": "a única RetiradaDeItem é de um item do pedido X da rodada antiga",
        "veredito": "íntegra",
    },
    (
        23,
        "Após sete dias, itens restantes aparecem como pendentes de decisão",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_23_prazo_e_descarte",
    ): {
        "preparacao": "recebimento e liberação; nova rodada; relógio em L+8 dias; descartes e reembolsos contados antes",
        "acao": "lê a página de retiradas; o administrador registra descarte de 4 de P2 (X) e 5 de P1 (Y)",
        "resultado": 'a página mostra "Prazo encerrado — pendentes de decisão" e ainda não existe DescarteDeItem',
        "veredito": "íntegra",
    },
    (
        23,
        "Após sete dias, o tempo sozinho não registra descarte",
        "tests/tecnicos/test_retirada.py::test_cenario_23_o_tempo_nao_descarta",
    ): {
        "preparacao": "pedido recebido e liberado; 4 de P1 retiradas; situação lida em L e em L+8 dias",
        "acao": "`situacao_da_retirada` antes e depois dos 8 dias",
        "resultado": "prazo encerrado só depois; vencidos listam P1 2 e P2 4; nenhum descarte; saldos dos itens iguais",
        "veredito": "íntegra",
    },
    (
        23,
        "Somente a ação administrativa registra descarte efetivo",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_23_prazo_e_descarte",
    ): {
        "preparacao": "recebimento e liberação; nova rodada; relógio em L+8 dias; descartes e reembolsos contados antes",
        "acao": "lê a página de retiradas; o administrador registra descarte de 4 de P2 (X) e 5 de P1 (Y)",
        "resultado": "nada registrado só com o tempo e a página; depois do POST do administrador há 2 descartes, sem reembolso novo e o saldo do item zerado",
        "veredito": "corrigida: religada (reúne o antes e o depois)",
    },
    (
        24,
        "Falha no WhatsApp não desfaz o pagamento",
        "tests/tecnicos/test_pedidos_quitacao.py::test_falha_do_whatsapp_nao_desfaz_a_quitacao",
    ): {
        "preparacao": "A com telefone e consentimento; o simulador do WhatsApp falha sempre; pagamento aprovado em T0+2h",
        "acao": "o aviso chega e as tarefas rodam 3 vezes (0, 1 e 10 min)",
        "resultado": "o pedido segue pago e não há Envio de WhatsApp bem-sucedido",
        "veredito": "íntegra",
    },
    (
        24,
        "Falha no WhatsApp não impede a notificação no site",
        "tests/tecnicos/test_pedidos_quitacao.py::test_falha_do_whatsapp_nao_desfaz_a_quitacao",
    ): {
        "preparacao": "A com telefone e consentimento; o simulador do WhatsApp falha sempre; pagamento aprovado em T0+2h",
        "acao": "o aviso chega e as tarefas rodam 3 vezes (0, 1 e 10 min)",
        "resultado": 'o e-mail fica enviado e /notificacoes/ mostra "Pagamento confirmado: F"',
        "veredito": "íntegra",
    },
    (
        24,
        "Falha no WhatsApp não impede o estado correto no site",
        "tests/tecnicos/test_pedidos_abertura.py::test_falha_do_whatsapp_nao_desfaz_a_abertura",
    ): {
        "preparacao": "A com telefone e consentimento; o WhatsApp falha sempre; pagamento aberto",
        "acao": "3 rodadas de envio (0, 1 e 10 min) e leitura da página de A",
        "resultado": '2 pedidos; WhatsApp falhou com 3 tentativas; e-mails enviados; etapa PAGAMENTO; página com "Pagamento aberto: F"',
        "veredito": "íntegra",
    },
    (
        25,
        "Pagamento iniciado antes de T0 + 24h e aprovado em T0 + 30h quita o pedido",
        "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_25_aprovado_em_30h_e_avisado_depois_de_48h_quita_o_pedido",
    ): {
        "preparacao": "pedido X com cobrança c.p criada antes de T0+24h",
        "acao": "aprovada em T0+30h e o aviso chega em T0+50h",
        "resultado": "destino quita sem motivo; pedido pago com quitado_em T0+30h; nenhuma obrigação de devolução",
        "veredito": "íntegra",
    },
    (
        25,
        "A quitação vale mesmo que a notificação chegue depois de T0 + 48h",
        "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_25_aprovado_em_30h_e_avisado_depois_de_48h_quita_o_pedido",
    ): {
        "preparacao": "pedido X com cobrança c.p criada antes de T0+24h",
        "acao": "aprovada em T0+30h e o aviso chega em T0+50h",
        "resultado": "primeiro aviso em T0+50h e mesmo assim pago com quitado_em T0+30h",
        "veredito": "íntegra",
    },
    (
        26,
        "Pagamento aprovado depois de T0 + 48h não quita o pedido",
        "tests/tecnicos/test_pedidos_quitacao.py::test_aprovacao_depois_da_margem_gera_devolucao",
    ): {
        "preparacao": "pedido X com cobrança c.p; aprovação em T0+49h e aviso em T0+50h; log de aviso capturado",
        "acao": "o aviso é processado (`_aprovar_e_receber`)",
        "resultado": "destino devolução com motivo aprovado_apos_a_margem; pedido segue aguardando pagamento; sem aviso de confirmação; auditoria e log de aviso",
        "veredito": "íntegra",
    },
    (
        26,
        "Pagamento aprovado depois de T0 + 48h gera obrigação de devolução integral",
        "tests/tecnicos/test_apuracao_inicio.py::test_reconsulta_registra_o_pagamento_aprovado_depois_de_48_horas",
    ): {
        "preparacao": "X pago; Y pago em PRAZO+1 ms sem aviso entregue; relógio em T0+49h",
        "acao": "`iniciar_apuracao` reconsulta o pagamento de Y",
        "resultado": "destino devolução (aprovado_apos_a_margem); obrigação integral igual ao total de Y; Y cancelado por inadimplência",
        "veredito": "íntegra",
    },
    (
        26,
        "A devolução do pagamento tardio pode ser feita pela plataforma",
        "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_17_webhook_repetido_nao_duplica_estorno",
    ): {
        "preparacao": "pagamento aprovado em T0+49h e recebido em T0+50h (tardio)",
        "acao": "devolução autorizada e processada no simulador; aviso reemitido",
        "resultado": "1 obrigação, 1 parcela de devolução e 1 estorno simulado concluído do pagamento tardio",
        "veredito": "corrigida: religada (antes o teste usava a obrigação de um parcial)",
    },
    (
        26,
        "A devolução do pagamento tardio pode ser feita pela devolução excepcional",
        "tests/aceitacao/test_cenarios_17_25_webhook_e_aprovacao_tardia.py::test_cenario_26_pagamento_tardio_devolvido_pela_devolucao_excepcional",
    ): {
        "preparacao": "pagamento tardio (T0+49h, aviso T0+50h) com obrigação integral; o provedor recusa o estorno (prazo_vencido); comprovante",
        "acao": "autoriza a devolução, confirma a devolução excepcional (transferência)",
        "resultado": "parcela elegível e depois concluída fora da plataforma; confirmação do pedido e da compradora; obrigação liquidada",
        "veredito": "corrigida: caracterização nova (R6)",
    },
    (
        27,
        "A apuração final não começa antes de T0 + 48h",
        "tests/tecnicos/test_pedidos_prazos.py::test_a_apuracao_so_pode_comecar_em_48_horas",
    ): {
        "preparacao": "pedidos X e Y pagos aos 30 e 40 min; abertura de T0",
        "acao": "`pode_iniciar_apuracao` em MARGEM−1 ms e em MARGEM (função pura)",
        "resultado": "falso em T0+48h−1 ms e verdadeiro em T0+48h; a rodada segue em PAGAMENTO; nenhuma auditoria de apuração",
        "veredito": "íntegra",
    },
    (
        27,
        "A apuração não começa antes de T0 + 48h mesmo com todos os pedidos pagos",
        "tests/tecnicos/test_apuracao_inicio.py::test_antes_de_48_horas_e_recusada_sem_consulta_nem_escrita",
    ): {
        "preparacao": "AP com X e Y pagos; relógio em PRAZO−1 ms; estado fotografado",
        "acao": "`iniciar_apuracao` pelo administrador",
        "resultado": "ApuracaoRecusada antes_do_prazo com a data 04/11/2026 10:00 (Brasília); nenhuma consulta ao provedor; estado igual",
        "veredito": "íntegra",
    },
    (
        27,
        "A partir de T0 + 48h a apuração só começa com autorização do administrador",
        "tests/tecnicos/test_apuracao_inicio.py::test_so_o_administrador_apura",
    ): {
        "preparacao": "AP em T0+48h; estado fotografado",
        "acao": "`iniciar_apuracao` com A (comprador), uma conta de fornecedor e None como autor",
        "resultado": "PermissionDenied nos três e estado igual ao fotografado",
        "veredito": "íntegra",
    },
    (
        28,
        "O administrador não consegue prorrogar o prazo de pagamento",
        "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos",
    ): {
        "preparacao": "administrador logado; pedido aberto; rotas e formulários varridos pelos nomes de prazo, t0 e margem",
        "acao": "varredura das rotas e POST de prorrogação do fechamento fora do fechamento",
        "resultado": "nenhuma rota com t0, margem ou prazo de pagamento; nenhum campo de formulário com esses nomes; a prorrogação fora do fechamento dá 409",
        "veredito": "íntegra",
    },
    (
        28,
        "O administrador não consegue prorrogar a margem operacional",
        "tests/tecnicos/test_pedidos_prazos.py::test_o_t0_nao_muda_nem_por_sql",
    ): {
        "preparacao": "pedido aberto com T0 (prazo e margem derivados)",
        "acao": "altera T0 por `save()`, por `update()` e por SQL direto",
        "resultado": "as três tentativas falham (RegistroImutavel e DatabaseError) e prazo e fim da margem seguem PRAZO e MARGEM",
        "veredito": "íntegra",
    },
    (
        28,
        "O administrador continua podendo prorrogar o fechamento",
        "tests/tecnicos/test_rodadas_fechamento_prorrogacao.py::test_prorrogacao_estende_o_prazo_e_audita",
    ): {
        "preparacao": "rodada em fechamento com término T; relógio em T−2h",
        "acao": "o administrador prorroga o fechamento para T+24h",
        "resultado": "devolve o novo prazo; prazos de origem INICIO e PRORROGACAO; auditoria com rodada, ciclo e prazos",
        "veredito": "íntegra",
    },
    (
        29,
        "O aporte inicial de R$ 1.000,00 entra na reserva",
        "tests/aceitacao/test_cenario_29_aporte.py::test_o_aporte_inicial_vai_so_para_a_reserva",
    ): {
        "preparacao": "mundo financeiro montado (fornecedores A e B, rodadas, contas)",
        "acao": "o administrador registra o aporte de 1.000,00 (`registrar_aporte`)",
        "resultado": "saldo da reserva 1.000,00 e livre 1.000,00",
        "veredito": "íntegra",
    },
    (
        29,
        "O aporte inicial não altera a receita de serviço",
        "tests/aceitacao/test_cenario_29_aporte.py::test_o_aporte_inicial_vai_so_para_a_reserva",
    ): {
        "preparacao": "mundo financeiro montado (fornecedores A e B, rodadas, contas)",
        "acao": "o administrador registra o aporte de 1.000,00 (`registrar_aporte`)",
        "resultado": "nenhuma conta de receita de serviço com saldo diferente de zero",
        "veredito": "íntegra",
    },
    (
        29,
        "O aporte inicial não altera outra destinação",
        "tests/aceitacao/test_cenario_29_aporte.py::test_o_aporte_inicial_vai_so_para_a_reserva",
    ): {
        "preparacao": "mundo financeiro montado (fornecedores A e B, rodadas, contas)",
        "acao": "o administrador registra o aporte de 1.000,00 (`registrar_aporte`)",
        "resultado": "contas de obrigação de fornecedor e (R7) todas as contas fora da reserva sem saldo",
        "veredito": "corrigida: assert acrescentado (todas as demais destinações)",
    },
    (
        30,
        "A tarifa do provedor é registrada como despesa",
        "tests/aceitacao/test_cenario_30_tarifa.py::test_a_tarifa_e_registrada_como_despesa_e_nao_chega_ao_comprador",
    ): {
        "preparacao": "tarifa do Pix de 1,00%; pedido composto de 100,00 + 5,00 + 20,00; pedido e itens fotografados antes",
        "acao": "o comprador paga (cobrança aprovada e sincronizada)",
        "resultado": "1 Despesa tipo tarifa de 1,25; 1 movimento de tarifa; saldo de despesas −1,25",
        "veredito": "íntegra",
    },
    (
        30,
        "A tarifa é coberta pela receita de serviço",
        "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_30_a_tarifa_e_coberta_pela_receita_de_servico",
    ): {
        "preparacao": "tarifa de 1,00%; AP com X pago; aporte de 1.000,00; a despesa de tarifa existe; apuração registrada no livro",
        "acao": "a apuração no livro cobre a tarifa pela receita de serviço",
        "resultado": 'pendente da despesa 1,25 antes e 0,00 depois; justificativa "Tarifa coberta pela receita de serviço"',
        "veredito": "íntegra",
    },
    (
        30,
        "A tarifa não altera obrigações com fornecedores",
        "tests/aceitacao/test_cenario_30_tarifa.py::test_a_tarifa_e_registrada_como_despesa_e_nao_chega_ao_comprador",
    ): {
        "preparacao": "tarifa do Pix de 1,00%; pedido composto de 100,00 + 5,00 + 20,00; pedido e itens fotografados antes",
        "acao": "o comprador paga (cobrança aprovada e sincronizada)",
        "resultado": "(R8) nenhuma conta de obrigação de fornecedor com saldo depois da tarifa",
        "veredito": "corrigida: assert acrescentado",
    },
    (
        30,
        "A tarifa não altera valores cobrados de compradores",
        "tests/aceitacao/test_cenario_30_tarifa.py::test_a_tarifa_e_registrada_como_despesa_e_nao_chega_ao_comprador",
    ): {
        "preparacao": "tarifa do Pix de 1,00%; pedido composto de 100,00 + 5,00 + 20,00; pedido e itens fotografados antes",
        "acao": "o comprador paga (cobrança aprovada e sincronizada)",
        "resultado": "pedido e itens iguais por conteúdo ao fotografado; custódia do comprador 100,00/5,00/20,00",
        "veredito": "íntegra",
    },
    (
        31,
        "O déficit de frete é registrado separadamente",
        "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre",
    ): {
        "preparacao": "AP com X pago; aporte de 1.000,00; valores cobrados fotografados; apuração no livro",
        "acao": "o administrador cobre o déficit: 3,75 pela receita e 6,25 pela reserva",
        "resultado": "relatório com efetivo 30,00, arrecadado 20,00 e déficit 10,00; a Despesa deficit_frete é um registro à parte",
        "veredito": "íntegra",
    },
    (
        31,
        "O déficit de frete é coberto",
        "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre",
    ): {
        "preparacao": "AP com X pago; aporte de 1.000,00; valores cobrados fotografados; apuração no livro",
        "acao": "o administrador cobre o déficit: 3,75 pela receita e 6,25 pela reserva",
        "resultado": "`deficit_coberto == 10,00`; frete do ciclo 30,00; receita da rodada 0,00",
        "veredito": "íntegra",
    },
    (
        31,
        "O déficit de frete é coberto pela reserva",
        "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre",
    ): {
        "preparacao": "AP com X pago; aporte de 1.000,00; valores cobrados fotografados; apuração no livro",
        "acao": "o administrador cobre o déficit: 3,75 pela receita e 6,25 pela reserva",
        "resultado": "a reserva fica em 993,75 (1.000,00 − 6,25) depois da cobertura de 6,25",
        "veredito": "íntegra",
    },
    (
        31,
        "O déficit de frete não gera cobrança retroativa a compradores",
        "tests/aceitacao/test_cenario_31_deficit_de_frete.py::test_o_deficit_aparece_na_apuracao_e_o_administrador_o_cobre",
    ): {
        "preparacao": "AP com X pago; aporte de 1.000,00; valores cobrados fotografados; apuração no livro",
        "acao": "o administrador cobre o déficit: 3,75 pela receita e 6,25 pela reserva",
        "resultado": "produtos, serviço e frete dos pedidos iguais aos valores lidos antes da apuração",
        "veredito": "íntegra",
    },
    (
        32,
        "Recursos do fornecedor A não cobrem tarifa do fornecedor B",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
    ): {
        "preparacao": "100,00 na custódia e 100,00 na obrigação devida de A; tarifa de 1,00 em despesas; saldos e movimentos lidos antes",
        "acao": "7 lançamentos de A para despesa, obrigação de B, frete de B, reserva, receita e repasse de B",
        "resultado": "cobertura de despesa com dinheiro da custódia de A: MovimentoProibido e saldos e movimentos iguais (a tarifa é a conta global de despesas)",
        "veredito": "íntegra",
    },
    (
        32,
        "Recursos do fornecedor A não cobrem déficit nem prejuízo de B",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
    ): {
        "preparacao": "100,00 na custódia e 100,00 na obrigação devida de A; tarifa de 1,00 em despesas; saldos e movimentos lidos antes",
        "acao": "7 lançamentos de A para despesa, obrigação de B, frete de B, reserva, receita e repasse de B",
        "resultado": "cobertura do frete de B com a obrigação devida de A: MovimentoProibido e saldos e movimentos iguais",
        "veredito": "íntegra",
    },
    (
        32,
        "Recursos do fornecedor A não cobrem obrigação do fornecedor B",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
    ): {
        "preparacao": "100,00 na custódia e 100,00 na obrigação devida de A; tarifa de 1,00 em despesas; saldos e movimentos lidos antes",
        "acao": "7 lançamentos de A para despesa, obrigação de B, frete de B, reserva, receita e repasse de B",
        "resultado": "financiamento e repasse da obrigação devida de A para a obrigação de B: MovimentoProibido e saldos e movimentos iguais",
        "veredito": "íntegra",
    },
    (
        32,
        "A movimentação com esse efeito é recusada",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
    ): {
        "preparacao": "100,00 na custódia e 100,00 na obrigação devida de A; tarifa de 1,00 em despesas; saldos e movimentos lidos antes",
        "acao": "7 lançamentos de A para despesa, obrigação de B, frete de B, reserva, receita e repasse de B",
        "resultado": "todos os 7 lançamentos levantam MovimentoProibido e nada muda",
        "veredito": "íntegra",
    },
    (
        33,
        "Devolução devida antes do repasse é financiada pelos recursos da própria rodada",
        "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_antes_do_repasse_a_devolucao_sai_dos_recursos_da_propria_rodada",
    ): {
        "preparacao": "tarifa 1,00%; AP com X pago e nenhum repasse; a obrigação com o comprador B é registrada",
        "acao": "`registrar_obrigacao_com_comprador` antes do repasse",
        "resultado": "sem_cobertura 0,00; a custódia de B tem 75,00, 3,75 e 15,00 depois do financiamento pelos recursos da rodada",
        "veredito": "íntegra",
    },
    (
        33,
        "Devolução depois do repasse é coberta pela taxa de serviço",
        "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_depois_do_repasse_o_que_falta_fica_sem_cobertura_ate_o_administrador_escolher",
    ): {
        "preparacao": "AP com X pago; aporte de 1.000,00; apuração; repasse de 100,00 ao fornecedor; obrigação de devolução de 25,00 sem cobertura",
        "acao": "o administrador cobre 10,00 pela receita de outra rodada e 15,00 pela reserva",
        "resultado": "devido 25,00 e sem cobertura 25,00 antes; cobertura de 10,00 pela receita; ao fim nenhum item de obrigação sem cobertura",
        "veredito": "íntegra",
    },
    (
        33,
        "Devolução depois do repasse é coberta pela reserva",
        "tests/aceitacao/test_cenario_33_devolucao_e_repasse.py::test_depois_do_repasse_o_que_falta_fica_sem_cobertura_ate_o_administrador_escolher",
    ): {
        "preparacao": "AP com X pago; aporte de 1.000,00; apuração; repasse de 100,00 ao fornecedor; obrigação de devolução de 25,00 sem cobertura",
        "acao": "o administrador cobre 10,00 pela receita de outra rodada e 15,00 pela reserva",
        "resultado": "designação de 15,00 da reserva; ao fim nenhum item de obrigação sem cobertura",
        "veredito": "íntegra",
    },
    (
        33,
        "Devolução depois do repasse é coberta por novo aporte",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_34_depois_do_aporte_a_devolucao_e_concluida_sem_duplicidade",
    ): {
        "preparacao": "devolução do arranjo; reserva consumida por outra designação; a obrigação sem cobertura; alerta de reserva insuficiente aberto",
        "acao": "nova designação recusada, novo aporte, designação e conclusão no simulador; repetição",
        "resultado": "nova designação possível depois do aporte: a obrigação é concluída no simulador com 1 estorno e conta em 0,00",
        "veredito": "íntegra",
    },
    (
        34,
        "Com reserva insuficiente, a obrigação permanece integralmente registrada",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_34_depois_do_aporte_a_devolucao_e_concluida_sem_duplicidade",
    ): {
        "preparacao": "devolução do arranjo; reserva consumida por outra designação; a obrigação sem cobertura; alerta de reserva insuficiente aberto",
        "acao": "nova designação recusada, novo aporte, designação e conclusão no simulador; repetição",
        "resultado": "a designação falha com ReservaInsuficiente e a obrigação segue com o valor devido integral e sem movimento novo",
        "veredito": "íntegra",
    },
    (
        34,
        "Com reserva insuficiente, o sistema alerta",
        "tests/aceitacao/test_cenario_34_reserva_insuficiente.py::test_reserva_que_nao_cobre_alerta_e_o_aporte_do_administrador_resolve",
    ): {
        "preparacao": "reserva com 30,00; obrigação de 50,00; designação de 50,00 pedida",
        "acao": "a designação é recusada, a reserva é avaliada e o administrador faz um aporte de 40,00",
        "resultado": "ReservaInsuficiente; 1 alerta aberto de reserva_insuficiente; reserva 30,00 e livre 20,00; o alerta resolve depois do aporte",
        "veredito": "íntegra",
    },
    (
        34,
        "Depois de novo aporte, a devolução é concluída",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_34_depois_do_aporte_a_devolucao_e_concluida_sem_duplicidade",
    ): {
        "preparacao": "devolução do arranjo; reserva consumida por outra designação; a obrigação sem cobertura; alerta de reserva insuficiente aberto",
        "acao": "nova designação recusada, novo aporte, designação e conclusão no simulador; repetição",
        "resultado": "1 estorno concluído; parcela concluída; conta da obrigação em 0,00",
        "veredito": "íntegra",
    },
    (
        34,
        "Depois de novo aporte, a devolução não é duplicada",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_34_depois_do_aporte_a_devolucao_e_concluida_sem_duplicidade",
    ): {
        "preparacao": "devolução do arranjo; reserva consumida por outra designação; a obrigação sem cobertura; alerta de reserva insuficiente aberto",
        "acao": "nova designação recusada, novo aporte, designação e conclusão no simulador; repetição",
        "resultado": "na repetição: 1 estorno, 1 parcela, nenhum movimento novo e a reserva igual",
        "veredito": "íntegra",
    },
    (
        35,
        "Quando a devolução pela plataforma é inviável, o administrador devolve diretamente ao comprador",
        "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional",
    ): {
        "preparacao": "arranjo da devolução (O1 de um parcial); o provedor recusa o estorno (prazo_vencido); a parcela fica elegível por `levar_a_elegivel`",
        "acao": "o administrador confirma a devolução excepcional (transferência TED-9 com comprovante)",
        "resultado": "depois da recusa definitiva a parcela passa a concluída fora da plataforma pela confirmação do administrador",
        "veredito": "íntegra",
    },
    (
        35,
        "A plataforma registra a confirmação administrativa do pedido e do comprador",
        "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional",
    ): {
        "preparacao": "arranjo da devolução (O1 de um parcial); o provedor recusa o estorno (prazo_vencido); a parcela fica elegível por `levar_a_elegivel`",
        "acao": "o administrador confirma a devolução excepcional (transferência TED-9 com comprovante)",
        "resultado": "a confirmação traz o pedido e o comprador da obrigação (`pedido_id`, `comprador_id`)",
        "veredito": "íntegra",
    },
    (
        35,
        "A confirmação baixa a obrigação",
        "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional",
    ): {
        "preparacao": "arranjo da devolução (O1 de um parcial); o provedor recusa o estorno (prazo_vencido); a parcela fica elegível por `levar_a_elegivel`",
        "acao": "o administrador confirma a devolução excepcional (transferência TED-9 com comprovante)",
        "resultado": "o liquidado da conta da obrigação passa a ser igual ao devido",
        "veredito": "íntegra",
    },
    (
        35,
        "Até a confirmação, a obrigação permanece integral",
        "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_35_confirmacao_da_devolucao_excepcional",
    ): {
        "preparacao": "arranjo da devolução (O1 de um parcial); o provedor recusa o estorno (prazo_vencido); a parcela fica elegível por `levar_a_elegivel`",
        "acao": "o administrador confirma a devolução excepcional (transferência TED-9 com comprovante)",
        "resultado": "antes da confirmação: devido menos liquidado é igual ao devido (nada baixado)",
        "veredito": "íntegra",
    },
    (
        36,
        "A confirmação é recusada enquanto houver devolução pendente na plataforma",
        "tests/aceitacao/test_cenarios_35_36_excepcional.py::test_cenario_36_pela_tela",
    ): {
        "preparacao": "arranjo da devolução com o administrador logado; estornos em processamento no simulador; devolução autorizada e processada uma vez",
        "acao": "POST /administracao/financeiro/devolucoes/<O1>/excepcional/ com meio pix",
        "resultado": '409 com "há devolução pendente na plataforma"',
        "veredito": "íntegra",
    },
    (
        36,
        "A confirmação é recusada com falha definitiva ainda não comprovada",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_falha_definitiva_ainda_nao_comprovada_bloqueia",
    ): {
        "preparacao": "estorno recusado em definitivo e processado uma vez; a parcela fica falha_definitiva (ainda não elegível); pasta de comprovantes vazia",
        "acao": "tenta confirmar a devolução excepcional",
        "resultado": 'DevolucaoRecusada com "há devolução pendente na plataforma" e nenhum comprovante gravado',
        "veredito": "íntegra",
    },
    (
        36,
        "A confirmação não pode ser feita duas vezes para a mesma parcela",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_nao_vale_duas_vezes",
    ): {
        "preparacao": "parcela elegível já confirmada uma vez; contagens (confirmações, movimentos, arquivos) lidas depois da primeira",
        "acao": "segunda confirmação da mesma parcela",
        "resultado": 'DevolucaoRecusada "já confirmada"; contagens iguais e 1 comprovante só',
        "veredito": "íntegra",
    },
    (
        37,
        "Não existe forma de registrar pagamento de comprador recebido fora da plataforma integrada",
        "tests/tecnicos/test_pagamentos_fronteiras.py::test_nenhuma_rota_comando_ou_admin_registra_pagamento",
    ): {
        "preparacao": "a configuração real do projeto (INSTALLED_APPS, URLs e comandos)",
        "acao": "varre rotas, comandos de gerenciamento e o admin do Django (`_confere_as_rotas`)",
        "resultado": "o admin do Django não está instalado e nenhuma rota, comando ou tela cria pagamento (asserts do auxiliar)",
        "veredito": "íntegra",
    },
    (
        37,
        "Só a sincronização com o provedor escreve nos registros de pagamento",
        "tests/tecnicos/test_pagamentos_fronteiras.py::test_so_a_sincronizacao_escreve_nos_registros_de_pagamento",
    ): {
        "preparacao": "o código dos apps (sem migrações)",
        "acao": "leitura estática: procura escrita nos modelos de pagamento fora de `sincronizacao.py` e `models.py`",
        "resultado": "nenhum outro módulo escreve nos registros de pagamento e a sincronização escreve",
        "veredito": "íntegra",
    },
    (
        38,
        "A aplicação não inicia em produção com o simulador habilitado",
        "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_com_o_simulador_nao_carrega",
    ): {
        "preparacao": "ambiente de produção completo com PROVEDOR_PAGAMENTOS=simulador, em subprocesso",
        "acao": "carrega `config.settings.prod`",
        "resultado": "saída diferente de zero com ImproperlyConfigured e a mensagem do simulador; segredos fora do erro",
        "veredito": "íntegra",
    },
    (
        39,
        "Com dois pagamentos aceitos, apenas um quita o pedido",
        "tests/tecnicos/test_pedidos_quitacao.py::test_dois_pagamentos_aceitos_so_um_quita",
    ): {
        "preparacao": "a primeira cobrança expira e uma segunda tentativa é criada; as duas são aprovadas, nas duas ordens (parametrize)",
        "acao": "os dois avisos são sincronizados na ordem do caso",
        "resultado": "um pagamento com destino quita e o pedido pago com esse quitador; 1 aviso e 1 auditoria de quitação; nas duas ordens",
        "veredito": "íntegra",
    },
    (
        39,
        "Com dois pagamentos aceitos, o outro gera obrigação de devolução integral",
        "tests/tecnicos/test_financeiro_concorrencia.py::test_dois_pagamentos_do_mesmo_pedido_ao_mesmo_tempo",
    ): {
        "preparacao": "pedido X de B com duas cobranças aprovadas (125,00 cada)",
        "acao": "as duas sincronizações rodam em paralelo (barreira)",
        "resultado": "a obrigação do pagamento duplicado tem valor integral de 125,00",
        "veredito": "corrigida: religada (antes só o destino devolução)",
    },
    (
        39,
        "Dois pagamentos simultâneos geram uma só entrada para devolução",
        "tests/tecnicos/test_financeiro_concorrencia.py::test_dois_pagamentos_do_mesmo_pedido_ao_mesmo_tempo",
    ): {
        "preparacao": "pedido X de B com duas cobranças aprovadas (125,00 cada)",
        "acao": "as duas sincronizações rodam em paralelo (barreira)",
        "resultado": "1 entrada para devolução (1 movimento) de 125,00; custódia total igual ao total do pedido",
        "veredito": "íntegra",
    },
    (
        40,
        "O repasse manual ao fornecedor continua registrável",
        "tests/tecnicos/test_repasse.py::test_o_repasse_so_baixa_a_obrigacao_com_o_fornecedor",
    ): {
        "preparacao": "AF com X pago; obrigação de 170,00, liberado de 80,00; saldos das outras contas lidos antes",
        "acao": "repasse manual de 80,00 (pix-001) pelo administrador",
        "resultado": "movimento do tipo repasse; auditoria com rodada, fornecedor, valor 80,00 e identificação; saldo da obrigação 90,00",
        "veredito": "íntegra",
    },
    (
        40,
        "O repasse consome apenas a obrigação com aquele fornecedor",
        "tests/tecnicos/test_repasse.py::test_o_repasse_so_baixa_a_obrigacao_com_o_fornecedor",
    ): {
        "preparacao": "AF com X pago; obrigação de 170,00, liberado de 80,00; saldos das outras contas lidos antes",
        "acao": "repasse manual de 80,00 (pix-001) pelo administrador",
        "resultado": "só o saldo da obrigação do fornecedor cai de 170,00 para 90,00; os saldos de todas as outras contas ficam iguais",
        "veredito": "íntegra",
    },
    (
        41,
        "O cancelamento administrativo afeta todos os compradores da rodada",
        "tests/tecnicos/test_cancelamento_com_pedidos.py::test_cancela_o_nao_pago_e_preserva_o_pago",
    ): {
        "preparacao": "AP com X (A) pago e Y (B) não pago; parcelas de A e de B ativas",
        "acao": "o administrador cancela a rodada (`cancelar_rodada`)",
        "resultado": "rodada cancelada; Y cancelado por cancelamento; X segue pago; parcelas de A e B no estado final e reservado de P1 e P2 igual a 0",
        "veredito": "íntegra",
    },
    (
        41,
        "Não existe forma de cancelar a rodada para compradores selecionados",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http",
    ): {
        "preparacao": "administrador com passkey; AP com pagamento aberto; A (comprador) e uma conta de fornecedor logadas; invariante financeiro ok",
        "acao": "POST de cancelamento com compradores=1; POST de A e do fornecedor; POST do administrador sem motivo",
        "resultado": "o POST com a lista de compradores dá 400 e a rodada segue em pagamento",
        "veredito": "íntegra",
    },
    (
        42,
        "Somente o administrador ativo cancela a rodada",
        "tests/tecnicos/test_cancelamento_da_rodada.py::test_so_o_administrador_ativo_cancela",
    ): {
        "preparacao": "rodada em pagamento; A (comprador), uma conta de fornecedor, o administrador suspenso e None; estado fotografado",
        "acao": "`cancelar_rodada` com cada autor",
        "resultado": "PermissionDenied para os quatro e estado igual ao fotografado",
        "veredito": "íntegra",
    },
    (
        42,
        "Comprador e fornecedor são recusados no cancelamento",
        "tests/tecnicos/test_cancelamento_telas.py::test_comprador_e_fornecedor_nao_cancelam",
    ): {
        "preparacao": "AP com pagamento aberto; A e uma conta de fornecedor logadas",
        "acao": "POST de cancelamento e GET da página da rodada",
        "resultado": "POST e GET recusados (302 ou 403) e a etapa segue pagamento",
        "veredito": "íntegra",
    },
    (
        42,
        "A recusa vale também por acesso direto à rota",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http",
    ): {
        "preparacao": "administrador com passkey; AP com pagamento aberto; A (comprador) e uma conta de fornecedor logadas; invariante financeiro ok",
        "acao": "POST de cancelamento com compradores=1; POST de A e do fornecedor; POST do administrador sem motivo",
        "resultado": "o POST direto de A e do fornecedor dá 302 ou 403 e a rodada segue em pagamento",
        "veredito": "íntegra",
    },
    (
        42,
        "O cancelamento é aceito sem motivo",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http",
    ): {
        "preparacao": "administrador com passkey; AP com pagamento aberto; A (comprador) e uma conta de fornecedor logadas; invariante financeiro ok",
        "acao": "POST de cancelamento com compradores=1; POST de A e do fornecedor; POST do administrador sem motivo",
        "resultado": "o POST do administrador só com o campo de reembolso (sem motivo) dá 302 e a rodada fica cancelada",
        "veredito": "íntegra",
    },
    (
        42,
        "O cancelamento é aceito sem informação sobre o fornecedor",
        "tests/tecnicos/test_cancelamento_da_rodada.py::test_a_assinatura_nao_aceita_lista_de_compradores_nem_motivo",
    ): {
        "preparacao": "rodada em pagamento; estado fotografado; a assinatura de `cancelar_rodada` lida",
        "acao": 'chamadas com compradores=[A] e com motivo="x"',
        "resultado": "parâmetros só autor, rodada, com_reembolso e mensagem (nenhum de fornecedor); TypeError nas duas chamadas e estado igual",
        "veredito": "íntegra",
    },
    (
        43,
        "Cada comprador que pagou recebe devolução integral de produtos, serviço e frete",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_reembolso_integral_do_pedido_pago",
    ): {
        "preparacao": "AP com X pago (94,35) e Y não pago; rodada cancelada com reembolso",
        "acao": "lê o reembolso e a obrigação do cancelamento de X",
        "resultado": "reembolso integral do sistema com produtos 80,00, serviço 4,00 e frete 10,35; obrigação de 94,35 sem cobertura pendente",
        "veredito": "íntegra",
    },
    (
        43,
        "A devolução integral desconta o que já foi devolvido",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago",
    ): {
        "preparacao": "pedido de 9,99 pago; um reembolso parcial concluído no simulador; rodada cancelada com reembolso",
        "acao": "as chamadas pendentes são processadas",
        "resultado": "o reembolso do cancelamento tem produtos 5,99 (o saldo) e o estornado no simulador soma 9,99",
        "veredito": "íntegra",
    },
    (
        43,
        "A devolução integral desconta o que está pendente",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido",
    ): {
        "preparacao": "AP com X pago; apuração com caixa invalidada gera a obrigação pendente de 23,59 (sem parcela de devolução)",
        "acao": "a rodada é cancelada com reembolso",
        "resultado": "a obrigação de caixa segue 23,59 sem parcela; o reembolso do cancelamento traz só o restante e o total de X é 94,35",
        "veredito": "íntegra",
    },
    (
        43,
        "O total devolvido nunca ultrapassa o valor pago",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago",
    ): {
        "preparacao": "pedido de 9,99 pago; um reembolso parcial concluído no simulador; rodada cancelada com reembolso",
        "acao": "as chamadas pendentes são processadas",
        "resultado": "o estornado total é igual ao total do pedido (9,99), sem excesso",
        "veredito": "íntegra",
    },
    (
        43,
        "Quem não pagou não recebe devolução",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_reembolso_integral_do_pedido_pago",
    ): {
        "preparacao": "AP com X pago (94,35) e Y não pago; rodada cancelada com reembolso",
        "acao": "lê o reembolso e a obrigação do cancelamento de X",
        "resultado": "nenhum reembolso para o pedido Y",
        "veredito": "íntegra",
    },
    (
        44,
        "Cancelamento sem reembolso não gera obrigação de cancelamento",
        "tests/tecnicos/test_cancelamento_telas.py::test_cancelar_sem_reembolso_pela_tela",
    ): {
        "preparacao": "administrador com passkey; X pago; pagamento em andamento",
        "acao": "POST de cancelamento com reembolso=nao e leitura da página",
        "resultado": 'mensagem "Rodada cancelada." e "sem reembolso"; nenhuma obrigação com motivo cancelamento_da_rodada',
        "veredito": "íntegra",
    },
    (
        44,
        "Cancelamento sem reembolso não inicia nenhuma parcela de devolução",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente",
    ): {
        "preparacao": "X pago; Y pagou depois da margem (obrigação existente de devolução integral); obrigações fotografadas antes",
        "acao": "cancelamento sem reembolso; depois a devolução existente é autorizada e processada",
        "resultado": "rodada cancelada; obrigações iguais às fotografadas; a obrigação existente segue sem parcela de devolução depois do cancelamento",
        "veredito": "íntegra",
    },
    (
        44,
        "Uma obrigação de devolução existente continua pendente",
        "tests/tecnicos/test_cancelamento_com_pedidos.py::test_pagamento_em_duplicidade_continua_como_estava",
    ): {
        "preparacao": "AP com X e Y pagos e um segundo pagamento em duplicidade já com destino de devolução; contagens e livro fotografados",
        "acao": "a rodada é cancelada",
        "resultado": "o destino segue devolução por duplicidade; número de obrigações e livro (movimentos e saldos) iguais",
        "veredito": "íntegra",
    },
    (
        44,
        "A obrigação existente é liquidada depois",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente",
    ): {
        "preparacao": "X pago; Y pagou depois da margem (obrigação existente de devolução integral); obrigações fotografadas antes",
        "acao": "cancelamento sem reembolso; depois a devolução existente é autorizada e processada",
        "resultado": "autorizada depois, o estornado no simulador de Y é igual à obrigação integral",
        "veredito": "íntegra",
    },
    (
        45,
        "Depois do cancelamento, os registros financeiros anteriores continuam inalterados",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_depois_da_aprovacao_do_resultado",
    ): {
        "preparacao": "X pago; apuração e aprovação; aporte de 1.000,00; receita da rodada movida para despesas; aprovações fotografadas antes",
        "acao": "cancelamento com reembolso; cobertura pela reserva; devolução autorizada e processada; conciliação dos dias",
        "resultado": "aprovações do resultado iguais às lidas antes do cancelamento; nenhuma conciliação divergente; devolução concluída; invariante financeiro ok",
        "veredito": "íntegra",
    },
    (
        45,
        "Depois do cancelamento, os registros financeiros anteriores continuam consultáveis",
        "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_45_os_registros_anteriores_continuam_consultaveis_depois_do_cancelamento",
    ): {
        "preparacao": "X pago; administrador com passkey; rodada cancelada sem reembolso",
        "acao": "GET /administracao/historico/",
        "resultado": "200 e o histórico lista pedido.quitar e rodada.cancelar",
        "veredito": "íntegra",
    },
    (
        46,
        "Reembolsos do cancelamento usam a plataforma de pagamentos",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_com_reembolso_durante_a_margem",
    ): {
        "preparacao": "X pago e Y com cobrança pendente na margem; administrador com passkey",
        "acao": "cancelamento com reembolso pela tela e processamento das chamadas",
        "resultado": "302; a cobrança de Y cancelada no simulador; X estornado em 94,35; parcela concluída; obrigação liquidada e aviso de estorno",
        "veredito": "íntegra",
    },
    (
        46,
        "Se a plataforma for inviável, o cancelamento usa a devolução excepcional confirmada",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_falha_definitiva_segue_para_a_devolucao_excepcional",
    ): {
        "preparacao": "X pago; o provedor recusa o estorno em definitivo; rodada cancelada; MEDIA_ROOT temporário",
        "acao": "autoriza a devolução, confirma a devolução excepcional e tenta confirmar de novo",
        "resultado": "parcela elegível excepcional e depois a obrigação liquidada; segunda confirmação recusada; 1 parcela de devolução",
        "veredito": "íntegra",
    },
    (
        46,
        "O cancelamento não duplica devoluções pendentes",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido",
    ): {
        "preparacao": "AP com X pago; apuração com caixa invalidada gera a obrigação pendente de 23,59 (sem parcela de devolução)",
        "acao": "a rodada é cancelada com reembolso",
        "resultado": "a obrigação anterior não é substituída nem duplicada e o total devolvido de X é 94,35",
        "veredito": "íntegra",
    },
    (
        47,
        "Comprador não consegue adicionar interesse depois da abertura do pagamento",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409",
    ): {
        "preparacao": "pagamento aberto; A (comprador com pedido) e o administrador; pedidos e itens fotografados antes",
        "acao": "A faz POST /interesses/ com 7 e com 5 para P1 (aumenta e reduz); o administrador faz POST com 7",
        "resultado": "(R10) o POST de C comprador novo e o de A que aumenta (7) dão 409; os pedidos seguem iguais",
        "veredito": "corrigida: assert acrescentado (comprador novo)",
    },
    (
        47,
        "Comprador não consegue remover interesse depois da abertura do pagamento",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409",
    ): {
        "preparacao": "pagamento aberto; A (comprador com pedido) e o administrador; pedidos e itens fotografados antes",
        "acao": "A faz POST /interesses/ com 7 e com 5 para P1 (aumenta e reduz); o administrador faz POST com 7",
        "resultado": "o POST de A que reduz (5) dá 409 com a mensagem da etapa; pedidos e itens iguais por conteúdo",
        "veredito": "íntegra",
    },
    (
        47,
        "Comprador não consegue alterar quantidades depois da abertura do pagamento",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_interesse_depois_da_abertura_e_recusado_com_409",
    ): {
        "preparacao": "pagamento aberto; A (comprador com pedido) e o administrador; pedidos e itens fotografados antes",
        "acao": "A faz POST /interesses/ com 7 e com 5 para P1 (aumenta e reduz); o administrador faz POST com 7",
        "resultado": "os POST de A com 7 e com 5 dão 409 com a mensagem da etapa; pedidos e itens iguais por conteúdo",
        "veredito": "íntegra",
    },
    (
        47,
        "Administrador não consegue adicionar, remover ou alterar o pedido depois da abertura",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_administrador_e_recusado_pela_politica_sem_a_mensagem_da_etapa",
    ): {
        "preparacao": "pagamento aberto; administrador autenticado; pedidos, itens e parcelas fotografados antes",
        "acao": "o administrador faz POST /interesses/ com P1 e quantidade 7",
        "resultado": "status 403 exato; sem a mensagem da etapa; pedidos, itens e parcelas iguais por conteúdo",
        "veredito": "corrigida: religada (a ligação antiga aceitava 302 ou 403)",
    },
    (
        48,
        "A ocorrência de 2 unidades faltantes gera reembolso de produtos de R$ 20,00",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual",
    ): {
        "preparacao": "arranjo único: pedido pago de A a R$ 12,50/unidade, em PRAZO; o item de P1",
        "acao": "o administrador registra ocorrência faltante de 2 unidades",
        "resultado": "componentes (20,00, 1,00, 4,00): produtos 20,00",
        "veredito": "íntegra",
    },
    (
        48,
        "A ocorrência de 2 unidades faltantes gera reembolso de serviço de R$ 1,00",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual",
    ): {
        "preparacao": "arranjo único: pedido pago de A a R$ 12,50/unidade, em PRAZO; o item de P1",
        "acao": "o administrador registra ocorrência faltante de 2 unidades",
        "resultado": "componentes (20,00, 1,00, 4,00): serviço 1,00",
        "veredito": "íntegra",
    },
    (
        48,
        "A ocorrência de 2 unidades faltantes gera reembolso de frete de R$ 4,00",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual",
    ): {
        "preparacao": "arranjo único: pedido pago de A a R$ 12,50/unidade, em PRAZO; o item de P1",
        "acao": "o administrador registra ocorrência faltante de 2 unidades",
        "resultado": "componentes (20,00, 1,00, 4,00): frete 4,00",
        "veredito": "íntegra",
    },
    (
        48,
        "O reembolso pontual soma R$ 25,00",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual",
    ): {
        "preparacao": "arranjo único: pedido pago de A a R$ 12,50/unidade, em PRAZO; o item de P1",
        "acao": "o administrador registra ocorrência faltante de 2 unidades",
        "resultado": "total do reembolso 25,00 e obrigação de 25,00 com a compradora",
        "veredito": "íntegra",
    },
    (
        48,
        "O pedido original continua igual",
        "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenarios_48_e_52_a_ocorrencia_nao_muda_pedido_nem_rodada",
    ): {
        "preparacao": "arranjo único; pedidos e itens fotografados antes",
        "acao": "ocorrência faltante de 2 unidades",
        "resultado": "reembolso 20,00/1,00/4,00; Pedido e ItemDoPedido iguais por conteúdo ao fotografado",
        "veredito": "íntegra",
    },
    (
        48,
        "Ocorrência e reembolso ficam registrados à parte",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_48_faltante_gera_reembolso_pontual",
    ): {
        "preparacao": "arranjo único: pedido pago de A a R$ 12,50/unidade, em PRAZO; o item de P1",
        "acao": "o administrador registra ocorrência faltante de 2 unidades",
        "resultado": "1 ocorrência (faltante, 2,000, autor administrador, em PRAZO) ligada a um Reembolso próprio com motivo ocorrencia_de_entrega",
        "veredito": "íntegra",
    },
    (
        49,
        "A soma das ocorrências de um item não pode ultrapassar a quantidade paga",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_49_a_soma_nao_passa_da_quantidade_paga",
    ): {
        "preparacao": "AE com X pago; uma ocorrência de 4 unidades já registrada; registros fotografados",
        "acao": "segunda ocorrência de 3 unidades (nao_entregue) no mesmo item",
        "resultado": "OcorrenciaRecusada passa_do_saldo_do_item com saldo de 2 unidades; registros iguais ao fotografado",
        "veredito": "íntegra",
    },
    (
        49,
        "Uma ocorrência que ultrapasse a quantidade paga é recusada",
        "tests/tecnicos/test_recebimento_e_retirada_telas.py::test_ocorrencia_acima_do_saldo",
    ): {
        "preparacao": "AE com X pago e administrador logado; ocorrência de 2 unidades já registrada; estado fotografado",
        "acao": "POST da tela com ocorrência nao_entregue acima do saldo",
        "resultado": '409 com "A quantidade passa do saldo deste item (4 unidade)." e registros iguais',
        "veredito": "íntegra",
    },
    (
        50,
        "O comprador não consegue registrar falta",
        "tests/tecnicos/test_retirada_comprador.py::test_as_rotas_do_comprador_nao_criam_ocorrencia",
    ): {
        "preparacao": "AE com X pago; A (comprador) logada; pedidos, itens e registros contados antes",
        "acao": "A envia campos de ocorrência (item, tipo faltante, 2) às rotas do pedido (detalhe e pagar)",
        "resultado": "detalhe responde 405, pagar 302 ou 409 e nenhum registro novo (ocorrência, reembolso, descarte)",
        "veredito": "íntegra",
    },
    (
        50,
        "O comprador não consegue pedir substituição alterando o pedido",
        "tests/tecnicos/test_retirada_comprador.py::test_as_rotas_do_comprador_nao_criam_ocorrencia",
    ): {
        "preparacao": "AE com X pago; A (comprador) logada; pedidos, itens e registros contados antes",
        "acao": "A envia campos de ocorrência (item, tipo faltante, 2) às rotas do pedido (detalhe e pagar)",
        "resultado": "Pedido e ItemDoPedido iguais por conteúdo ao fotografado depois dos envios",
        "veredito": "íntegra",
    },
    (
        51,
        "Pagamento comunicado depois da apuração é registrado como devolução",
        "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta",
    ): {
        "preparacao": "AP apurada com Y sem pagamento; cobrança de Y aprovada antes do prazo mas só avisada depois; composição fotografada",
        "acao": "o aviso chega em T0+50h e a tarefa sincroniza o pagamento",
        "resultado": "Y cancelado por inadimplência, destino devolução (pedido_cancelado) e obrigação integral igual ao total de Y",
        "veredito": "íntegra",
    },
    (
        51,
        "Pagamento comunicado depois do cancelamento é registrado como devolução",
        "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta",
    ): {
        "preparacao": "rodada cancelada com Y não pago; cobrança de Y aprovada depois; composição fotografada pelo auxiliar",
        "acao": "a aprovação chega e é sincronizada",
        "resultado": "Y segue cancelado por cancelamento da rodada; destino devolução (pedido_cancelado); obrigação integral de 106,15",
        "veredito": "íntegra",
    },
    (
        51,
        "O pagamento tardio é tratado com auditoria de alerta crítico",
        "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta",
    ): {
        "preparacao": "rodada cancelada com Y não pago; cobrança de Y aprovada depois; composição fotografada pelo auxiliar",
        "acao": "a aprovação chega e é sincronizada",
        "resultado": "alerta de gravidade crítica com a chave da cobrança e dados do pedido",
        "veredito": "íntegra",
    },
    (
        51,
        "O pagamento tardio não edita o pedido",
        "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta",
    ): {
        "preparacao": "rodada cancelada com Y não pago; cobrança de Y aprovada depois; composição fotografada pelo auxiliar",
        "acao": "a aprovação chega e é sincronizada",
        "resultado": "composição (pedidos, itens, parcelas) igual à fotografada antes da aprovação",
        "veredito": "íntegra",
    },
    (
        52,
        "Registrar uma ocorrência de entrega não cancela a rodada",
        "tests/aceitacao/test_cenarios_18_48_49_52_ocorrencias.py::test_cenarios_48_e_52_a_ocorrencia_nao_muda_pedido_nem_rodada",
    ): {
        "preparacao": "arranjo único; pedidos e itens fotografados antes",
        "acao": "ocorrência faltante de 2 unidades",
        "resultado": "depois da ocorrência a rodada segue em aguardando_fornecedor (não cancelada)",
        "veredito": "íntegra",
    },
    (
        52,
        "Cancelar a rodada não registra ocorrências",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_cenario_52_cancelamento_com_ocorrencia_anterior",
    ): {
        "preparacao": "AE pela tela; ocorrência faltante de 2 registrada antes (reembolso lido); estado inicial fotografado",
        "acao": "o administrador cancela a rodada com reembolso; tenta receber e registrar nova ocorrência",
        "resultado": "depois do cancelamento continua 1 ocorrência, o reembolso anterior igual, o cancelamento deve 70,76; recebimento e nova ocorrência dão 409",
        "veredito": "íntegra",
    },
    (
        53,
        "As unidades que A pagou na caixa invalidada recebem estorno proporcional",
        "tests/tecnicos/test_apuracao_viavel.py::test_estorno_proporcional_das_unidades_em_caixa_invalidada",
    ): {
        "preparacao": "AP-viável: X (A) pago, Y (B) não pago; apurado em T0+48h; a caixa de P2 fica inválida",
        "acao": "`_viavel` apura; o teste lê os reembolsos do pedido X",
        "resultado": "reembolso parcial do item de P2 com 4,000 unidades por 20,00, serviço 1,00 e frete 2,59; obrigação de 23,59",
        "veredito": "íntegra",
    },
    (
        53,
        "As unidades da caixa invalidada voltam ao interesse com a posição original",
        "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila",
    ): {
        "preparacao": "AP-viável apurado; a parcela do pedido de A na caixa de P2 lida antes",
        "acao": "a apuração restaura a caixa invalidada",
        "resultado": "a parcela original (mesmo pk) volta pendente com 4 unidades e a restauração liga a parcela do pedido à parcela de interesse",
        "veredito": "íntegra",
    },
    (
        53,
        "As unidades voltam ao interesse antes da conclusão do estorno",
        "tests/tecnicos/test_apuracao_viavel.py::test_a_restauracao_nao_espera_a_autorizacao_da_devolucao",
    ): {
        "preparacao": "AP-viável apurado; nenhuma devolução autorizada",
        "acao": "lê as parcelas de devolução e a parcela de A em P2",
        "resultado": "nenhuma parcela de devolução e a parcela de A em P2 já está pendente",
        "veredito": "íntegra",
    },
    (
        53,
        "Os itens válidos de A no ciclo não mudam",
        "tests/tecnicos/test_apuracao_viavel.py::test_so_a_parte_da_caixa_invalidada_e_estornada_e_restaurada",
    ): {
        "preparacao": "P2 com parcelas de A (4), C (2), A (2) e B (4); X e Z pagos e Y não; apurado",
        "acao": "a apuração restaura só a parte da caixa invalidada",
        "resultado": "a primeira parcela de A (4) segue em pedido reservada; só a segunda (2) volta pendente; Z sem reembolso; só uma restauração",
        "veredito": "íntegra",
    },
    (
        54,
        "O inadimplente B perde as reservas do fornecedor",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor",
    ): {
        "preparacao": "apurada com só X pago; as 3 parcelas de B em pedido lidas antes",
        "acao": "`iniciar_apuracao`",
        "resultado": "as 3 parcelas de B passam de em_pedido a removida, com mesmo pk, sequência e original, e reservado e pendente 0",
        "veredito": "íntegra",
    },
    (
        54,
        "O inadimplente B perde as posições na fila do fornecedor",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai",
    ): {
        "preparacao": "apurada com só X pago; B com 3 pendentes antigas de P3, do mesmo fornecedor e fora da rodada",
        "acao": "`iniciar_apuracao`",
        "resultado": "a pendente antiga de B fica removida com pendente 0 e B não tem mais parcela na fila do fornecedor",
        "veredito": "íntegra",
    },
    (
        54,
        "Itens de B de outros fornecedores não são afetados",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_parcelas_de_outro_fornecedor_nao_mudam",
    ): {
        "preparacao": "apurada com só X pago; B com parcela em produto do fornecedor G, fora da apuração; campos lidos antes",
        "acao": "`iniciar_apuracao`",
        "resultado": "a parcela de B no fornecedor G tem todos os campos iguais aos lidos antes",
        "veredito": "íntegra",
    },
    (
        55,
        "A restauração repetida não duplica a parcela",
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ): {
        "preparacao": "AP-viável apurado; a parcela de A em P2 restaurada e lida antes; resultado da apuração recalculado",
        "acao": "o passo de restauração e estorno é repetido numa transação",
        "resultado": "continua 1 restauração, 1 reembolso e 1 obrigação de X; a parcela de A segue única com pendente 4,000",
        "veredito": "íntegra",
    },
    (
        55,
        "A restauração repetida não duplica a posição",
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ): {
        "preparacao": "AP-viável apurado; a parcela de A em P2 restaurada e lida antes; resultado da apuração recalculado",
        "acao": "o passo de restauração e estorno é repetido numa transação",
        "resultado": "depois da repetição a sequência da parcela é igual à de antes",
        "veredito": "íntegra",
    },
    (
        55,
        "A restauração em paralelo com novas adições não duplica a reserva",
        "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X pago; C comprador novo; corrida pelo ponto depois da restauração das reservas",
        "acao": "duas threads: a apuração (A) e a adição de 5 de P1 por C (B), B esperando",
        "resultado": "nenhuma exceção; B esperou; C fica ativa com 5; reservado total de P1 não passa de 11 (sem reserva duplicada)",
        "veredito": "íntegra",
    },
    (
        55,
        "Uma parcela adicionada depois da adição original da parcela restaurada fica atrás dela",
        "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X pago; C comprador novo; corrida pelo ponto depois da restauração das reservas",
        "acao": "duas threads: a apuração (A) e a adição de 5 de P1 por C (B), B esperando",
        "resultado": "(R11) a sequência da parcela de C é maior que a de toda parcela de A em P1",
        "veredito": "corrigida: assert acrescentado",
    },
    (
        56,
        "Rodada que volta para interesse mantém o estoque cadastrado",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "os limites de estoque da rodada seguem 11 e 12",
        "veredito": "íntegra",
    },
    (
        56,
        "As reservas de quem pagou continuam com a ordem original",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "as sequências de todas as parcelas iguais às lidas antes da apuração",
        "veredito": "íntegra",
    },
    (
        56,
        "As reservas dos inadimplentes são liberadas",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "todas as parcelas de B ficam removidas",
        "veredito": "íntegra",
    },
    (
        56,
        "As reservas liberadas dos inadimplentes ficam disponíveis",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "o reservado total cai para 6 em P1 e 4 em P2 (limites 11 e 12): as unidades liberadas voltam ao estoque",
        "veredito": "íntegra",
    },
    (
        56,
        "Estornos pendentes não impedem novas adições",
        "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_56_o_estorno_pendente_nao_impede_novas_adicoes",
    ): {
        "preparacao": "rodada devolvida ao interesse com a obrigação de X sem parcela de devolução; C é um comprador novo",
        "acao": "C adiciona 5 de P1",
        "resultado": "a parcela de C em P1 existe; a obrigação de X segue única e nenhuma parcela de devolução foi criada",
        "veredito": "íntegra",
    },
    (
        56,
        "Estornos pendentes não impedem novo fechamento",
        "tests/tecnicos/test_apuracao_retorno.py::test_novo_fechamento_com_estorno_pendente",
    ): {
        "preparacao": "rodada devolvida ao interesse com a obrigação de X (estorno não autorizado); C pede 5 de P1",
        "acao": "o administrador inicia um novo fechamento",
        "resultado": "com a obrigação de X pendente, o novo fechamento começa (ciclo 2) sem criar parcela de devolução",
        "veredito": "íntegra",
    },
    (
        57,
        "O total reservado de cada produto nunca passa do estoque",
        "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; C com 3 pendentes de P1; X pago",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "reservado de P1 igual a 9 (limite 11) e de P2 igual a 4 (limite 12) com 3 pendentes de C na fila",
        "veredito": "íntegra",
    },
    (
        57,
        "Nenhuma reserva aparece duplicada depois do retorno",
        "tests/tecnicos/test_apuracao_retorno.py::test_total_reservado_cabe_no_estoque_sem_reserva_duplicada",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; C com 3 pendentes de P1; X pago",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "em toda parcela o reservado mais o pendente não passa da quantidade original",
        "veredito": "íntegra",
    },
    (
        58,
        "E-mail de conta removida é recusado no login por senha",
        "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite",
    ): {
        "preparacao": "conta ana@x.com com senha, removida pelo administrador",
        "acao": "tenta login por senha, pedido de link e retorno do Google; tenta novo convite com o e-mail",
        "resultado": "o POST de login com a senha não abre sessão para a conta removida",
        "veredito": "íntegra",
    },
    (
        58,
        "E-mail de conta removida é recusado no login por link",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link",
    ): {
        "preparacao": "conta ana@x.com removida, ou ativa com e-mail em EmailBanido; 3 grafias do e-mail e 2 casos",
        "acao": "pedido de link com a grafia do caso",
        "resultado": "removida: resposta padrão, 0 links, 0 e-mails e (R2) sem sessão; nas 3 grafias do e-mail",
        "veredito": "corrigida: assert acrescentado (sem sessão)",
    },
    (
        58,
        "E-mail de conta removida é recusado no login pelo Google",
        "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite",
    ): {
        "preparacao": "conta ana@x.com com senha, removida pelo administrador",
        "acao": "tenta login por senha, pedido de link e retorno do Google; tenta novo convite com o e-mail",
        "resultado": "o retorno do Google volta a /entrar/ sem sessão",
        "veredito": "íntegra",
    },
    (
        58,
        "Um novo convite para o e-mail de conta removida não permite cadastro",
        "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite",
    ): {
        "preparacao": "conta ana@x.com com senha, removida pelo administrador",
        "acao": "tenta login por senha, pedido de link e retorno do Google; tenta novo convite com o e-mail",
        "resultado": "o convite levanta EmailEmUso e nenhum Convite é criado",
        "veredito": "íntegra",
    },
    (
        58,
        "O histórico financeiro continua consultável pelo administrador",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_20_o_administrador_consulta_o_historico_financeiro_do_removido",
    ): {
        "preparacao": "pedido pago de A e conta de A removida; administrador autenticado por passkey",
        "acao": "GET /administracao/historico/",
        "resultado": "a página do histórico lista pedido.quitar (financeiro)",
        "veredito": "íntegra",
    },
    (
        58,
        "O histórico da conta removida continua consultável pelo administrador",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_20_o_administrador_consulta_o_historico_financeiro_do_removido",
    ): {
        "preparacao": "pedido pago de A e conta de A removida; administrador autenticado por passkey",
        "acao": "GET /administracao/historico/",
        "resultado": "a página do histórico lista conta.remover",
        "veredito": "íntegra",
    },
    (
        59,
        "O endereço banido com outras maiúsculas é recusado no login e no novo cadastro",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_59_o_endereco_banido_com_outras_maiusculas_e_recusado_no_login",
    ): {
        "preparacao": "conta ana@x.com banida (e aliases ana+1 e a.na criados por `_banida_e_aliases`)",
        "acao": 'tenta login por senha com "ANA@x.com" e "  Ana@X.com "',
        "resultado": "nenhuma das duas grafias abre sessão (cláusula do login; o novo cadastro é provado pelo outro teste, como prescreve a A-36)",
        "veredito": "íntegra",
    },
    (
        59,
        "O endereço banido com outras maiúsculas é recusado no login e no novo cadastro",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_59_o_endereco_banido_com_outras_maiusculas_e_recusado_no_novo_cadastro",
    ): {
        "preparacao": "e-mail ana@x.com banido; contas contadas antes",
        "acao": 'o administrador emite convite para "ANA@x.com" e "  Ana@X.com "',
        "resultado": "os dois convites levantam EmailEmUso e o número de contas não muda (cláusula do cadastro)",
        "veredito": "íntegra",
    },
    (
        59,
        "O banimento não vale para o alias com +",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_afeta_so_o_endereco_exato",
    ): {
        "preparacao": "contas ana@x.com e o alias ana+1@x.com (com senha); o administrador remove ana",
        "acao": "o alias faz login e o administrador emite convite para a.na@x.com",
        "resultado": "o alias ana+1@x.com segue ativo e com sessão aberta; o endereço a.na@x.com ainda aceita convite",
        "veredito": "íntegra",
    },
    (
        59,
        "O banimento não vale para o alias com pontos",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_59_o_alias_com_pontos_nao_e_afetado",
    ): {
        "preparacao": "ana@x.com banida; conta alias a.na@x.com com senha",
        "acao": "login por senha do alias com pontos",
        "resultado": "o alias a.na@x.com abre sessão",
        "veredito": "íntegra",
    },
    (
        59,
        "O banimento não bloqueia o IP",
        "tests/aceitacao/test_cenario_59_banimento_so_do_endereco.py::test_cenario_59_ip_dispositivo_e_telefone_nao_sao_bloqueados",
    ): {
        "preparacao": "conta ana banida e a conta bia com o mesmo telefone; o mesmo navegador e IP da conta banida",
        "acao": "bia faz login do mesmo navegador e IP",
        "resultado": "o e-mail de ana está banido e bia abre sessão do mesmo IP",
        "veredito": "íntegra",
    },
    (
        59,
        "O banimento não bloqueia o dispositivo",
        "tests/aceitacao/test_cenario_59_banimento_so_do_endereco.py::test_cenario_59_ip_dispositivo_e_telefone_nao_sao_bloqueados",
    ): {
        "preparacao": "conta ana banida e a conta bia com o mesmo telefone; o mesmo navegador e IP da conta banida",
        "acao": "bia faz login do mesmo navegador e IP",
        "resultado": "bia abre sessão no mesmo navegador (cookies) da conta banida",
        "veredito": "íntegra",
    },
    (
        59,
        "O banimento não bloqueia o telefone",
        "tests/aceitacao/test_cenario_59_banimento_so_do_endereco.py::test_cenario_59_ip_dispositivo_e_telefone_nao_sao_bloqueados",
    ): {
        "preparacao": "conta ana banida e a conta bia com o mesmo telefone; o mesmo navegador e IP da conta banida",
        "acao": "bia faz login do mesmo navegador e IP",
        "resultado": "bia, com o mesmo telefone da conta banida, abre sessão",
        "veredito": "íntegra",
    },
    (
        60,
        "A suspensão continua reversível",
        "tests/tecnicos/test_moderacao_servicos.py::test_reativar_volta_a_ativa_sem_restaurar_nada",
    ): {
        "preparacao": "conta de comprador suspensa; campos da conta lidos antes",
        "acao": "o administrador reativa a conta",
        "resultado": "situação suspensa antes e ativa depois; os demais campos iguais; 1 auditoria de reativação; nenhum e-mail banido",
        "veredito": "íntegra",
    },
    (
        60,
        "A suspensão não bane o e-mail",
        "tests/tecnicos/test_moderacao_servicos.py::test_suspender_pela_tela_nao_encerra_a_sessao_nem_bane",
    ): {
        "preparacao": "administrador logado; comprador ana com sessão aberta",
        "acao": "o administrador suspende ana pela tela",
        "resultado": "302; situação suspensa; nenhum EmailBanido; a sessão de ana segue com /inicio/ 200; 1 auditoria de suspensão",
        "veredito": "íntegra",
    },
    (
        61,
        "Cada login de uma pessoa com duas contas vê só os dados da sua conta",
        "tests/aceitacao/test_cenario_61_contas_independentes.py::test_cada_sessao_ve_so_a_propria_conta",
    ): {
        "preparacao": "compradora Ana e fornecedora Ana com e-mails diferentes, cada uma com sessão",
        "acao": "cada uma abre /inicio/ e /perfil/",
        "resultado": "cada sessão mostra o próprio nome, papel e e-mail e nenhum dado da outra conta",
        "veredito": "íntegra",
    },
    (
        61,
        "Cada login vê só as permissões da sua conta: o fornecedor não compra",
        "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
    ): {
        "preparacao": "conta de fornecedor logada; rotas de teste do carrinho e do pagamento; com e sem cabeçalho HTMX (2 casos)",
        "acao": "GET e POST do carrinho; POST, PUT, PATCH e DELETE do pagamento",
        "resultado": "todas as chamadas dão 403 e nenhuma view de compra foi executada (`views.CHAMADAS == []`)",
        "veredito": "íntegra",
    },
    (
        61,
        "Cada login vê só as permissões da sua conta: o comprador não entra no portal do fornecedor",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_comprador_nao_entra_no_portal",
    ): {
        "preparacao": "AF com A (comprador) logada",
        "acao": "GET do portal, da rodada e do CSV do pedido formal do fornecedor",
        "resultado": "as 3 respostas são 403",
        "veredito": "íntegra",
    },
    (
        61,
        "A conta de fornecedor é recusada ao tentar comprar",
        "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
    ): {
        "preparacao": "conta de fornecedor logada; rotas de teste do carrinho e do pagamento; com e sem cabeçalho HTMX (2 casos)",
        "acao": "GET e POST do carrinho; POST, PUT, PATCH e DELETE do pagamento",
        "resultado": "403 em todas as chamadas de compra e nenhuma view executada",
        "veredito": "íntegra",
    },
    (
        61,
        "A conta de fornecedor é recusada ao tentar comprar também por chamada direta à API",
        "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
    ): {
        "preparacao": "conta de fornecedor logada; rotas de teste do carrinho e do pagamento; com e sem cabeçalho HTMX (2 casos)",
        "acao": "GET e POST do carrinho; POST, PUT, PATCH e DELETE do pagamento",
        "resultado": "as chamadas diretas HTTP (PUT, PATCH, DELETE, também com HTMX) dão 403 e nenhuma view executada",
        "veredito": "íntegra",
    },
    (
        62,
        "Conta de fornecedor é criada pelo convite de fornecedor",
        "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_fornecedor",
    ): {
        "preparacao": "convite de fornecedor do F1, e-mail ze@x.com; F2 existe",
        "acao": "POST de cadastro com fornecedor=F2 e papel=comprador extras",
        "resultado": "a conta criada pelo convite de fornecedor tem papel fornecedor e é do F1 (os extras F2 e papel comprador são ignorados)",
        "veredito": "íntegra",
    },
    (
        62,
        "Conta de comprador não é convertida em conta de fornecedor",
        "tests/aceitacao/test_cenario_62_papel_imutavel.py::test_banco_recusa_trocar_o_papel_mesmo_com_fornecedor_preenchido",
    ): {
        "preparacao": "conta de comprador ana e um fornecedor existente",
        "acao": "UPDATE em SQL direto trocando o papel para fornecedor e preenchendo o fornecedor",
        "resultado": "o banco levanta DatabaseError citando papel; depois de reler, a conta segue comprador e sem fornecedor",
        "veredito": "íntegra",
    },
    (
        62,
        "Conta de comprador não ganha o perfil de fornecedor",
        "tests/tecnicos/test_convites_cadastro.py::test_campos_extras_do_post_sao_ignorados_comprador",
    ): {
        "preparacao": "convite de comprador para bia@x.com; um fornecedor existente",
        "acao": "POST de cadastro com email, papel=fornecedor e fornecedor=<id> extras",
        "resultado": "a conta criada é comprador e sem fornecedor; nenhuma conta com o e-mail extra",
        "veredito": "íntegra",
    },
    (
        63,
        "Produto por peso a R$ 12,00/kg com incremento de 0,5 kg: 1,5 kg é aceito",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (KG, 0.5, 1.5): reservado e parcela de 1,5",
        "veredito": "íntegra",
    },
    (
        63,
        "Produto por peso a R$ 12,00/kg: 1,5 kg custa R$ 18,00",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (KG, 0.5, 1.5): subtotal de 1,5 a 12,00 igual a 18,00",
        "veredito": "íntegra",
    },
    (
        63,
        "Produto por peso com incremento de 0,5 kg: 1,2 kg é recusado pelo servidor",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (KG, 0.5, 1.2): QuantidadeInvalida, nenhuma parcela e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        63,
        "A recusa de 1,2 kg vale também pela API",
        "tests/aceitacao/test_cenario_63_rota_1_2_kg.py::test_cenario_63_rota_recusa_1_2_kg_sem_gravar",
    ): {
        "preparacao": "produto em kg a R$ 12,00 e incremento 0,5; comprador sem interesse e outro com 1,5 reservado",
        "acao": "POST /interesses/ com quantidade 1.2 e origem carrinho, pelos dois",
        "resultado": '200 com a mensagem de quantidade e sem "Interesse atualizado"; sem parcela nova; reservado 1,500 e a parcela original igual por conteúdo',
        "veredito": "íntegra",
    },
    (
        64,
        "0,35 kg a R$ 12,99/kg dá subtotal arredondado de R$ 4,55",
        "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_e_arredondado_uma_vez_so",
    ): {
        "preparacao": "um comprador com um item de 0,350 a 12,99 e frete 0,00 (função pura, sem produto)",
        "acao": "`calcular_cobranca`",
        "resultado": "subtotal 4,55 (de 4,5465), preço unitário 12,99 e quantidade 0,350",
        "veredito": "íntegra",
    },
    (
        64,
        "O arredondamento de 12,99 × 0,35 acontece uma única vez",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_12_99_vezes_0_35",
    ): {
        "preparacao": "os decimais 12,99 e 0,35",
        "acao": "`arredondar_centavos` do produto exato",
        "resultado": "o produto exato 4,5465 é arredondado de uma vez para 4,55",
        "veredito": "íntegra",
    },
    (
        65,
        "A quantidade do produto por peso fica congelada na abertura",
        "tests/tecnicos/test_pedidos_abertura.py::test_produto_por_peso_guarda_o_subtotal_arredondado",
    ): {
        "preparacao": "rodada com fechamento encerrado; produto por peso a 12,99 e 0,350 reservados",
        "acao": "abre o pagamento",
        "resultado": "o item gravado tem quantidade 0,350 (a do interesse)",
        "veredito": "íntegra",
    },
    (
        65,
        "O preço do produto por peso fica congelado na abertura",
        "tests/tecnicos/test_pedidos_abertura.py::test_produto_por_peso_guarda_o_subtotal_arredondado",
    ): {
        "preparacao": "rodada com fechamento encerrado; produto por peso a 12,99 e 0,350 reservados",
        "acao": "abre o pagamento",
        "resultado": "o item gravado tem preço unitário 12,99 e subtotal 4,55",
        "veredito": "íntegra",
    },
    (
        65,
        "Não há ajuste posterior por pesagem",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_nenhuma_rota_altera_pedido_item_t0_ou_frete",
    ): {
        "preparacao": "a lista de rotas do projeto",
        "acao": "varredura de rotas por nome (pedido, item, t0, frete) e das políticas",
        "resultado": "nenhuma rota de edição de pedido, item, T0 ou frete fora das permitidas; nenhuma rota sem política",
        "veredito": "íntegra",
    },
    (
        66,
        "Cadastro de produto com múltiplo incompatível com o incremento é recusado pelo serviço",
        "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
    ): {
        "preparacao": "administrador e fornecedor; 5 casos de incremento e múltiplo incompatíveis",
        "acao": "`criar_produto` com o caso",
        "resultado": "MultiploInvalido e nenhum produto criado, nos 5 casos",
        "veredito": "íntegra",
    },
    (
        66,
        "Cadastro de produto com múltiplo incompatível é recusado pela tela",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
    ): {
        "preparacao": "administrador logado; fornecedor; 4 casos de incremento e múltiplo incompatíveis",
        "acao": "POST do formulário de cadastro de produto com o caso",
        "resultado": "200 com erro no campo múltiplo e nenhum produto, nos 4 casos",
        "veredito": "íntegra",
    },
    (
        67,
        "O fornecedor vê seus produtos",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor",
    ): {
        "preparacao": "AF com a conta do fornecedor F logada",
        "acao": "GET da página da rodada no portal",
        "resultado": "a página lista P1 e P2",
        "veredito": "íntegra",
    },
    (
        67,
        "O fornecedor vê as quantidades",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal",
    ): {
        "preparacao": "AF com a conta do fornecedor logada",
        "acao": "GET do CSV do pedido formal",
        "resultado": "as linhas do CSV trazem a quantidade (P1;unidade;11;...)",
        "veredito": "íntegra",
    },
    (
        67,
        "O fornecedor vê os preços unitários",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal",
    ): {
        "preparacao": "AF com a conta do fornecedor logada",
        "acao": "GET do CSV do pedido formal",
        "resultado": "as linhas do CSV trazem o preço unitário 10,00 e o total 110,00",
        "veredito": "íntegra",
    },
    (
        67,
        "O fornecedor vê os valores totais dos produtos",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor",
    ): {
        "preparacao": "AF com a conta do fornecedor F logada",
        "acao": "GET da página da rodada no portal",
        "resultado": '"R$ 110,00", "R$ 60,00" e "Total dos produtos: R$ 170,00"',
        "veredito": "íntegra",
    },
    (
        67,
        "O fornecedor vê o andamento",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_portal_nao_expoe_dado_da_e14",
    ): {
        "preparacao": "AE liberada com ocorrência e retirada registradas; fornecedor logado",
        "acao": "GET da página da rodada e do CSV",
        "resultado": 'a página mostra "Disponível para retirada" e "Pedido formal"; sem previsão depois da liberação; dados só da etapa',
        "veredito": "íntegra",
    },
    (
        67,
        "O fornecedor vê o pedido formal",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor",
    ): {
        "preparacao": "AF com a conta do fornecedor F logada",
        "acao": "GET da página da rodada no portal",
        "resultado": '"Pedido formal nº" com o número e "Emitido em 04/11/2026 10:00"',
        "veredito": "íntegra",
    },
    (
        67,
        "O fornecedor vê a previsão de entrega",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_pedido_formal_e_a_previsao_para_o_fornecedor",
    ): {
        "preparacao": "AF com a conta do fornecedor F logada",
        "acao": "GET da página da rodada no portal",
        "resultado": '"Previsão de entrega: 11/11/2026"; e nenhum termo proibido (Tentativa, Frete, serviço, Repasse)',
        "veredito": "íntegra",
    },
    (
        67,
        "Consulta de pagamentos individuais é recusada ao fornecedor",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
    ): {
        "preparacao": "arranjo AF com a conta do fornecedor F logada; pedido X de A",
        "acao": "9 acessos diretos (GET e POST) a pedido de comprador, pagar e telas financeiras",
        "resultado": "o GET da página e o POST de pagar do pedido de A dão 403, nos 9 acessos",
        "veredito": "íntegra",
    },
    (
        67,
        "Consulta de dados de compradores é recusada ao fornecedor",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
    ): {
        "preparacao": "arranjo AF com a conta do fornecedor F logada; pedido X de A",
        "acao": "9 acessos diretos (GET e POST) a pedido de comprador, pagar e telas financeiras",
        "resultado": 'as 9 respostas são 403 e a página não traz "Comprador A"',
        "veredito": "íntegra",
    },
    (
        67,
        "Consulta da taxa de serviço é recusada ao fornecedor",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
    ): {
        "preparacao": "arranjo AF com a conta do fornecedor F logada; pedido X de A",
        "acao": "9 acessos diretos (GET e POST) a pedido de comprador, pagar e telas financeiras",
        "resultado": "as telas do financeiro (resumo) respondem 403 ao fornecedor",
        "veredito": "íntegra",
    },
    (
        67,
        "Consulta da reserva é recusada ao fornecedor",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
    ): {
        "preparacao": "arranjo AF com a conta do fornecedor F logada; pedido X de A",
        "acao": "9 acessos diretos (GET e POST) a pedido de comprador, pagar e telas financeiras",
        "resultado": "a tela da reserva e a de movimentos respondem 403 ao fornecedor",
        "veredito": "íntegra",
    },
    (
        67,
        "Consulta de dados de outro fornecedor é recusada",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_rodada_de_outro_fornecedor_ou_inexistente_da_o_mesmo_404",
    ): {
        "preparacao": "fornecedor F logado; fornecedor G com rodada em interesse",
        "acao": "GET da rodada de G, do CSV do pedido formal de G e de uma rodada inexistente",
        "resultado": "a rodada, o CSV de G e uma rodada inexistente dão 404 com o mesmo corpo",
        "veredito": "íntegra",
    },
    (
        67,
        "A exportação do fornecedor só traz campos permitidos",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal",
    ): {
        "preparacao": "AF com a conta do fornecedor logada",
        "acao": "GET do CSV do pedido formal",
        "resultado": "CSV com cabeçalho e linhas exatos e 7 colunas; tipo text/csv utf-8",
        "veredito": "íntegra",
    },
    (
        68,
        "Falha na primeira tentativa e sucesso na segunda: duas tentativas registradas",
        "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha",
    ): {
        "preparacao": "AF; o backend de e-mail falha na 1ª tentativa; envio do pedido formal criado",
        "acao": "processa em PRAZO e de novo em PRAZO+5 min",
        "resultado": "tentativa 1 falha (ConnectionError) e 2 sucesso; envio concluído com sucesso; próxima tentativa agendada em +5 min",
        "veredito": "íntegra",
    },
    (
        68,
        "Falha na primeira tentativa e sucesso na segunda: um envio",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_do_resultado_aprovado_ao_pedido_aceito",
    ): {
        "preparacao": "AF pela tela; o backend de e-mail falha uma vez; outbox limpo",
        "acao": "processa em PRAZO e em PRAZO+5 min; o portal é lido",
        "resultado": "tentativas (1, falha) e (2, sucesso); exatamente 1 e-mail igual ao pedido formal; sem aviso de falha",
        "veredito": "íntegra",
    },
    (
        68,
        "Falha na primeira tentativa e sucesso na segunda: sem aviso ao administrador",
        "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha",
    ): {
        "preparacao": "AF; o backend de e-mail falha na 1ª tentativa; envio do pedido formal criado",
        "acao": "processa em PRAZO e de novo em PRAZO+5 min",
        "resultado": "nenhuma notificação de falha do pedido formal",
        "veredito": "íntegra",
    },
    (
        69,
        "Três tentativas falham: não há quarta tentativa automática",
        "tests/tecnicos/test_pedido_formal_envio.py::test_exatamente_tres_tentativas_automaticas",
    ): {
        "preparacao": "AF; o backend de e-mail falha sempre; envio criado em PRAZO",
        "acao": "`_tres_falhas` processa as 3 tentativas; depois processa em +120 min e +1 dia",
        "resultado": "3 tentativas automáticas (1, 2, 3) com falha; envio concluído com falhas, sem próxima tentativa; os processamentos seguintes devolvem 0 e continuam 3 tentativas",
        "veredito": "íntegra",
    },
    (
        69,
        "Três tentativas falham: o administrador é notificado",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
    ): {
        "preparacao": "AF pela tela; backend de e-mail falho; pedido formal fotografado antes",
        "acao": "3 falhas automáticas; durante o envio o POST de reenvio; depois 2 reenvios manuais pela tela",
        "resultado": "a notificação de falha ao administrador existe e tem link; tipos das tentativas 3 automáticas e 2 manuais; envio concluído com falhas",
        "veredito": "íntegra",
    },
    (
        69,
        "Três tentativas falham: o botão Reenviar pedido fica disponível",
        "tests/tecnicos/test_pedido_formal_telas.py::test_depois_das_tres_falhas_o_formulario_aparece",
    ): {
        "preparacao": "administrador logado; AF com 3 falhas automáticas",
        "acao": "GET da página do pedido formal",
        "resultado": 'a página mostra "Envio automático concluído sem sucesso depois de 3 tentativas.", 3 falhas ConnectionError e o formulário com o campo token',
        "veredito": "íntegra",
    },
    (
        69,
        "O reenvio usa o mesmo pedido formal",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
    ): {
        "preparacao": "AF com 3 falhas; outbox limpo; pedido formal fotografado",
        "acao": "`reenviar_pedido_formal` pelo administrador com um token",
        "resultado": "a tentativa manual 4 (sucesso, token, destino) é do mesmo pedido; o pedido formal e suas linhas ficam iguais ao fotografado",
        "veredito": "íntegra",
    },
    (
        69,
        "O reenvio usa os mesmos produtos, quantidades e valores",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
    ): {
        "preparacao": "AF com 3 falhas; outbox limpo; pedido formal fotografado",
        "acao": "`reenviar_pedido_formal` pelo administrador com um token",
        "resultado": "o e-mail enviado tem o assunto e o corpo do pedido formal; produtos, quantidades e valores iguais ao fotografado",
        "veredito": "íntegra",
    },
    (
        70,
        "Duplo clique em Reenviar pedido gera um único envio",
        "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro",
    ): {
        "preparacao": "administrador logado; AF com 3 falhas; token lido da página; outbox limpo",
        "acao": "POST de reenvio duas vezes com o mesmo token; depois novo POST com o token novo",
        "resultado": 'o segundo POST mostra "Este reenvio já tinha sido registrado." e só 1 e-mail foi enviado',
        "veredito": "íntegra",
    },
    (
        70,
        "Um novo clique feito depois gera uma nova tentativa registrada",
        "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro",
    ): {
        "preparacao": "administrador logado; AF com 3 falhas; token lido da página; outbox limpo",
        "acao": "POST de reenvio duas vezes com o mesmo token; depois novo POST com o token novo",
        "resultado": "o token novo difere do anterior e passa a haver 2 e-mails, ambos iguais ao pedido formal",
        "veredito": "íntegra",
    },
    (
        70,
        "O duplo clique não cria pedido novo",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
    ): {
        "preparacao": "AF pela tela; 3 falhas; dois POST em paralelo com o mesmo token, o primeiro pausado dentro do envio",
        "acao": "os dois POST são executados em paralelo",
        "resultado": "os dois dão 302; 1 e-mail; 1 tentativa manual; (R12) continua 1 PedidoFormal da rodada",
        "veredito": "corrigida: assert acrescentado (um só pedido formal)",
    },
    (
        70,
        "O novo clique depois não cria pedido novo",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
    ): {
        "preparacao": "AF pela tela; 3 falhas; dois POST em paralelo com tokens diferentes",
        "acao": "os dois POST são executados em paralelo",
        "resultado": "a segunda tentativa só começa depois de a primeira terminar; 2 e-mails; (R12) continua 1 PedidoFormal",
        "veredito": "corrigida: assert acrescentado (um só pedido formal)",
    },
    (
        71,
        "Na fase de interesse o administrador altera o mínimo",
        "tests/tecnicos/test_rodadas_minimo.py::test_altera_o_minimo_em_interesse_e_audita",
    ): {
        "preparacao": "fornecedor com mínimo 150,00 e rodada em interesse; administrador logado",
        "acao": 'POST do mínimo "200,00"',
        "resultado": "302 para o fornecedor; mínimo 200,00; auditoria com anterior 150,00",
        "veredito": "íntegra",
    },
    (
        71,
        "Na fase de interesse o administrador altera o múltiplo",
        "tests/tecnicos/test_catalogo_condicoes.py::test_alterar_e_remover_o_multiplo_em_interesse",
    ): {
        "preparacao": "produto com incremento 0,25 e múltiplo 1 em rodada de interesse; administrador logado",
        "acao": 'POST do múltiplo "2" e depois vazio',
        "resultado": "302 nos dois; múltiplo 2,000 e depois nenhum; auditorias das duas alterações",
        "veredito": "íntegra",
    },
    (
        71,
        "Na fase de interesse o administrador altera o estoque",
        "tests/tecnicos/test_rodadas_estoque.py::test_reducao_ate_o_reservado_e_aceita",
    ): {
        "preparacao": "estoque com limite 10 e 6 reservadas",
        "acao": "`alterar_estoque` para 8 e depois para 6",
        "resultado": "limite 6,000; auditorias com anterior e novo (10→8, 8→6) e rodada, produto e estoque",
        "veredito": "íntegra",
    },
    (
        71,
        "Redução de estoque abaixo da quantidade reservada é recusada",
        "tests/tecnicos/test_rodadas_estoque.py::test_reducao_abaixo_do_reservado_e_recusada",
    ): {
        "preparacao": "estoque com limite 10 e 6 reservadas",
        "acao": "`alterar_estoque` para 5",
        "resultado": "EstoqueAbaixoDoReservado citando 6; limite segue 10,000; nenhuma auditoria nem sinal",
        "veredito": "íntegra",
    },
    (
        72,
        "Do fechamento em diante alterar o mínimo é recusado",
        "tests/tecnicos/test_rodadas_minimo.py::test_minimo_congelado_pelo_servico",
    ): {
        "preparacao": "fornecedor com mínimo 150,00 e rodada em cada etapa congelada (parametrize ETAPAS_CONGELADAS)",
        "acao": '`alterar_minimo` para "200,00" pelo administrador',
        "resultado": "CondicoesCongeladas (fora_de_interesse) em cada etapa de fechamento em diante; mínimo 150,00 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        72,
        "Do fechamento em diante alterar o múltiplo é recusado",
        "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico",
    ): {
        "preparacao": "produto em rodada em cada etapa congelada, sem rodada e em retirada (parametrize); administrador logado",
        "acao": 'POST do múltiplo "2" pela rota e `alterar_multiplo` pelo serviço',
        "resultado": "a rota dá 409 com a mensagem e o serviço levanta CondicoesCongeladas; múltiplo segue 1,000 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        72,
        "Do fechamento em diante alterar o estoque é recusado",
        "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pelo_servico",
    ): {
        "preparacao": "rodada em cada etapa congelada com estoque 10 e outro produto",
        "acao": "`incluir_produto_na_rodada` e `alterar_estoque` pelo administrador",
        "resultado": "CondicoesCongeladas (fora_de_interesse) nas duas operações; limite segue 10,000, 1 estoque e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        72,
        "A recusa vale para o administrador",
        "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pela_rota",
    ): {
        "preparacao": "rodada em cada etapa congelada; administrador logado",
        "acao": "POSTs de incluir e de alterar o estoque",
        "resultado": "o administrador recebe 409 com a mensagem; limite 10,000, 1 estoque e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        72,
        "A recusa vale pela API",
        "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico",
    ): {
        "preparacao": "produto em rodada em cada etapa congelada, sem rodada e em retirada (parametrize); administrador logado",
        "acao": 'POST do múltiplo "2" pela rota e `alterar_multiplo` pelo serviço',
        "resultado": "a rota HTTP chamada direto dá 409 com a mensagem de condições congeladas, em todas as etapas do caso",
        "veredito": "corrigida: religada (a ligação anterior usava só serviços)",
    },
    (
        72,
        "Alterar preço continua permitido no fechamento",
        "tests/tecnicos/test_catalogo_incremento.py::test_preco_continua_editavel_no_fechamento",
    ): {
        "preparacao": "produto do cenário 105 em rodada em fechamento; administrador logado",
        "acao": "POST de edição do produto com preço 12,50",
        "resultado": "302 e preço 12,50 gravado",
        "veredito": "íntegra",
    },
    (
        72,
        "A alteração de preço no fechamento atinge os interesses",
        "tests/tecnicos/test_interesses_preco.py::test_preco_alterado_no_fechamento_atinge_o_carrinho",
    ): {
        "preparacao": "produto em kg a 7,99 com rodada em fechamento; A com 1 kg reservado",
        "acao": "o administrador muda o preço para 8,99; A abre o carrinho",
        "resultado": 'A recebe 1 aviso preco_alterado e o carrinho mostra "Subtotal: R$ 8,99"',
        "veredito": "íntegra",
    },
    (
        73,
        "Quando a rodada volta para interesse, as condições voltam a ser editáveis",
        "tests/tecnicos/test_rodadas_ciclos.py::test_condicoes_voltam_a_ser_editaveis_na_volta_para_interesse",
    ): {
        "preparacao": "cenário com mínimo 150, P (múltiplo 3, estoque 10); fechamento simulado",
        "acao": "tenta alterar o mínimo no fechamento; depois da volta para interesse altera mínimo, múltiplo e estoque",
        "resultado": "recusa em fechamento (CondicoesCongeladas); depois da volta: mínimo 200,00, múltiplo 6,000 e estoque 20,000",
        "veredito": "íntegra",
    },
    (
        73,
        "Os registros do ciclo anterior continuam com os valores originais",
        "tests/tecnicos/test_rodadas_ciclos.py::test_cenario_73_ciclos_anteriores_nao_mudam",
    ): {
        "preparacao": "fechamento do ciclo 1 simulado e volta para interesse; condições do ciclo 1 lidas",
        "acao": "altera mínimo e múltiplo e inicia o ciclo 2",
        "resultado": "o ciclo 1 mantém mínimo 150,00 e suas condições; o ciclo 2 tem 200,00 e as novas condições; 2 ciclos numerados 1 e 2",
        "veredito": "íntegra",
    },
    (
        74,
        "As unidades pagas por A na caixa invalidada vão para a fila de pendentes do fornecedor",
        "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila",
    ): {
        "preparacao": "AP-viável apurado; a parcela do pedido de A na caixa de P2 lida antes",
        "acao": "a apuração restaura a caixa invalidada",
        "resultado": "a parcela de A em P2 fica pendente com 4,000 e 0 reservado; a restauração liga ao pedido e à apuração",
        "veredito": "íntegra",
    },
    (
        74,
        "As unidades voltam à fila sem reservar estoque da rodada apurada",
        "tests/tecnicos/test_apuracao_viavel.py::test_a_fila_nao_reserva_na_rodada_apurada",
    ): {
        "preparacao": "AP-viável apurado; unidades de P2 de A pendentes depois da caixa invalidada",
        "acao": "lê o reservado total de P2 e chama `alocar_pendentes` do fornecedor",
        "resultado": "alocação 0,000 e reservado de P2 0,000; a parcela segue pendente com a mesma sequência",
        "veredito": "íntegra",
    },
    (
        74,
        "As unidades voltam à fila antes da conclusão do estorno",
        "tests/tecnicos/test_apuracao_viavel.py::test_a_restauracao_nao_espera_a_autorizacao_da_devolucao",
    ): {
        "preparacao": "AP-viável apurado; nenhuma devolução autorizada",
        "acao": "lê as parcelas de devolução e a parcela de A em P2",
        "resultado": "nenhuma parcela de devolução e a parcela de A em P2 já pendente",
        "veredito": "íntegra",
    },
    (
        74,
        "O pedido congelado não muda",
        "tests/tecnicos/test_apuracao_viavel.py::test_o_pedido_congelado_nao_muda",
    ): {
        "preparacao": "AP: X pago, relógio no prazo; pedidos, itens e parcelas do pedido fotografados antes da apuração",
        "acao": "`iniciar_apuracao`",
        "resultado": "pedidos, itens e parcelas no pedido iguais por conteúdo ao fotografado antes da apuração",
        "veredito": "íntegra",
    },
    (
        74,
        "Os itens válidos de A não mudam",
        "tests/tecnicos/test_apuracao_viavel.py::test_unidades_da_caixa_invalidada_voltam_para_a_fila",
    ): {
        "preparacao": "AP-viável apurado; a parcela do pedido de A na caixa de P2 lida antes",
        "acao": "a apuração restaura a caixa invalidada",
        "resultado": "a parcela de A em P1 segue em pedido com 6,000 reservadas depois da apuração",
        "veredito": "íntegra",
    },
    (
        75,
        "Na próxima rodada, A recebe 6 reservadas",
        "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes e C com 8 pendentes (nessa ordem); sequências lidas",
        "acao": "`alocar_pendentes` do fornecedor",
        "resultado": "A fica ativa com 6 reservadas e 0 pendentes",
        "veredito": "íntegra",
    },
    (
        75,
        "Na próxima rodada, C recebe 4 reservadas",
        "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes e C com 8 pendentes (nessa ordem); sequências lidas",
        "acao": "`alocar_pendentes` do fornecedor",
        "resultado": "C fica ativa com 4 reservadas",
        "veredito": "íntegra",
    },
    (
        75,
        "Na próxima rodada, 4 unidades de C continuam pendentes sem reserva",
        "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes e C com 8 pendentes (nessa ordem); sequências lidas",
        "acao": "`alocar_pendentes` do fornecedor",
        "resultado": "C tem 4 pendentes depois da alocação (original 8); sequências e originais iguais",
        "veredito": "íntegra",
    },
    (
        75,
        "O total reservado é 10",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_do_produto_atende_a_fila_pela_sequencia_original",
    ): {
        "preparacao": "FP: A, C e B da R1 apurada; sequências lidas; R2 aberta com limite 10 para P",
        "acao": "inclui P na rodada pelo serviço",
        "resultado": "reservado total de P igual a 10,000 (A 6, C 4 e 4 pendentes); sequências iguais",
        "veredito": "íntegra",
    },
    (
        76,
        "A adição de D sem estoque livre é recusada",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_adicao_sem_estoque_e_recusada_e_o_aumento_atende_c_antes_de_d",
    ): {
        "preparacao": "FP; R2 aberta com limite 10 para P (A 6 e C 4 reservadas, C com 4 pendentes); D é comprador novo",
        "acao": "D adiciona 3 sem estoque livre; o estoque é aumentado pelo serviço",
        "resultado": "EstoqueInsuficiente e D sem nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        76,
        "Liberado ou aumentado o estoque, as 4 pendentes de C são atendidas antes de D",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_adicao_sem_estoque_e_recusada_e_o_aumento_atende_c_antes_de_d",
    ): {
        "preparacao": "FP; R2 aberta com limite 10 para P (A 6 e C 4 reservadas, C com 4 pendentes); D é comprador novo",
        "acao": "D adiciona 3 sem estoque livre; o estoque é aumentado pelo serviço",
        "resultado": "depois do aumento C fica ativa com 8 reservadas e 0 pendentes, D continua sem parcela e o total reservado é 14",
        "veredito": "íntegra",
    },
    (
        77,
        "Unidades pendentes sem reserva não contam para o mínimo",
        "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
    ): {
        "preparacao": "produto a 10,00 sem limite; mínimo de 100,00; A com 8 reservadas e C com 5 pendentes",
        "acao": "`progresso_da_rodada(rodada, c)` do ponto de vista de C",
        "resultado": "elegível 80,00 (8 reservadas de A), 80%, mínimo de 100,00 não atingido, falta 20,00; C tem 0 reservado e 5 pendente",
        "veredito": "íntegra",
    },
    (
        77,
        "Unidades pendentes sem reserva não entram em pedido quando a rodada abre pagamento",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
    ): {
        "preparacao": "FP; R2 com P (limite 10) e Q; A adiciona 10 de Q; C tem 4 pendentes de P",
        "acao": "o progresso é lido e o administrador inicia o fechamento (e o pedido é aberto)",
        "resultado": "o item de P do pedido de C tem 4,000 (só as reservadas)",
        "veredito": "íntegra",
    },
    (
        77,
        "As pendentes continuam na fila para a rodada seguinte",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
    ): {
        "preparacao": "FP; R2 com P (limite 10) e Q; A adiciona 10 de Q; C tem 4 pendentes de P",
        "acao": "o progresso é lido e o administrador inicia o fechamento (e o pedido é aberto)",
        "resultado": "a parcela de C segue pendente com 4,000 depois de aberto o pagamento",
        "veredito": "íntegra",
    },
    (
        78,
        "A apuração reexecutada não duplica parcela nem restauração",
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ): {
        "preparacao": "AP-viável apurado; a parcela de A em P2 restaurada e lida antes; resultado da apuração recalculado",
        "acao": "o passo de restauração e estorno é repetido numa transação",
        "resultado": "depois de repetir o passo: 1 restauração, 1 reembolso, 1 obrigação e a parcela única igual",
        "veredito": "íntegra",
    },
    (
        78,
        "A reserva da fila em paralelo com novas adições não duplica a reserva",
        "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem",
    ): {
        "preparacao": "produto com limite 6; A com 4 pendentes; E é comprador novo",
        "acao": "a alocação da fila e a adição de 4 por E em paralelo, nas duas ordens",
        "resultado": 'sem exceções; a adição de E recusada com "Há apenas 2 unidade disponível."; A com 4 reservadas e 0 pendentes; só 1 parcela',
        "veredito": "íntegra",
    },
    (
        78,
        "O total reservado nunca passa do estoque",
        "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem",
    ): {
        "preparacao": "produto com limite 6; A com 4 pendentes; E é comprador novo",
        "acao": "a alocação da fila e a adição de 4 por E em paralelo, nas duas ordens",
        "resultado": "o total reservado é 4, dentro do limite 6, nas duas ordens",
        "veredito": "íntegra",
    },
    (
        78,
        "A ordem da fila segue a posição original",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro",
    ): {
        "preparacao": "FP; R2 sem múltiplo; E comprador novo; corrida entre incluir P na rodada e a adição de E",
        "acao": "duas threads: a inclusão de P (atende a fila) e a adição de E",
        "resultado": "A 6 e C 4 ativas (C com 4 pendentes), E recusado por EstoqueInsuficiente e sem parcela; total reservado 10",
        "veredito": "íntegra",
    },
    (
        79,
        "O inadimplente B não tem unidade do fornecedor na fila de pendentes",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_inadimplente_perde_as_parcelas_do_fornecedor",
    ): {
        "preparacao": "apurada com só X pago; as 3 parcelas de B em pedido lidas antes",
        "acao": "`iniciar_apuracao`",
        "resultado": "as 3 parcelas de B passam a removidas, sem reservado nem pendente",
        "veredito": "íntegra",
    },
    (
        79,
        "A pendente antiga do inadimplente também sai da fila",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai",
    ): {
        "preparacao": "apurada com só X pago; B com 3 pendentes antigas de P3, do mesmo fornecedor e fora da rodada",
        "acao": "`iniciar_apuracao`",
        "resultado": "a pendente antiga de B fica removida e B não tem mais parcela na fila do fornecedor",
        "veredito": "íntegra",
    },
    (
        80,
        "Convite para e-mail já usado por outra conta é recusado",
        "tests/tecnicos/test_convites_emissao.py::test_emissao_recusa_email_ja_em_uso_por_qualquer_conta",
    ): {
        "preparacao": "conta ana@exemplo.com em cada situação (ativa, suspensa, removida) e como comprador ou fornecedor (6 casos)",
        "acao": 'o administrador emite convite para "  Ana@Exemplo.com "',
        "resultado": "EmailEmUso nos 6 casos, nenhum Convite criado e nenhum e-mail enviado",
        "veredito": "íntegra",
    },
    (
        80,
        "Cadastro para e-mail já usado por outra conta é recusado",
        "tests/tecnicos/test_convites_cadastro_concorrencia.py::test_dois_convites_com_mesmo_email_normalizado_em_paralelo",
    ): {
        "preparacao": "10 repetições: dois convites (comprador e fornecedor) para o mesmo e-mail",
        "acao": "os dois cadastros rodam em paralelo",
        "resultado": "só 1 cadastro conclui; o outro falha com email_em_uso; 1 conta com o e-mail; o recusado não consome o convite",
        "veredito": "íntegra",
    },
    (
        80,
        "O e-mail escrito com maiúsculas ou espaços diferentes também é recusado",
        "tests/tecnicos/test_contas_modelo.py::test_conta_recusa_email_em_uso_com_variacao_de_caixa_e_espacos",
    ): {
        "preparacao": "conta ana@exemplo.com existente",
        "acao": 'tenta criar contas com "  Ana@Exemplo.com " (comprador e fornecedor)',
        "resultado": "EmailEmUso nas duas tentativas e continua 1 conta",
        "veredito": "íntegra",
    },
    (
        81,
        "As contas de comprador e de fornecedor da mesma pessoa funcionam de forma independente",
        "tests/tecnicos/test_convites_cadastro.py::test_comprador_e_fornecedor_com_emails_diferentes_sao_contas_independentes",
    ): {
        "preparacao": "dois convites: ana@exemplo.com (comprador) e ana.fornecedor@exemplo.com (fornecedor)",
        "acao": "as duas pessoas se cadastram e abrem /inicio/",
        "resultado": "2 contas; cada /inicio/ mostra só o próprio nome e papel",
        "veredito": "íntegra",
    },
    (
        81,
        "Banir o e-mail do comprador não bloqueia o do fornecedor",
        "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa",
    ): {
        "preparacao": "contas ana (comprador) e ana.fornecedor (fornecedor), cada uma com sessões abertas por login",
        "acao": "o administrador remove a conta de comprador; a fornecedora abre /inicio/ e entra de novo",
        "resultado": "a sessão da fornecedora segue com /inicio/ 200, a do comprador cai (302) e a fornecedora entra de novo",
        "veredito": "íntegra",
    },
    (
        82,
        "Google com e-mail de uma conta acessa somente essa conta",
        "tests/tecnicos/test_contas_google_login.py::test_segundo_login_com_o_mesmo_uid_entra_na_mesma_conta",
    ): {
        "preparacao": "conta ana@x.com; um primeiro retorno do Google já feito",
        "acao": 'outro cliente retorna do Google com o mesmo uid e "ANA@x.com"',
        "resultado": "a sessão do segundo cliente é da mesma conta e há 1 SocialAccount",
        "veredito": "íntegra",
    },
    (
        82,
        "Google com e-mail de uma conta nunca cria uma segunda",
        "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social",
    ): {
        "preparacao": "conta ana@x.com existente; contagem de contas lida antes",
        "acao": 'retorno do Google com "Ana@X.com"',
        "resultado": "302; sessão da conta existente; conta social ligada a ela; número de contas igual",
        "veredito": "íntegra",
    },
    (
        82,
        "Google com e-mail sem conta nem convite válido não cria conta",
        "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada",
    ): {
        "preparacao": "nenhuma conta nem convite; contagens lidas antes",
        "acao": "retorno do Google com nova@x.com",
        "resultado": "`_recusado`: 302 para /entrar/, recusa, sem sessão e contagens iguais",
        "veredito": "íntegra",
    },
    (
        83,
        "No banimento, as duas sessões abertas são invalidadas",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes",
    ): {
        "preparacao": "administrador logado; conta ana@x.com com 2 sessões abertas por login real",
        "acao": "o administrador remove a conta pela tela",
        "resultado": "antes 2 sessões; depois 0 (Session e UserSession); conta removida; e-mail banido pelo administrador; 1 auditoria de remoção",
        "veredito": "íntegra",
    },
    (
        83,
        "No banimento, a próxima requisição de cada sessão é recusada",
        "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou",
    ): {
        "preparacao": "conta com 4 sessões; o apagamento de sessões é anulado (monkeypatch) e a conta é removida",
        "acao": "GET nas duas primeiras sessões e POST nas duas últimas",
        "resultado": "nada foi apagado (4 sessões); o GET vai a /entrar/ com a mensagem de sessão encerrada; o POST dá 403; nenhuma view autenticada executou",
        "veredito": "íntegra",
    },
    (
        83,
        "Novo login por senha de conta banida é recusado",
        "tests/tecnicos/test_moderacao_remocao.py::test_conta_removida_nao_entra_por_nenhum_metodo_nem_recebe_convite",
    ): {
        "preparacao": "conta ana@x.com com senha, removida pelo administrador",
        "acao": "tenta login por senha, pedido de link e retorno do Google; tenta novo convite com o e-mail",
        "resultado": "a conta removida (e-mail banido pela remoção) não abre sessão por senha",
        "veredito": "íntegra",
    },
    (
        83,
        "Novo login por link de conta banida é recusado",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link",
    ): {
        "preparacao": "conta ana@x.com removida, ou ativa com e-mail em EmailBanido; 3 grafias do e-mail e 2 casos",
        "acao": "pedido de link com a grafia do caso",
        "resultado": "banido: resposta padrão, 0 links, 0 e-mails e sem sessão, nas 3 grafias do e-mail",
        "veredito": "íntegra",
    },
    (
        83,
        "Novo login pelo Google de conta banida é recusado",
        "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
    ): {
        "preparacao": "conta com e-mail banido (ana@x.com, com espaço e caixa) ou conta removida; contagens antes (2 casos)",
        "acao": "retorno do Google com esse e-mail",
        "resultado": "banido (com espaço e caixa): `_recusado`, 302 para /entrar/, sem sessão e contagens iguais",
        "veredito": "íntegra",
    },
    (
        83,
        "Os históricos são preservados",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_preserva_conta_historico_e_convite",
    ): {
        "preparacao": "convite consumido que criou a conta ana@x.com",
        "acao": "o administrador remove a conta",
        "resultado": "a conta continua existindo como removida; o convite segue ligado a ela; auditoria da remoção do objeto",
        "veredito": "íntegra",
    },
    (
        84,
        "usuario@gmail.com e usuario+teste@gmail.com podem pertencer a contas distintas",
        "tests/aceitacao/test_cenarios_84_aliases_contas_distintas.py::test_cenario_84_aliases_com_mais_sao_contas_distintas",
    ): {
        "preparacao": "dois convites: usuario@gmail.com e usuario+teste@gmail.com",
        "acao": "dois clientes fazem o cadastro por convite, um por e-mail",
        "resultado": "2 contas distintas (pk diferentes) com os dois e-mails exatos e nomes Base e Alias; cada sessão é da própria conta",
        "veredito": "íntegra",
    },
    (
        84,
        "Banir um endereço não afeta o outro",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_afeta_so_o_endereco_exato",
    ): {
        "preparacao": "contas ana@x.com e o alias ana+1@x.com (com senha); o administrador remove ana",
        "acao": "o alias faz login e o administrador emite convite para a.na@x.com",
        "resultado": "ao remover ana@x.com, o alias ana+1@x.com segue ativo e com sessão (mesma forma de usuario e usuario+teste; os endereços são ilustrativos)",
        "veredito": "íntegra",
    },
    (
        85,
        "Produto em litros com incremento de 0,5 L: 1,5 L é aceito",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (LITRO, 0.5, 1.5): reservado e parcela de 1,5",
        "veredito": "íntegra",
    },
    (
        85,
        "Produto em litros com incremento de 0,5 L: 1,2 L é recusado",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (LITRO, 0.5, 1.2): QuantidadeInvalida e nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        85,
        "Produto em unidades com incremento 1: 2 é aceito",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (UNIDADE, 1, 2): reservado e parcela de 2",
        "veredito": "íntegra",
    },
    (
        85,
        "Produto em unidades com incremento 1: 2,5 é recusado",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (UNIDADE, 1, 2.5): QuantidadeInvalida e nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        85,
        "Produto em kg com incremento de 0,25 kg: 0,75 kg é aceito",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (KG, 0.25, 0.75): reservado e parcela de 0,75",
        "veredito": "íntegra",
    },
    (
        85,
        "As validações de quantidade ocorrem no servidor, inclusive pela API",
        "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
    ): {
        "preparacao": "produto montado sem banco com o incremento do caso (14 casos de entradas recusadas)",
        "acao": "`validar_quantidade(produto, entrada)`",
        "resultado": 'a função de servidor `validar_quantidade` levanta QuantidadeInvalida nos casos recusados (cláusula "no servidor"; a cláusula "pela API" é provada pelo teste da rota)',
        "veredito": "íntegra",
    },
    (
        85,
        "As validações de quantidade ocorrem no servidor, inclusive pela API",
        "tests/aceitacao/test_cenario_63_rota_1_2_kg.py::test_cenario_63_rota_recusa_1_2_kg_sem_gravar",
    ): {
        "preparacao": "produto em kg a R$ 12,00 e incremento 0,5; comprador sem interesse e outro com 1,5 reservado",
        "acao": "POST /interesses/ com quantidade 1.2 e origem carrinho, pelos dois",
        "resultado": "a rota HTTP chamada direto recusa a quantidade inválida (200 com a mensagem, sem parcela e sem alterar o reservado)",
        "veredito": "íntegra",
    },
    (
        86,
        "Incremento igual a zero é recusado no cadastro do produto",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela",
    ): {
        "preparacao": "administrador logado; fornecedor; 4 entradas de incremento (0, -1, 0,0001, abc)",
        "acao": "POST do cadastro do produto com o incremento do caso",
        "resultado": 'caso "0": 200 com erro no campo incremento e nenhum produto',
        "veredito": "íntegra",
    },
    (
        86,
        "Incremento negativo é recusado no cadastro do produto",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incremento_invalido_na_tela",
    ): {
        "preparacao": "administrador logado; fornecedor; 4 entradas de incremento (0, -1, 0,0001, abc)",
        "acao": "POST do cadastro do produto com o incremento do caso",
        "resultado": 'caso "-1": 200 com erro no campo incremento e nenhum produto',
        "veredito": "íntegra",
    },
    (
        87,
        "Múltiplo de 1 kg com incremento de 0,25 kg é aceito",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
    ): {
        "preparacao": "administrador logado; fornecedor; os casos (0,25 e 1) e (2 e 12), unidade kg do formulário",
        "acao": "POST do cadastro do produto com o incremento e o múltiplo do caso",
        "resultado": 'caso ("0,25", "1"): 302 e o produto gravado com múltiplo 1',
        "veredito": "íntegra",
    },
    (
        87,
        "Múltiplo de 1 kg com incremento de 0,3 kg é recusado",
        "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
    ): {
        "preparacao": "administrador e fornecedor; 5 casos de incremento e múltiplo incompatíveis",
        "acao": "`criar_produto` com o caso",
        "resultado": 'caso ("0.3", "1") em kg: MultiploInvalido e nenhum produto',
        "veredito": "íntegra",
    },
    (
        87,
        "Na fase de interesse, alteração que torne o múltiplo incompatível é recusada",
        "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_invalido_em_interesse",
    ): {
        "preparacao": "produto com incremento 0,25 e múltiplo 1 em rodada de interesse; administrador logado",
        "acao": 'POST do múltiplo "0,9"',
        "resultado": "200 com erro no campo múltiplo; o múltiplo segue 1,000 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        87,
        "A partir do fechamento, qualquer alteração de múltiplo é recusada",
        "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_congelado_pela_rota_e_pelo_servico",
    ): {
        "preparacao": "produto em rodada em cada etapa congelada, sem rodada e em retirada (parametrize); administrador logado",
        "acao": 'POST do múltiplo "2" pela rota e `alterar_multiplo` pelo serviço',
        "resultado": "em cada etapa congelada a rota dá 409 com a mensagem e o serviço levanta CondicoesCongeladas; o múltiplo segue 1,000",
        "veredito": "íntegra",
    },
    (
        88,
        "7,99/kg × 0,25 kg tem subtotal cobrado de R$ 2,00",
        "tests/tecnicos/test_pedidos_calculo.py::test_subtotal_arredondado_por_item",
    ): {
        "preparacao": "um comprador com itens de 7,99, 2,50 e 12,99 por 0,250, 0,250 e 0,350 (função pura)",
        "acao": "`calcular_cobranca`",
        "resultado": "os subtotais são 2,00 (7,99 × 0,250), 0,63 e 4,55",
        "veredito": "íntegra",
    },
    (
        88,
        "O produto exato 7,99 × 0,25 é arredondado para R$ 2,00",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_7_99_vezes_0_25",
    ): {
        "preparacao": "os decimais 7,99 e 0,25",
        "acao": "`arredondar_centavos` do produto exato",
        "resultado": "o produto exato 1,9975 vira 2,00",
        "veredito": "íntegra",
    },
    (
        89,
        "2,50/kg × 0,25 kg arredonda para R$ 0,63",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_2_50_vezes_0_25",
    ): {
        "preparacao": "os decimais 2,50 e 0,25",
        "acao": "`arredondar_centavos` do produto exato",
        "resultado": "o produto exato 0,625 vira 0,63",
        "veredito": "íntegra",
    },
    (
        89,
        "Dois itens de R$ 0,625 somam P = R$ 1,26",
        "tests/tecnicos/test_pedidos_calculo.py::test_produtos_soma_os_subtotais_ja_arredondados",
    ): {
        "preparacao": "um comprador com dois itens de 2,50 por 0,250 (função pura)",
        "acao": "`calcular_cobranca`",
        "resultado": "o total de produtos é 1,26 (dois subtotais de 0,63)",
        "veredito": "íntegra",
    },
    (
        89,
        "A soma dos subtotais arredondados não é R$ 1,25",
        "tests/tecnicos/test_interesses_progresso.py::test_arredondamento_por_comprador",
    ): {
        "preparacao": "produto em kg a 2,50 e incremento 0,25; duas compradoras com 0,25 reservado cada",
        "acao": "`progresso_da_rodada`",
        "resultado": "o valor elegível é 1,26 (arredondado por comprador) e o bruto é 1,25: a soma não é 1,25",
        "veredito": "íntegra",
    },
    (
        90,
        "O preço novo do catálogo não altera o valor registrado de R$ 2,00",
        "tests/aceitacao/test_cenarios_90_item_inteiro_de_0_25_kg.py::test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado",
    ): {
        "preparacao": "pedido pago de 2,00 + 0,10 + 0,40 com um item de 0,250 kg a 7,99 (subtotal 2,00); o administrador muda o preço do produto para 8,99",
        "acao": "ocorrência da quantidade inteira (0,25) do item (`parcial`)",
        "resultado": "o produto passa a 8,99 e o item registrado segue com preço unitário 7,99 (e subtotal 2,00)",
        "veredito": "íntegra",
    },
    (
        90,
        "A ocorrência da quantidade inteira reembolsa o valor registrado de produtos",
        "tests/aceitacao/test_cenarios_90_item_inteiro_de_0_25_kg.py::test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado",
    ): {
        "preparacao": "pedido pago de 2,00 + 0,10 + 0,40 com um item de 0,250 kg a 7,99 (subtotal 2,00); o administrador muda o preço do produto para 8,99",
        "acao": "ocorrência da quantidade inteira (0,25) do item (`parcial`)",
        "resultado": "a linha do reembolso é o item inteiro: 0,250 por 2,00",
        "veredito": "íntegra",
    },
    (
        90,
        "Serviço e frete do reembolso são proporcionais aos valores registrados",
        "tests/aceitacao/test_cenarios_90_item_inteiro_de_0_25_kg.py::test_cenario_90_item_inteiro_de_0_25_kg_reembolsa_pelo_registrado",
    ): {
        "preparacao": "pedido pago de 2,00 + 0,10 + 0,40 com um item de 0,250 kg a 7,99 (subtotal 2,00); o administrador muda o preço do produto para 8,99",
        "acao": "ocorrência da quantidade inteira (0,25) do item (`parcial`)",
        "resultado": "componentes do reembolso 2,00, 0,10 e 0,40 (os registrados, não os recalculados com 8,99)",
        "veredito": "íntegra",
    },
    (
        91,
        "A devolução integral do cancelamento soma exatamente os valores cobrados registrados",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenarios_90_e_91_integral_devolve_exatamente_o_cobrado",
    ): {
        "preparacao": "pedido N pago de 100,00 + 5,00 + 20,00 com dois itens",
        "acao": "um reembolso parcial de 1 unidade e depois o integral do pedido",
        "resultado": "o acumulado devolvido do pedido é exatamente 100,00, 5,00 e 20,00",
        "veredito": "íntegra",
    },
    (
        91,
        "A devolução integral desconta as devoluções já concluídas",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago",
    ): {
        "preparacao": "pedido de 9,99 pago; um reembolso parcial concluído no simulador; rodada cancelada com reembolso",
        "acao": "as chamadas pendentes são processadas",
        "resultado": "o reembolso do cancelamento traz o saldo (5,99) e o estornado total soma 9,99",
        "veredito": "íntegra",
    },
    (
        91,
        "A devolução integral desconta as devoluções pendentes",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido",
    ): {
        "preparacao": "AP com X pago; apuração com caixa invalidada gera a obrigação pendente de 23,59 (sem parcela de devolução)",
        "acao": "a rodada é cancelada com reembolso",
        "resultado": "a obrigação pendente de caixa continua e o total devolvido de X é 94,35",
        "veredito": "íntegra",
    },
    (
        92,
        "Depois de um envio bem-sucedido, o botão Reenviar pedido está disponível",
        "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso",
    ): {
        "preparacao": "administrador logado; AF com envio automático bem-sucedido",
        "acao": "lê o token da página e faz POST do reenvio",
        "resultado": "a página do pedido formal traz o formulário com o token e o POST dele funciona (redireciona à mesma página)",
        "veredito": "íntegra",
    },
    (
        92,
        "O acionamento do reenvio gera uma única tentativa",
        "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso",
    ): {
        "preparacao": "administrador logado; AF com envio automático bem-sucedido",
        "acao": "lê o token da página e faz POST do reenvio",
        "resultado": 'as tentativas são exatamente uma automática e uma manual; a página mostra o sucesso, "Manual" e o administrador',
        "veredito": "íntegra",
    },
    (
        92,
        "O reenvio usa o mesmo pedido formal e o mesmo conteúdo",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
    ): {
        "preparacao": "AF com 3 falhas; outbox limpo; pedido formal fotografado",
        "acao": "`reenviar_pedido_formal` pelo administrador com um token",
        "resultado": "o reenvio é do mesmo pedido formal: assunto e corpo iguais e o pedido e as linhas iguais ao fotografado",
        "veredito": "íntegra",
    },
    (
        92,
        "O reenvio depois do sucesso não gera tentativas automáticas adicionais",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico",
    ): {
        "preparacao": "AF com envio automático bem-sucedido (1 tentativa)",
        "acao": "reenvio manual pelo administrador; depois processa +24 h",
        "resultado": "a tentativa 2 é sucesso; envio concluído com sucesso; o processamento depois de 24 h não faz nada e há só 2 tentativas",
        "veredito": "íntegra",
    },
    (
        93,
        "Reenvio manual que falha tem a falha registrada",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_que_falha_e_registrado_e_o_botao_continua",
    ): {
        "preparacao": "AF com 3 falhas; o backend de e-mail continua falhando; notificações contadas antes",
        "acao": "reenvio manual pelo administrador; depois processa +24 h",
        "resultado": "tentativa manual com resultado falha e resposta ConnectionError",
        "veredito": "íntegra",
    },
    (
        93,
        "Reenvio manual que falha não inicia tentativa automática",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_que_falha_e_registrado_e_o_botao_continua",
    ): {
        "preparacao": "AF com 3 falhas; o backend de e-mail continua falhando; notificações contadas antes",
        "acao": "reenvio manual pelo administrador; depois processa +24 h",
        "resultado": "o processamento depois de 24 h não faz nada; tentativas são 3 automáticas e 1 manual; nenhum aviso novo",
        "veredito": "íntegra",
    },
    (
        93,
        "Reenvio manual que falha mantém o botão disponível",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_que_falha_e_registrado_e_o_botao_continua",
    ): {
        "preparacao": "AF com 3 falhas; o backend de e-mail continua falhando; notificações contadas antes",
        "acao": "reenvio manual pelo administrador; depois processa +24 h",
        "resultado": "`pode_reenviar` continua verdadeiro depois do reenvio que falhou",
        "veredito": "íntegra",
    },
    (
        94,
        "Durante o ciclo automático o reenvio manual é recusado pelo serviço",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado",
    ): {
        "preparacao": "AF no meio do ciclo automático; estado das tentativas fotografado; consulta ao provedor substituída por um contador",
        "acao": "reenvio manual pelo serviço",
        "resultado": "ReenvioRecusado ciclo_em_andamento com a mensagem; nenhuma consulta ao provedor; estado igual ao fotografado",
        "veredito": "íntegra",
    },
    (
        94,
        "Durante o ciclo automático o reenvio manual é recusado pela tela",
        "tests/tecnicos/test_pedido_formal_telas.py::test_reenvio_durante_o_ciclo_e_recusado_com_409",
    ): {
        "preparacao": "administrador logado; AF no meio do ciclo automático",
        "acao": "POST de reenvio com um token novo",
        "resultado": "409 com a mensagem de envio em andamento; só a tentativa automática segue registrada",
        "veredito": "íntegra",
    },
    (
        95,
        "Dois acionamentos concorrentes da mesma solicitação geram um único envio",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_em_paralelo_envia_uma_vez",
    ): {
        "preparacao": "AF com 3 falhas; dois reenvios em paralelo com o mesmo token, o primeiro pausado no envio",
        "acao": "os dois reenvios rodam em paralelo pelo serviço",
        "resultado": "as duas chamadas devolvem a mesma tentativa (uma nova e uma repetida); 1 e-mail e 1 tentativa manual",
        "veredito": "íntegra",
    },
    (
        95,
        "Dois acionamentos distintos geram duas tentativas registradas",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
    ): {
        "preparacao": "AF pela tela; 3 falhas; dois POST em paralelo com tokens diferentes",
        "acao": "os dois POST são executados em paralelo",
        "resultado": "duas tentativas manuais executadas em sequência (a segunda só começa quando a primeira termina) e 2 e-mails",
        "veredito": "íntegra",
    },
    (
        95,
        "Em nenhum caso há segundo pedido formal",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
    ): {
        "preparacao": "AF pela tela; 3 falhas; dois POST em paralelo com tokens diferentes",
        "acao": "os dois POST são executados em paralelo",
        "resultado": "(R12) continua 1 PedidoFormal da rodada depois dos dois reenvios",
        "veredito": "corrigida: assert acrescentado",
    },
    (
        95,
        "Em nenhum caso há mudança no conteúdo original",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
    ): {
        "preparacao": "AF pela tela; 3 falhas; dois POST em paralelo com o mesmo token, o primeiro pausado dentro do envio",
        "acao": "os dois POST são executados em paralelo",
        "resultado": "o único e-mail enviado é igual ao conteúdo original do pedido formal (assunto, corpo e snapshot)",
        "veredito": "íntegra",
    },
    (
        96,
        "O carrinho mostra Reservado: 6 e Pendente: 4 de um produto",
        "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado",
    ): {
        "preparacao": "produto com limite 6 e A com parcela de 10 originais, 6 reservadas e 4 pendentes (livre zero)",
        "acao": "A abre o carrinho",
        "resultado": 'A com 10 originais, 6 reservadas e 4 pendentes de um produto com limite 6 (livre zero): o carrinho mostra "Reservado: 6" e "Pendente: 4"',
        "veredito": "íntegra",
    },
    (
        96,
        "O carrinho mostra reservado e pendente separados com o estoque do produto zerado",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero",
    ): {
        "preparacao": "FP; R2 com limite 10 para P (A com 6; C com 4 reservadas e 4 pendentes reais da apuração)",
        "acao": "C e A abrem o carrinho",
        "resultado": 'o carrinho de C mostra "Reservado: 4" e "Pendente: 4" com o livre zero; o de A mostra "Reservado: 6" e nenhum pendente',
        "veredito": "íntegra",
    },
    (
        96,
        "O histórico (Meus pedidos) mostra Reservado: 6 e Pendente: 4, inclusive com o estoque do produto zerado",
        "tests/aceitacao/test_cenario_96_historico.py::test_cenario_96_historico_mostra_reservado_e_pendente_com_estoque_zerado",
    ): {
        "preparacao": "FP com A em 10 de P (caixa invalidada); R2 com limite 6: A com 6 reservadas e 4 pendentes reais",
        "acao": "A abre GET /pedidos/",
        "resultado": 'A com 6 reservadas e 4 pendentes reais (apuração); a seção do histórico em /pedidos/ mostra "Reservado: 6" antes de "Pendente: 4", com o total reservado igual ao limite',
        "veredito": "íntegra",
    },
    (
        97,
        "Remover 2 das 4 pendentes faz a pendência cair para 2",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
    ): {
        "preparacao": "A com parcela de 10 originais, 6 reservadas e 4 pendentes; outra compradora com 5 reservadas; sequências lidas antes",
        "acao": "remove 2 pendentes e depois as 2 restantes (`remover_pendente`)",
        "resultado": "depois da 1ª remoção: reservado 6 e pendente 2 (resumo e parcela)",
        "veredito": "íntegra",
    },
    (
        97,
        "Remover pendentes não muda as reservas de A",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
    ): {
        "preparacao": "A com parcela de 10 originais, 6 reservadas e 4 pendentes; outra compradora com 5 reservadas; sequências lidas antes",
        "acao": "remove 2 pendentes e depois as 2 restantes (`remover_pendente`)",
        "resultado": "a parcela de A segue ativa com 6 reservadas nas duas remoções",
        "veredito": "íntegra",
    },
    (
        97,
        "Remover pendentes não muda as reservas de outros compradores",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
    ): {
        "preparacao": "A com parcela de 10 originais, 6 reservadas e 4 pendentes; outra compradora com 5 reservadas; sequências lidas antes",
        "acao": "remove 2 pendentes e depois as 2 restantes (`remover_pendente`)",
        "resultado": "a parcela da outra compradora segue ativa com 5 reservadas e 0 pendentes",
        "veredito": "íntegra",
    },
    (
        97,
        "Remover pendentes não muda as posições FIFO de outras parcelas",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
    ): {
        "preparacao": "A com parcela de 10 originais, 6 reservadas e 4 pendentes; outra compradora com 5 reservadas; sequências lidas antes",
        "acao": "remove 2 pendentes e depois as 2 restantes (`remover_pendente`)",
        "resultado": "as sequências das duas parcelas e a quantidade original (10) iguais às lidas antes",
        "veredito": "íntegra",
    },
    (
        97,
        "Remover pendentes não muda o reembolso já devido a A",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno",
    ): {
        "preparacao": "FP; R2 com limite 10: C com 4 reservadas e 4 pendentes reais; reembolsos de C e sequências lidos antes",
        "acao": "C remove 2 e depois as 4 pendentes pela rota",
        "resultado": "C fica com 4 reservadas e pendente 2 e depois 0; A segue com 6; sequências iguais; os reembolsos e obrigações de C iguais aos lidos antes",
        "veredito": "íntegra",
    },
    (
        97,
        "Ao remover as 2 restantes, a pendência zera",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
    ): {
        "preparacao": "A com parcela de 10 originais, 6 reservadas e 4 pendentes; outra compradora com 5 reservadas; sequências lidas antes",
        "acao": "remove 2 pendentes e depois as 2 restantes (`remover_pendente`)",
        "resultado": "depois da 2ª remoção: reservado 6 e pendente 0",
        "veredito": "íntegra",
    },
    (
        97,
        "Ao remover as 2 restantes, a parcela sai da fila",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
    ): {
        "preparacao": "A com parcela de 10 originais, 6 reservadas e 4 pendentes; outra compradora com 5 reservadas; sequências lidas antes",
        "acao": "remove 2 pendentes e depois as 2 restantes (`remover_pendente`)",
        "resultado": "a parcela fica ativa com pendente 0 (deixa de estar na fila) e há 2 auditorias de remoção",
        "veredito": "íntegra",
    },
    (
        98,
        "Remoção de pendente maior que a existente é recusada sem alteração",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava",
    ): {
        "preparacao": 'produto com limite 10 e A com 4 pendentes; 6 entradas do parametrize ("5", "1.5", "0", "-1", "abc" e 1.0)',
        "acao": "`remover_pendente(a, produto, entrada)`",
        "resultado": 'caso "5": RemocaoAcimaDoPendente "A remoção passa da quantidade pendente (4)."; a parcela segue pendente com 4 e nenhuma auditoria',
        "veredito": "íntegra",
    },
    (
        98,
        "Remoção de pendente fora do incremento é recusada sem alteração",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava",
    ): {
        "preparacao": 'produto com limite 10 e A com 4 pendentes; 6 entradas do parametrize ("5", "1.5", "0", "-1", "abc" e 1.0)',
        "acao": "`remover_pendente(a, produto, entrada)`",
        "resultado": 'caso "1.5": QuantidadeInvalida; a parcela segue pendente com 4 e nenhuma auditoria',
        "veredito": "íntegra",
    },
    (
        99,
        "A remoção de pendentes sobre item de pedido congelado é recusada pelo servidor",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao",
    ): {
        "preparacao": "parcela de A em pedido com 6 originais, 4 reservadas e 2 pendentes",
        "acao": "`remover_pendente` de 2 pelo serviço",
        "resultado": "RemocaoAcimaDoPendente com pendente 0; a parcela segue em pedido (4 e 2) e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        99,
        "A rota de remoção não alcança o item do pedido congelado",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_com_o_pk_real_do_item_congelado_e_recusada",
    ): {
        "preparacao": "FP; item de pedido de A em Q existente; pedidos, itens, reembolsos e parcelas de A lidos antes",
        "acao": "POST da rota de remoção de pendentes com o pk real do item congelado",
        "resultado": "resposta 200, 404 ou 409 (nunca sucesso) e pedidos, itens, reembolsos e parcelas de A iguais por conteúdo",
        "veredito": "corrigida: religada (antes só enviava pk inexistente e o produto)",
    },
    (
        99,
        "Pedido e registros financeiros não mudam",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido",
    ): {
        "preparacao": "FP; A com item de pedido em Q e a parcela de Q só em pedido; itens, reembolsos e estado lidos antes",
        "acao": "POST da rota de remoção com o pk do item mais 10.000 e com o produto Q",
        "resultado": "respostas 200, 404 ou 409; itens, reembolsos e a parcela de A em Q iguais ao lido antes",
        "veredito": "íntegra",
    },
    (
        100,
        "Em paralelo com a alocação da fila, reservado mais pendente nunca passa da quantidade original",
        "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes; duas ordens (remoção primeiro ou alocação primeiro)",
        "acao": "a remoção de 6 e a alocação da fila em paralelo",
        "resultado": "nas duas ordens reservado mais pendente da parcela não passa do original",
        "veredito": "íntegra",
    },
    (
        100,
        "Em paralelo com a alocação da fila, nenhuma reserva passa do estoque",
        "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes; duas ordens (remoção primeiro ou alocação primeiro)",
        "acao": "a remoção de 6 e a alocação da fila em paralelo",
        "resultado": "o total reservado fica 0 (removida primeiro) ou 6 (alocada primeiro), sempre dentro do limite 10",
        "veredito": "íntegra",
    },
    (
        100,
        "A quantidade removida nunca vira reserva",
        "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes; duas ordens (remoção primeiro ou alocação primeiro)",
        "acao": "a remoção de 6 e a alocação da fila em paralelo",
        "resultado": "removida primeiro: parcela removida e total reservado 0; alocada primeiro: a remoção é recusada (pendente 0) e as 6 ficam reservadas",
        "veredito": "íntegra",
    },
    (
        101,
        "Quando D remove 3 reservadas, C recebe as 3 antes de qualquer nova reserva",
        "tests/tecnicos/test_interesses_fila.py::test_liberacao_vai_para_a_fila_na_mesma_transacao",
    ): {
        "preparacao": "produto com limite 10: D com 3, outra com 7 reservadas e C com 4 pendentes",
        "acao": "D reduz 3 (`reduzir_interesse`)",
        "resultado": "D fica com 0 e removida; C passa a ter 3 reservadas e 1 pendente; total reservado 10",
        "veredito": "íntegra",
    },
    (
        101,
        "Um interesse novo de E feito ao mesmo tempo recebe só o que sobrar",
        "tests/tecnicos/test_interesses_concorrencia.py::test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado",
    ): {
        "preparacao": "o mesmo arranjo e E comprador novo; a redução de D e a adição de E em paralelo",
        "acao": "D reduz 3 e E adiciona (esperando)",
        "resultado": "a redução conclui; a adição de E recebe EstoqueInsuficiente (nada sobrou); C com as 3 liberadas; total 10 e E sem parcela",
        "veredito": "íntegra",
    },
    (
        102,
        "Pendentes do fornecedor X nunca são alocados em rodada do fornecedor Y",
        "tests/tecnicos/test_interesses_fila.py::test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele",
    ): {
        "preparacao": "rodada do fornecedor X com estoque livre; pendente de 4 de um produto do fornecedor Y; um produto novo de X",
        "acao": "`alocar_pendentes` do fornecedor X",
        "resultado": "alocação 0; a pendente de Y segue pendente com 4; reservado do produto de X igual a 0; nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        103,
        "As reservas dos adimplentes ficam na própria rodada",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "as parcelas de A seguem ativas com 6 em P1 e 4 em P2 e os limites de estoque da rodada ficam",
        "veredito": "íntegra",
    },
    (
        103,
        "As reservas dos adimplentes não passam pela fila de pendentes",
        "tests/tecnicos/test_apuracao_retorno.py::test_unidades_de_caixa_invalidada_ficam_reservadas_sem_passar_pela_fila",
    ): {
        "preparacao": "AP com mínimo insuficiente e X pago; a rodada volta ao interesse",
        "acao": "`iniciar_apuracao` e leitura da parcela de A em P2",
        "resultado": "a parcela de A em P2 fica ativa com 4 reservadas e não há nenhuma restauração de caixa (a fila não foi usada)",
        "veredito": "íntegra",
    },
    (
        104,
        "O progresso elegível é R$ 80,00 com as 5 pendentes de C fora",
        "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
    ): {
        "preparacao": "produto a 10,00 sem limite; mínimo de 100,00; A com 8 reservadas e C com 5 pendentes",
        "acao": "`progresso_da_rodada(rodada, c)` do ponto de vista de C",
        "resultado": "elegível 80,00 (8 reservadas de A) com as 5 pendentes de C fora; 80%, não atingido e falta 20,00",
        "veredito": "íntegra",
    },
    (
        104,
        "O fechamento não pode ser iniciado por causa das pendentes de C",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_minimo_nao_conta_pendentes",
    ): {
        "preparacao": "produto a 10,00 com 8 reservadas de uma compradora e 5 pendentes de outra (13 contariam 130,00 ≥ mínimo)",
        "acao": "o administrador inicia o fechamento",
        "resultado": "TransicaoRecusada minimo_nao_atingido com a mensagem; a rodada segue em interesse e nada é gravado",
        "veredito": "íntegra",
    },
    (
        104,
        "Se a rodada chegar ao pagamento, as pendentes de C não entram em pedido",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
    ): {
        "preparacao": "FP; R2 com P (limite 10) e Q; A adiciona 10 de Q; C tem 4 pendentes de P",
        "acao": "o progresso é lido e o administrador inicia o fechamento (e o pedido é aberto)",
        "resultado": "o item de P do pedido de C tem 4,000 (só as reservadas)",
        "veredito": "íntegra",
    },
    (
        104,
        "Se a rodada chegar ao pagamento, as pendentes de C não entram em cobrança",
        "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_104_a_cobranca_do_pedido_ignora_as_pendentes",
    ): {
        "preparacao": "FP; R2 com P e Q; A adiciona 10 de Q; C com 4 reservadas e 4 pendentes de P; fechamento e abertura do pagamento",
        "acao": "abre o pagamento e lê o pedido de C",
        "resultado": "o total de produtos do pedido de C é o subtotal de 4,000 unidades de P (as reservadas)",
        "veredito": "íntegra",
    },
    (
        104,
        "As pendentes de C continuam na fila",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
    ): {
        "preparacao": "FP; R2 com P (limite 10) e Q; A adiciona 10 de Q; C tem 4 pendentes de P",
        "acao": "o progresso é lido e o administrador inicia o fechamento (e o pedido é aberto)",
        "resultado": "a parcela de C segue pendente com 4,000 depois de aberto o pagamento",
        "veredito": "íntegra",
    },
    (
        105,
        "A alteração do incremento para 0,25 kg é aceita",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_compativel_e_aceito",
    ): {
        "preparacao": "produto em kg do cenário 105 (incremento 0,5, múltiplo 3, reservadas 1,0 e 1,5 e pendente 2,0) em interesse; parcelas fotografadas; administrador logado",
        "acao": 'POST do incremento "0,25"',
        "resultado": "302; incremento 0,250 e auditoria com anterior 0,500 e novo 0,250",
        "veredito": "íntegra",
    },
    (
        105,
        "A alteração compatível do incremento não muda nenhum interesse",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_compativel_e_aceito",
    ): {
        "preparacao": "produto em kg do cenário 105 (incremento 0,5, múltiplo 3, reservadas 1,0 e 1,5 e pendente 2,0) em interesse; parcelas fotografadas; administrador logado",
        "acao": 'POST do incremento "0,25"',
        "resultado": "o estado de todas as parcelas é igual ao fotografado antes da alteração",
        "veredito": "íntegra",
    },
    (
        106,
        "A alteração para 1 kg é recusada porque 1,5 kg reservado deixa de ser múltiplo",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado",
    ): {
        "preparacao": "produto em kg do cenário 105; parcelas fotografadas; administrador logado",
        "acao": "`alterar_incremento` para 1 pelo serviço e POST da rota com 1",
        "resultado": "IncrementoIncompativel de quantidade (1,5 reservado deixa de ser múltiplo) pelo serviço e 200 com a mensagem pela rota",
        "veredito": "íntegra",
    },
    (
        106,
        "A alteração para 2 kg é recusada porque o múltiplo de 3 kg não é divisível por 2",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_o_multiplo_e_recusado",
    ): {
        "preparacao": "cenário 105 sem as reservadas (só a pendente de 2,0 em uso, múltiplo 3 que não é divisível por 2)",
        "acao": "`alterar_incremento` para 2 pelo serviço e POST da rota com 2",
        "resultado": "IncrementoIncompativel de múltiplo (MSG_MULTIPLO) pelo serviço e 200 com a mensagem pela rota; incremento segue 0,500 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        106,
        "Na recusa da alteração para 1 kg, nada é alterado",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado",
    ): {
        "preparacao": "produto em kg do cenário 105; parcelas fotografadas; administrador logado",
        "acao": "`alterar_incremento` para 1 pelo serviço e POST da rota com 1",
        "resultado": "incremento segue 0,500, parcelas iguais ao fotografado e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        106,
        "Na recusa da alteração para 2 kg, nada é alterado",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_para_2_no_cenario_106_e_recusado",
    ): {
        "preparacao": "produto em kg do cenário 105 (as parcelas de 1,5 e 2,0 não são múltiplos de 2)",
        "acao": "`alterar_incremento` para 2 pelo serviço",
        "resultado": "IncrementoIncompativel; incremento segue 0,500 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        107,
        "A partir do fechamento, alterar o incremento é recusado pelo serviço",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_congelado",
    ): {
        "preparacao": "produto do cenário 105 em cada etapa congelada, sem rodada e em retirada (parametrize); administrador logado",
        "acao": 'POST do incremento "0,25" pela rota e `alterar_incremento` pelo serviço',
        "resultado": "o serviço levanta CondicoesCongeladas em cada etapa do caso; incremento segue 0,500 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        107,
        "A recusa de alterar o incremento no fechamento vale para o administrador pela rota",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_congelado",
    ): {
        "preparacao": "produto do cenário 105 em cada etapa congelada, sem rodada e em retirada (parametrize); administrador logado",
        "acao": 'POST do incremento "0,25" pela rota e `alterar_incremento` pelo serviço',
        "resultado": "o administrador recebe 409 com a mensagem de condições congeladas em cada etapa do caso",
        "veredito": "íntegra",
    },
    (
        107,
        "A alteração de preço continua permitida no fechamento",
        "tests/tecnicos/test_catalogo_incremento.py::test_preco_continua_editavel_no_fechamento",
    ): {
        "preparacao": "produto do cenário 105 em rodada em fechamento; administrador logado",
        "acao": "POST de edição do produto com preço 12,50",
        "resultado": "302 e preço 12,50 gravado com a rodada em fechamento",
        "veredito": "íntegra",
    },
    (
        108,
        "Alteração de incremento e adição em paralelo: ou a adição é validada ou a alteração é recusada",
        "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam",
    ): {
        "preparacao": "produto sem limite, incremento 1; A adiciona 3 e o administrador altera o incremento para 2; as duas ordens (parametrize)",
        "acao": "a adição e a alteração em paralelo",
        "resultado": "adição primeiro: a adição conclui e a alteração é recusada (IncrementoIncompativel, incremento 1); alteração primeiro: a adição é recusada (QuantidadeInvalida), incremento 2 e nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        108,
        "Nunca fica parcela fora do incremento vigente",
        "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam",
    ): {
        "preparacao": "produto sem limite, incremento 1; A adiciona 3 e o administrador altera o incremento para 2; as duas ordens (parametrize)",
        "acao": "a adição e a alteração em paralelo",
        "resultado": "a quantidade reservada de toda parcela é múltipla do incremento vigente",
        "veredito": "íntegra",
    },
    (
        109,
        "Ovos (unidade, incremento 1): 12 é aceito",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (UNIDADE, 1, 12): reservado e parcela de 12",
        "veredito": "íntegra",
    },
    (
        109,
        "Ovos (unidade, incremento 1): 12,5 é recusado",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (UNIDADE, 1, 12.5): QuantidadeInvalida e nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        109,
        "Maçãs (unidade, incremento 2): 4 é aceito",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (UNIDADE, 2, 4): reservado e parcela de 4",
        "veredito": "íntegra",
    },
    (
        109,
        "Maçãs (unidade, incremento 2): 3 é recusado",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (UNIDADE, 2, 3): QuantidadeInvalida e nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        109,
        "Banana (kg, 0,25): 1,25 é aceito",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (KG, 0.25, 1.25): reservado e parcela de 1,25",
        "veredito": "íntegra",
    },
    (
        109,
        "Leite (litro, 0,5): 2,5 é aceito",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (LITRO, 0.5, 2.5): reservado e parcela de 2,5 (caso acrescentado)",
        "veredito": "íntegra",
    },
    (
        109,
        "Caixa de produtos (caixa, 1): 3 é aceito",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (CAIXA, 1, 3): reservado e parcela de 3",
        "veredito": "íntegra",
    },
    (
        109,
        "Caixa de produtos (caixa, 1): 1,5 é recusado",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (CAIXA, 1, 1.5): QuantidadeInvalida e nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        110,
        "O incremento 0 é recusado",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_zero_e_recusado_e_o_produto_nao_e_criado",
    ): {
        "preparacao": "administrador e fornecedor",
        "acao": "`criar_produto` com incremento 0",
        "resultado": "IncrementoInvalido e nenhum produto criado",
        "veredito": "íntegra",
    },
    (
        110,
        "O incremento -1 é recusado",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_negativo_e_recusado_e_o_produto_nao_e_criado",
    ): {
        "preparacao": "administrador e fornecedor",
        "acao": "`criar_produto` com incremento -1",
        "resultado": "IncrementoInvalido e nenhum produto criado",
        "veredito": "íntegra",
    },
    (
        110,
        "O incremento 0,0001 é recusado",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_com_mais_de_3_casas_e_recusado_e_o_produto_nao_e_criado",
    ): {
        "preparacao": "administrador e fornecedor",
        "acao": "`criar_produto` com incremento 0,0001",
        "resultado": "IncrementoInvalido e nenhum produto criado",
        "veredito": "íntegra",
    },
    (
        110,
        "Os incrementos 0,001 e 2 são aceitos",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos",
    ): {
        "preparacao": "os 5 incrementos válidos do parametrize (1, 2, 0,25, 0,5 e 0,001)",
        "acao": "`validar_incremento` com texto e com Decimal",
        "resultado": 'casos "2" e "0.001": o incremento é devolvido igual (texto e Decimal)',
        "veredito": "íntegra",
    },
    (
        111,
        "Maçãs com incremento 2 e múltiplo 12 são aceitas",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_valido_no_cadastro",
    ): {
        "preparacao": "administrador logado; fornecedor; os casos (0,25 e 1) e (2 e 12), unidade kg do formulário",
        "acao": "POST do cadastro do produto com o incremento e o múltiplo do caso",
        "resultado": 'caso ("2", "12"): 302 e o produto gravado com múltiplo 12',
        "veredito": "íntegra",
    },
    (
        111,
        "Com múltiplo 5 e incremento 2 a configuração é recusada pelo serviço",
        "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
    ): {
        "preparacao": "administrador e fornecedor; 5 casos de incremento e múltiplo incompatíveis",
        "acao": "`criar_produto` com o caso",
        "resultado": 'caso ("2", "5"): MultiploInvalido e nenhum produto',
        "veredito": "íntegra",
    },
    (
        111,
        "Com múltiplo 5 e incremento 2 a configuração é recusada pelo formulário",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
    ): {
        "preparacao": "administrador logado; fornecedor; 4 casos de incremento e múltiplo incompatíveis",
        "acao": "POST do formulário de cadastro de produto com o caso",
        "resultado": 'caso ("2", "5"): 200 com erro no campo múltiplo e nenhum produto',
        "veredito": "íntegra",
    },
    (
        112,
        "O item de 1,000 kg a R$ 7,99/kg tem subtotal registrado de R$ 7,99",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_117_cada_devolucao_e_registrada_separadamente",
    ): {
        "preparacao": "pedido pago com um item de 1,000 kg a 7,99 (K)",
        "acao": "4 reembolsos parciais de 0,25",
        "resultado": "o item é kg, 1,000 a 7,99; depois dos 4 reembolsos mantém quantidade 1,000 e subtotal 7,99",
        "veredito": "íntegra",
    },
    (
        112,
        "A ocorrência de 0,25 kg reembolsa R$ 2,00 de produtos",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_112_parcial_usa_o_valor_registrado",
    ): {
        "preparacao": "pedido pago com um item de 1,000 kg a 7,99 (K)",
        "acao": "um reembolso parcial de 0,25",
        "resultado": "o reembolso de 0,25 kg devolve 2,00 de produtos",
        "veredito": "íntegra",
    },
    (
        112,
        "Uma mudança posterior do preço não altera o valor",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
    ): {
        "preparacao": "pedido pago com item de 1,000 kg a 7,99; o preço do produto do catálogo muda para 9,99",
        "acao": "reembolso parcial de 0,25",
        "resultado": "com o catálogo a 9,99 o reembolso segue 2,00 de produtos, na linha do item com 0,250 por 2,00",
        "veredito": "íntegra",
    },
    (
        113,
        "Três ocorrências de 0,25 kg reembolsam R$ 2,00 cada",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
    ): {
        "preparacao": "pedido pago com um item de 1,000 kg a 7,99 (K), serviço 0,40 e frete 1,60",
        "acao": "4 reembolsos parciais de 0,25",
        "resultado": "os produtos dos quatro reembolsos são 2,00, 2,00, 2,00 e 1,99: os três primeiros 2,00",
        "veredito": "íntegra",
    },
    (
        113,
        "A quarta ocorrência reembolsa R$ 1,99",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
    ): {
        "preparacao": "pedido pago com um item de 1,000 kg a 7,99 (K), serviço 0,40 e frete 1,60",
        "acao": "4 reembolsos parciais de 0,25",
        "resultado": "o quarto reembolso tem produtos 1,99, serviço 0,10 e frete 0,40",
        "veredito": "íntegra",
    },
    (
        113,
        "A soma dos reembolsos é exatamente R$ 7,99",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
    ): {
        "preparacao": "pedido pago com um item de 1,000 kg a 7,99 (K), serviço 0,40 e frete 1,60",
        "acao": "4 reembolsos parciais de 0,25",
        "resultado": "produtos somam 7,99, serviço 0,40 e frete 1,60",
        "veredito": "íntegra",
    },
    (
        114,
        "O cancelamento depois de uma parcial devolve para o item exatamente o saldo de R$ 5,99",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_integral_depois_de_parcial_concluida_soma_exatamente_o_pago",
    ): {
        "preparacao": "pedido de 9,99 pago; um reembolso parcial concluído no simulador; rodada cancelada com reembolso",
        "acao": "as chamadas pendentes são processadas",
        "resultado": "o reembolso do cancelamento tem produtos 5,99 e o estornado total soma 9,99",
        "veredito": "íntegra",
    },
    (
        114,
        "O cancelamento depois da parcial devolve só o saldo restante do pedido",
        "tests/tecnicos/test_ocorrencias.py::test_o_cancelamento_devolve_so_o_saldo_restante",
    ): {
        "preparacao": "AE com X pago; uma ocorrência faltante já registrada",
        "acao": "o administrador cancela a rodada com reembolso",
        "resultado": "a obrigação do cancelamento deve 70,76; o total devolvido ao pedido é 60,00 (restante) e há 1 ocorrência",
        "veredito": "íntegra",
    },
    (
        115,
        "O item de 0,6 kg a R$ 0,15/kg tem subtotal de R$ 0,09",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_115_centavos_nao_passam_do_pago",
    ): {
        "preparacao": "pedido pago com um item de 0,600 kg a 0,15 (M)",
        "acao": "6 reembolsos parciais de 0,1 e um sétimo",
        "resultado": "o item é kg, 0,600 a 0,15 e os seis reembolsos somam 0,09 de produtos",
        "veredito": "íntegra",
    },
    (
        115,
        "Cada ocorrência de 0,1 kg calcula R$ 0,015 arredondado para R$ 0,02",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago",
    ): {
        "preparacao": "AE com X pago e o item M (0,600 kg a 0,15); a rodada liberada",
        "acao": "6 ocorrências faltantes de 0,1 e uma sétima",
        "resultado": "os produtos das ocorrências são 0,02 (de 0,015 arredondado) nas quatro primeiras",
        "veredito": "íntegra",
    },
    (
        115,
        "A quinta ocorrência é limitada a R$ 0,01",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago",
    ): {
        "preparacao": "AE com X pago e o item M (0,600 kg a 0,15); a rodada liberada",
        "acao": "6 ocorrências faltantes de 0,1 e uma sétima",
        "resultado": "a quinta ocorrência reembolsa 0,01",
        "veredito": "íntegra",
    },
    (
        115,
        "A sexta ocorrência reembolsa R$ 0,00",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago",
    ): {
        "preparacao": "AE com X pago e o item M (0,600 kg a 0,15); a rodada liberada",
        "acao": "6 ocorrências faltantes de 0,1 e uma sétima",
        "resultado": "a sexta reembolsa 0,00 sem obrigação, com o reembolso registrado",
        "veredito": "íntegra",
    },
    (
        115,
        "A soma dos reembolsos nunca passa de R$ 0,09",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_115_centavos_nao_passam_do_pago",
    ): {
        "preparacao": "pedido pago com um item de 0,600 kg a 0,15 (M)",
        "acao": "6 reembolsos parciais de 0,1 e um sétimo",
        "resultado": "a soma dos 6 reembolsos é 0,09 e o sétimo levanta ReembolsoRecusado",
        "veredito": "íntegra",
    },
    (
        115,
        "Uma ocorrência acima da quantidade paga é recusada",
        "tests/tecnicos/test_ocorrencias.py::test_cenario_115_centavos_nao_passam_do_pago",
    ): {
        "preparacao": "AE com X pago e o item M (0,600 kg a 0,15); a rodada liberada",
        "acao": "6 ocorrências faltantes de 0,1 e uma sétima",
        "resultado": "a sétima ocorrência é recusada com passa_do_saldo_do_item",
        "veredito": "íntegra",
    },
    (
        116,
        "Um reembolso parcial de R$ 2,00 de produtos devolve também R$ 0,10 de serviço",
        "tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py::test_cenario_116_numeros_do_cenario",
    ): {
        "preparacao": "pedido de 100,00 + 5,00 + 20,00 pago; um item de 2,00; o integral de outro registrado",
        "acao": "reembolso parcial de 1 unidade do item",
        "resultado": "o parcial devolve produtos 2,00, serviço 0,10 e frete 0,40",
        "veredito": "íntegra",
    },
    (
        116,
        "Um reembolso parcial de R$ 2,00 de produtos devolve também R$ 0,40 de frete",
        "tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py::test_cenario_116_numeros_do_cenario",
    ): {
        "preparacao": "pedido de 100,00 + 5,00 + 20,00 pago; um item de 2,00; o integral de outro registrado",
        "acao": "reembolso parcial de 1 unidade do item",
        "resultado": "o parcial devolve produtos 2,00, serviço 0,10 e frete 0,40",
        "veredito": "íntegra",
    },
    (
        116,
        "O acumulado de cada componente nunca passa do valor registrado",
        "tests/aceitacao/test_cenario_116_servico_e_frete_do_parcial.py::test_cenario_116_numeros_do_cenario",
    ): {
        "preparacao": "pedido de 100,00 + 5,00 + 20,00 pago; um item de 2,00; o integral de outro registrado",
        "acao": "reembolso parcial de 1 unidade do item",
        "resultado": "o acumulado do pedido depois do parcial e do integral é exatamente 100,00, 5,00 e 20,00 (produtos, serviço e frete)",
        "veredito": "corrigida: religada (a ligação anterior só cobria produtos)",
    },
    (
        117,
        "Cada reembolso parcial é registrado separadamente",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_117_cada_devolucao_e_registrada_separadamente",
    ): {
        "preparacao": "pedido pago com um item de 1,000 kg a 7,99 (K)",
        "acao": "4 reembolsos parciais de 0,25",
        "resultado": "4 reembolsos distintos para o pedido depois das 4 devoluções de 0,25",
        "veredito": "íntegra",
    },
    (
        117,
        "Cada reembolso parcial guarda item, quantidade e valores",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
    ): {
        "preparacao": "pedido pago com item de 1,000 kg a 7,99; o preço do produto do catálogo muda para 9,99",
        "acao": "reembolso parcial de 0,25",
        "resultado": "a linha do reembolso guarda o item, a quantidade 0,250 e o valor 2,00",
        "veredito": "íntegra",
    },
    (
        117,
        "O pedido congelado continua com a composição original",
        "tests/aceitacao/test_cenarios_90_91_112_117_reembolso.py::test_cenario_117_cada_devolucao_e_registrada_separadamente",
    ): {
        "preparacao": "pedido pago com um item de 1,000 kg a 7,99 (K)",
        "acao": "4 reembolsos parciais de 0,25",
        "resultado": "o item do pedido segue com quantidade 1,000 e subtotal 7,99 depois dos 4 reembolsos",
        "veredito": "íntegra",
    },
    (
        118,
        "O acionamento manual simultâneo com a tentativa automática é recusado",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar",
    ): {
        "preparacao": "AF; a tentativa automática pausada dentro do envio",
        "acao": "reenvio manual enquanto a automática roda",
        "resultado": "a automática conclui e o manual levanta ReenvioRecusado ciclo_em_andamento sem esperar",
        "veredito": "íntegra",
    },
    (
        118,
        "Nenhuma tentativa a mais é feita no acionamento manual simultâneo",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar",
    ): {
        "preparacao": "AF; a tentativa automática pausada dentro do envio",
        "acao": "reenvio manual enquanto a automática roda",
        "resultado": "as tentativas registradas são só as 3 automáticas",
        "veredito": "íntegra",
    },
    (
        119,
        "Dois manuais distintos feitos ao mesmo tempo são executados um depois do outro",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia",
    ): {
        "preparacao": "AF com 3 falhas; dois reenvios em paralelo com tokens diferentes, o primeiro pausado no envio",
        "acao": "os dois reenvios rodam em paralelo pelo serviço",
        "resultado": "a quinta tentativa só começa depois de a quarta concluir",
        "veredito": "íntegra",
    },
    (
        119,
        "Dois manuais distintos nunca executam ao mesmo tempo",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
    ): {
        "preparacao": "AF pela tela; 3 falhas; dois POST em paralelo com tokens diferentes",
        "acao": "os dois POST são executados em paralelo",
        "resultado": "pelas rotas, a segunda tentativa só começa depois de a primeira concluir; 2 e-mails",
        "veredito": "íntegra",
    },
    (
        119,
        "Cada manual distinto tem uma única tentativa registrada",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia",
    ): {
        "preparacao": "AF com 3 falhas; dois reenvios em paralelo com tokens diferentes, o primeiro pausado no envio",
        "acao": "os dois reenvios rodam em paralelo pelo serviço",
        "resultado": "as duas novas tentativas são a 4 e a 5 (uma por token) e os dois e-mails têm o corpo do pedido formal",
        "veredito": "íntegra",
    },
    (
        "T-1",
        "Tentativa criada em T0 + 24h − 1 ms é aceita",
        "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento",
    ): {
        "preparacao": "pedido X de A com pagamento aberto em T0; relógio em T0+24h menos 1 ms, depois em T0+24h e T0+24h mais 1 ms",
        "acao": "A pede o pagamento (`pedir_pagamento`) em cada instante",
        "resultado": "em T0+24h−1 ms: 1 tentativa criada e 1 chamada criar_cobranca",
        "veredito": "íntegra",
    },
    (
        "T-1",
        "Tentativa em T0 + 24h é recusada com a tarefa de bloqueio parada",
        "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento",
    ): {
        "preparacao": "pedido X de A com pagamento aberto em T0; relógio em T0+24h menos 1 ms, depois em T0+24h e T0+24h mais 1 ms",
        "acao": "A pede o pagamento (`pedir_pagamento`) em cada instante",
        "resultado": "em T0+24h exato (sem a tarefa de bloqueio) PagamentoRecusado prazo_encerrado com a mensagem; continua 1 tentativa",
        "veredito": "corrigida: religada (antes o instante era T0+24h+5 min)",
    },
    (
        "T-1",
        "Tentativa em T0 + 24h + 1 ms é recusada com a tarefa de bloqueio parada",
        "tests/tecnicos/test_pedidos_tentativas.py::test_fronteira_de_24_horas_para_pedir_pagamento",
    ): {
        "preparacao": "pedido X de A com pagamento aberto em T0; relógio em T0+24h menos 1 ms, depois em T0+24h e T0+24h mais 1 ms",
        "acao": "A pede o pagamento (`pedir_pagamento`) em cada instante",
        "resultado": "em T0+24h+1 ms (sem a tarefa de bloqueio) PagamentoRecusado prazo_encerrado; continua 1 tentativa e 1 chamada",
        "veredito": "íntegra",
    },
    (
        "T-2",
        "date_approved em T0 + 48h é aceito",
        "tests/tecnicos/test_pedidos_quitacao.py::test_fronteira_de_48_horas_da_margem",
    ): {
        "preparacao": "3 pedidos avulsos de 50,00 com cobrança; relógio em T0+49h",
        "acao": "aprova os pagamentos em T0+48h−1 ms, T0+48h e T0+48h+1 ms; processa os avisos",
        "resultado": "as aprovações em −1 ms e em exatamente T0+48h quitam (destino quita, pedido pago, na_margem verdadeiro)",
        "veredito": "íntegra",
    },
    (
        "T-2",
        "date_approved em T0 + 48h + 1 ms gera obrigação de devolução",
        "tests/tecnicos/test_apuracao_inicio.py::test_reconsulta_registra_o_pagamento_aprovado_depois_de_48_horas",
    ): {
        "preparacao": "X pago; Y pago em PRAZO+1 ms sem aviso entregue; relógio em T0+49h",
        "acao": "`iniciar_apuracao` reconsulta o pagamento de Y",
        "resultado": "destino devolução (aprovado_apos_a_margem), obrigação integral igual ao total de Y e Y cancelado por inadimplência",
        "veredito": "corrigida: religada (o teste anterior só conferia o destino)",
    },
    (
        "T-3",
        "Aprovação em T0 + 47h59 com webhook em T0 + 50h quita o pedido se a apuração ainda não ocorreu",
        "tests/tecnicos/test_pedidos_quitacao.py::test_aviso_atrasado_nao_muda_o_horario_de_aprovacao",
    ): {
        "preparacao": "pedido X com cobrança; aprovação em T0+47h59 e aviso em T0+50h; a apuração não rodou",
        "acao": "o aviso é processado",
        "resultado": "destino quita; pedido pago com quitado_em igual à aprovação (47h59); primeiro aviso em T0+50h",
        "veredito": "íntegra",
    },
    (
        "T-4",
        "Apuração em T0 + 48h − 1 ms é recusada",
        "tests/tecnicos/test_apuracao_inicio.py::test_antes_de_48_horas_e_recusada_sem_consulta_nem_escrita",
    ): {
        "preparacao": "AP com X e Y pagos; relógio em PRAZO−1 ms; estado fotografado",
        "acao": "`iniciar_apuracao` pelo administrador",
        "resultado": "em PRAZO−1 ms ApuracaoRecusada antes_do_prazo com a data da primeira apuração permitida; sem consulta ao provedor e estado igual",
        "veredito": "íntegra",
    },
    (
        "T-4",
        "Apuração em T0 + 48h − 1 ms é recusada mesmo com 100% pago",
        "tests/tecnicos/test_apuracao_inicio.py::test_antes_de_48_horas_e_recusada_sem_consulta_nem_escrita",
    ): {
        "preparacao": "AP com X e Y pagos; relógio em PRAZO−1 ms; estado fotografado",
        "acao": "`iniciar_apuracao` pelo administrador",
        "resultado": "com X e Y pagos (100%) e PRAZO−1 ms a apuração é recusada (antes_do_prazo) e nada é gravado",
        "veredito": "corrigida: religada (a tela usada antes não tinha os pedidos pagos)",
    },
    (
        "T-4",
        "Em T0 + 48h a apuração exige autorização do administrador",
        "tests/tecnicos/test_apuracao_inicio.py::test_so_o_administrador_apura",
    ): {
        "preparacao": "AP em T0+48h; estado fotografado",
        "acao": "`iniciar_apuracao` com A (comprador), uma conta de fornecedor e None como autor",
        "resultado": "em T0+48h, comprador, fornecedor e None são recusados (PermissionDenied) e o estado fica igual",
        "veredito": "íntegra",
    },
    (
        "T-5",
        "Nenhuma rota permite alterar T0",
        "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos",
    ): {
        "preparacao": "administrador logado; pedido aberto; rotas e formulários varridos pelos nomes de prazo, t0 e margem",
        "acao": "varredura das rotas e POST de prorrogação do fechamento fora do fechamento",
        "resultado": "nenhuma rota com t0 no caminho ou no nome e nenhum campo de formulário com nomes de prazo",
        "veredito": "corrigida: religada (antes o teste era de imutabilidade por SQL)",
    },
    (
        "T-5",
        "Nenhuma rota permite alterar o prazo de pagamento",
        "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos",
    ): {
        "preparacao": "administrador logado; pedido aberto; rotas e formulários varridos pelos nomes de prazo, t0 e margem",
        "acao": "varredura das rotas e POST de prorrogação do fechamento fora do fechamento",
        "resultado": "nenhuma rota com prazo de pagamento ou margem e nenhum campo de formulário com esses nomes",
        "veredito": "íntegra",
    },
    (
        "T-5",
        "Nem o perfil de administrador altera T0 ou o prazo",
        "tests/tecnicos/test_pedidos_prazos.py::test_nenhuma_rota_formulario_ou_servico_altera_os_prazos",
    ): {
        "preparacao": "administrador logado; pedido aberto; rotas e formulários varridos pelos nomes de prazo, t0 e margem",
        "acao": "varredura das rotas e POST de prorrogação do fechamento fora do fechamento",
        "resultado": "com o administrador logado não há rota de prazo e a prorrogação fora do fechamento dá 409",
        "veredito": "íntegra",
    },
    (
        "T-6",
        "Webhook repetido 5 vezes em paralelo reconhece o pagamento uma única vez",
        "tests/tecnicos/test_pagamentos_concorrencia.py::test_mesmo_aviso_cinco_vezes_em_paralelo_reconhece_o_pagamento_uma_vez",
    ): {
        "preparacao": "cobrança pendente aprovada no simulador; 5 avisos iguais",
        "acao": "os 5 POST do webhook em paralelo e o processamento das chamadas",
        "resultado": "5 respostas 200; 1 aviso, 1 chamada, 1 consulta, 1 pagamento aprovado, 1 auditoria de situação e 1 sinal",
        "veredito": "íntegra",
    },
    (
        "T-7",
        "Webhook e bloqueio de T0 + 24h concorrendo dão o mesmo resultado em qualquer ordem",
        "tests/tecnicos/test_pedidos_concorrencia.py::test_bloqueio_e_aviso_de_outra_mudanca_ao_mesmo_tempo",
    ): {
        "preparacao": "pedido X com cobrança pendente; aviso reemitido; relógio em T0+24h",
        "acao": "o bloqueio do prazo e o aviso rodam em paralelo (barreira)",
        "resultado": "sem exceções; o pagamento fica cancelado, o pedido segue aguardando pagamento e não há destino de pagamento",
        "veredito": "íntegra",
    },
    (
        "T-7",
        "Webhook e bloqueio de T0 + 24h concorrendo dão o mesmo resultado em qualquer ordem",
        "tests/tecnicos/test_pedidos_concorrencia.py::test_bloqueio_e_aviso_dao_o_mesmo_resultado_nas_duas_ordens",
    ): {
        "preparacao": "pedido X com cobrança pendente; aviso reemitido; relógio em T0+24h; dois casos de ordem (parametrize)",
        "acao": "bloqueio e depois aviso, ou aviso e depois bloqueio, em sequência",
        "resultado": "nas duas ordens o pagamento fica cancelado, o pedido segue aguardando pagamento e não há destino de pagamento",
        "veredito": "corrigida: caracterização nova (as duas ordens)",
    },
    (
        "T-7",
        "Webhook antes da apuração quita o pedido",
        "tests/tecnicos/test_apuracao_inicio.py::test_aviso_antes_da_apuracao_quita_y",
    ): {
        "preparacao": "AP com X pago e Y aprovado em T0+47h; relógio no prazo",
        "acao": "o aviso de Y é processado antes de a apuração iniciar; depois a apuração",
        "resultado": "Y aprovado em T0+47h e avisado antes da apuração: pago, 2 pedidos pagos na apuração e destino quita",
        "veredito": "íntegra",
    },
    (
        "T-7",
        "Apuração que cancelou o pedido antes do webhook dá devolução",
        "tests/tecnicos/test_apuracao_inicio.py::test_aviso_espera_a_apuracao_que_ja_cancelou_y",
    ): {
        "preparacao": "AP com X pago e Y sem pagamento; aviso de Y em corrida com a apuração (pontos de espera)",
        "acao": "a apuração cancela Y e o aviso de Y é processado em seguida",
        "resultado": "apuração e aviso em corrida: Y cancelado por inadimplência, destino devolução (pedido_cancelado), obrigação integral de 106,15 e 1 alerta",
        "veredito": "íntegra",
    },
    (
        "T-7",
        "Apuração concorrente com o webhook espera o aviso que trava a situação",
        "tests/tecnicos/test_apuracao_inicio.py::test_apuracao_espera_o_aviso_que_trava_a_situacao_de_y",
    ): {
        "preparacao": "AP com X pago e Y aprovado dentro do prazo; o aviso de Y trava a situação",
        "acao": "apuração e aviso em paralelo, a apuração esperando a trava",
        "resultado": "apuração e aviso em corrida: a apuração espera o aviso; Y fica pago, 2 pedidos pagos e destino quita",
        "veredito": "íntegra",
    },
    (
        "T-8",
        "A devolução com falha temporária repetida reaproveita a chave de idempotência",
        "tests/tecnicos/test_devolucoes_execucao.py::test_falha_depois_de_executar_repete_a_mesma_chave",
    ): {
        "preparacao": "arranjo da devolução; o simulador falha 2 vezes depois de executar o estorno",
        "acao": "autoriza a devolução e processa as chamadas com avanço do relógio",
        "resultado": "a chamada ao provedor usa a mesma chave da parcela; duas falhas temporárias e depois concluída",
        "veredito": "íntegra",
    },
    (
        "T-8",
        "A devolução com falha temporária repetida não devolve duas vezes",
        "tests/tecnicos/test_devolucoes_execucao.py::test_falha_depois_de_executar_repete_a_mesma_chave",
    ): {
        "preparacao": "arranjo da devolução; o simulador falha 2 vezes depois de executar o estorno",
        "acao": "autoriza a devolução e processa as chamadas com avanço do relógio",
        "resultado": "1 estorno no simulador e 1 movimento de devolução, apesar das falhas depois de executar",
        "veredito": "íntegra",
    },
    (
        "T-9",
        "A confirmação excepcional é recusada com devolução em processamento no provedor",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_estorno_em_processamento_no_provedor_recusa_e_agenda_a_verificacao",
    ): {
        "preparacao": "estorno recusado mas processado no provedor (em processamento) e a parcela elegível excepcional; estado fotografado",
        "acao": "tenta confirmar a devolução excepcional",
        "resultado": 'DevolucaoRecusada "em processamento ou concluída no provedor"; contagens e comprovantes iguais e a verificação agendada',
        "veredito": "íntegra",
    },
    (
        "T-9",
        "Nova tentativa no provedor é recusada depois da confirmação",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_depois_da_confirmacao_o_provedor_nao_e_mais_chamado",
    ): {
        "preparacao": "parcela confirmada fora da plataforma",
        "acao": "tenta a devolução de novo, autoriza de novo e processa uma chamada pendente de estorno criada à mão",
        "resultado": "a nova tentativa é recusada; a autorização devolve a mesma parcela; a chamada falha com parcela_encerrada e nenhum estorno no simulador",
        "veredito": "íntegra",
    },
    (
        "T-9",
        "A segunda confirmação da mesma parcela é recusada",
        "tests/tecnicos/test_devolucoes_excepcional.py::test_nao_vale_duas_vezes",
    ): {
        "preparacao": "parcela elegível já confirmada uma vez; contagens (confirmações, movimentos, arquivos) lidas depois da primeira",
        "acao": "segunda confirmação da mesma parcela",
        "resultado": 'DevolucaoRecusada "já confirmada"; contagens iguais e 1 comprovante',
        "veredito": "íntegra",
    },
    (
        "T-10",
        "A utilização da reserva acima do saldo livre é recusada",
        "tests/tecnicos/test_financeiro_reserva.py::test_uso_acima_do_livre_e_recusado_inteiro",
    ): {
        "preparacao": "reserva com 30,00; obrigação de 50,00 e tarifa de 40,00; estado fotografado",
        "acao": "designa 50,00 da reserva à obrigação e depois à tarifa",
        "resultado": "ReservaInsuficiente nas duas designações; movimentos, designações e saldos iguais ao fotografado e os itens sem cobertura seguem",
        "veredito": "íntegra",
    },
    (
        "T-10",
        "A obrigação sem cobertura é mantida integral",
        "tests/tecnicos/test_financeiro_reserva.py::test_obrigacoes_sem_cobertura_acima_do_livre_abrem_o_alerta",
    ): {
        "preparacao": "reserva com 30,00; obrigação de 50,00 e tarifa de 2,00 sem cobertura",
        "acao": "`avaliar_reserva`",
        "resultado": "o total sem cobertura é 52,00 (50,00 da obrigação inteira e 2,00 da tarifa)",
        "veredito": "íntegra",
    },
    (
        "T-10",
        "A obrigação sem cobertura gera alerta de insuficiência",
        "tests/tecnicos/test_financeiro_reserva.py::test_obrigacoes_sem_cobertura_acima_do_livre_abrem_o_alerta",
    ): {
        "preparacao": "reserva com 30,00; obrigação de 50,00 e tarifa de 2,00 sem cobertura",
        "acao": "`avaliar_reserva`",
        "resultado": "1 alerta aberto reserva_insuficiente com sem_cobertura 52,00 e livre 30,00",
        "veredito": "íntegra",
    },
    (
        "T-11",
        "Lançamento com recursos do fornecedor A para tarifa é recusado",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
    ): {
        "preparacao": "100,00 na custódia e 100,00 na obrigação devida de A; tarifa de 1,00 em despesas; saldos e movimentos lidos antes",
        "acao": "7 lançamentos de A para despesa, obrigação de B, frete de B, reserva, receita e repasse de B",
        "resultado": "cobertura de despesa com a custódia de A: MovimentoProibido e saldos e movimentos iguais",
        "veredito": "íntegra",
    },
    (
        "T-11",
        "Lançamento com recursos do fornecedor A para déficit de B é recusado",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
    ): {
        "preparacao": "100,00 na custódia e 100,00 na obrigação devida de A; tarifa de 1,00 em despesas; saldos e movimentos lidos antes",
        "acao": "7 lançamentos de A para despesa, obrigação de B, frete de B, reserva, receita e repasse de B",
        "resultado": "cobertura do frete de B com a obrigação devida de A: MovimentoProibido e saldos e movimentos iguais",
        "veredito": "íntegra",
    },
    (
        "T-11",
        "Lançamento com recursos do fornecedor A para obrigação de B é recusado",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_dinheiro_do_fornecedor_nao_cobre_despesa_nem_vai_para_outro_uso",
    ): {
        "preparacao": "100,00 na custódia e 100,00 na obrigação devida de A; tarifa de 1,00 em despesas; saldos e movimentos lidos antes",
        "acao": "7 lançamentos de A para despesa, obrigação de B, frete de B, reserva, receita e repasse de B",
        "resultado": "financiamento e repasse da obrigação devida de A para a obrigação de B: MovimentoProibido e saldos e movimentos iguais",
        "veredito": "íntegra",
    },
    (
        "T-11",
        "O repasse a A é limitado ao valor liberado de A",
        "tests/tecnicos/test_repasse.py::test_o_repasse_nao_passa_do_liberado",
    ): {
        "preparacao": "AF com liberado de 80,00 e a liberar de 90,00; estado fotografado",
        "acao": "repasse de 80,01",
        "resultado": "LiquidezInsuficiente citando R$ 80,00 e R$ 90,00; movimentos e auditorias iguais",
        "veredito": "íntegra",
    },
    (
        "T-11",
        "O repasse a A é limitado ao valor liberado de A",
        "tests/aceitacao/test_cenario_32_recursos_por_fornecedor.py::test_o_repasse_de_a_nao_usa_o_dinheiro_liberado_de_b",
    ): {
        "preparacao": "L: A e B com recursos liberados; saldo da obrigação de B lido antes",
        "acao": "repasse de 50,00 da obrigação de A",
        "resultado": "o repasse de A acima do liberado de A levanta LiquidezInsuficiente e a obrigação de B segue igual",
        "veredito": "íntegra",
    },
    (
        "T-11",
        "O repasse acima do liberado é recusado pela tela",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_repasse_limitado_ao_liberado_e_conciliado",
    ): {
        "preparacao": "AF pela tela com liberação em 72 h; repasses pelas telas",
        "acao": "repasses até o liberado e um acima dele pela tela; conciliação dos dias",
        "resultado": "o repasse acima do liberado dá 409 com o liberado; 2 repasses registrados; nenhuma conciliação divergente",
        "veredito": "íntegra",
    },
    (
        "T-12",
        "A aplicação com o simulador em produção encerra na inicialização",
        "tests/tecnicos/test_configuracao_pagamentos.py::test_producao_com_o_simulador_nao_carrega",
    ): {
        "preparacao": "ambiente de produção completo com PROVEDOR_PAGAMENTOS=simulador, em subprocesso",
        "acao": "carrega `config.settings.prod`",
        "resultado": "`config.settings.prod` com simulador falha com ImproperlyConfigured e a mensagem do simulador, sem expor segredos",
        "veredito": "íntegra",
    },
    (
        "T-13",
        "Dois cancelamentos com reembolso em paralelo: um é recusado",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_dois_cancelamentos_em_paralelo_geram_um_estorno_por_pagamento",
    ): {
        "preparacao": "AP com X e Y pagos; dois cancelamentos com reembolso em paralelo (corrida)",
        "acao": "`cancelar_rodada` duas vezes em paralelo",
        "resultado": "o primeiro conclui e o segundo levanta CancelamentoRecusado ja_cancelada",
        "veredito": "íntegra",
    },
    (
        "T-13",
        "Dois cancelamentos com reembolso em paralelo não duplicam devolução",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_dois_cancelamentos_em_paralelo_geram_um_estorno_por_pagamento",
    ): {
        "preparacao": "AP com X e Y pagos; dois cancelamentos com reembolso em paralelo (corrida)",
        "acao": "`cancelar_rodada` duas vezes em paralelo",
        "resultado": "2 estornos concluídos (um por pagamento) e o estornado é 94,35 e 106,15",
        "veredito": "íntegra",
    },
    (
        "T-14",
        "O cancelamento com parcial pendente cobre só o saldo restante",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido",
    ): {
        "preparacao": "AP com X pago; apuração com caixa invalidada gera a obrigação pendente de 23,59 (sem parcela de devolução)",
        "acao": "a rodada é cancelada com reembolso",
        "resultado": "com a devolução parcial de caixa pendente (23,59 sem parcela de devolução), o cancelamento cobre só o restante",
        "veredito": "corrigida: religada (a ligação anterior era de parcial concluída)",
    },
    (
        "T-14",
        "O total devolvido com parcial pendente nunca passa do valor pago",
        "tests/tecnicos/test_cancelamento_com_reembolso.py::test_o_reembolso_anterior_pendente_nao_e_substituido",
    ): {
        "preparacao": "AP com X pago; apuração com caixa invalidada gera a obrigação pendente de 23,59 (sem parcela de devolução)",
        "acao": "a rodada é cancelada com reembolso",
        "resultado": "com a parcial pendente o total devolvido de X é 94,35, o valor pago",
        "veredito": "corrigida: religada (a ligação anterior era de parcial concluída)",
    },
    (
        "T-15",
        "O cancelamento sem reembolso não gera obrigação nova",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente",
    ): {
        "preparacao": "X pago; Y pagou depois da margem (obrigação existente de devolução integral); obrigações fotografadas antes",
        "acao": "cancelamento sem reembolso; depois a devolução existente é autorizada e processada",
        "resultado": "depois do cancelamento sem reembolso as obrigações são iguais por conteúdo às fotografadas antes",
        "veredito": "íntegra",
    },
    (
        "T-15",
        "A obrigação existente continua pendente e não é baixada",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_cancelamento_sem_reembolso_mantem_a_obrigacao_existente",
    ): {
        "preparacao": "X pago; Y pagou depois da margem (obrigação existente de devolução integral); obrigações fotografadas antes",
        "acao": "cancelamento sem reembolso; depois a devolução existente é autorizada e processada",
        "resultado": "a obrigação existente segue sem parcela de devolução depois do cancelamento (não baixada)",
        "veredito": "íntegra",
    },
    (
        "T-16",
        "A rota de cancelamento recusa lista de compradores",
        "tests/tecnicos/test_cancelamento_telas.py::test_a_rota_recusa_campos_fora_da_indicacao",
    ): {
        "preparacao": "administrador com passkey; pagamento aberto; dois casos de campo extra (compradores=1 e motivo=x)",
        "acao": "POST de cancelamento com o campo extra",
        "resultado": "caso compradores=1: 400 com a mensagem de só a indicação; o serviço não é chamado e a rodada segue em pagamento",
        "veredito": "íntegra",
    },
    (
        "T-16",
        "A rota de cancelamento aceita requisição sem motivo",
        "tests/tecnicos/test_cancelamento_ponta_a_ponta.py::test_a_rota_pelo_cliente_http",
    ): {
        "preparacao": "administrador com passkey; AP com pagamento aberto; A (comprador) e uma conta de fornecedor logadas; invariante financeiro ok",
        "acao": "POST de cancelamento com compradores=1; POST de A e do fornecedor; POST do administrador sem motivo",
        "resultado": "o POST só com o campo de reembolso (sem motivo) dá 302 e a rodada fica cancelada",
        "veredito": "íntegra",
    },
    (
        "T-16",
        "Comprador e fornecedor recebem recusa no cancelamento",
        "tests/tecnicos/test_cancelamento_telas.py::test_comprador_e_fornecedor_nao_cancelam",
    ): {
        "preparacao": "AP com pagamento aberto; A e uma conta de fornecedor logadas",
        "acao": "POST de cancelamento e GET da página da rodada",
        "resultado": "POST e GET de A e do fornecedor recusados (302 ou 403) e a etapa segue pagamento",
        "veredito": "íntegra",
    },
    (
        "T-17",
        "UPDATE ou DELETE direto sobre item de pedido congelado é recusado pela trigger",
        "tests/tecnicos/test_pedidos_abertura.py::test_composicao_do_pedido_nao_muda_nem_some",
    ): {
        "preparacao": "uma abertura, um pedido, um item e uma parcela do pedido gravados; registros de cada modelo do pedido fotografados",
        "acao": "save, delete, update e delete em lote e SQL direto (UPDATE e DELETE) em cada modelo",
        "resultado": "cada operação levanta RegistroImutavel (ORM, com o log de aviso) ou DatabaseError (SQL direto) e os registros ficam iguais ao fotografado",
        "veredito": "íntegra",
    },
    (
        "T-17",
        "Nenhuma rota permite edição do pedido congelado",
        "tests/tecnicos/test_pedidos_abertura_tela.py::test_nenhuma_rota_altera_pedido_item_t0_ou_frete",
    ): {
        "preparacao": "a lista de rotas do projeto",
        "acao": "varredura de rotas por nome (pedido, item, t0, frete) e das políticas",
        "resultado": "nenhuma rota de edição de pedido, item, T0 ou frete fora das permitidas; nenhuma rota sem política",
        "veredito": "íntegra",
    },
    (
        "T-18",
        "Ocorrências concorrentes sobre o mesmo item não ultrapassam a quantidade paga",
        "tests/tecnicos/test_retirada_ponta_a_ponta.py::test_t18_duas_ocorrencias_ao_mesmo_tempo_pela_rota",
    ): {
        "preparacao": "AE pela tela; item de X com 4 unidades pagas; duas ocorrências do mesmo item em paralelo pelas rotas (a segunda passaria do saldo)",
        "acao": "dois POST de ocorrência em paralelo",
        "resultado": 'um POST dá 302 e o outro 409 com "passa do saldo deste item (2 unidade)"; as ocorrências do item somam 4 (a quantidade paga)',
        "veredito": "íntegra",
    },
    (
        "T-18",
        "Cada ocorrência gera um único reembolso",
        "tests/tecnicos/test_ocorrencias.py::test_o_mesmo_acionamento_em_paralelo",
    ): {
        "preparacao": "AE com X pago; um acionamento de ocorrência repetido em duas threads",
        "acao": "a mesma ocorrência registrada duas vezes em paralelo",
        "resultado": "as duas chamadas devolvem a mesma ocorrência (uma nova e uma repetida); 1 ocorrência, 1 reembolso e 1 obrigação",
        "veredito": "íntegra",
    },
    (
        "T-18",
        "O reembolso da ocorrência tem o valor do §9.2",
        "tests/tecnicos/test_ocorrencias.py::test_duas_ocorrencias_no_mesmo_item_t18",
    ): {
        "preparacao": "AE com X pago; duas ocorrências distintas sobre o mesmo item, em paralelo",
        "acao": "as duas ocorrências em threads",
        "resultado": "a que vence reembolsa 40,00, 2,00 e 5,18 (produtos, serviço e frete proporcionais); a outra é recusada (passa_do_saldo_do_item); 1 reembolso",
        "veredito": "íntegra",
    },
    (
        "T-19",
        "Pagamento informado depois da apuração fica registrado",
        "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta",
    ): {
        "preparacao": "AP apurada com Y sem pagamento; cobrança de Y aprovada antes do prazo mas só avisada depois; composição fotografada",
        "acao": "o aviso chega em T0+50h e a tarefa sincroniza o pagamento",
        "resultado": "destino devolução (pedido_cancelado) e obrigação integral igual ao total de Y; Y cancelado por inadimplência",
        "veredito": "íntegra",
    },
    (
        "T-19",
        "Pagamento informado depois da apuração gera alerta",
        "tests/tecnicos/test_apuracao_inicio.py::test_pagamento_no_prazo_informado_depois_da_apuracao_vira_devolucao_e_alerta",
    ): {
        "preparacao": "AP apurada com Y sem pagamento; cobrança de Y aprovada antes do prazo mas só avisada depois; composição fotografada",
        "acao": "o aviso chega em T0+50h e a tarefa sincroniza o pagamento",
        "resultado": "alerta crítico com pedido, comprador, valor e aprovado_em",
        "veredito": "íntegra",
    },
    (
        "T-19",
        "Pagamento informado depois do cancelamento fica registrado com alerta",
        "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta",
    ): {
        "preparacao": "rodada cancelada com Y não pago; cobrança de Y aprovada depois; composição fotografada pelo auxiliar",
        "acao": "a aprovação chega e é sincronizada",
        "resultado": "destino devolução, obrigação integral de 106,15 e alerta crítico com a chave da cobrança",
        "veredito": "íntegra",
    },
    (
        "T-19",
        "Pagamento tardio não altera o pedido",
        "tests/tecnicos/test_pagamento_depois_do_cancelamento.py::test_pagamento_aprovado_depois_do_cancelamento_vai_para_devolucao_com_alerta",
    ): {
        "preparacao": "rodada cancelada com Y não pago; cobrança de Y aprovada depois; composição fotografada pelo auxiliar",
        "acao": "a aprovação chega e é sincronizada",
        "resultado": "a composição do pedido igual à fotografada antes da aprovação",
        "veredito": "íntegra",
    },
    (
        "T-20",
        "A apuração repetida restaura as parcelas uma única vez",
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ): {
        "preparacao": "AP-viável apurado; a parcela de A em P2 restaurada e lida antes; resultado da apuração recalculado",
        "acao": "o passo de restauração e estorno é repetido numa transação",
        "resultado": "depois de repetir o passo continua 1 restauração, 1 reembolso e 1 obrigação",
        "veredito": "íntegra",
    },
    (
        "T-20",
        "A apuração repetida mantém o mesmo número de sequência",
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ): {
        "preparacao": "AP-viável apurado; a parcela de A em P2 restaurada e lida antes; resultado da apuração recalculado",
        "acao": "o passo de restauração e estorno é repetido numa transação",
        "resultado": "a sequência da parcela depois da repetição é igual à de antes",
        "veredito": "íntegra",
    },
    (
        "T-20",
        "A apuração repetida não duplica a reserva",
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ): {
        "preparacao": "AP-viável apurado; a parcela de A em P2 restaurada e lida antes; resultado da apuração recalculado",
        "acao": "o passo de restauração e estorno é repetido numa transação",
        "resultado": "a parcela segue única com pendente 4,000 e uma só restauração (nenhuma reserva extra)",
        "veredito": "íntegra",
    },
    (
        "T-21",
        "A restauração com adição concorrente respeita a ordem FIFO original",
        "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X pago; C comprador novo; corrida pelo ponto depois da restauração das reservas",
        "acao": "duas threads: a apuração (A) e a adição de 5 de P1 por C (B), B esperando",
        "resultado": "a parcela de C, adicionada durante a restauração, tem sequência maior que a de toda parcela de A e fica ativa com 5",
        "veredito": "íntegra",
    },
    (
        "T-21",
        "A restauração com adição concorrente mantém o total reservado dentro do estoque",
        "tests/tecnicos/test_apuracao_retorno.py::test_adicao_espera_o_retorno_e_recebe_o_estoque_livre",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X pago; C comprador novo; corrida pelo ponto depois da restauração das reservas",
        "acao": "duas threads: a apuração (A) e a adição de 5 de P1 por C (B), B esperando",
        "resultado": "o total reservado de P1 não passa de 11",
        "veredito": "íntegra",
    },
    (
        "T-22",
        "O retorno ao interesse mantém o estoque cadastrado",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "os limites de estoque da rodada seguem 11 e 12 depois do retorno",
        "veredito": "íntegra",
    },
    (
        "T-22",
        "O retorno ao interesse libera as reservas dos inadimplentes",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "todas as parcelas de B ficam removidas e o reservado total cai para 6 e 4",
        "veredito": "íntegra",
    },
    (
        "T-22",
        "O retorno ao interesse mantém as reservas dos pagantes com a sequência original",
        "tests/tecnicos/test_apuracao_retorno.py::test_reservas_de_quem_pagou_ficam_e_as_de_quem_nao_pagou_saem",
    ): {
        "preparacao": "AP com mínimo insuficiente e limites 11 e 12; X (A) pago; sequências fotografadas antes",
        "acao": "`iniciar_apuracao` no prazo",
        "resultado": "as parcelas de A seguem ativas com 6 e 4 e todas as sequências iguais às de antes",
        "veredito": "íntegra",
    },
    (
        "T-23",
        "Alterar o mínimo é recusado pelo servidor fora de interesse",
        "tests/tecnicos/test_rodadas_minimo.py::test_minimo_congelado_pelo_servico",
    ): {
        "preparacao": "fornecedor com mínimo 150,00 e rodada em cada etapa congelada (parametrize ETAPAS_CONGELADAS)",
        "acao": '`alterar_minimo` para "200,00" pelo administrador',
        "resultado": "CondicoesCongeladas (fora_de_interesse) em cada etapa congelada; mínimo 150,00 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        "T-23",
        "Alterar o múltiplo é recusado pelo servidor fora de interesse",
        "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_nenhuma_condicao_muda_fora_de_interesse",
    ): {
        "preparacao": "uma condição (mínimo, múltiplo ou estoque) em cada situação fora de interesse (parametrize cruzado); administrador logado; estado fotografado",
        "acao": "POST da rota da condição e a chamada do serviço",
        "resultado": "no caso do múltiplo a rota dá 409 com a mensagem e o serviço levanta CondicoesCongeladas; estado igual e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        "T-23",
        "Alterar o estoque é recusado pelo servidor fora de interesse",
        "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pelo_servico",
    ): {
        "preparacao": "rodada em cada etapa congelada com estoque 10 e outro produto",
        "acao": "`incluir_produto_na_rodada` e `alterar_estoque` pelo administrador",
        "resultado": "CondicoesCongeladas (fora_de_interesse) em incluir e alterar o estoque; limite 10,000 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        "T-23",
        "A recusa vale em fechamento, pagamento, margem e etapas seguintes",
        "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_nenhuma_condicao_muda_fora_de_interesse",
    ): {
        "preparacao": "uma condição (mínimo, múltiplo ou estoque) em cada situação fora de interesse (parametrize cruzado); administrador logado; estado fotografado",
        "acao": "POST da rota da condição e a chamada do serviço",
        "resultado": "409 e CondicoesCongeladas em cada etapa fora de interesse do parametrize (fechamento, pagamento, margem e seguintes)",
        "veredito": "íntegra",
    },
    (
        "T-23",
        "A recusa vale inclusive para o administrador",
        "tests/tecnicos/test_rodadas_estoque.py::test_estoque_congelado_pela_rota",
    ): {
        "preparacao": "rodada em cada etapa congelada; administrador logado",
        "acao": "POSTs de incluir e de alterar o estoque",
        "resultado": "o administrador recebe 409 com a mensagem em cada etapa congelada; estoque e auditoria iguais",
        "veredito": "íntegra",
    },
    (
        "T-23",
        "O preço é aceito no fechamento",
        "tests/tecnicos/test_rodadas_fechamento_inicio.py::test_condicoes_congeladas_mas_o_preco_continua_editavel",
    ): {
        "preparacao": "fechamento iniciado com 10 reservadas; as operações de mínimo, estoque e outras condições preparadas",
        "acao": "tenta alterar cada condição e depois o preço para 12,00",
        "resultado": "as condições levantam CondicoesCongeladas e o preço do produto fica 12,00",
        "veredito": "íntegra",
    },
    (
        "T-23",
        "O preço é aceito nas quatro etapas ativas",
        "tests/tecnicos/test_condicoes_congeladas_matriz.py::test_preco_muda_nas_quatro_etapas_ativas",
    ): {
        "preparacao": "produto em cada uma das quatro etapas ativas; administrador logado",
        "acao": "POST do preço 12,50 e depois alteração pelo serviço para 13,00",
        "resultado": "302 e preço 12,50; depois 13,00 pelo serviço, em cada etapa ativa",
        "veredito": "íntegra",
    },
    (
        "T-23",
        "A redução de estoque abaixo do reservado é recusada",
        "tests/tecnicos/test_rodadas_estoque.py::test_reducao_abaixo_do_reservado_e_recusada",
    ): {
        "preparacao": "estoque com limite 10 e 6 reservadas",
        "acao": "`alterar_estoque` para 5",
        "resultado": "EstoqueAbaixoDoReservado citando 6; limite segue 10,000 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        "T-24",
        "O login por senha com e-mail banido é recusado",
        "tests/tecnicos/test_contas_login_senha.py::test_login_de_email_banido_e_recusado_com_a_mensagem_generica",
    ): {
        "preparacao": "conta ana@x.com com senha e e-mail banido; três grafias (ana@x.com, ANA@X.COM e com espaços)",
        "acao": "login por senha com a grafia do caso",
        "resultado": "200 com a mensagem genérica e sem sessão, nas três grafias",
        "veredito": "íntegra",
    },
    (
        "T-24",
        "O login por link com e-mail banido é recusado",
        "tests/tecnicos/test_contas_link_de_acesso.py::test_banido_ou_removido_nao_recebe_link",
    ): {
        "preparacao": "conta ana@x.com removida, ou ativa com e-mail em EmailBanido; 3 grafias do e-mail e 2 casos",
        "acao": "pedido de link com a grafia do caso",
        "resultado": "banido: resposta padrão, 0 links, 0 e-mails e sem sessão, nas 3 grafias",
        "veredito": "íntegra",
    },
    (
        "T-24",
        "O login pelo Google com e-mail banido é recusado",
        "tests/tecnicos/test_contas_google_login.py::test_banido_ou_removido_nao_entra_pelo_google",
    ): {
        "preparacao": "conta com e-mail banido (ana@x.com, com espaço e caixa) ou conta removida; contagens antes (2 casos)",
        "acao": "retorno do Google com esse e-mail",
        "resultado": "banido (com espaço e caixa): recusa, sem sessão e contagens iguais",
        "veredito": "íntegra",
    },
    (
        "T-24",
        "O e-mail banido com maiúsculas e espaços variados é recusado",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_cenario_59_o_endereco_banido_com_outras_maiusculas_e_recusado_no_login",
    ): {
        "preparacao": "conta ana@x.com banida (e aliases ana+1 e a.na criados por `_banida_e_aliases`)",
        "acao": 'tenta login por senha com "ANA@x.com" e "  Ana@X.com "',
        "resultado": 'as grafias "ANA@x.com" e "  Ana@X.com " não abrem sessão',
        "veredito": "íntegra",
    },
    (
        "T-24",
        "O alias com + não é bloqueado",
        "tests/tecnicos/test_contas_login_senha.py::test_login_de_alias_nao_e_afetado_pelo_banimento_do_endereco_base",
    ): {
        "preparacao": "e-mail ana@x.com banido; conta ana+1@x.com com senha",
        "acao": "login por senha do alias",
        "resultado": "o alias ana+1@x.com abre sessão",
        "veredito": "íntegra",
    },
    (
        "T-24",
        "A sessão aberta é encerrada no banimento",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes",
    ): {
        "preparacao": "administrador logado; conta ana@x.com com 2 sessões abertas por login real",
        "acao": "o administrador remove a conta pela tela",
        "resultado": "as 2 sessões abertas passam a 0 na remoção e a conta fica removida com o e-mail banido",
        "veredito": "corrigida: religada (antes só a recusa pelo middleware com o apagamento anulado)",
    },
    (
        "T-25",
        "A conta de fornecedor é recusada nas rotas de carrinho",
        "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
    ): {
        "preparacao": "conta de fornecedor logada; rotas de teste do carrinho e do pagamento; com e sem cabeçalho HTMX (2 casos)",
        "acao": "GET e POST do carrinho; POST, PUT, PATCH e DELETE do pagamento",
        "resultado": "GET e POST do carrinho dão 403 ao fornecedor, com e sem HTMX",
        "veredito": "íntegra",
    },
    (
        "T-25",
        "A conta de fornecedor é recusada nas rotas de pagamento",
        "tests/tecnicos/test_permissoes_papeis.py::test_fornecedor_nao_compra_nem_por_chamada_direta",
    ): {
        "preparacao": "conta de fornecedor logada; rotas de teste do carrinho e do pagamento; com e sem cabeçalho HTMX (2 casos)",
        "acao": "GET e POST do carrinho; POST, PUT, PATCH e DELETE do pagamento",
        "resultado": "POST, PUT, PATCH e DELETE do pagamento dão 403 ao fornecedor e nenhuma view executa",
        "veredito": "íntegra",
    },
    (
        "T-25",
        "A conta de comprador é recusada nas rotas de fornecedor",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_comprador_nao_entra_no_portal",
    ): {
        "preparacao": "AF com A (comprador) logada",
        "acao": "GET do portal, da rodada e do CSV do pedido formal do fornecedor",
        "resultado": "o portal, a rodada e o CSV do fornecedor respondem 403 ao comprador",
        "veredito": "íntegra",
    },
    (
        "T-26",
        "A quantidade fora do incremento é recusada pela API",
        "tests/tecnicos/test_catalogo_quantidades.py::test_quantidades_recusadas",
    ): {
        "preparacao": "produto montado sem banco com o incremento do caso (14 casos de entradas recusadas)",
        "acao": "`validar_quantidade(produto, entrada)`",
        "resultado": "`validar_quantidade` recusa as quantidades fora do incremento nos 14 casos (cláusula do servidor; a da API é provada pela rota)",
        "veredito": "íntegra",
    },
    (
        "T-26",
        "A quantidade fora do incremento é recusada pela API",
        "tests/aceitacao/test_cenario_63_rota_1_2_kg.py::test_cenario_63_rota_recusa_1_2_kg_sem_gravar",
    ): {
        "preparacao": "produto em kg a R$ 12,00 e incremento 0,5; comprador sem interesse e outro com 1,5 reservado",
        "acao": "POST /interesses/ com quantidade 1.2 e origem carrinho, pelos dois",
        "resultado": "a rota HTTP chamada direto recusa 1,2 kg (200 com a mensagem, sem parcela e sem mudar o reservado)",
        "veredito": "íntegra",
    },
    (
        "T-26",
        "0,35 × 12,99 resulta em 455 centavos",
        "tests/tecnicos/test_catalogo_quantidades.py::test_subtotal_de_455_centavos",
    ): {
        "preparacao": "os decimais 12,99 e 0,35",
        "acao": "`calcular_subtotal` e conversão para centavos",
        "resultado": "o subtotal de 0,35 × 12,99 em centavos é 455",
        "veredito": "íntegra",
    },
    (
        "T-26",
        "O múltiplo que não é múltiplo do incremento é recusado no cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_servico_recusa_multiplo_invalido",
    ): {
        "preparacao": "administrador e fornecedor; 5 casos de incremento e múltiplo incompatíveis",
        "acao": "`criar_produto` com o caso",
        "resultado": "MultiploInvalido e nenhum produto nos 5 casos do cadastro",
        "veredito": "íntegra",
    },
    (
        "T-27",
        "O fornecedor consultando por identificador direto dados que não são dele recebe recusa",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_o_fornecedor_nao_alcanca_o_que_nao_e_dele",
    ): {
        "preparacao": "arranjo AF com a conta do fornecedor F logada; pedido X de A",
        "acao": "9 acessos diretos (GET e POST) a pedido de comprador, pagar e telas financeiras",
        "resultado": "os acessos diretos pelo id do pedido do comprador (e do pagar) dão 403 ao fornecedor e a página não traz dados do comprador",
        "veredito": "íntegra",
    },
    (
        "T-27",
        "A exportação só contém campos permitidos",
        "tests/tecnicos/test_portal_do_fornecedor.py::test_a_exportacao_do_pedido_formal",
    ): {
        "preparacao": "AF com a conta do fornecedor logada",
        "acao": "GET do CSV do pedido formal",
        "resultado": "o CSV tem o cabeçalho e as linhas exatos, 7 colunas",
        "veredito": "íntegra",
    },
    (
        "T-28",
        "Com o SES falhando três vezes há exatamente três tentativas",
        "tests/tecnicos/test_pedido_formal_envio.py::test_exatamente_tres_tentativas_automaticas",
    ): {
        "preparacao": "AF; o backend de e-mail falha sempre; envio criado em PRAZO",
        "acao": "`_tres_falhas` processa as 3 tentativas; depois processa em +120 min e +1 dia",
        "resultado": "3 tentativas automáticas com falha e nenhuma quarta, mesmo processando depois",
        "veredito": "íntegra",
    },
    (
        "T-28",
        "Com o SES falhando três vezes o administrador recebe alerta",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tres_falhas_e_reenvio_pela_tela",
    ): {
        "preparacao": "AF pela tela; backend de e-mail falho; pedido formal fotografado antes",
        "acao": "3 falhas automáticas; durante o envio o POST de reenvio; depois 2 reenvios manuais pela tela",
        "resultado": "o administrador recebe a notificação de falha com link; envio concluído com falhas",
        "veredito": "íntegra",
    },
    (
        "T-28",
        "Com o SES falhando três vezes o botão fica disponível",
        "tests/tecnicos/test_pedido_formal_telas.py::test_depois_das_tres_falhas_o_formulario_aparece",
    ): {
        "preparacao": "administrador logado; AF com 3 falhas automáticas",
        "acao": "GET da página do pedido formal",
        "resultado": "a página traz o formulário com o token depois das 3 falhas",
        "veredito": "íntegra",
    },
    (
        "T-28",
        "Falha seguida de sucesso não faz nenhuma tentativa a mais",
        "tests/tecnicos/test_pedido_formal_envio.py::test_sucesso_depois_de_uma_falha",
    ): {
        "preparacao": "AF; o backend de e-mail falha na 1ª tentativa; envio do pedido formal criado",
        "acao": "processa em PRAZO e de novo em PRAZO+5 min",
        "resultado": "só 2 tentativas (falha e sucesso); envio concluído com sucesso e sem aviso",
        "veredito": "íntegra",
    },
    (
        "T-29",
        "Duas requisições de reenvio com o mesmo token geram um envio",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_o_mesmo_token_gera_um_so_envio",
    ): {
        "preparacao": "AF com 3 falhas; outbox limpo; estado fotografado depois do primeiro reenvio",
        "acao": "dois reenvios com o mesmo token, em sequência",
        "resultado": "o primeiro é novo e o segundo não, com a mesma tentativa; estado igual; 1 e-mail e 1 tentativa manual",
        "veredito": "íntegra",
    },
    (
        "T-29",
        "Tokens distintos geram duas tentativas registradas",
        "tests/tecnicos/test_pedido_formal_telas.py::test_duplo_clique_gera_um_envio_e_novo_acionamento_outro",
    ): {
        "preparacao": "administrador logado; AF com 3 falhas; token lido da página; outbox limpo",
        "acao": "POST de reenvio duas vezes com o mesmo token; depois novo POST com o token novo",
        "resultado": "o novo token difere do primeiro e passam a existir 2 e-mails, iguais ao pedido formal",
        "veredito": "íntegra",
    },
    (
        "T-29",
        "O conteúdo enviado é idêntico ao snapshot",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_mesmo_token_em_dois_post_envia_uma_vez",
    ): {
        "preparacao": "AF pela tela; 3 falhas; dois POST em paralelo com o mesmo token, o primeiro pausado dentro do envio",
        "acao": "os dois POST são executados em paralelo",
        "resultado": "o e-mail enviado é igual ao snapshot do pedido formal (assunto e corpo)",
        "veredito": "íntegra",
    },
    (
        "T-30",
        "O alocar_pendentes reserva por ordem de sequência",
        "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes e C com 8 pendentes (nessa ordem); sequências lidas",
        "acao": "`alocar_pendentes` do fornecedor",
        "resultado": "A (6 pendentes, sequência menor) fica ativa com 6 e C com 4: a alocação segue a ordem e devolve 10",
        "veredito": "íntegra",
    },
    (
        "T-30",
        "A última parcela atendida fica parcialmente atendida com o restante pendente",
        "tests/tecnicos/test_interesses_fila.py::test_pendentes_sao_atendidas_pela_ordem_original",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes e C com 8 pendentes (nessa ordem); sequências lidas",
        "acao": "`alocar_pendentes` do fornecedor",
        "resultado": "a última parcela atendida (C) fica com 4 reservadas e 4 pendentes de 8 originais",
        "veredito": "íntegra",
    },
    (
        "T-30",
        "O total reservado é igual ao estoque",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_do_produto_atende_a_fila_pela_sequencia_original",
    ): {
        "preparacao": "FP: A, C e B da R1 apurada; sequências lidas; R2 aberta com limite 10 para P",
        "acao": "inclui P na rodada pelo serviço",
        "resultado": "o reservado total de P é 10,000, igual ao limite da rodada",
        "veredito": "íntegra",
    },
    (
        "T-31",
        "Os pendentes são atendidos primeiro em paralelo com a adição nova",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro",
    ): {
        "preparacao": "FP; R2 sem múltiplo; E comprador novo; corrida entre incluir P na rodada e a adição de E",
        "acao": "duas threads: a inclusão de P (atende a fila) e a adição de E",
        "resultado": "A 6 e C 4 ativas (C com 4 pendentes) e E recusado por EstoqueInsuficiente sem parcela",
        "veredito": "íntegra",
    },
    (
        "T-31",
        "Nenhuma reserva passa do estoque em paralelo com a adição nova",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_inclusao_em_paralelo_com_adicao_de_e_atende_a_fila_primeiro",
    ): {
        "preparacao": "FP; R2 sem múltiplo; E comprador novo; corrida entre incluir P na rodada e a adição de E",
        "acao": "duas threads: a inclusão de P (atende a fila) e a adição de E",
        "resultado": "o reservado total de P é 10,000 (o limite)",
        "veredito": "íntegra",
    },
    (
        "T-31",
        "O resultado é idêntico em qualquer ordem",
        "tests/tecnicos/test_interesses_concorrencia.py::test_fila_e_nova_adicao_se_serializam_em_qualquer_ordem",
    ): {
        "preparacao": "produto com limite 6; A com 4 pendentes; E é comprador novo",
        "acao": "a alocação da fila e a adição de 4 por E em paralelo, nas duas ordens",
        "resultado": "a alocação da fila e a adição de E em paralelo dão o mesmo resultado: A com 4, E recusada com a mensagem e total 4",
        "veredito": "íntegra",
    },
    (
        "T-32",
        "A apuração reexecutada não faz segunda restauração",
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ): {
        "preparacao": "AP-viável apurado; a parcela de A em P2 restaurada e lida antes; resultado da apuração recalculado",
        "acao": "o passo de restauração e estorno é repetido numa transação",
        "resultado": "depois de repetir o passo continua 1 restauração, 1 reembolso e 1 obrigação",
        "veredito": "íntegra",
    },
    (
        "T-32",
        "A apuração reexecutada não cria nova parcela nem nova sequência",
        "tests/tecnicos/test_apuracao_viavel.py::test_repetir_o_passo_nao_restaura_nem_estorna_de_novo",
    ): {
        "preparacao": "AP-viável apurado; a parcela de A em P2 restaurada e lida antes; resultado da apuração recalculado",
        "acao": "o passo de restauração e estorno é repetido numa transação",
        "resultado": "a parcela de A segue única com a mesma sequência e pendente 4,000",
        "veredito": "íntegra",
    },
    (
        "T-33",
        "A parcela pendente sem reserva fica fora do mínimo",
        "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
    ): {
        "preparacao": "produto a 10,00 sem limite; mínimo de 100,00; A com 8 reservadas e C com 5 pendentes",
        "acao": "`progresso_da_rodada(rodada, c)` do ponto de vista de C",
        "resultado": "elegível 80,00 sem as 5 pendentes de C; mínimo não atingido",
        "veredito": "íntegra",
    },
    (
        "T-33",
        "A parcela pendente sem reserva fica fora das caixas e do pedido na abertura",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
    ): {
        "preparacao": "FP; R2 com P (limite 10) e Q; A adiciona 10 de Q; C tem 4 pendentes de P",
        "acao": "o progresso é lido e o administrador inicia o fechamento (e o pedido é aberto)",
        "resultado": "cláusula do pedido: o item de P do pedido de C tem 4,000 (só as reservadas); a das caixas é provada pelo teste do T-47",
        "veredito": "íntegra",
    },
    (
        "T-33",
        "A parcela pendente sem reserva fica fora das caixas e do pedido na abertura",
        "tests/tecnicos/test_interesses_progresso.py::test_a_formacao_de_caixas_ignora_as_pendentes",
    ): {
        "preparacao": "produto com múltiplo 10 a 10,00; A com 7 reservadas e C com 5 pendentes (7+5 completaria uma caixa)",
        "acao": "`progresso_da_rodada` antes e depois de A reservar mais 3",
        "resultado": "cláusula das caixas: com múltiplo 10, 7 reservadas e 5 pendentes não se forma caixa (0 completas, elegível 0)",
        "veredito": "íntegra",
    },
    (
        "T-33",
        "A parcela pendente continua pendente na rodada seguinte",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
    ): {
        "preparacao": "FP; R2 com P (limite 10) e Q; A adiciona 10 de Q; C tem 4 pendentes de P",
        "acao": "o progresso é lido e o administrador inicia o fechamento (e o pedido é aberto)",
        "resultado": "a parcela de C segue pendente com 4,000 depois de aberto o pagamento",
        "veredito": "íntegra",
    },
    (
        "T-33",
        "O inadimplente fica sem parcelas pendentes",
        "tests/tecnicos/test_apuracao_inadimplentes.py::test_pendente_antigo_de_outro_produto_do_fornecedor_tambem_sai",
    ): {
        "preparacao": "apurada com só X pago; B com 3 pendentes antigas de P3, do mesmo fornecedor e fora da rodada",
        "acao": "`iniciar_apuracao`",
        "resultado": "a pendente antiga de B fica removida com pendente 0 e B não tem parcela na fila do fornecedor",
        "veredito": "corrigida: religada (antes o teste só tinha parcelas em pedido)",
    },
    (
        "T-34",
        "Dois cadastros simultâneos com o mesmo e-mail dão um sucesso",
        "tests/tecnicos/test_convites_cadastro_concorrencia.py::test_dois_convites_com_mesmo_email_normalizado_em_paralelo",
    ): {
        "preparacao": "10 repetições: dois convites (comprador e fornecedor) para o mesmo e-mail",
        "acao": "os dois cadastros rodam em paralelo",
        "resultado": "em 10 repetições só 1 cadastro conclui, 1 conta por e-mail e o recusado não consome o convite",
        "veredito": "íntegra",
    },
    (
        "T-34",
        "Dois cadastros simultâneos com o mesmo e-mail dão uma recusa pela restrição UNIQUE",
        "tests/tecnicos/test_contas_modelo.py::test_banco_recusa_segunda_conta_com_o_mesmo_email_pela_restricao_unique",
    ): {
        "preparacao": "uma conta ana@x.com inserida em SQL e um fornecedor existente",
        "acao": "INSERT direto de uma segunda conta (fornecedora) com o mesmo e-mail",
        "resultado": "IntegrityError da restrição conta_email_unico e continua 1 conta com o e-mail",
        "veredito": "corrigida: caracterização nova (a causa UNIQUE)",
    },
    (
        "T-35",
        "Google com e-mail de uma conta em maiúsculas diferentes entra nessa conta",
        "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social",
    ): {
        "preparacao": "conta ana@x.com existente; contagem de contas lida antes",
        "acao": 'retorno do Google com "Ana@X.com"',
        "resultado": 'com "Ana@X.com" a sessão é da conta existente e a conta social fica ligada a ela',
        "veredito": "íntegra",
    },
    (
        "T-35",
        "Google com e-mail de uma conta em maiúsculas diferentes não cria outra",
        "tests/tecnicos/test_contas_google_login.py::test_conta_existente_entra_pelo_email_e_vincula_a_conta_social",
    ): {
        "preparacao": "conta ana@x.com existente; contagem de contas lida antes",
        "acao": 'retorno do Google com "Ana@X.com"',
        "resultado": "o número de contas é igual ao de antes",
        "veredito": "íntegra",
    },
    (
        "T-35",
        "Google sem conta e sem convite não cria nada",
        "tests/tecnicos/test_contas_google_login.py::test_sem_conta_e_sem_convite_nao_cria_nada",
    ): {
        "preparacao": "nenhuma conta nem convite; contagens lidas antes",
        "acao": "retorno do Google com nova@x.com",
        "resultado": "`_recusado`: 302 para /entrar/, recusa, sem sessão e contagens iguais",
        "veredito": "íntegra",
    },
    (
        "T-36",
        "Banimento com sessões em dois navegadores apaga as sessões",
        "tests/tecnicos/test_moderacao_remocao.py::test_remocao_bane_o_email_e_apaga_as_sessoes",
    ): {
        "preparacao": "administrador logado; conta ana@x.com com 2 sessões abertas por login real",
        "acao": "o administrador remove a conta pela tela",
        "resultado": "as 2 sessões (dois navegadores) passam a 0 e o e-mail fica banido",
        "veredito": "íntegra",
    },
    (
        "T-36",
        "A próxima requisição de cada sessão é recusada pelo middleware",
        "tests/tecnicos/test_moderacao_remocao.py::test_middleware_recusa_sessao_que_o_apagamento_nao_alcancou",
    ): {
        "preparacao": "conta com 4 sessões; o apagamento de sessões é anulado (monkeypatch) e a conta é removida",
        "acao": "GET nas duas primeiras sessões e POST nas duas últimas",
        "resultado": "com o apagamento anulado, a próxima requisição de cada sessão é recusada pelo middleware (GET 302 e POST 403)",
        "veredito": "íntegra",
    },
    (
        "T-36",
        "A outra conta da mesma pessoa continua acessível",
        "tests/tecnicos/test_moderacao_remocao.py::test_remover_comprador_nao_afeta_a_conta_de_fornecedor_da_mesma_pessoa",
    ): {
        "preparacao": "contas ana (comprador) e ana.fornecedor (fornecedor), cada uma com sessões abertas por login",
        "acao": "o administrador remove a conta de comprador; a fornecedora abre /inicio/ e entra de novo",
        "resultado": "a sessão da conta de fornecedor segue com /inicio/ 200 depois da remoção da de comprador",
        "veredito": "íntegra",
    },
    (
        "T-37",
        "normalizar_email é usado na unicidade da conta",
        "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos",
    ): {
        "preparacao": "conta existente, conta banida e aliases com + (hypothesis, 15 exemplos)",
        "acao": "cria conta, emite convite, faz login, cadastra, pede link, entra pelo Google e bane com variações de caixa e espaços",
        "resultado": "criar conta com a variação do e-mail levanta EmailEmUso",
        "veredito": "íntegra",
    },
    (
        "T-37",
        "normalizar_email é usado no convite",
        "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos",
    ): {
        "preparacao": "conta existente, conta banida e aliases com + (hypothesis, 15 exemplos)",
        "acao": "cria conta, emite convite, faz login, cadastra, pede link, entra pelo Google e bane com variações de caixa e espaços",
        "resultado": "emitir convite com a variação levanta EmailEmUso e o alias com + é emitido normalmente",
        "veredito": "íntegra",
    },
    (
        "T-37",
        "normalizar_email é usado no login",
        "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos",
    ): {
        "preparacao": "conta existente, conta banida e aliases com + (hypothesis, 15 exemplos)",
        "acao": "cria conta, emite convite, faz login, cadastra, pede link, entra pelo Google e bane com variações de caixa e espaços",
        "resultado": "o login e o link com a variação entram na conta do endereço base e o alias com + não",
        "veredito": "íntegra",
    },
    (
        "T-37",
        "normalizar_email é usado no cadastro",
        "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos",
    ): {
        "preparacao": "conta existente, conta banida e aliases com + (hypothesis, 15 exemplos)",
        "acao": "cria conta, emite convite, faz login, cadastra, pede link, entra pelo Google e bane com variações de caixa e espaços",
        "resultado": "consumir convite com a variação levanta ConviteInvalido email_em_uso",
        "veredito": "íntegra",
    },
    (
        "T-37",
        "normalizar_email é usado no banimento",
        "tests/tecnicos/test_normalizacao_varredura.py::test_variacoes_de_caixa_e_espaco_sao_o_mesmo_endereco_em_todos_os_fluxos",
    ): {
        "preparacao": "conta existente, conta banida e aliases com + (hypothesis, 15 exemplos)",
        "acao": "cria conta, emite convite, faz login, cadastra, pede link, entra pelo Google e bane com variações de caixa e espaços",
        "resultado": "a função de banimento reconhece o e-mail banido com variação de caixa e espaços, a emissão de convite para ele levanta EmailBanidoErro e o alias com + não está banido",
        "veredito": "íntegra",
    },
    (
        "T-37",
        "Aliases com + continuam distintos",
        "tests/tecnicos/test_contas_emails.py::test_normalizar_email_propriedade_alias_continua_distinto",
    ): {
        "preparacao": "e-mails e etiquetas gerados (hypothesis)",
        "acao": "`normalizar_email` do e-mail e do alias com +",
        "resultado": "o alias normalizado é diferente do e-mail base para os exemplos gerados",
        "veredito": "íntegra",
    },
    (
        "T-38",
        "Quantidades em L são validadas contra o incremento",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "casos (LITRO, 0.5, 1.5): aceito (reservado e parcela de 1,5) e (LITRO, 0.5, 1.2): QuantidadeInvalida e nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        "T-38",
        "Quantidades em kg são validadas contra o incremento",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (KG, 0.5, 1.2): QuantidadeInvalida e nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        "T-38",
        "Quantidades em unidade são validadas contra o incremento",
        "tests/tecnicos/test_interesses_servicos.py::test_quantidades_e_incrementos",
    ): {
        "preparacao": "produto da unidade e do incremento do caso, a R$ 12,00; comprador novo; 14 casos do parametrize",
        "acao": "`adicionar_interesse` com a entrada do caso",
        "resultado": "caso (UNIDADE, 1, 2.5): QuantidadeInvalida e nenhuma parcela",
        "veredito": "íntegra",
    },
    (
        "T-38",
        "Incremento zero é recusado",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_zero_e_recusado_e_o_produto_nao_e_criado",
    ): {
        "preparacao": "administrador e fornecedor",
        "acao": "`criar_produto` com incremento 0",
        "resultado": "IncrementoInvalido e nenhum produto criado",
        "veredito": "íntegra",
    },
    (
        "T-38",
        "Incremento negativo é recusado",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_negativo_e_recusado_e_o_produto_nao_e_criado",
    ): {
        "preparacao": "administrador e fornecedor",
        "acao": "`criar_produto` com incremento -1",
        "resultado": "IncrementoInvalido e nenhum produto criado",
        "veredito": "íntegra",
    },
    (
        "T-38",
        "Incremento com mais de 3 casas é recusado",
        "tests/aceitacao/test_cenarios_20_34_59_t38_atomicos.py::test_t38_incremento_com_mais_de_3_casas_e_recusado_e_o_produto_nao_e_criado",
    ): {
        "preparacao": "administrador e fornecedor",
        "acao": "`criar_produto` com incremento 0,0001",
        "resultado": "IncrementoInvalido e nenhum produto criado",
        "veredito": "íntegra",
    },
    (
        "T-38",
        "Múltiplo incompatível é recusado no cadastro",
        "tests/tecnicos/test_catalogo_quantidades.py::test_multiplo_invalido_no_cadastro",
    ): {
        "preparacao": "administrador logado; fornecedor; 4 casos de incremento e múltiplo incompatíveis",
        "acao": "POST do formulário de cadastro de produto com o caso",
        "resultado": "200 com erro no campo múltiplo e nenhum produto, nos 4 casos",
        "veredito": "íntegra",
    },
    (
        "T-38",
        "Múltiplo incompatível é recusado na alteração em interesse",
        "tests/tecnicos/test_catalogo_condicoes.py::test_multiplo_invalido_em_interesse",
    ): {
        "preparacao": "produto com incremento 0,25 e múltiplo 1 em rodada de interesse; administrador logado",
        "acao": 'POST do múltiplo "0,9"',
        "resultado": "200 com erro no campo múltiplo; o múltiplo segue 1,000",
        "veredito": "íntegra",
    },
    (
        "T-39",
        "7,99 × 0,25 arredonda para 2,00",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_7_99_vezes_0_25",
    ): {
        "preparacao": "os decimais 7,99 e 0,25",
        "acao": "`arredondar_centavos` do produto exato",
        "resultado": "o produto exato 1,9975 vira 2,00",
        "veredito": "íntegra",
    },
    (
        "T-39",
        "2,50 × 0,25 arredonda para 0,63",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_2_50_vezes_0_25",
    ): {
        "preparacao": "os decimais 2,50 e 0,25",
        "acao": "`arredondar_centavos` do produto exato",
        "resultado": "o produto exato 0,625 vira 0,63",
        "veredito": "íntegra",
    },
    (
        "T-39",
        "12,99 × 0,35 arredonda para 4,55",
        "tests/tecnicos/test_nucleo_valores.py::test_arredondamento_12_99_vezes_0_35",
    ): {
        "preparacao": "os decimais 12,99 e 0,35",
        "acao": "`arredondar_centavos` do produto exato",
        "resultado": "o produto exato 4,5465 vira 4,55",
        "veredito": "íntegra",
    },
    (
        "T-39",
        "P é a soma dos subtotais arredondados",
        "tests/tecnicos/test_pedidos_calculo.py::test_produtos_soma_os_subtotais_ja_arredondados",
    ): {
        "preparacao": "um comprador com dois itens de 2,50 por 0,250 (função pura)",
        "acao": "`calcular_cobranca`",
        "resultado": "o total de produtos de dois itens de 0,63 é 1,26 (soma dos subtotais já arredondados)",
        "veredito": "íntegra",
    },
    (
        "T-39",
        "A verificação estática não encontra float em código monetário",
        "tests/tecnicos/test_varredura_float.py::test_modulos_de_dinheiro_nao_usam_float",
    ): {
        "preparacao": "os módulos de dinheiro do código",
        "acao": "varredura estática por uso de float",
        "resultado": "a lista de usos de float nos módulos de dinheiro é vazia",
        "veredito": "íntegra",
    },
    (
        "T-40",
        "O reembolso do item inteiro depois de mudar o preço usa o subtotal do snapshot",
        "tests/aceitacao/test_t40_reembolso_do_item_inteiro.py::test_t40_reembolso_do_item_inteiro_depois_de_mudar_o_preco",
    ): {
        "preparacao": "pedido pago com item de 1,000 kg a 7,99 (K); o preço do catálogo muda para 9,99",
        "acao": "reembolso parcial da quantidade inteira (1)",
        "resultado": "o reembolso é 7,99, 0,40 e 1,60 (o registrado, não 9,99) e a linha é o item inteiro com 1,000 por 7,99",
        "veredito": "íntegra",
    },
    (
        "T-40",
        "A soma da devolução integral bate com os valores cobrados registrados",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
    ): {
        "preparacao": "pedido N pago de 100,00 + 5,00 + 20,00 com dois itens; um parcial de 1 unidade do segundo",
        "acao": "reembolso integral do pedido",
        "resultado": "o integral devolve o restante de cada item (25,00 e 50,00), componentes 75,00, 3,75 e 15,00 e o acumulado 100,00, 5,00 e 20,00",
        "veredito": "íntegra",
    },
    (
        "T-41",
        "O reenvio manual é recusado durante o ciclo automático",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_durante_o_ciclo_automatico_o_reenvio_e_recusado",
    ): {
        "preparacao": "AF no meio do ciclo automático; estado das tentativas fotografado; consulta ao provedor substituída por um contador",
        "acao": "reenvio manual pelo serviço",
        "resultado": "ReenvioRecusado ciclo_em_andamento; nenhuma consulta ao provedor; estado igual",
        "veredito": "íntegra",
    },
    (
        "T-41",
        "O reenvio manual é aceito depois da terceira falha",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
    ): {
        "preparacao": "AF com 3 falhas; outbox limpo; pedido formal fotografado",
        "acao": "`reenviar_pedido_formal` pelo administrador com um token",
        "resultado": "tentativa manual 4 com sucesso, token e destino; e-mail com o assunto e o corpo do pedido",
        "veredito": "íntegra",
    },
    (
        "T-41",
        "O reenvio manual é aceito depois de sucesso",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico",
    ): {
        "preparacao": "AF com envio automático bem-sucedido (1 tentativa)",
        "acao": "reenvio manual pelo administrador; depois processa +24 h",
        "resultado": "tentativa 2 com sucesso depois do sucesso automático",
        "veredito": "íntegra",
    },
    (
        "T-41",
        "O reenvio gera uma tentativa por acionamento",
        "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso",
    ): {
        "preparacao": "administrador logado; AF com envio automático bem-sucedido",
        "acao": "lê o token da página e faz POST do reenvio",
        "resultado": "as tentativas são exatamente uma automática e uma manual depois de um acionamento",
        "veredito": "íntegra",
    },
    (
        "T-41",
        "O reenvio não inicia novo ciclo automático",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico",
    ): {
        "preparacao": "AF com envio automático bem-sucedido (1 tentativa)",
        "acao": "reenvio manual pelo administrador; depois processa +24 h",
        "resultado": "o processamento depois de 24 h não faz nada e continuam 2 tentativas",
        "veredito": "íntegra",
    },
    (
        "T-41",
        "O reenvio mantém o snapshot e o identificador do pedido formal",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
    ): {
        "preparacao": "AF com 3 falhas; outbox limpo; pedido formal fotografado",
        "acao": "`reenviar_pedido_formal` pelo administrador com um token",
        "resultado": "o pedido formal (identificador e linhas) igual ao fotografado e o envio segue concluído com falhas",
        "veredito": "íntegra",
    },
    (
        "T-42",
        "A consulta do comprador devolve reservado e pendente em campos separados",
        "tests/tecnicos/test_interesses_carrinho.py::test_reservado_e_pendente_aparecem_juntos_com_estoque_zerado",
    ): {
        "preparacao": "produto com limite 6 e A com parcela de 10 originais, 6 reservadas e 4 pendentes (livre zero)",
        "acao": "A abre o carrinho",
        "resultado": 'a consulta de A mostra "Reservado: 6" e "Pendente: 4" separados, com o livre zero',
        "veredito": "íntegra",
    },
    (
        "T-42",
        "A consulta separa reservado e pendente com estoque zero",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero",
    ): {
        "preparacao": "FP; R2 com limite 10 para P (A com 6; C com 4 reservadas e 4 pendentes reais da apuração)",
        "acao": "C e A abrem o carrinho",
        "resultado": 'C vê "Reservado: 4" e "Pendente: 4" com o livre zero',
        "veredito": "íntegra",
    },
    (
        "T-42",
        "Outro comprador não vê essas parcelas",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_carrinho_separa_reservado_e_pendente_com_o_livre_zero",
    ): {
        "preparacao": "FP; R2 com limite 10 para P (A com 6; C com 4 reservadas e 4 pendentes reais da apuração)",
        "acao": "C e A abrem o carrinho",
        "resultado": 'A não vê o "Pendente: 4" de C e vê só o próprio "Reservado: 6"',
        "veredito": "íntegra",
    },
    (
        "T-43",
        "A remoção parcial e total muda só a quantidade pendente",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
    ): {
        "preparacao": "A com parcela de 10 originais, 6 reservadas e 4 pendentes; outra compradora com 5 reservadas; sequências lidas antes",
        "acao": "remove 2 pendentes e depois as 2 restantes (`remover_pendente`)",
        "resultado": "depois de remover 2 e as 2 restantes o reservado segue 6 e o pendente vai 2 e 0",
        "veredito": "íntegra",
    },
    (
        "T-43",
        "A remoção mantém as sequências inalteradas",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_parcial_e_total_da_pendencia",
    ): {
        "preparacao": "A com parcela de 10 originais, 6 reservadas e 4 pendentes; outra compradora com 5 reservadas; sequências lidas antes",
        "acao": "remove 2 pendentes e depois as 2 restantes (`remover_pendente`)",
        "resultado": "as sequências das duas parcelas iguais às lidas antes",
        "veredito": "íntegra",
    },
    (
        "T-43",
        "A remoção mantém as reservas inalteradas",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_remover_pendentes_nao_mexe_nas_reservas_nem_no_estorno",
    ): {
        "preparacao": "FP; R2 com limite 10: C com 4 reservadas e 4 pendentes reais; reembolsos de C e sequências lidos antes",
        "acao": "C remove 2 e depois as 4 pendentes pela rota",
        "resultado": "A segue com 6 reservadas e C com 4 depois de remover as pendentes; sequências iguais",
        "veredito": "íntegra",
    },
    (
        "T-43",
        "As parcelas mais recentes são reduzidas primeiro",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_comeca_pela_parcela_mais_recente",
    ): {
        "preparacao": "A com duas pendentes: a antiga de 2 e a recente de 3",
        "acao": "remove 4 pendentes",
        "resultado": "a parcela recente fica removida e a antiga fica pendente com 1; a auditoria lista a recente antes da antiga",
        "veredito": "íntegra",
    },
    (
        "T-43",
        "Quantidade fora do incremento é recusada sem escrita",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava",
    ): {
        "preparacao": 'produto com limite 10 e A com 4 pendentes; 6 entradas do parametrize ("5", "1.5", "0", "-1", "abc" e 1.0)',
        "acao": "`remover_pendente(a, produto, entrada)`",
        "resultado": 'caso "1.5": QuantidadeInvalida; a parcela segue pendente com 4 e nenhuma auditoria',
        "veredito": "íntegra",
    },
    (
        "T-43",
        "Quantidade acima do pendente é recusada sem escrita",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_remocao_invalida_nao_grava",
    ): {
        "preparacao": 'produto com limite 10 e A com 4 pendentes; 6 entradas do parametrize ("5", "1.5", "0", "-1", "abc" e 1.0)',
        "acao": "`remover_pendente(a, produto, entrada)`",
        "resultado": 'caso "5": RemocaoAcimaDoPendente; a parcela segue pendente com 4 e nenhuma auditoria',
        "veredito": "íntegra",
    },
    (
        "T-44",
        "A remoção com item de pedido congelado é recusada",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_com_o_pk_real_do_item_congelado_e_recusada",
    ): {
        "preparacao": "FP; item de pedido de A em Q existente; pedidos, itens, reembolsos e parcelas de A lidos antes",
        "acao": "POST da rota de remoção de pendentes com o pk real do item congelado",
        "resultado": "POST da rota com o pk real do item de A em Q: resposta 200, 404 ou 409 e pedidos, itens, reembolsos e parcelas iguais",
        "veredito": "íntegra",
    },
    (
        "T-44",
        "A remoção com parcela em pedido é recusada pelo serviço",
        "tests/tecnicos/test_interesses_remover_pendente.py::test_parcela_em_pedido_nao_entra_na_remocao",
    ): {
        "preparacao": "parcela de A em pedido com 6 originais, 4 reservadas e 2 pendentes",
        "acao": "`remover_pendente` de 2 pelo serviço",
        "resultado": "RemocaoAcimaDoPendente e a parcela segue em pedido (4 e 2)",
        "veredito": "íntegra",
    },
    (
        "T-44",
        "A remoção com parcela em pedido é recusada pela rota",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido",
    ): {
        "preparacao": "FP; A com item de pedido em Q e a parcela de Q só em pedido; itens, reembolsos e estado lidos antes",
        "acao": "POST da rota de remoção com o pk do item mais 10.000 e com o produto Q",
        "resultado": "a rota com o produto Q (só em pedido) e com um pk inexistente responde 200, 404 ou 409 e o estado de A em Q fica igual",
        "veredito": "íntegra",
    },
    (
        "T-44",
        "Pedido, trigger e registros financeiros ficam inalterados",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_de_remocao_nao_alcanca_o_que_so_esta_em_pedido",
    ): {
        "preparacao": "FP; A com item de pedido em Q e a parcela de Q só em pedido; itens, reembolsos e estado lidos antes",
        "acao": "POST da rota de remoção com o pk do item mais 10.000 e com o produto Q",
        "resultado": "itens, reembolsos e parcela de A em Q iguais aos lidos antes",
        "veredito": "íntegra",
    },
    (
        "T-44",
        "Pedido, trigger e registros financeiros ficam inalterados",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_rota_com_o_pk_real_do_item_congelado_e_recusada",
    ): {
        "preparacao": "FP; item de pedido de A em Q existente; pedidos, itens, reembolsos e parcelas de A lidos antes",
        "acao": "POST da rota de remoção de pendentes com o pk real do item congelado",
        "resultado": "pedidos, itens, reembolsos e parcelas de A iguais por conteúdo aos lidos antes",
        "veredito": "íntegra",
    },
    (
        "T-45",
        "Remoção em paralelo com a alocação: reservado mais pendente não passa do original",
        "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes; duas ordens (remoção primeiro ou alocação primeiro)",
        "acao": "a remoção de 6 e a alocação da fila em paralelo",
        "resultado": "nas duas ordens reservado mais pendente não passa do original",
        "veredito": "íntegra",
    },
    (
        "T-45",
        "Remoção em paralelo com a alocação: o total reservado não passa do estoque",
        "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes; duas ordens (remoção primeiro ou alocação primeiro)",
        "acao": "a remoção de 6 e a alocação da fila em paralelo",
        "resultado": "o total reservado fica dentro do limite 10 nas duas ordens",
        "veredito": "íntegra",
    },
    (
        "T-45",
        "A quantidade removida nunca é reservada",
        "tests/tecnicos/test_interesses_concorrencia.py::test_remocao_e_atendimento_da_fila_se_serializam",
    ): {
        "preparacao": "produto com limite 10; A com 6 pendentes; duas ordens (remoção primeiro ou alocação primeiro)",
        "acao": "a remoção de 6 e a alocação da fila em paralelo",
        "resultado": "removida primeiro: total 0 e parcela removida; alocada primeiro: a remoção é recusada",
        "veredito": "íntegra",
    },
    (
        "T-46",
        "A liberação de estoque em paralelo com nova reserva atende os pendentes pela sequência",
        "tests/tecnicos/test_interesses_concorrencia.py::test_reducao_e_adicao_concorrentes_dao_a_fila_o_que_foi_liberado",
    ): {
        "preparacao": "o mesmo arranjo e E comprador novo; a redução de D e a adição de E em paralelo",
        "acao": "D reduz 3 e E adiciona (esperando)",
        "resultado": "C recebe as 3 unidades liberadas antes da nova reserva de E, que é recusada; total 10",
        "veredito": "íntegra",
    },
    (
        "T-46",
        "Pendentes do fornecedor X nunca são alocados em rodada do fornecedor Y",
        "tests/tecnicos/test_interesses_fila.py::test_a_fila_de_um_fornecedor_so_vai_para_as_rodadas_dele",
    ): {
        "preparacao": "rodada do fornecedor X com estoque livre; pendente de 4 de um produto do fornecedor Y; um produto novo de X",
        "acao": "`alocar_pendentes` do fornecedor X",
        "resultado": "a alocação do fornecedor X devolve 0; a pendente de Y segue pendente com 4",
        "veredito": "íntegra",
    },
    (
        "T-47",
        "O cálculo do mínimo ignora a quantidade pendente",
        "tests/tecnicos/test_interesses_progresso.py::test_pendentes_nao_entram_no_minimo",
    ): {
        "preparacao": "produto a 10,00 sem limite; mínimo de 100,00; A com 8 reservadas e C com 5 pendentes",
        "acao": "`progresso_da_rodada(rodada, c)` do ponto de vista de C",
        "resultado": "elegível 80,00 (só as 8 reservadas de A) com 5 pendentes de C; mínimo de 100,00 não atingido",
        "veredito": "íntegra",
    },
    (
        "T-47",
        "A formação de caixas ignora a quantidade pendente",
        "tests/tecnicos/test_interesses_progresso.py::test_a_formacao_de_caixas_ignora_as_pendentes",
    ): {
        "preparacao": "produto com múltiplo 10 a 10,00; A com 7 reservadas e C com 5 pendentes (7+5 completaria uma caixa)",
        "acao": "`progresso_da_rodada` antes e depois de A reservar mais 3",
        "resultado": "com múltiplo 10, 7 reservadas e 5 pendentes: 0 caixas e elegível 0; com 10 reservadas: 1 caixa, e a pendente de 5 segue pendente",
        "veredito": "íntegra",
    },
    (
        "T-47",
        "A abertura do pagamento e o pedido ignoram a quantidade pendente",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
    ): {
        "preparacao": "FP; R2 com P (limite 10) e Q; A adiciona 10 de Q; C tem 4 pendentes de P",
        "acao": "o progresso é lido e o administrador inicia o fechamento (e o pedido é aberto)",
        "resultado": "o item de P do pedido de C tem 4,000 (só as reservadas) e o progresso soma 200,00",
        "veredito": "íntegra",
    },
    (
        "T-47",
        "O pedido formal ignora a quantidade pendente",
        "tests/tecnicos/test_pedido_formal.py::test_as_quantidades_pendentes_nao_entram",
    ): {
        "preparacao": "AF com 2 unidades pendentes de A em P1; pedido formal gerado",
        "acao": "lê as linhas do pedido formal e a parcela de A",
        "resultado": "a linha de P1 do pedido formal tem 11,000 (sem as 2 pendentes) e a parcela de A segue com pendente 2,000",
        "veredito": "íntegra",
    },
    (
        "T-47",
        "A cobrança ignora a quantidade pendente",
        "tests/aceitacao/test_cenarios_15_30_45_56_104_atomicos.py::test_cenario_104_a_cobranca_do_pedido_ignora_as_pendentes",
    ): {
        "preparacao": "FP; R2 com P e Q; A adiciona 10 de Q; C com 4 reservadas e 4 pendentes de P; fechamento e abertura do pagamento",
        "acao": "abre o pagamento e lê o pedido de C",
        "resultado": "o total de produtos do pedido de C é o subtotal das 4,000 reservadas de P",
        "veredito": "íntegra",
    },
    (
        "T-47",
        "A quantidade pendente continua na fila depois da abertura do pagamento",
        "tests/tecnicos/test_fila_ponta_a_ponta.py::test_progresso_e_pedido_so_contam_as_reservadas",
    ): {
        "preparacao": "FP; R2 com P (limite 10) e Q; A adiciona 10 de Q; C tem 4 pendentes de P",
        "acao": "o progresso é lido e o administrador inicia o fechamento (e o pedido é aberto)",
        "resultado": "a parcela de C segue pendente com 4,000 depois da abertura do pagamento",
        "veredito": "íntegra",
    },
    (
        "T-48",
        "Valor compatível de incremento é aceito na fase de interesse",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_compativel_e_aceito",
    ): {
        "preparacao": "produto em kg do cenário 105 (incremento 0,5, múltiplo 3, reservadas 1,0 e 1,5 e pendente 2,0) em interesse; parcelas fotografadas; administrador logado",
        "acao": 'POST do incremento "0,25"',
        "resultado": "302; incremento 0,250 e auditoria com anterior 0,500 e novo 0,250",
        "veredito": "íntegra",
    },
    (
        "T-48",
        "Incremento incompatível com o reservado é recusado sem escrita",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_reservada_e_recusado",
    ): {
        "preparacao": "produto em kg do cenário 105; parcelas fotografadas; administrador logado",
        "acao": "`alterar_incremento` para 1 pelo serviço e POST da rota com 1",
        "resultado": "IncrementoIncompativel de quantidade (serviço) e 200 com a mensagem (rota); incremento 0,500, parcelas iguais e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        "T-48",
        "Incremento incompatível com o pendente é recusado sem escrita",
        "tests/tecnicos/test_catalogo_incremento.py::test_pendente_da_fila_tambem_conta",
    ): {
        "preparacao": "produto com incremento 0,25 e uma parcela só pendente de 0,75",
        "acao": "`alterar_incremento` para 0,5 pelo administrador",
        "resultado": "IncrementoIncompativel de quantidade (0,75 pendente não é múltiplo de 0,5); incremento segue 0,250 e (R13) nenhuma auditoria",
        "veredito": "corrigida: assert acrescentado (sem escrita)",
    },
    (
        "T-48",
        "Incremento incompatível com o múltiplo é recusado sem escrita",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_incompativel_com_o_multiplo_e_recusado",
    ): {
        "preparacao": "cenário 105 sem as reservadas (só a pendente de 2,0 em uso, múltiplo 3 que não é divisível por 2)",
        "acao": "`alterar_incremento` para 2 pelo serviço e POST da rota com 2",
        "resultado": "IncrementoIncompativel de múltiplo; incremento segue 0,500 e nenhuma auditoria",
        "veredito": "íntegra",
    },
    (
        "T-48",
        "Qualquer valor de incremento é recusado a partir do fechamento",
        "tests/tecnicos/test_catalogo_incremento.py::test_incremento_congelado",
    ): {
        "preparacao": "produto do cenário 105 em cada etapa congelada, sem rodada e em retirada (parametrize); administrador logado",
        "acao": 'POST do incremento "0,25" pela rota e `alterar_incremento` pelo serviço',
        "resultado": "(R14) em cada etapa congelada a rota dá 409 e o serviço levanta CondicoesCongeladas para 0,25, 1, 0,125 e 0,5",
        "veredito": "corrigida: asserts acrescentados (mais valores)",
    },
    (
        "T-49",
        "A alteração do incremento e a adição em paralelo são serializadas pela trava do produto",
        "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam",
    ): {
        "preparacao": "produto sem limite, incremento 1; A adiciona 3 e o administrador altera o incremento para 2; as duas ordens (parametrize)",
        "acao": "a adição e a alteração em paralelo",
        "resultado": "adição primeiro: alteração recusada (incremento 1); alteração primeiro: adição recusada (incremento 2 e nenhuma parcela)",
        "veredito": "íntegra",
    },
    (
        "T-49",
        "Nenhuma parcela fica fora do incremento vigente ao final",
        "tests/tecnicos/test_interesses_concorrencia.py::test_adicao_e_alteracao_de_incremento_se_serializam",
    ): {
        "preparacao": "produto sem limite, incremento 1; A adiciona 3 e o administrador altera o incremento para 2; as duas ordens (parametrize)",
        "acao": "a adição e a alteração em paralelo",
        "resultado": "a quantidade reservada de toda parcela é múltipla do incremento vigente",
        "veredito": "íntegra",
    },
    (
        "T-50",
        "A tabela de incrementos válidos da especificação é aceita",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos",
    ): {
        "preparacao": "os 5 incrementos válidos do parametrize (1, 2, 0,25, 0,5 e 0,001)",
        "acao": "`validar_incremento` com texto e com Decimal",
        "resultado": "os 5 incrementos válidos do parametrize são devolvidos iguais",
        "veredito": "íntegra",
    },
    (
        "T-50",
        "Os incrementos inválidos 0, -1 e 0,0001 são recusados",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_invalidos_no_servico",
    ): {
        "preparacao": "os 6 casos de incremento inválido do parametrize (0, -1, 0,0001, abc, float 0,25 e int 1)",
        "acao": "`validar_incremento(entrada)`",
        "resultado": 'IncrementoInvalido para "0", "-1" e "0.0001" (e para os outros casos do parametrize)',
        "veredito": "íntegra",
    },
    (
        "T-50",
        "Quantidades inteiras e fracionárias são validadas com Decimal",
        "tests/tecnicos/test_catalogo_quantidades.py::test_incrementos_validos",
    ): {
        "preparacao": "os 5 incrementos válidos do parametrize (1, 2, 0,25, 0,5 e 0,001)",
        "acao": "`validar_incremento` com texto e com Decimal",
        "resultado": "a entrada como Decimal também é aceita para os incrementos inteiros e fracionários",
        "veredito": "íntegra",
    },
    (
        "T-50",
        "Número em ponto flutuante na API é recusado",
        "tests/tecnicos/test_nucleo_valores.py::test_conversao_recusa_float",
    ): {
        "preparacao": "as funções `dinheiro` e `quantidade` (parametrize)",
        "acao": "conversão de 7,99 como float",
        "resultado": "ValorInvalido por tipo nas duas funções (interface de serviço; pela rota HTTP não chega float)",
        "veredito": "íntegra",
    },
    (
        "T-51",
        "O reembolso parcial de 7,99 × 0,25 é 2,00",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_o_valor_vem_do_registrado_e_nao_do_catalogo",
    ): {
        "preparacao": "pedido pago com item de 1,000 kg a 7,99; o preço do produto do catálogo muda para 9,99",
        "acao": "reembolso parcial de 0,25",
        "resultado": "o reembolso parcial de 0,25 sobre 7,99 devolve 2,00 de produtos",
        "veredito": "íntegra",
    },
    (
        "T-51",
        "A sequência de quatro parciais é 2,00, 2,00, 2,00 e 1,99",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_quatro_parciais_completam_o_pedido_exatamente",
    ): {
        "preparacao": "pedido pago com um item de 1,000 kg a 7,99 (K), serviço 0,40 e frete 1,60",
        "acao": "4 reembolsos parciais de 0,25",
        "resultado": "os produtos dos quatro parciais são 2,00, 2,00, 2,00 e 1,99",
        "veredito": "íntegra",
    },
    (
        "T-51",
        "O caso de R$ 0,09 tem limite ao saldo",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo",
    ): {
        "preparacao": "pedido pago com um item de 0,600 kg a 0,15 (M)",
        "acao": "5 parciais de 0,1, um sexto e um sétimo",
        "resultado": "os 6 reembolsos são 0,02 ×4, 0,01 e 0,00 (soma 0,09); o sexto sem obrigação; o sétimo recusado por passar da quantidade paga",
        "veredito": "íntegra",
    },
    (
        "T-51",
        "A mudança do preço de catálogo não altera nenhum valor",
        "tests/aceitacao/test_t40_reembolso_do_item_inteiro.py::test_t40_reembolso_do_item_inteiro_depois_de_mudar_o_preco",
    ): {
        "preparacao": "pedido pago com item de 1,000 kg a 7,99 (K); o preço do catálogo muda para 9,99",
        "acao": "reembolso parcial da quantidade inteira (1)",
        "resultado": "com o catálogo a 9,99 os três componentes do reembolso seguem 7,99, 0,40 e 1,60",
        "veredito": "corrigida: religada (a ligação anterior só conferia os produtos)",
    },
    (
        "T-52",
        "O reembolso acima da quantidade paga é recusado",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_centavos_que_nao_fecham_o_ultimo_leva_o_saldo",
    ): {
        "preparacao": "pedido pago com um item de 0,600 kg a 0,15 (M)",
        "acao": "5 parciais de 0,1, um sexto e um sétimo",
        "resultado": 'ReembolsoRecusado "passa da quantidade paga" no sétimo parcial; nenhum registro novo',
        "veredito": "corrigida: religada (a ligação anterior tratava quantidades inválidas, não acima do pago)",
    },
    (
        "T-52",
        "A devolução integral depois de parciais completa exatamente o saldo",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
    ): {
        "preparacao": "pedido N pago de 100,00 + 5,00 + 20,00 com dois itens; um parcial de 1 unidade do segundo",
        "acao": "reembolso integral do pedido",
        "resultado": "o integral devolve o restante de cada item (25,00 e 50,00) e de cada componente (75,00, 3,75 e 15,00)",
        "veredito": "íntegra",
    },
    (
        "T-52",
        "O acumulado de serviço nunca passa do registrado",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
    ): {
        "preparacao": "pedido N pago de 100,00 + 5,00 + 20,00 com dois itens; um parcial de 1 unidade do segundo",
        "acao": "reembolso integral do pedido",
        "resultado": "o acumulado de serviço do pedido é exatamente 5,00, o registrado",
        "veredito": "íntegra",
    },
    (
        "T-52",
        "O acumulado de frete nunca passa do registrado",
        "tests/tecnicos/test_devolucoes_reembolso.py::test_integral_devolve_o_restante_de_cada_item_e_componente",
    ): {
        "preparacao": "pedido N pago de 100,00 + 5,00 + 20,00 com dois itens; um parcial de 1 unidade do segundo",
        "acao": "reembolso integral do pedido",
        "resultado": "o acumulado de frete do pedido é exatamente 20,00, o registrado",
        "veredito": "íntegra",
    },
    (
        "T-53",
        "Dois reembolsos parciais concorrentes são serializados pela trava",
        "tests/tecnicos/test_devolucoes_concorrencia.py::test_dois_parciais_do_mesmo_item_nunca_passam_do_pago",
    ): {
        "preparacao": "pedido pago com item de 1,000 kg a 7,99; dois parciais do mesmo item que juntos passariam de 1,000, em corrida pela trava",
        "acao": "as duas chamadas em paralelo",
        "resultado": "uma conclui e a outra é recusada (ReembolsoRecusado); o acumulado do item é 0,500 e 4,00",
        "veredito": "íntegra",
    },
    (
        "T-53",
        "A soma dos reembolsos concorrentes não passa do subtotal",
        "tests/tecnicos/test_devolucoes_concorrencia.py::test_tres_parciais_ao_mesmo_tempo_respeitam_o_pago",
    ): {
        "preparacao": "pedido pago com item de 1,000 kg a 7,99; três parciais em paralelo (uma soma passaria de 1,000)",
        "acao": "as três chamadas em paralelo",
        "resultado": "quantidade ≤ 1,000, valor e produtos ≤ 7,99, serviço ≤ 0,40 e frete ≤ 1,60; alguma foi recusada",
        "veredito": "íntegra",
    },
    (
        "T-53",
        "Nenhum registro de reembolso é duplicado",
        "tests/tecnicos/test_devolucoes_concorrencia.py::test_dois_parciais_do_mesmo_item_nunca_passam_do_pago",
    ): {
        "preparacao": "pedido pago com item de 1,000 kg a 7,99; dois parciais do mesmo item que juntos passariam de 1,000, em corrida pela trava",
        "acao": "as duas chamadas em paralelo",
        "resultado": "1 Reembolso e 1 ItemReembolsado e 1 obrigação",
        "veredito": "íntegra",
    },
    (
        "T-54",
        "O reenvio manual é recusado com tentativa automática agendada",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_antes_da_primeira_tentativa_automatica_o_reenvio_e_recusado",
    ): {
        "preparacao": "AF com a primeira tentativa automática ainda agendada; estado fotografado",
        "acao": "reenvio manual pelo serviço",
        "resultado": "ReenvioRecusado ciclo_em_andamento e estado igual ao fotografado",
        "veredito": "íntegra",
    },
    (
        "T-54",
        "O reenvio manual é recusado com tentativa automática em execução",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar",
    ): {
        "preparacao": "AF; a tentativa automática pausada dentro do envio",
        "acao": "reenvio manual enquanto a automática roda",
        "resultado": "com a automática pausada dentro do envio, o manual levanta ReenvioRecusado ciclo_em_andamento sem esperar",
        "veredito": "corrigida: religada (antes a ligação era a do ciclo entre tentativas)",
    },
    (
        "T-54",
        "O reenvio manual é aceito depois do sucesso",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_do_sucesso_automatico",
    ): {
        "preparacao": "AF com envio automático bem-sucedido (1 tentativa)",
        "acao": "reenvio manual pelo administrador; depois processa +24 h",
        "resultado": "tentativa 2 com sucesso depois do sucesso automático",
        "veredito": "íntegra",
    },
    (
        "T-54",
        "O reenvio manual é aceito depois da terceira falha",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_depois_das_tres_falhas",
    ): {
        "preparacao": "AF com 3 falhas; outbox limpo; pedido formal fotografado",
        "acao": "`reenviar_pedido_formal` pelo administrador com um token",
        "resultado": "tentativa manual 4 com sucesso depois das 3 falhas",
        "veredito": "íntegra",
    },
    (
        "T-54",
        "O reenvio manual gera uma tentativa por acionamento",
        "tests/tecnicos/test_pedido_formal_telas.py::test_reenviar_depois_do_sucesso",
    ): {
        "preparacao": "administrador logado; AF com envio automático bem-sucedido",
        "acao": "lê o token da página e faz POST do reenvio",
        "resultado": "exatamente uma tentativa manual por acionamento",
        "veredito": "íntegra",
    },
    (
        "T-55",
        "A tentativa automática e o acionamento manual concorrentes recusam o manual",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_reenvio_durante_a_tentativa_automatica_e_recusado_sem_esperar",
    ): {
        "preparacao": "AF; a tentativa automática pausada dentro do envio",
        "acao": "reenvio manual enquanto a automática roda",
        "resultado": "a automática conclui e o manual concorrente é recusado (ciclo_em_andamento); só 3 tentativas automáticas",
        "veredito": "íntegra",
    },
    (
        "T-55",
        "Dois manuais distintos depois do ciclo executam em sequência",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia",
    ): {
        "preparacao": "AF com 3 falhas; dois reenvios em paralelo com tokens diferentes, o primeiro pausado no envio",
        "acao": "os dois reenvios rodam em paralelo pelo serviço",
        "resultado": "a quinta tentativa só começa depois da quarta",
        "veredito": "íntegra",
    },
    (
        "T-55",
        "Dois manuais distintos nunca executam ao mesmo tempo",
        "tests/tecnicos/test_pedido_formal_ponta_a_ponta.py::test_tokens_distintos_em_dois_post_se_executam_em_sequencia",
    ): {
        "preparacao": "AF pela tela; 3 falhas; dois POST em paralelo com tokens diferentes",
        "acao": "os dois POST são executados em paralelo",
        "resultado": "pelas rotas, a segunda tentativa só começa depois de a primeira concluir",
        "veredito": "íntegra",
    },
    (
        "T-55",
        "O snapshot fica inalterado",
        "tests/tecnicos/test_pedido_formal_reenvio.py::test_tokens_distintos_em_paralelo_se_executam_em_sequencia",
    ): {
        "preparacao": "AF com 3 falhas; dois reenvios em paralelo com tokens diferentes, o primeiro pausado no envio",
        "acao": "os dois reenvios rodam em paralelo pelo serviço",
        "resultado": "os e-mails das duas tentativas têm o corpo do pedido formal original",
        "veredito": "íntegra",
    },
}
