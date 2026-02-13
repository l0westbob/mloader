"""Image decryption helpers used for encrypted page payloads."""

from __future__ import annotations

from mloader.types import SessionLike

def _convert_hex_to_bytes(hex_str: str) -> bytes:
    """
    Convert a hexadecimal string to bytes.
    """
    return bytes.fromhex(hex_str)


def _xor_decrypt(data: bytearray, key: bytes) -> bytearray:
    """
    Decrypt data using XOR with a repeating key.
    """
    key_length = len(key)
    for index in range(len(data)):
        data[index] ^= key[index % key_length]
    return data


class DecryptionMixin:
    """Provide image retrieval and XOR decryption behavior."""

    session: SessionLike
    request_timeout: tuple[float, float]

    def _decrypt_image(self, url: str, encryption_hex: str) -> bytearray:
        """
        Retrieve and decrypt an image using XOR decryption with a repeating key.
        """
        encrypted_data = self._fetch_encrypted_data(url)
        encryption_key = _convert_hex_to_bytes(encryption_hex)
        return _xor_decrypt(encrypted_data, encryption_key)

    def _fetch_encrypted_data(self, url: str) -> bytearray:
        """
        Fetch encrypted image data from the provided URL.
        """
        response = self.session.get(url, timeout=self.request_timeout)
        response.raise_for_status()
        return bytearray(response.content)
