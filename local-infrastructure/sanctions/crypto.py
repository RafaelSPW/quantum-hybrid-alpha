"""
Cifrado de sobre (envelope encryption) para datos sensibles de cumplimiento.

  KEK (Key Encryption Key) — gestionada en Google Cloud KMS, nunca toca este proceso.
  DEK (Data Encryption Key) — generada aleatoriamente aquí, cifrada con KMS, almacenada
      junto al ciphertext en Firestore.
  Datos — cifrados con AES-256-GCM (AESGCM de la librería cryptography).

AAD: el Additional Authenticated Data se ata a "{legajo_id}|{owner_uid}".
Esto impide mover un ciphertext a otro legajo o a otro usuario —
AESGCM lanzará InvalidTag si el AAD no coincide al descifrar.

Configuración requerida: variable de entorno KMS_KEY_NAME con el nombre completo
del recurso KMS.
  Ejemplo: projects/mi-proyecto/locations/us-central1/keyRings/ahc-compliance/cryptoKeys/sensitive-data

Nunca se almacenan claves en el código ni en el repo.
El KMS solo maneja la KEK; los datos nunca pasan por KMS.

Marco legal: Ley 18.331 (protección de datos personales), Ley 19.574 (AML).
"""

import os
import secrets
from base64 import b64decode, b64encode
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KMS_KEY_NAME_ENV = "KMS_KEY_NAME"
_DEK_BYTES = 32   # 256 bits
_NONCE_BYTES = 12  # 96 bits — estándar GCM


class KMSNotConfiguredError(RuntimeError):
    """
    KMS_KEY_NAME no está configurado.
    No se procesa datos sensibles sin KMS — nunca se cae a texto plano silenciosamente.
    """


def _key_name() -> str:
    name = os.environ.get(KMS_KEY_NAME_ENV, "").strip()
    if not name:
        raise KMSNotConfiguredError(
            f"Variable de entorno {KMS_KEY_NAME_ENV!r} no configurada. "
            "Configurar el nombre completo del recurso KMS antes de procesar datos sensibles. "
            "Ejemplo: projects/PROYECTO/locations/us-central1/keyRings/ahc-compliance/cryptoKeys/sensitive-data"
        )
    return name


def _make_kms_client():
    """Instancia el cliente KMS. Separado para facilitar mock en tests."""
    from google.cloud import kms  # type: ignore
    return kms.KeyManagementServiceClient()


def cifrar(
    plaintext: str | bytes,
    legajo_id: str,
    owner_uid: str,
    *,
    kms_client: Any = None,
) -> dict[str, str]:
    """
    Cifra plaintext con AES-256-GCM usando envelope encryption.

    Args:
        plaintext:   datos a cifrar (str o bytes).
        legajo_id:   ID de la evaluación — parte del AAD.
        owner_uid:   UID del propietario — parte del AAD.
        kms_client:  cliente KMS inyectable (para tests; None = cliente real).

    Returns:
        Dict serializable a Firestore:
          {algoritmo, kek_version, encrypted_dek_b64, nonce_b64, ciphertext_b64}

    Raises:
        KMSNotConfiguredError si KMS_KEY_NAME no está configurado.
        google.api_core.exceptions.GoogleAPIError si KMS falla.
    """
    key_name = _key_name()
    client = kms_client if kms_client is not None else _make_kms_client()

    # 1. Generar DEK aleatoria
    dek = secrets.token_bytes(_DEK_BYTES)

    # 2. Cifrar DEK con KMS (wrap)
    wrap_resp = client.encrypt(request={"name": key_name, "plaintext": dek})
    encrypted_dek = wrap_resp.ciphertext
    kek_version = wrap_resp.name  # nombre completo con versión, para descifrado posterior

    # 3. Cifrar datos con AESGCM — AAD ata el ciphertext a este legajo+usuario
    aad = f"{legajo_id}|{owner_uid}".encode("utf-8")
    if isinstance(plaintext, str):
        plaintext = plaintext.encode("utf-8")

    nonce = secrets.token_bytes(_NONCE_BYTES)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)

    # Limpiar DEK de memoria (best effort en CPython)
    dek = b"\x00" * _DEK_BYTES  # type: ignore[assignment]

    return {
        "algoritmo":         "AES-256-GCM",
        "kek_version":       kek_version,
        "encrypted_dek_b64": b64encode(encrypted_dek).decode(),
        "nonce_b64":         b64encode(nonce).decode(),
        "ciphertext_b64":    b64encode(ciphertext).decode(),
    }


def descifrar(
    cifrado: dict[str, str],
    legajo_id: str,
    owner_uid: str,
    *,
    kms_client: Any = None,
) -> bytes:
    """
    Descifra un bloque producido por cifrar().

    El AAD (legajo_id|owner_uid) debe coincidir exactamente con el usado al cifrar.
    Si no coincide, AESGCM lanza cryptography.exceptions.InvalidTag — el ciphertext
    fue modificado, corrompido, o movido a otro legajo/usuario.

    Args:
        cifrado:    dict producido por cifrar().
        legajo_id:  debe ser igual al usado al cifrar.
        owner_uid:  debe ser igual al usado al cifrar.
        kms_client: cliente KMS inyectable (para tests).

    Returns:
        bytes del plaintext original.

    Raises:
        KMSNotConfiguredError si KMS_KEY_NAME no está configurado.
        cryptography.exceptions.InvalidTag si AAD no coincide o datos alterados.
    """
    client = kms_client if kms_client is not None else _make_kms_client()

    encrypted_dek = b64decode(cifrado["encrypted_dek_b64"])
    nonce = b64decode(cifrado["nonce_b64"])
    ciphertext = b64decode(cifrado["ciphertext_b64"])
    kek_version = cifrado["kek_version"]

    # 1. Descifrar DEK con KMS (unwrap)
    unwrap_resp = client.decrypt(
        request={"name": kek_version, "ciphertext": encrypted_dek}
    )
    dek = unwrap_resp.plaintext

    # 2. Descifrar datos con AESGCM
    aad = f"{legajo_id}|{owner_uid}".encode("utf-8")
    plaintext = AESGCM(dek).decrypt(nonce, ciphertext, aad)

    dek = b"\x00" * _DEK_BYTES  # type: ignore[assignment]
    return plaintext
