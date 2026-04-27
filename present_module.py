"""
present_module.py — PRESENT ultra‑lightweight block cipher (80‑bit key).

PRESENT is an ISO/IEC 29192‑2 standardised lightweight cipher designed
for extremely constrained environments (RFID tags, smart cards).

    Block size : 64 bits  (8 bytes)
    Key size   : 80 bits  (10 bytes)
    Rounds     : 31
    Structure  : SPN (Substitution‑Permutation Network)

Reference: Bogdanov et al., "PRESENT: An Ultra‑Lightweight Block Cipher",
           CHES 2007.

This module implements the cipher from scratch following the specification,
then wraps it in ECB→CTR mode so it can encrypt arbitrary‑length data.
A simple HMAC‑SHA256 tag is appended for integrity verification.

NOTE: This is an *educational / benchmarking* implementation.
      Do NOT use it to protect production data.
"""

import os
import struct
import hashlib
import hmac
from typing import Tuple

# ═══════════════════════════════════════════════════════════════════
#  PRESENT primitives
# ═══════════════════════════════════════════════════════════════════

# 4‑bit S‑Box (from the PRESENT specification)
SBOX = [0xC, 0x5, 0x6, 0xB, 0x9, 0x0, 0xA, 0xD,
        0x3, 0xE, 0xF, 0x8, 0x4, 0x7, 0x1, 0x2]

SBOX_INV = [0] * 16
for _i, _v in enumerate(SBOX):
    SBOX_INV[_v] = _i

# Bit permutation table (64‑bit)
PBOX = [
    0, 16, 32, 48,  1, 17, 33, 49,
    2, 18, 34, 50,  3, 19, 35, 51,
    4, 20, 36, 52,  5, 21, 37, 53,
    6, 22, 38, 54,  7, 23, 39, 55,
    8, 24, 40, 56,  9, 25, 41, 57,
   10, 26, 42, 58, 11, 27, 43, 59,
   12, 28, 44, 60, 13, 29, 45, 61,
   14, 30, 46, 62, 15, 31, 47, 63,
]

PBOX_INV = [0] * 64
for _i, _v in enumerate(PBOX):
    PBOX_INV[_v] = _i


def _sbox_layer(state: int) -> int:
    """Apply the 4‑bit S‑box to every nibble of the 64‑bit state."""
    result = 0
    for i in range(16):
        nibble = (state >> (i * 4)) & 0xF
        result |= SBOX[nibble] << (i * 4)
    return result


def _sbox_layer_inv(state: int) -> int:
    """Inverse S‑box layer."""
    result = 0
    for i in range(16):
        nibble = (state >> (i * 4)) & 0xF
        result |= SBOX_INV[nibble] << (i * 4)
    return result


def _p_layer(state: int) -> int:
    """Bit permutation layer."""
    result = 0
    for i in range(64):
        if state & (1 << i):
            result |= 1 << PBOX[i]
    return result


def _p_layer_inv(state: int) -> int:
    """Inverse bit permutation."""
    result = 0
    for i in range(64):
        if state & (1 << i):
            result |= 1 << PBOX_INV[i]
    return result


def _generate_round_keys_80(key: int) -> list:
    """
    Generate 32 round keys from an 80‑bit master key.

    Key register is 80 bits wide.  After extracting the round key
    (bits 79..16) the register is updated:
        1. Rotate left by 61
        2. S‑box the top nibble
        3. XOR the round counter into bits 19..15
    """
    keys = []
    key_reg = key & ((1 << 80) - 1)

    for i in range(1, 33):
        # Round key = top 64 bits
        round_key = (key_reg >> 16) & 0xFFFFFFFFFFFFFFFF
        keys.append(round_key)

        # 1. Rotate left by 61 (equivalent to rotate right by 19 on 80 bits)
        key_reg = ((key_reg << 61) | (key_reg >> 19)) & ((1 << 80) - 1)

        # 2. S‑box on the top nibble (bits 79‑76)
        top_nibble = (key_reg >> 76) & 0xF
        key_reg = (key_reg & ~(0xF << 76)) | (SBOX[top_nibble] << 76)

        # 3. XOR round counter into bits 19..15
        key_reg ^= (i << 15)

    return keys


