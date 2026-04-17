# 🔐 Performance Evaluation of Encryption Algorithms on Edge Devices

**AES-256-GCM · ChaCha20-Poly1305 · PRESENT · SPECK-64/128**

A comprehensive benchmarking system that simulates an edge computing environment and
compares four symmetric encryption algorithms across **encryption time, decryption time,
CPU usage, memory consumption, and throughput**.

---

## 📁 Project Structure

```
Distributed_Systems/
├── main.py               # CLI entry point — runs experiments
├── config.py             # Central configuration (sizes, iterations, paths)
├── data_generator.py     # Synthetic IoT sensor data generator
├── aes_module.py         # AES-256-GCM  (PyCryptodome)
├── chacha20_module.py    # ChaCha20-Poly1305  (PyCryptodome)
├── present_module.py     # PRESENT 80-bit  (pure Python, from spec)
├── speck_module.py       # SPECK-64/128  (pure Python, from NSA spec)
├── metrics.py            # Profiling utilities (time, CPU, memory, throughput)
├── edge_simulator.py     # Edge → Cloud pipeline simulator
├── visualization.py      # Graph generation (matplotlib)
├── requirements.txt      # Python dependencies
└── results/              # Auto-generated output
    ├── benchmark_results.csv
    ├── benchmark_results.json
    ├── experiment.log
    └── graphs/
        ├── encryption_time.png
        ├── decryption_time.png
        ├── cpu_usage.png
        ├── memory_usage.png
        ├── throughput.png
        └── summary_dashboard.png
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+

### Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

### Run the Benchmark

```bash
# Full benchmark (all algorithms, all data sizes, 5 iterations)
python main.py

# Quick test run
python main.py --sizes 1KB 10KB --iterations 1

# Custom configuration
python main.py --algorithms AES ChaCha20 --sizes 1KB 100KB --iterations 10

# Regenerate graphs from existing results
python main.py --graphs-only

# Run without graph generation
python main.py --no-graphs

# Custom output directory
python main.py --output results_v2
```

---

## 📊 Metrics Measured

| Metric | Description | Unit |
|--------|-------------|------|
| **Encryption Time** | Wall-clock time to encrypt the payload | ms |
| **Decryption Time** | Wall-clock time to decrypt + verify | ms |
| **CPU Usage** | Process CPU utilisation during operation | % |
| **Memory (Peak)** | Peak memory allocation via `tracemalloc` | KB |
| **Throughput** | Data processed per second | MB/s |

---

## 🧪 Algorithms

| Algorithm | Type | Key Size | Block Size | Library |
|-----------|------|----------|------------|---------|
| **AES-256-GCM** | Block cipher (AEAD) | 256 bits | 128 bits | PyCryptodome |
| **ChaCha20-Poly1305** | Stream cipher (AEAD) | 256 bits | — | PyCryptodome |
| **PRESENT** | Lightweight block cipher | 80 bits | 64 bits | Pure Python |
| **SPECK-64/128** | Lightweight ARX cipher | 128 bits | 64 bits | Pure Python |

---

## 📈 Data Sizes

The benchmark tests each algorithm against four representative IoT payload sizes:

- **1 KB** — Single sensor reading
- **10 KB** — Small batch of readings
- **100 KB** — Medium telemetry burst
- **1 MB** — Large aggregated payload

---

## 🖥️ CLI Reference

```
usage: main.py [-h] [--algorithms {AES,ChaCha20,PRESENT,SPECK} ...]
               [--sizes {1KB,10KB,100KB,1MB} ...] [--iterations N]
               [--output DIR] [--graphs-only] [--no-graphs]

Options:
  -a, --algorithms    Algorithms to benchmark (default: all four)
  -s, --sizes         Data sizes to test (default: 1KB 10KB 100KB 1MB)
  -n, --iterations    Repetitions per experiment (default: 5)
  -o, --output        Output directory (default: results)
  --graphs-only       Skip benchmarks; regenerate graphs from existing JSON
  --no-graphs         Run benchmarks but skip graph generation
```

---

## 📋 Output Files

| File | Format | Content |
|------|--------|---------|
| `benchmark_results.csv` | CSV | All measurements in tabular form |
| `benchmark_results.json` | JSON | Same data, structured for programmatic access |
| `experiment.log` | Text | Timestamped log of the entire experiment run |
| `graphs/*.png` | PNG | Six comparison charts (see below) |

### Generated Graphs

1. **Encryption Time** — Time vs Algorithm, grouped by data size
2. **Decryption Time** — Time vs Algorithm, grouped by data size
3. **CPU Usage** — CPU % vs Algorithm during encryption
4. **Memory Usage** — Peak memory vs Algorithm during encryption
5. **Throughput** — MB/s vs Algorithm, grouped by data size
6. **Summary Dashboard** — 2×3 panel combining all key metrics

---

## ⚙️ Configuration

Edit `config.py` to adjust:

```python
DATA_SIZES = {
    "1KB":   1024,
    "10KB":  10240,
    "100KB": 102400,
    "1MB":   1048576,
}
DEFAULT_ITERATIONS = 5
ALGORITHMS = ["AES", "ChaCha20", "PRESENT", "SPECK"]
```

---

## 🏆 Expected Findings

| Criterion | Best Candidate |
|-----------|---------------|
| **Fastest throughput** | AES (with AES-NI) / ChaCha20 (software-only) |
| **Lowest memory** | PRESENT / SPECK (lightweight designs) |
| **Best for ARM/RISC-V** | ChaCha20 (no hardware dependency) |
| **Ultra-constrained (RFID)** | PRESENT (minimal gate count) |

> **Note:** PRESENT and SPECK are implemented in pure Python for educational
> transparency. In production C/assembly, they would be orders of magnitude faster.

---

## 📄 License

This project is for academic and research purposes.
