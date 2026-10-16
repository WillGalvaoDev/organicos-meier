"""Dublê determinístico da cerimônia WebAuthn (E02-03).

Só a verificação criptográfica é trocada (as cinco funções de
`allauth.mfa.webauthn.internal.auth` listadas na spec, versão 65.19.7 do allauth). Views,
estágios de login, registros de autenticação na sessão e o modelo `Authenticator` são reais.
As credenciais geradas aqui são estruturas WebAuthn válidas para o parser do `fido2`.
"""

import json
import os
from typing import Any

import pytest
from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.mfa.models import Authenticator
from cryptography.hazmat.primitives.asymmetric import ec
from django.contrib.auth import get_user_model
from fido2.cbor import encode
from fido2.cose import ES256
from fido2.utils import sha256, websafe_decode, websafe_encode
from fido2.webauthn import AttestedCredentialData, AuthenticatorData


def novo_id_de_credencial() -> bytes:
    return os.urandom(16)


def registro_json(credencial_id: bytes) -> dict[str, Any]:
    """Resposta de registro (attestation "none") estruturalmente válida."""
    chave_publica = ec.generate_private_key(ec.SECP256R1()).public_key()
    dados = AttestedCredentialData.create(
        b"\0" * 16, credencial_id, ES256.from_cryptography_key(chave_publica)
    )
    auth_data = AuthenticatorData.create(
        sha256(b"localhost"), AuthenticatorData.FLAG.UP | AuthenticatorData.FLAG.AT, 0, dados
    )
    attestation = encode({"fmt": "none", "attStmt": {}, "authData": bytes(auth_data)})
    cliente = json.dumps(
        {"type": "webauthn.create", "challenge": "abc", "origin": "http://localhost"}
    ).encode()
    return {
        "id": websafe_encode(credencial_id),
        "rawId": websafe_encode(credencial_id),
        "type": "public-key",
        "response": {
            "attestationObject": websafe_encode(attestation),
            "clientDataJSON": websafe_encode(cliente),
        },
        "clientExtensionResults": {"credProps": {"rk": False}},
    }


def autenticacao_json(credencial_id: bytes, usuario_pk: int) -> dict[str, Any]:
    """Resposta de autenticação estruturalmente válida (a assinatura é ignorada pelo dublê)."""
    auth_data = AuthenticatorData.create(sha256(b"localhost"), AuthenticatorData.FLAG.UP, 5)
    cliente = json.dumps(
        {"type": "webauthn.get", "challenge": "abc", "origin": "http://localhost"}
    ).encode()
    return {
        "id": websafe_encode(credencial_id),
        "rawId": websafe_encode(credencial_id),
        "type": "public-key",
        "response": {
            "authenticatorData": websafe_encode(bytes(auth_data)),
            "clientDataJSON": websafe_encode(cliente),
            "signature": websafe_encode(b"assinatura"),
            "userHandle": websafe_encode(str(usuario_pk).encode()),
        },
        "clientExtensionResults": {},
    }


class DubleWebAuthn:
    """Controle do dublê: `recusar = True` faz a verificação de autenticação falhar."""

    def __init__(self) -> None:
        self.recusar = False

    def comecar(self, *args: Any, **kwargs: Any) -> dict[str, str]:
        return {"challenge": "dublê"}

    def completar_registro(self, credencial: dict[str, Any]) -> None:
        return None

    def completar_autenticacao(self, usuario: Any, resposta: dict[str, Any]) -> Authenticator:
        if self.recusar:
            raise get_account_adapter().validation_error("incorrect_code")
        credencial_id = websafe_decode(resposta["id"])
        for autenticador in Authenticator.objects.filter(
            user_id=usuario.pk, type=Authenticator.Type.WEBAUTHN
        ):
            dados = autenticador.wrap().authenticator_data.credential_data
            if dados is not None and dados.credential_id == credencial_id:
                return autenticador
        raise get_account_adapter().validation_error("incorrect_code")

    def extrair_usuario(self, resposta: dict[str, Any]) -> Any:
        identificador = websafe_decode(resposta["response"]["userHandle"]).decode()
        return get_user_model().objects.get(pk=int(identificador))


def instalar(monkeypatch: pytest.MonkeyPatch) -> DubleWebAuthn:
    from allauth.mfa.webauthn.internal import auth

    duble = DubleWebAuthn()
    monkeypatch.setattr(auth, "begin_registration", duble.comecar)
    monkeypatch.setattr(auth, "complete_registration", duble.completar_registro)
    monkeypatch.setattr(auth, "begin_authentication", duble.comecar)
    monkeypatch.setattr(auth, "complete_authentication", duble.completar_autenticacao)
    monkeypatch.setattr(auth, "extract_user_from_response", duble.extrair_usuario)
    return duble
