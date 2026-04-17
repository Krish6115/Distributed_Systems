"""
data_generator.py — Synthetic IoT data generator for edge‑device benchmarks.

Produces JSON‑formatted sensor payloads (temperature, humidity, pressure,
light, and generic sensor readings) that are representative of real
IoT telemetry streams.  The generator pads or repeats records until the
requested byte‑size is reached, which gives the encryption modules
realistic, structured plaintext to work with.
"""

import json
import random
import time
from typing import Dict


def _generate_single_reading() -> Dict:
    """Return one synthetic IoT sensor reading."""
    return {
        "timestamp": time.time() + random.uniform(0, 1000),
        "device_id": f"edge-{random.randint(1000, 9999)}",
        "temperature_c": round(random.uniform(-10.0, 50.0), 2),
        "humidity_pct": round(random.uniform(10.0, 95.0), 2),
        "pressure_hpa": round(random.uniform(980.0, 1050.0), 2),
        "light_lux": round(random.uniform(0.0, 100000.0), 2),
        "sensor_voltage": round(random.uniform(2.8, 3.6), 3),
        "status": random.choice(["OK", "WARN", "CRITICAL"]),
    }


def generate_iot_data(target_bytes: int) -> bytes:
    """
    Generate synthetic IoT JSON data of approximately *target_bytes* size.

    Strategy:
        1. Build individual sensor records.
        2. Accumulate them into a list until the serialised JSON
           meets or exceeds the requested size.
        3. Return the UTF‑8 encoded bytes of the JSON array.

    Parameters
    ----------
    target_bytes : int
        Desired payload size in bytes.

    Returns
    -------
    bytes
        UTF‑8 encoded JSON array of sensor readings.
    """
    records = []
    current_size = 2  # account for '[]' wrapper

    while current_size < target_bytes:
        record = _generate_single_reading()
        record_json = json.dumps(record)
        current_size += len(record_json) + 2  # +2 for ', ' separator
        records.append(record)

    payload = json.dumps(records, indent=None, separators=(",", ":"))
    payload_bytes = payload.encode("utf-8")

    # Trim or pad to get close to target size
    if len(payload_bytes) > target_bytes:
        payload_bytes = payload_bytes[:target_bytes]
    elif len(payload_bytes) < target_bytes:
        padding = b"\x00" * (target_bytes - len(payload_bytes))
        payload_bytes += padding

    return payload_bytes


if __name__ == "__main__":
    # Quick self‑test
    for label, size in [("1KB", 1024), ("10KB", 10240)]:
        data = generate_iot_data(size)
        print(f"[{label}] requested={size}B  actual={len(data)}B  "
              f"preview={data[:80]}...")
