"""Tests for decryption helper functions."""

from __future__ import annotations

from mloader.manga_loader import decryption


def test_convert_hex_to_bytes_and_xor_decrypt_roundtrip() -> None:
    """Verify XOR decryption restores the original plaintext bytes."""
    key = decryption._convert_hex_to_bytes("0f")
    encrypted = bytearray([0x41 ^ 0x0F, 0x42 ^ 0x0F])

    decrypted = decryption._xor_decrypt(encrypted, key)

    assert decrypted == bytearray(b"AB")


def test_xor_decrypt_accepts_repeating_key() -> None:
    """Verify XOR decryption supports keys shorter than the payload."""
    key_hex = "0f0f"
    original = bytearray(b"abc")
    encrypted = decryption._xor_decrypt(bytearray(original), bytes.fromhex(key_hex))

    decrypted = decryption._xor_decrypt(encrypted, decryption._convert_hex_to_bytes(key_hex))

    assert decrypted == original