def _encrypt_block(block: int, round_keys: list) -> int:
    """Encrypt a single 64‑bit block."""
    state = block
    for i in range(31):
        state ^= round_keys[i]           # addRoundKey
        state = _sbox_layer(state)        # sBoxLayer
        state = _p_layer(state)           # pLayer
    state ^= round_keys[31]              # final addRoundKey
    return state


def _decrypt_block(block: int, round_keys: list) -> int:
    """Decrypt a single 64‑bit block."""
    state = block
    state ^= round_keys[31]
    for i in range(30, -1, -1):
        state = _p_layer_inv(state)
        state = _sbox_layer_inv(state)
        state ^= round_keys[i]
    return state


# ═══════════════════════════════════════════════════════════════════
#  CTR mode wrapper (arbitrary‑length data)
# ═══════════════════════════════════════════════════════════════════

def _int_to_bytes8(val: int) -> bytes:
    return val.to_bytes(8, "big")


def _bytes8_to_int(b: bytes) -> int:
    return int.from_bytes(b, "big")


def _ctr_process(data: bytes, round_keys: list, nonce: bytes) -> bytes:
    """Encrypt / decrypt *data* in CTR mode using PRESENT as the block cipher."""
    nonce_int = int.from_bytes(nonce, "big")  # 4 bytes → 32 bits
    nonce_shifted = (nonce_int << 32) & 0xFFFFFFFFFFFFFFFF
    
    out = bytearray()
    block_count = (len(data) + 7) // 8

    for ctr in range(block_count):
        # Counter block: upper 32 = nonce, lower 32 = counter
        counter_block = nonce_shifted | ctr
        keystream_block = _encrypt_block(counter_block, round_keys)
        ks_bytes = keystream_block.to_bytes(8, "big")

        start = ctr * 8
        end = start + 8
        chunk = data[start:end]
        # Direct generator XOR is slightly faster than byte-by-byte append
        out.extend(b ^ k for b, k in zip(chunk, ks_bytes))

    return bytes(out)


# ═══════════════════════════════════════════════════════════════════
#  Public API  (matches the interface of aes_module / chacha20_module)
# ═══════════════════════════════════════════════════════════════════

def generate_key() -> bytes:
    """Return a fresh 80‑bit (10‑byte) random key."""
    return os.urandom(10)


def encrypt(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Encrypt *plaintext* with PRESENT in CTR mode + HMAC‑SHA256 tag.

    Returns
    -------
    (nonce, ciphertext, tag)
    """
    key_int = int.from_bytes(key[:10], "big")
    round_keys = _generate_round_keys_80(key_int)

    nonce = os.urandom(4)  # 32‑bit nonce (upper half of 64‑bit counter block)
    ciphertext = _ctr_process(plaintext, round_keys, nonce)

    # Integrity tag (HMAC‑SHA256 keyed by the cipher key)
    tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()

    return nonce, ciphertext, tag


def decrypt(nonce: bytes, ciphertext: bytes, tag: bytes, key: bytes) -> bytes:
    """
    Decrypt a PRESENT‑CTR ciphertext and verify its HMAC tag.

    Raises
    ------
    ValueError
        If the HMAC tag verification fails.
    """
    # Verify integrity first
    expected_tag = hmac.new(key, nonce + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(tag, expected_tag):
        raise ValueError("PRESENT: HMAC tag verification failed — data may be corrupted.")

    key_int = int.from_bytes(key[:10], "big")
    round_keys = _generate_round_keys_80(key_int)
    plaintext = _ctr_process(ciphertext, round_keys, nonce)

    return plaintext


# ── Self‑test ───────────────────────────────────────────────────────
if __name__ == "__main__":
    # Block‑level round‑trip
    k = 0x00000000000000000000
    rk = _generate_round_keys_80(k)
    ct = _encrypt_block(0x0000000000000000, rk)
    pt = _decrypt_block(ct, rk)
    assert pt == 0x0000000000000000, f"Block round‑trip failed: {pt:#018x}"
    print(f"[PRESENT] block test OK  ct={ct:#018x}")

    # Full API round‑trip
    key = generate_key()
    msg = b"Hello from PRESENT cipher on the edge!"
    nonce, ct_bytes, tag = encrypt(msg, key)
    pt_bytes = decrypt(nonce, ct_bytes, tag, key)
    assert pt_bytes == msg, "API round‑trip failed!"
    print(f"[PRESENT] API test OK  plaintext={pt_bytes}")
