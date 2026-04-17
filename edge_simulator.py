"""
edge_simulator.py — Simulates an edge‑device encryption pipeline.

Models the full data lifecycle on a resource‑constrained edge node:

    1. Generate IoT sensor data
    2. Encrypt at the edge
    3. (Simulated) transmit to a cloud/fog node
    4. Decrypt and verify integrity

This module ties together the data generator and any encryption module
to provide a single callable pipeline for the benchmark harness.
"""

import time
import hashlib
from typing import Tuple, Dict, Any

from data_generator import generate_iot_data


def edge_pipeline(
    encrypt_fn,
    decrypt_fn,
    key: bytes,
    data: bytes,
) -> Dict[str, Any]:
    """
    Run one full edge‑to‑cloud encrypt→transmit→decrypt cycle.

    Parameters
    ----------
    encrypt_fn : callable(plaintext, key) → (nonce, ciphertext, tag)
    decrypt_fn : callable(nonce, ciphertext, tag, key) → plaintext
    key        : bytes — symmetric key
    data       : bytes — plaintext IoT payload

    Returns
    -------
    dict with:
        original_hash   — SHA‑256 of the original plaintext
        decrypted_hash  — SHA‑256 of the decrypted output
        integrity_ok    — bool, True if hashes match
        ciphertext_size — int, byte length of the ciphertext
    """
    # 1. Compute original hash for integrity check
    original_hash = hashlib.sha256(data).hexdigest()

    # 2. Encrypt at the edge
    nonce, ciphertext, tag = encrypt_fn(data, key)

    # 3. Simulated network transmission delay (optional)
    #    time.sleep(0.001)   # uncomment to model latency

    # 4. Decrypt at receiver
    plaintext = decrypt_fn(nonce, ciphertext, tag, key)

    # 5. Verify integrity
    decrypted_hash = hashlib.sha256(plaintext).hexdigest()

    return {
        "original_hash":   original_hash,
        "decrypted_hash":  decrypted_hash,
        "integrity_ok":    original_hash == decrypted_hash,
        "ciphertext_size": len(ciphertext),
    }
