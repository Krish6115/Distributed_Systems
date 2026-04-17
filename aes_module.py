"""
aes_module.py — AES‑256‑GCM encryption / decryption module.

Uses PyCryptodome's AES in GCM mode (authenticated encryption) which is
the gold standard for symmetric encryption on modern hardware.

GCM provides:
    • Confidentiality (AES‑CTR underneath)
    • Integrity & authenticity (GHASH tag)

Key  : 256 bits (32 bytes)
Nonce: 96 bits  (12 bytes, recommended for GCM)
Tag  : 128 bits (16 bytes)
"""

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
from typing import Tuple


# ── Key generation ──────────────────────────────────────────────────
def generate_key() -> bytes:
    """Return a fresh 256‑bit random key."""
    return get_random_bytes(32)


# ── Encryption ──────────────────────────────────────────────────────
def encrypt(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypt *plaintext* with AES‑256‑GCM.

    Returns
    -------
    (nonce, ciphertext, tag)
        All three are needed for decryption / verification.
    """
    nonce = get_random_bytes(12)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return nonce, ciphertext, tag


# ── Decryption ──────────────────────────────────────────────────────
def decrypt(nonce: bytes, ciphertext: bytes, tag: bytes, key: bytes) -> bytes:
    """
    Decrypt and verify an AES‑256‑GCM ciphertext.

    Raises
    ------
    ValueError
        If the tag verification fails (data was tampered with).
    """
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return plaintext


# ── Self‑test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    key = generate_key()
    msg = b"Hello from AES-256-GCM on the edge!"
    nonce, ct, tag = encrypt(msg, key)
    pt = decrypt(nonce, ct, tag, key)
    assert pt == msg, "Round‑trip failed!"
    print(f"[AES] OK  plaintext={pt}")
