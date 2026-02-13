from types import SimpleNamespace

from mloader.manga_loader import decryption


class DummyDecryptor(decryption.DecryptionMixin):
    def __init__(self, payload: bytes):
        self.session = SimpleNamespace(get=lambda _url: SimpleNamespace(content=payload))


def test_convert_hex_to_bytes_and_xor_decrypt_roundtrip():
    key = decryption._convert_hex_to_bytes("0f")
    encrypted = bytearray([0x41 ^ 0x0F, 0x42 ^ 0x0F])

    decrypted = decryption._xor_decrypt(encrypted, key)

    assert decrypted == bytearray(b"AB")


def test_fetch_encrypted_data_and_decrypt_image():
    key_hex = "0f0f"
    original = bytearray(b"abc")
    encrypted = decryption._xor_decrypt(bytearray(original), bytes.fromhex(key_hex))

    decryptor = DummyDecryptor(bytes(encrypted))
    fetched = decryptor._fetch_encrypted_data("http://example")
    decrypted = decryptor._decrypt_image("http://example", key_hex)

    assert fetched == encrypted
    assert decrypted == original
