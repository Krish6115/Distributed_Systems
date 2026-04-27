"""
visualization.py — Graph generation for encryption benchmark results.

Reads the structured CSV/JSON results produced by main.py and generates
publication-quality comparison charts:

    1. Encryption Time vs Algorithm (grouped by data size)
    2. Decryption Time vs Algorithm
    3. CPU Usage vs Algorithm
    4. Memory Usage vs Algorithm
    5. Throughput vs Algorithm
    6. Combined summary dashboard

All graphs are saved to the results/graphs/ directory.

NOTE: Metrics with huge dynamic range (e.g. AES ~1 ms vs PRESENT ~37 000 ms)
use a **logarithmic Y-axis** and **value labels** on every bar so that no
algorithm is invisible regardless of scale differences.
"""

import os
import json
import csv
from collections import defaultdict
from typing import List, Dict

import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

from config import GRAPHS_DIR, RESULTS_JSON, ALGORITHMS

# -- Style constants ----------------------------------------------------------
COLORS = {
    "AES":      "#2563eb",   # blue
    "ChaCha20": "#16a34a",   # green
    "PRESENT":  "#dc2626",   # red
    "SPECK":    "#9333ea",   # purple
}
BAR_WIDTH = 0.18
FONT = {"family": "sans-serif", "size": 11}
matplotlib.rc("font", **FONT)


def _load_results(path: str = RESULTS_JSON) -> List[Dict]:
    """Load benchmark results from JSON."""
    with open(path, "r") as f:
        return json.load(f)


def _aggregate(results: List[Dict], operation: str, metric: str):
    """
    Return {algo: {size_label: avg_metric_value}} for the given
    operation ("encrypt" / "decrypt") and metric key.
    """
    sums = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r["operation"] == operation:
            sums[r["algorithm"]][r["data_size_label"]].append(r[metric])

    agg = {}
    for algo, sizes in sums.items():
        agg[algo] = {}
        for size, vals in sizes.items():
            agg[algo][size] = sum(vals) / len(vals)
    return agg


def _needs_log_scale(data, size_order):
    """Return True if the value range across algorithms is > 100x."""
    all_vals = []
    for algo_vals in data.values():
        for s in size_order:
            v = algo_vals.get(s, 0)
            if v > 0:
                all_vals.append(v)
    if not all_vals:
        return False
    return max(all_vals) / max(min(all_vals), 1e-12) > 100


def _add_bar_labels(ax, bars, fontsize=8, use_log=False):
    """Add value labels on top of each bar so every value is visible."""
    for bar in bars:
        h = bar.get_height()
        if h <= 0:
            continue
        # Format: use scientific for very small, compact for large
        if h >= 1000:
            label = f"{h:,.0f}"
        elif h >= 1:
            label = f"{h:.2f}"
        elif h >= 0.001:
            label = f"{h:.4f}"
        else:
            label = f"{h:.2e}"
        ax.text(
            bar.get_x() + bar.get_width() / 2, h, label,
            ha="center", va="bottom", fontsize=fontsize,
            fontweight="bold", rotation=45,
        )


def _plot_grouped_bar(
    data,
    title: str,
    ylabel: str,
    filename: str,
    size_order: list,
):
    """
    Generic grouped bar chart — one group per data size,
    one bar per algorithm.

    Automatically uses log scale when the value range across
    algorithms exceeds 100x, and adds numeric labels on every bar.
    """
    fig, ax = plt.subplots(figsize=(10, 6))
    n_algorithms = len(ALGORITHMS)
    x_indices = range(len(size_order))
    use_log = _needs_log_scale(data, size_order)

    all_bars = []
    for i, algo in enumerate(ALGORITHMS):
        if algo not in data:
            continue
        values = [data[algo].get(s, 0) for s in size_order]
        offsets = [x + i * BAR_WIDTH for x in x_indices]
        bars = ax.bar(
            offsets, values,
            width=BAR_WIDTH,
            label=algo,
            color=COLORS.get(algo, "#888888"),
            edgecolor="white",
            linewidth=0.5,
        )
        all_bars.extend(bars)

    # Log scale for metrics with huge dynamic range
    if use_log:
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(ticker.ScalarFormatter())
        ax.yaxis.get_major_formatter().set_scientific(False)

    # Value labels on every bar
    _add_bar_labels(ax, all_bars, fontsize=7, use_log=use_log)

    ax.set_xlabel("Data Size", fontweight="bold")
    ax.set_ylabel(ylabel, fontweight="bold")
    ax.set_title(title, fontweight="bold", fontsize=14)
    ax.set_xticks([x + BAR_WIDTH * (n_algorithms - 1) / 2 for x in x_indices])
    ax.set_xticklabels(size_order)
    ax.legend(framealpha=0.9)
    ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()

    os.makedirs(GRAPHS_DIR, exist_ok=True)
    fig.savefig(os.path.join(GRAPHS_DIR, filename), dpi=150)
    plt.close(fig)
    print(f"  [OK] saved {filename}")


