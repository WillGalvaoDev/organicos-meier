"""Falhas do armazenamento de arquivos (E16-02).

Uma falha do R2 no envio (rede, credencial) vira `ArmazenamentoIndisponivel`, para que a ação do
usuário não seja gravada pela metade e a tela responda 503. O log leva só a operação e a classe do
erro: nunca chave de acesso, URL assinada nem nome de arquivo.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager

from boto3.exceptions import S3UploadFailedError
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)

MENSAGEM_DE_FALHA = "Não foi possível enviar o arquivo. Tente de novo."


class ArmazenamentoIndisponivel(Exception):
    """O armazenamento recusou ou não alcançou a gravação do arquivo."""


def _classe_do_erro(erro: BaseException) -> str:
    # o envio em partes do boto3 embrulha o `ClientError` num `S3UploadFailedError`
    causa = erro.__cause__ or erro.__context__
    if isinstance(erro, S3UploadFailedError) and causa is not None:
        return type(causa).__name__
    return type(erro).__name__


@contextmanager
def falha_do_armazenamento(operacao: str) -> Iterator[None]:
    try:
        yield
    except (ClientError, BotoCoreError, S3UploadFailedError) as erro:
        logger.error("armazenamento falhou: operacao=%s erro=%s", operacao, _classe_do_erro(erro))
        raise ArmazenamentoIndisponivel from erro
