"""
chacha20_module.py — ChaCha20‑Poly1305 encryption / decryption module.

Uses PyCryptodome's ChaCha20‑Poly1305 AEAD cipher, which provides:
    • Confidentiality   (ChaCha20 stream cipher)
    • Integrity & auth  (Poly1305 MAC)

Key  : 256 bits  (32 bytes)
Nonce: 96 bits   (12 bytes — RFC 7539 variant used by PyCryptodome)
Tag  : 128 bits  (16 bytes)

ChaCha20 is particularly attractive for edge / IoT because it does NOT
need AES‑NI hardware; it achieves high throughput in pure software on
ARM Cortex‑M, RISC‑V, and other resource‑constrained cores.
"""

from Crypto.Cipher import ChaCha20_Poly1305
from Crypto.Random import get_random_bytes
from typing import Tuple


# ── Key generation ──────────────────────────────────────────────────
def generate_key() -> bytes:
    """Return a fresh 256‑bit random key."""
    return get_random_bytes(32)


# ── Encryption ──────────────────────────────────────────────────────
def encrypt(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypt *plaintext* with ChaCha20‑Poly1305.

    Returns
    -------
    (nonce, ciphertext, tag)
    """
    nonce = get_random_bytes(12)
    cipher = ChaCha20_Poly1305.new(key=key, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return nonce, ciphertext, tag


# ── Decryption ──────────────────────────────────────────────────────
def decrypt(nonce: bytes, ciphertext: bytes, tag: bytes, key: bytes) -> bytes:
    """
    Decrypt and verify a ChaCha20‑Poly1305 ciphertext.

    Raises
    ------
    ValueError
        If the Poly1305 tag verification fails.
    """
    cipher = ChaCha20_Poly1305.new(key=key, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return plaintext


# ── Self‑test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    key = generate_key()
    msg = b"Hello from ChaCha20-Poly1305 on the edge!"
    nonce, ct, tag = encrypt(msg, key)
    pt = decrypt(nonce, ct, tag, key)
    assert pt == msg, "Round‑trip failed!"
    print(f"[ChaCha20] OK  plaintext={pt}")
