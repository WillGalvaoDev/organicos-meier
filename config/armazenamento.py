"""O armazenamento dos arquivos enviados no Cloudflare R2 (E16-02).

Uma função só monta a configuração, para que `prod.py` e os testes usem exatamente a mesma.
Os arquivos ficam num bucket privado: sem ACL pública e, se alguém chamar `.url`, o link é assinado
e vale 5 minutos. Nenhuma tela usa `.url`: os arquivos saem só pelas views `avatar` e `comprovante`.
"""

from typing import Any

VALIDADE_DO_LINK_ASSINADO = 300


def storage_do_r2(endpoint: str, bucket: str, access_key: str, secret_key: str) -> dict[str, Any]:
    return {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "endpoint_url": endpoint,
            "bucket_name": bucket,
            "access_key": access_key,
            "secret_key": secret_key,
            "region_name": "auto",
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": VALIDADE_DO_LINK_ASSINADO,
            "file_overwrite": False,
            "signature_version": "s3v4",
        },
    }
