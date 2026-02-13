"""Tests for decryption helper functions and mixin behavior."""

from __future__ import annotations

from types import SimpleNamespace

from mloader.manga_loader import decryption


class DummyDecryptor(decryption.DecryptionMixin):
    """Simple decryptor test double with an in-memory HTTP response."""

    def __init__(self, payload: bytes) -> None:
        """Store a fake session returning ``payload`` for any URL."""
        self.session = SimpleNamespace(get=lambda _url: SimpleNamespace(content=payload))


def test_convert_hex_to_bytes_and_xor_decrypt_roundtrip() -> None:
    """Verify XOR decryption restores the original plaintext bytes."""
    key = decryption._convert_hex_to_bytes("0f")
    encrypted = bytearray([0x41 ^ 0x0F, 0x42 ^ 0x0F])

    decrypted = decryption._xor_decrypt(encrypted, key)

    assert decrypted == bytearray(b"AB")


def test_fetch_encrypted_data_and_decrypt_image() -> None:
    """Verify mixin fetch and decrypt methods return the expected plaintext."""
    key_hex = "0f0f"
    original = bytearray(b"abc")
    encrypted = decryption._xor_decrypt(bytearray(original), bytes.fromhex(key_hex))

    decryptor = DummyDecryptor(bytes(encrypted))
    fetched = decryptor._fetch_encrypted_data("http://example")
    decrypted = decryptor._decrypt_image("http://example", key_hex)

    assert fetched == encrypted
    assert decrypted == original
