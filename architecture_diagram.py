"""
architecture_diagram.py — Generate a visual architecture diagram of the
distributed edge computing simulation.

Uses matplotlib patches and annotations (no extra dependencies) to produce
a publication-ready system diagram showing:
    • Edge nodes (N devices in the field)
    • Network links (encrypted data transmission)
    • Aggregator node (fog/cloud)
    • Metrics collection
"""

import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np


def generate_architecture_diagram(
    output_dir: str = "results/distributed_graphs",
    n_nodes_shown: int = 6,
):
    """
    Create and save the distributed system architecture diagram.

    Parameters
    ----------
    output_dir : str
        Directory to save the PNG.
    n_nodes_shown : int
        Number of edge nodes to display (visual, not functional).
    """
    fig, ax = plt.subplots(figsize=(16, 10))
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.axis("off")

    # ── Background: deployment area ──
    area_box = FancyBboxPatch(
        (0.5, 0.5), 15, 9,
        boxstyle="round,pad=0.3",
        facecolor="#f0f9ff", edgecolor="#94a3b8",
        linewidth=2, linestyle="--",
    )
    ax.add_patch(area_box)
    ax.text(
        8, 9.6, "Deployment Area  (A km²)",
        ha="center", fontsize=14, fontweight="bold", color="#475569",
        style="italic",
    )

    # ── Title ──
    ax.text(
        8, 9.15, "Distributed Edge Computing — Encryption Benchmark Architecture",
        ha="center", fontsize=16, fontweight="bold", color="#1e293b",
    )

    # ── Scaling formula ──
    ax.text(
        8, 8.5, "N = A × D    (Nodes = Area × Density)",
        ha="center", fontsize=12, fontweight="bold", color="#2563eb",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#dbeafe", edgecolor="#2563eb", alpha=0.9),
    )

    # ── Edge nodes ──
    node_colors = ["#2563eb", "#16a34a", "#dc2626", "#9333ea", "#ea580c", "#0891b2"]
    algo_labels = ["AES", "ChaCha20", "PRESENT", "SPECK", "AES", "ChaCha20"]
    node_y = 6.5
    node_spacing = 2.2
    start_x = 8 - (n_nodes_shown - 1) * node_spacing / 2

    for i in range(n_nodes_shown):
        x = start_x + i * node_spacing
        color = node_colors[i % len(node_colors)]
        algo = algo_labels[i % len(algo_labels)]

        # Node box
        node_box = FancyBboxPatch(
            (x - 0.7, node_y - 0.5), 1.4, 1.2,
            boxstyle="round,pad=0.15",
            facecolor=color, edgecolor="white",
            linewidth=2, alpha=0.85,
        )
        ax.add_patch(node_box)

        # Node label
        ax.text(x, node_y + 0.3, f"Edge {i+1}", ha="center", fontsize=9,
                fontweight="bold", color="white")
        ax.text(x, node_y - 0.05, algo, ha="center", fontsize=8, color="white")

        # IoT sensor icon (small circle)
        sensor = plt.Circle((x, node_y + 0.75), 0.12, color=color, alpha=0.5)
        ax.add_patch(sensor)
        ax.text(x, node_y + 0.75, "[S]", ha="center", fontsize=7)

        # Arrow from node to aggregator
        ax.annotate(
            "", xy=(8, 4.2), xytext=(x, node_y - 0.55),
            arrowprops=dict(
                arrowstyle="-|>", color=color, lw=1.5,
                connectionstyle="arc3,rad=0.1", alpha=0.6,
            ),
        )

    # "..." to indicate more nodes
    ax.text(8, 5.55, "· · ·  Encrypted Data (N channels)  · · ·",
            ha="center", fontsize=10, color="#64748b", style="italic")

    # ── Aggregator node ──
    agg_box = FancyBboxPatch(
        (5.5, 2.8), 5, 1.5,
        boxstyle="round,pad=0.2",
        facecolor="#1e293b", edgecolor="#334155",
        linewidth=2,
    )
    ax.add_patch(agg_box)

    ax.text(8, 3.95, "[Cloud]  Aggregator Node  (Fog / Cloud)", ha="center",
            fontsize=13, fontweight="bold", color="white")
    ax.text(8, 3.45, "• Decrypt all payloads    • Verify SHA-256 integrity",
            ha="center", fontsize=9, color="#94a3b8")
    ax.text(8, 3.05, "• Collect system metrics   • Compute scalability",
            ha="center", fontsize=9, color="#94a3b8")

    # ── Metrics output ──
    metrics_box = FancyBboxPatch(
        (5.5, 1.0), 5, 1.2,
        boxstyle="round,pad=0.2",
        facecolor="#fef3c7", edgecolor="#f59e0b",
        linewidth=2,
    )
    ax.add_patch(metrics_box)

    ax.text(8, 1.9, "[Metrics]  System Metrics Output", ha="center",
            fontsize=12, fontweight="bold", color="#92400e")
    ax.text(8, 1.4, "Throughput  |  Latency  |  CPU Usage  |  Scalability Factor  |  Load Balance",
            ha="center", fontsize=9, color="#a16207")

    # Arrow from aggregator to metrics
    ax.annotate(
        "", xy=(8, 2.2), xytext=(8, 2.75),
        arrowprops=dict(arrowstyle="-|>", color="#f59e0b", lw=2),
    )

    # ── Legend ──
    legend_elements = [
        mpatches.Patch(color="#2563eb", label="AES-256-GCM"),
        mpatches.Patch(color="#16a34a", label="ChaCha20-Poly1305"),
        mpatches.Patch(color="#dc2626", label="PRESENT-80"),
        mpatches.Patch(color="#9333ea", label="SPECK-64/128"),
    ]
    ax.legend(
        handles=legend_elements, loc="lower left",
        fontsize=10, framealpha=0.9, title="Encryption Algorithms",
        title_fontsize=11, bbox_to_anchor=(0.02, 0.02),
    )

    fig.tight_layout()
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, "architecture_diagram.png")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] saved architecture_diagram.png -> {path}")
    return path


if __name__ == "__main__":
    generate_architecture_diagram()
