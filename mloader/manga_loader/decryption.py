"""Image decryption helpers used for encrypted page payloads."""

from __future__ import annotations


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
