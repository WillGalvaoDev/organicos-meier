"""O endereço de retirada (E14-03): o registro só de inserção mantido pelo administrador.

O endereço vigente é o de maior `pk`. Vale para o carrinho, para as regras e para as liberações
seguintes; cada liberação guarda o que valia no momento dela (E14-04).
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.contas.models import Conta, Papel, Situacao
from apps.nucleo.auditoria import registrar_auditoria
from apps.pedidos.models import EnderecoDeRetirada

MAIOR_ENDERECO = 500
MENSAGENS = {
    "texto_invalido": "Informe o endereço de retirada, com até 500 caracteres.",
    "sem_alteracao": "O endereço informado é igual ao atual.",
}


class EnderecoRecusado(Exception):
    """O endereço não pôde ser registrado. `codigo` diz o motivo; a mensagem é a da tela."""

    def __init__(self, codigo: str) -> None:
        self.codigo = codigo
        super().__init__(MENSAGENS[codigo])


def endereco_vigente() -> EnderecoDeRetirada | None:
    """O último endereço registrado, ou `None` enquanto nenhum foi."""
    return EnderecoDeRetirada.objects.order_by("-pk").first()


def definir_endereco_de_retirada(autor: Conta | None, texto: object) -> EnderecoDeRetirada:
    """Registra um endereço novo. Só o administrador ativo (`PermissionDenied`). O texto perde os
    espaços das pontas e as quebras `\r\n`; vazio, longo ou igual ao vigente é recusado."""
    if autor is None or autor.papel != Papel.ADMINISTRADOR or autor.situacao != Situacao.ATIVA:
        raise PermissionDenied
    limpo = texto.replace("\r\n", "\n").strip() if isinstance(texto, str) else ""
    if not limpo or len(limpo) > MAIOR_ENDERECO:
        raise EnderecoRecusado("texto_invalido")
    with transaction.atomic():
        anterior = endereco_vigente()
        if anterior is not None and anterior.texto == limpo:
            raise EnderecoRecusado("sem_alteracao")
        registro = EnderecoDeRetirada.objects.create(texto=limpo, autor=autor)
        registrar_auditoria(
            autor,
            "retirada.definir_endereco",
            registro,
            {"anterior": anterior.texto if anterior is not None else "", "novo": limpo},
        )
    return registro
