"""As ocorrências de entrega (E14-02). Nesta fatia só a leitura de que o recebimento precisa."""

from decimal import Decimal

from apps.catalogo.models import Produto
from apps.pedidos.models import PedidoFormal

TIPOS = ("faltante", "incorreto", "nao_entregue")


def somas_das_ocorrencias(pedido_formal: PedidoFormal, produto: Produto) -> dict[str, Decimal]:
    """A soma por tipo das ocorrências registradas em `aguardando_fornecedor`, dos itens dos
    pedidos válidos do ciclo do pedido formal. Sem ocorrências (E14-02), tudo é zero."""
    return {tipo: Decimal("0") for tipo in TIPOS}
