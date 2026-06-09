"""
Tests unitarios para crypto.py (envelope encryption AES-256-GCM + KMS mock).

Casos cubiertos:
  1. Round-trip: cifrar → descifrar = plaintext original
  2. AAD incorrecto (legajo_id diferente) → InvalidTag
  3. AAD incorrecto (owner_uid diferente) → InvalidTag
  4. Ciphertext modificado → InvalidTag
  5. KMSNotConfiguredError cuando KMS_KEY_NAME no está configurado
  6. Diferentes plaintexts producen ciphertexts diferentes (nonce aleatorio)
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch

from cryptography.exceptions import InvalidTag

from sanctions.crypto import cifrar, descifrar, KMSNotConfiguredError, _DEK_BYTES


# ─── Mock del cliente KMS ─────────────────────────────────────────────────────

def _make_kms_mock():
    """
    Simula el cliente KMS con identidad (encrypt devuelve la DEK sin cifrar,
    decrypt la devuelve tal cual). Solo válido en tests — no representa seguridad real.
    """
    client = MagicMock()

    def fake_encrypt(request):
        resp = MagicMock()
        resp.ciphertext = request["plaintext"]   # "cifrado" = mismos bytes (mock)
        resp.name = "projects/test/locations/global/keyRings/test/cryptoKeys/test/cryptoKeyVersions/1"
        return resp

    def fake_decrypt(request):
        resp = MagicMock()
        resp.plaintext = request["ciphertext"]   # "descifra" = mismos bytes (mock)
        return resp

    client.encrypt.side_effect = fake_encrypt
    client.decrypt.side_effect = fake_decrypt
    return client


# ─── Tests ────────────────────────────────────────────────────────────────────

class TestRoundTrip(unittest.TestCase):

    def setUp(self):
        os.environ["KMS_KEY_NAME"] = "projects/test/locations/global/keyRings/test/cryptoKeys/test"
        self.kms = _make_kms_mock()

    def test_cifrar_descifrar_str(self):
        plaintext = "Datos sensibles de cliente: Juan Pérez, $ 150.000 UYU"
        cifrado = cifrar(plaintext, "legajo-001", "uid-abc", kms_client=self.kms)
        resultado = descifrar(cifrado, "legajo-001", "uid-abc", kms_client=self.kms)
        self.assertEqual(resultado.decode("utf-8"), plaintext)

    def test_cifrar_descifrar_bytes(self):
        plaintext = b"\x00\x01\x02datos binarios\xff"
        cifrado = cifrar(plaintext, "legajo-002", "uid-xyz", kms_client=self.kms)
        resultado = descifrar(cifrado, "legajo-002", "uid-xyz", kms_client=self.kms)
        self.assertEqual(resultado, plaintext)

    def test_cifrar_descifrar_json(self):
        datos = {"montos_confirmados": [{"descripcion": "Sueldo", "monto": "5000", "moneda": "USD"}]}
        plaintext = json.dumps(datos, ensure_ascii=False)
        cifrado = cifrar(plaintext, "legajo-003", "uid-user", kms_client=self.kms)
        resultado = descifrar(cifrado, "legajo-003", "uid-user", kms_client=self.kms)
        recuperado = json.loads(resultado.decode("utf-8"))
        self.assertEqual(recuperado, datos)

    def test_output_tiene_campos_requeridos(self):
        cifrado = cifrar("test", "legajo-x", "uid-y", kms_client=self.kms)
        for campo in ("algoritmo", "kek_version", "encrypted_dek_b64", "nonce_b64", "ciphertext_b64"):
            self.assertIn(campo, cifrado, f"Campo requerido ausente: {campo}")
        self.assertEqual(cifrado["algoritmo"], "AES-256-GCM")

    def test_nonces_diferentes_en_cada_cifrado(self):
        """Cada llamada genera un nonce diferente — nunca reutiliza."""
        c1 = cifrar("mismo plaintext", "legajo-x", "uid-y", kms_client=self.kms)
        c2 = cifrar("mismo plaintext", "legajo-x", "uid-y", kms_client=self.kms)
        self.assertNotEqual(c1["nonce_b64"], c2["nonce_b64"])
        self.assertNotEqual(c1["ciphertext_b64"], c2["ciphertext_b64"])


class TestAADBinding(unittest.TestCase):
    """El AAD ata el ciphertext al legajo_id y owner_uid específicos."""

    def setUp(self):
        os.environ["KMS_KEY_NAME"] = "projects/test/locations/global/keyRings/test/cryptoKeys/test"
        self.kms = _make_kms_mock()

    def test_legajo_id_diferente_falla(self):
        cifrado = cifrar("datos", "legajo-real", "uid-real", kms_client=self.kms)
        with self.assertRaises(InvalidTag):
            descifrar(cifrado, "legajo-OTRO", "uid-real", kms_client=self.kms)

    def test_owner_uid_diferente_falla(self):
        cifrado = cifrar("datos", "legajo-real", "uid-real", kms_client=self.kms)
        with self.assertRaises(InvalidTag):
            descifrar(cifrado, "legajo-real", "uid-OTRO", kms_client=self.kms)

    def test_ciphertext_modificado_falla(self):
        from base64 import b64decode, b64encode
        cifrado = cifrar("datos sensibles", "legajo-x", "uid-y", kms_client=self.kms)
        # Flip un bit en el ciphertext
        ct_bytes = bytearray(b64decode(cifrado["ciphertext_b64"]))
        ct_bytes[0] ^= 0xFF
        cifrado_modificado = {**cifrado, "ciphertext_b64": b64encode(bytes(ct_bytes)).decode()}
        with self.assertRaises(InvalidTag):
            descifrar(cifrado_modificado, "legajo-x", "uid-y", kms_client=self.kms)


class TestKMSNotConfigured(unittest.TestCase):

    def test_sin_env_var_lanza_error(self):
        # Remover la variable si existe
        os.environ.pop("KMS_KEY_NAME", None)
        with self.assertRaises(KMSNotConfiguredError):
            cifrar("datos", "legajo-x", "uid-y")

    def test_env_var_vacia_lanza_error(self):
        os.environ["KMS_KEY_NAME"] = "   "   # solo espacios
        with self.assertRaises(KMSNotConfiguredError):
            cifrar("datos", "legajo-x", "uid-y")

    def tearDown(self):
        os.environ.pop("KMS_KEY_NAME", None)


if __name__ == "__main__":
    unittest.main()