def plot_encryption_time(results):
    data = _aggregate(results, "encrypt", "elapsed_time_ms")
    sizes = list(list(data.values())[0].keys()) if data else []
    _plot_grouped_bar(
        data, "Encryption Time by Algorithm & Data Size",
        "Time (ms)", "encryption_time.png", sizes,
    )


def plot_decryption_time(results):
    data = _aggregate(results, "decrypt", "elapsed_time_ms")
    sizes = list(list(data.values())[0].keys()) if data else []
    _plot_grouped_bar(
        data, "Decryption Time by Algorithm & Data Size",
        "Time (ms)", "decryption_time.png", sizes,
    )


def plot_cpu_usage(results):
    data = _aggregate(results, "encrypt", "cpu_percent")
    sizes = list(list(data.values())[0].keys()) if data else []
    _plot_grouped_bar(
        data, "CPU Usage During Encryption by Algorithm",
        "CPU (%)", "cpu_usage.png", sizes,
    )


def plot_memory_usage(results):
    data = _aggregate(results, "encrypt", "memory_peak_kb")
    sizes = list(list(data.values())[0].keys()) if data else []
    _plot_grouped_bar(
        data, "Peak Memory During Encryption by Algorithm",
        "Memory (KB)", "memory_usage.png", sizes,
    )


def plot_throughput(results):
    data = _aggregate(results, "encrypt", "throughput_mbps")
    sizes = list(list(data.values())[0].keys()) if data else []
    _plot_grouped_bar(
        data, "Encryption Throughput by Algorithm & Data Size",
        "Throughput (MB/s)", "throughput.png", sizes,
    )


def plot_summary_dashboard(results):
    """
    Create a 2x3 dashboard summarising all key metrics in one figure.
    Uses log scale where needed so no algorithm bar disappears.
    """
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    fig.suptitle(
        "Encryption Algorithm Performance Dashboard",
        fontweight="bold", fontsize=16, y=0.98,
    )

    metrics = [
        ("encrypt", "elapsed_time_ms", "Encrypt Time (ms)"),
        ("decrypt", "elapsed_time_ms", "Decrypt Time (ms)"),
        ("encrypt", "cpu_percent",     "CPU % (Encrypt)"),
        ("encrypt", "memory_peak_kb",  "Memory KB (Encrypt)"),
        ("encrypt", "throughput_mbps", "Throughput MB/s (Encrypt)"),
    ]

    for idx, (op, metric, label) in enumerate(metrics):
        ax = axes[idx // 3][idx % 3]
        data = _aggregate(results, op, metric)
        sizes = list(list(data.values())[0].keys()) if data else []
        n = len(ALGORITHMS)
        x = range(len(sizes))
        use_log = _needs_log_scale(data, sizes)

        all_bars = []
        for i, algo in enumerate(ALGORITHMS):
            if algo not in data:
                continue
            vals = [data[algo].get(s, 0) for s in sizes]
            offsets = [xi + i * BAR_WIDTH for xi in x]
            bars = ax.bar(offsets, vals, BAR_WIDTH,
                   label=algo, color=COLORS.get(algo, "#888"),
                   edgecolor="white", linewidth=0.4)
            all_bars.extend(bars)

        if use_log:
            ax.set_yscale("log")

        _add_bar_labels(ax, all_bars, fontsize=6, use_log=use_log)

        ax.set_title(label, fontsize=11, fontweight="bold")
        ax.set_xticks([xi + BAR_WIDTH * (n - 1) / 2 for xi in x])
        ax.set_xticklabels(sizes, fontsize=9)
        ax.grid(axis="y", alpha=0.25)

    # Hide the last (empty) subplot
    axes[1][2].axis("off")

    # Single legend at bottom
    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower right",
               ncol=4, fontsize=11, framealpha=0.9,
               bbox_to_anchor=(0.95, 0.08))

    fig.tight_layout(rect=[0, 0.06, 1, 0.95])
    os.makedirs(GRAPHS_DIR, exist_ok=True)
    path = os.path.join(GRAPHS_DIR, "summary_dashboard.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  [OK] saved summary_dashboard.png")


def generate_all_graphs(results=None):
    """Generate the full suite of comparison graphs."""
    if results is None:
        results = _load_results()

    print("\n[GRAPHS] Generating comparison graphs...")
    plot_encryption_time(results)
    plot_decryption_time(results)
    plot_cpu_usage(results)
    plot_memory_usage(results)
    plot_throughput(results)
    plot_summary_dashboard(results)
    print(f"   All graphs saved to {GRAPHS_DIR}/\n")


if __name__ == "__main__":
    generate_all_graphs()
