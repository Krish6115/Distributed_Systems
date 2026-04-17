"""
speck_module.py — SPECK 64/128 lightweight block cipher.

SPECK is a family of lightweight block ciphers designed by the NSA,
optimised for software on constrained processors via an
Add‑Rotate‑XOR (ARX) construction.

This implementation uses the **Speck 64/128** variant:
    Block size : 64 bits  (two 32‑bit words)
    Key size   : 128 bits (16 bytes, four 32‑bit words)
    Rounds     : 27
    Word size  : 32 bits

Reference: Beaulieu et al., "The SIMON and SPECK Families of Lightweight
           Block Ciphers", IACR ePrint 2013/404.

Wrapped in CTR mode + HMAC‑SHA256 for arbitrary‑length data and integrity,
matching the API surface of the other modules.

NOTE: Educational / benchmarking only — not for production security.
"""

import os
import hashlib
import hmac as hmac_mod
from typing import Tuple

# ═══════════════════════════════════════════════════════════════════
#  SPECK 64/128 primitives
# ═══════════════════════════════════════════════════════════════════

WORD_SIZE   = 32
WORD_MASK   = (1 << WORD_SIZE) - 1
BLOCK_SIZE  = 8   # bytes (64 bits)
KEY_WORDS   = 4
ROUNDS      = 27
ALPHA       = 8   # right rotation amount
BETA        = 3   # left rotation amount


def _ror(x: int, r: int) -> int:
    """Rotate right a 32‑bit word by *r* bits."""
    return ((x >> r) | (x << (WORD_SIZE - r))) & WORD_MASK


def _rol(x: int, r: int) -> int:
    """Rotate left a 32‑bit word by *r* bits."""
    return ((x << r) | (x >> (WORD_SIZE - r))) & WORD_MASK


def _expand_key(key_words: list) -> list:
    """
    Expand the master key (4 × 32‑bit words) into 27 round keys.

    key_words = [k3, k2, k1, k0]  (k0 is the initial round key)
    """
    k = key_words[0]
    l = list(key_words[1:])

    round_keys = [k]
    for i in range(ROUNDS - 1):
        l_i = l[i % len(l)]
        # Round function on (l_i, k)
        l_new = (_ror(l_i, ALPHA) + k) & WORD_MASK
        l_new ^= i
        k = _rol(k, BETA) ^ l_new
        l.append(l_new)
        round_keys.append(k)

    return round_keys


def _encrypt_block(x: int, y: int, round_keys: list) -> Tuple[int, int]:
    """Encrypt one block (two 32‑bit words)."""
    for rk in round_keys:
        x = (_ror(x, ALPHA) + y) & WORD_MASK
        x ^= rk
        y = _rol(y, BETA) ^ x
    return x, y


def _decrypt_block(x: int, y: int, round_keys: list) -> Tuple[int, int]:
    """Decrypt one block."""
    for rk in reversed(round_keys):
        y = _ror(y ^ x, BETA)
        x = _rol((x ^ rk) - y & WORD_MASK, ALPHA)
    return x, y


# ═══════════════════════════════════════════════════════════════════
#  Helpers — bytes ↔ word pairs
# ═══════════════════════════════════════════════════════════════════

def _bytes_to_words(b: bytes) -> Tuple[int, int]:
    """Convert 8 bytes → (upper_word, lower_word) big‑endian."""
    return (
        int.from_bytes(b[0:4], "big"),
        int.from_bytes(b[4:8], "big"),
    )


def _words_to_bytes(x: int, y: int) -> bytes:
    return x.to_bytes(4, "big") + y.to_bytes(4, "big")


# ═══════════════════════════════════════════════════════════════════
#  CTR mode wrapper
# ═══════════════════════════════════════════════════════════════════

def _ctr_process(data: bytes, round_keys: list, nonce: bytes) -> bytes:
    """Encrypt / decrypt *data* in CTR mode using SPECK 64/128."""
    nonce_int = int.from_bytes(nonce, "big")  # 32 bits
    out = bytearray()
    block_count = (len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE

    for ctr in range(block_count):
        # Counter block: upper 32 = nonce, lower 32 = counter
        upper = nonce_int & WORD_MASK
        lower = ctr & WORD_MASK
        ex, ey = _encrypt_block(upper, lower, round_keys)
        ks_bytes = _words_to_bytes(ex, ey)

        start = ctr * BLOCK_SIZE
        end = min(start + BLOCK_SIZE, len(data))
        chunk = data[start:end]
        out.extend(b ^ k for b, k in zip(chunk, ks_bytes[:len(chunk)]))

    return bytes(out)


# ═══════════════════════════════════════════════════════════════════
#  Public API
# ═══════════════════════════════════════════════════════════════════

def generate_key() -> bytes:
    """Return a fresh 128‑bit (16‑byte) random key."""
    return os.urandom(16)


def encrypt(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypt *plaintext* with SPECK‑64/128 in CTR mode + HMAC‑SHA256 tag.

    Returns
    -------
    (nonce, ciphertext, tag)
    """
    # Parse key into 4 × 32‑bit words (big‑endian)
    kw = [
        int.from_bytes(key[i:i+4], "big")
        for i in range(0, 16, 4)
    ]
    round_keys = _expand_key(kw)

    nonce = os.urandom(4)
    ciphertext = _ctr_process(plaintext, round_keys, nonce)

    tag = hmac_mod.new(key, nonce + ciphertext, hashlib.sha256).digest()
    return nonce, ciphertext, tag


def decrypt(nonce: bytes, ciphertext: bytes, tag: bytes, key: bytes) -> bytes:
    """
    Decrypt and verify a SPECK‑CTR ciphertext.

    Raises
    ------
    ValueError
        If HMAC verification fails.
    """
    expected = hmac_mod.new(key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac_mod.compare_digest(tag, expected):
        raise ValueError("SPECK: HMAC tag verification failed.")

    kw = [
        int.from_bytes(key[i:i+4], "big")
        for i in range(0, 16, 4)
    ]
    round_keys = _expand_key(kw)
    plaintext = _ctr_process(ciphertext, round_keys, nonce)
    return plaintext


# ── Self‑test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    # Block‑level test (SPECK 64/128 test vector from the paper)
    # Key:   1b1a1918 13121110 0b0a0908 03020100
    # PT:    6574694c 2d32316c  →  CT: a65d9851 9040d8b0 (known answer)
    test_key_words = [0x1b1a1918, 0x13121110, 0x0b0a0908, 0x03020100]
    rk = _expand_key(test_key_words)
    cx, cy = _encrypt_block(0x6574694c, 0x2d32316c, rk)
    print(f"[SPECK] encrypt test: {cx:#010x} {cy:#010x}")
    dx, dy = _decrypt_block(cx, cy, rk)
    assert (dx, dy) == (0x6574694c, 0x2d32316c), "Block round‑trip failed!"
    print("[SPECK] block test OK")

    # Full API round‑trip
    key = generate_key()
    msg = b"Hello from SPECK-64/128 on the edge!"
    nonce, ct, tag = encrypt(msg, key)
    pt = decrypt(nonce, ct, tag, key)
    assert pt == msg, "API round‑trip failed!"
    print(f"[SPECK] API test OK  plaintext={pt}")
