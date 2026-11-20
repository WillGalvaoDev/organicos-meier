from typing import Any

import pytest

from tests.rastreabilidade.catalogo import nomes_do_banco


@pytest.fixture
def nomes_banco(db: Any) -> frozenset[str]:
    """Os nomes reais de restrições, índices únicos e triggers do banco de testes migrado."""
    return nomes_do_banco()
