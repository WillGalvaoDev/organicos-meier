# E02-09 — Perfil do usuário

Fatia 9 de 10 da milestone **E02 — Identidade, convites e acesso**. Agente 1 (especificador).

## Versões dos documentos-base

- Especificação funcional: v1.6
- Infraestrutura: v1.7
- Gate de especificação (AGENTS.md §4.3): por decisão do responsável pelo projeto em 2026-10-15, não há revisão separada da especificação. O próprio especificador verificou clareza, testabilidade e ausência de decisões novas, e a especificação está liberada para implementação. A revisão independente da implementação (agente 3, `review.md`) continua obrigatória.

## Contexto e objetivo

O cadastro exige só nome e e-mail. Telefone ou WhatsApp e avatar são opcionais e podem ser incluídos depois. Receber mensagens por WhatsApp exige número cadastrado e aceitação opcional do usuário. Esta fatia entrega a tela de perfil com esses dados e o registro do consentimento de WhatsApp, que a fase 3 vai usar. Nenhuma mensagem de WhatsApp é enviada aqui.

## Requisitos de origem

| Referência | Trecho ou resumo |
|---|---|
| Especificação §2 | O comprador ativo edita dados opcionais. |
| Especificação §3.2 | Cadastro exige nome e e-mail. Telefone ou WhatsApp e avatar opcionais, incluídos depois. WhatsApp exige número cadastrado e aceitação opcional. |
| Especificação §13 | Comprador: perfil com nome, avatar, WhatsApp e preferência de recebimento. |
| Especificação §15 | Dados pessoais mínimos; proteção apropriada. |
| Infraestrutura 2 | R2 para avatares. WhatsApp com opt-in registrado (fase 3). |
| Infraestrutura 5 | Nenhum dado pessoal em logs. |

## Escopo

**Dentro:**

- Campos novos em `Conta`:
  - `telefone`;
  - `avatar`;
  - `whatsapp_consentido_em`.
- Tela `/perfil/`, para os papéis comprador, fornecedor e administrador.
- Validação e normalização do telefone.
- Validação e regravação do avatar. Usa a dependência **Pillow**, justificada abaixo.
- Rota autenticada para servir o avatar.
- Auditoria das mudanças de consentimento.

**Fora:**

- Envio de WhatsApp e cadastro de templates (fase 3).
- Armazenamento no R2 em produção. A configuração do storage de produção entra com a homologação (E16). Aqui vale o storage padrão do Django em `MEDIA_ROOT`, em desenvolvimento e testes.
- Alteração de e-mail, papel, fornecedor ou situação pelo usuário, que não está prevista. O e-mail é a identidade da conta (especificação §2).
- Preferência de notificação por e-mail, sempre ativa, cujos eventos ficam na E04.

## Regras

**Campos editáveis:**

| Campo | Regra |
|---|---|
| `nome` | obrigatório, as mesmas regras da E02-01 |
| `telefone` | opcional. Aceita dígitos e os separadores espaço, parênteses, hífen e `+`. Normalizado para E.164 brasileiro, no formato `+55` seguido de DDD e número, com 10 ou 11 dígitos depois do `+55`. A entrada pode começar com `+55`, com `55` ou direto pelo DDD. O DDD não pode começar com 0. Qualquer outro formato é recusado com mensagem. Vazio remove o telefone |
| `avatar` | opcional. Imagem JPEG, PNG ou WebP, com até 2 MB e até 4096 × 4096 pixels |
| consentimento de WhatsApp | caixa de seleção, possível só com telefone cadastrado |

**Telefone:**

- A operação é local, com retirada no Méier, e o WhatsApp Cloud API usa E.164. Por isso a normalização segue o formato brasileiro.
- É uma decisão técnica sobre o formato, sem efeito comercial.
- Números estrangeiros não são aceitos nesta versão.

**Avatar:**

- **Validação:** o arquivo é aberto com Pillow e verificado. Se não for imagem nos formatos aceitos, se tiver mais de 2 MB ou se passar das dimensões, é recusado.
- **Regravação:** a imagem é regravada no mesmo formato, sem metadados, o que remove EXIF e GPS, para proteger os dados pessoais.
- **Nome do arquivo:** um UUID gerado pelo servidor, sem o nome original.
- **Troca e remoção:** trocar ou remover o avatar apaga o arquivo anterior do storage depois do commit.

**Pillow:**

- **Dependência nova:** entra só por necessidade demonstrada. Sem ela, não dá para verificar com segurança que o arquivo é uma imagem nem remover os metadados.
- **Instalação:** vai para `pyproject.toml` e `uv.lock`, com versão travada.

**Consentimento de WhatsApp:**

- **Marcar com telefone:** grava `whatsapp_consentido_em = agora()` e a auditoria `perfil.whatsapp_consentir`, com alterações `{"conta": <id>}`.
- **Desmarcar:** grava nulo e a auditoria `perfil.whatsapp_revogar`.
- **Remover o telefone com o consentimento ativo:** revoga o consentimento na mesma gravação, com a auditoria `perfil.whatsapp_revogar`.
- **Marcar sem telefone:** recusado com mensagem.
- **Trocar o telefone com o consentimento ativo:** revoga o consentimento. É preciso aceitar de novo para o número novo, porque o consentimento vale para um número.
- **Sem dado pessoal na auditoria:** a auditoria não registra o número.

**Acesso:**

- **`/perfil/`:** exige login e mostra e edita só a conta da sessão. Não há parâmetro de identificação de conta.
- **Avatar:** `/perfil/avatar/<id da conta>/` serve o arquivo à própria conta e ao administrador, que vê usuários na moderação. Os demais recebem 404, para não confirmar a existência.
- **Contas suspensas:** editam o perfil normalmente. A suspensão restringe compras (especificação §2), não o perfil.

## Interfaces

- `apps/contas/perfil.py`: `normalizar_telefone(texto) -> str | None` (levanta `TelefoneInvalido`) e `processar_avatar(arquivo) -> ContentFile` (levanta `AvatarInvalido`).
- `apps/contas/forms.py`: `FormularioPerfil`.
- `apps/contas/views.py`: `perfil` e `avatar`.
- Migração com os três campos novos.

## Invariantes

- O telefone gravado é sempre E.164 brasileiro ou nulo.
- O consentimento de WhatsApp só existe com telefone, garantido por `CHECK` no banco: `whatsapp_consentido_em IS NULL OR telefone IS NOT NULL`.
- Nenhum avatar gravado tem metadados EXIF.
- Nenhuma conta vê ou altera o perfil de outra.

## Casos-limite e concorrência

- **Telefone:** `(21) 99999-8888`, `21999998888`, `+55 21 99999-8888` e `5521999998888` resultam em `+5521999998888`. `2199998888` (fixo, 10 dígitos) resulta em `+552199998888`. São recusados `099999888`, `+1 212 555 0100`, `abc` e `21 9999`.
- **Avatar:** um arquivo `.png` que é na verdade texto é recusado. Um JPEG com GPS no EXIF é gravado sem EXIF.
- **Sem concorrência crítica.**

## Dependências e decisões em aberto

- Depende de E02-02 (sessão) e E02-03 (o administrador vê avatares).
- Sem decisões em aberto.
