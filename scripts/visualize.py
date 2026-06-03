"""
Visualization script for neoantigen screening results.

Usage:
    python scripts/visualize.py                          # auto-find latest results
    python scripts/visualize.py data/output/reports/xxx_results.json

Outputs (saved to docs/figures/):
    01_pipeline_flow.png       -- 4-step pipeline flowchart
    02_composite_scores.png    -- top candidates ranked by composite score
    03_ic50_rank_scatter.png   -- IC50 vs %Rank scatter plot
    04_metrics_heatmap.png     -- multi-metric heatmap
    05_agent_advantage.png     -- agent vs manual comparison table
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

ROOT = Path(__file__).parent.parent
FIGURES_DIR = ROOT / "docs" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family":       "DejaVu Sans",
    "axes.spines.top":   False,
    "axes.spines.right": False,
    "figure.dpi":        150,
})

GENE_COLORS = {
    "KRAS":   "#E63946",
    "TP53":   "#457B9D",
    "BRAF":   "#2A9D8F",
    "EGFR":   "#E9C46A",
    "PIK3CA": "#F4A261",
}
DEFAULT_COLOR = "#A8DADC"


# ── 1. Pipeline flowchart ─────────────────────────────────────────────────────

def plot_pipeline(out: Path):
    fig, ax = plt.subplots(figsize=(14, 4))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 4)
    ax.axis("off")

    steps = [
        ("Input\nHLA + Mutations",    "#4A90D9", 0.6),
        ("Generate\n9-mer Candidates", "#5BA85A", 2.4),
        ("Deep Learning\nddG Scoring", "#E87722", 4.7),
        ("MCMC\nOptimization",         "#9B59B6", 7.0),
        ("HLA Binding\nValidation",    "#E74C3C", 9.3),
        ("Top-10\nReport",             "#1ABC9C", 11.6),
    ]

    subtitles = [
        "",
        "AttABseq\nModel",
        "ImmuneAI\nScreener",
        "mhcflurry\nIC50 / %Rank",
        "",
        "",
    ]

    box_w, box_h = 1.7, 1.2
    y_center = 2.0

    for i, ((label, color, x), sub) in enumerate(zip(steps, subtitles)):
        rect = mpatches.FancyBboxPatch(
            (x - box_w / 2, y_center - box_h / 2),
            box_w, box_h,
            boxstyle="round,pad=0.08",
            facecolor=color, edgecolor="white", linewidth=2, alpha=0.92,
        )
        ax.add_patch(rect)
        ax.text(x, y_center + 0.05, label, ha="center", va="center",
                fontsize=9, fontweight="bold", color="white",
                multialignment="center")
        if sub:
            ax.text(x, y_center - box_h / 2 - 0.25, sub, ha="center", va="top",
                    fontsize=7, color="#555555", multialignment="center")

        if i < len(steps) - 1:
            x_next = steps[i + 1][2]
            ax.annotate(
                "", xy=(x_next - box_w / 2 - 0.02, y_center),
                xytext=(x + box_w / 2 + 0.02, y_center),
                arrowprops=dict(arrowstyle="->", color="#666666", lw=1.8),
            )

    ax.text(7, 3.7, "AI Agent Automated Neoantigen Screening Pipeline",
            ha="center", va="center", fontsize=12, fontweight="bold", color="#2C3E50")

    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── 2. Composite score bar chart ──────────────────────────────────────────────

def plot_scores(top10: List[Dict[str, Any]], out: Path):
    if not top10:
        print("  Skip scores: no candidates")
        return

    labels = [c.get("optimized_peptide", c.get("peptide", "?")) for c in top10]
    scores = [c.get("composite_score", 0) for c in top10]
    genes  = [c.get("gene", "?") for c in top10]
    colors = [GENE_COLORS.get(g, DEFAULT_COLOR) for g in genes]

    fig, ax = plt.subplots(figsize=(10, max(4, len(labels) * 0.55 + 1.5)))
    y = np.arange(len(labels))
    bars = ax.barh(y, scores, color=colors, edgecolor="white", height=0.65)

    for bar, score in zip(bars, scores):
        ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height() / 2,
                f"{score:.4f}", va="center", ha="left", fontsize=8.5)

    ax.set_yticks(y)
    ax.set_yticklabels([f"{lb}  ({g})" for lb, g in zip(labels, genes)], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Composite Score", fontsize=10)
    ax.set_title("Top Neoantigen Candidates — Composite Score Ranking",
                 fontsize=12, fontweight="bold", pad=12)
    ax.set_xlim(0, max(scores) * 1.18 if scores else 1)

    legend_patches = [mpatches.Patch(color=c, label=g)
                      for g, c in GENE_COLORS.items() if g in genes]
    if legend_patches:
        ax.legend(handles=legend_patches, loc="lower right", fontsize=8, framealpha=0.7)

    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── 3. IC50 vs %Rank scatter ──────────────────────────────────────────────────

def _jitter_overlapping(
    xs: List[float], ys: List[float],
    tol_x_frac: float = 0.04, tol_y_frac: float = 0.04,
) -> tuple[List[float], List[float]]:
    """Nudge points that are extremely close so they don't fully overlap."""
    xs, ys = list(xs), list(ys)
    x_span = max(xs) - min(xs) + 1e-9
    y_span = max(ys) - min(ys) + 1e-9
    rng = np.random.default_rng(seed=42)
    for i in range(len(xs)):
        for j in range(i + 1, len(xs)):
            if (abs(xs[i] - xs[j]) / x_span < tol_x_frac and
                    abs(ys[i] - ys[j]) / y_span < tol_y_frac):
                xs[i] += rng.uniform(-0.015, 0.015) * x_span
                ys[i] += rng.uniform(-0.015, 0.015) * y_span
                xs[j] += rng.uniform(-0.015, 0.015) * x_span
                ys[j] += rng.uniform(-0.015, 0.015) * y_span
    return xs, ys


def plot_scatter(top10: List[Dict[str, Any]], out: Path):
    valid = [c for c in top10
             if c.get("ic50") is not None and c.get("percentile_rank") is not None]
    if not valid:
        print("  Skip scatter: no IC50 / %Rank data")
        return

    # ── Layout: scatter (left 60%) + detail table (right 38%) ────────────────
    fig = plt.figure(figsize=(15, 7))
    ax     = fig.add_axes([0.07, 0.11, 0.54, 0.78])
    ax_tbl = fig.add_axes([0.64, 0.05, 0.35, 0.90])
    ax_tbl.axis("off")

    # ── Auto log-scale if IC50 spans more than one decade ────────────────────
    ic50_raw  = [c["ic50"] for c in valid]
    rank_raw  = [c["percentile_rank"] for c in valid]
    use_log   = max(ic50_raw) / (min(ic50_raw) + 1e-9) > 10
    
    ax.set_xscale("log")
    ax.set_yscale("log")
    # ── Jitter near-identical points ─────────────────────────────────────────
    # Work in linear space even if axis is log
    xs_j, ys_j = _jitter_overlapping(ic50_raw, rank_raw)

    # ── Plot dots (number inside, size ∝ composite_score) ────────────────────
    for rank_idx, (c, xp, yp) in enumerate(zip(valid, xs_j, ys_j)):
        gene  = c.get("gene", "?")
        color = GENE_COLORS.get(gene, DEFAULT_COLOR)
        score = c.get("composite_score", 0.0)
        size  = 180 + score * 350          # larger = better composite score

        ax.scatter(xp, yp, color=color, s=size,
                   edgecolors="white", linewidths=1.5, zorder=3, alpha=0.88)
        ax.text(xp, yp, str(rank_idx + 1),
                ha="center", va="center", fontsize=8, fontweight="bold",
                color="white", zorder=4)

    # ── Reference lines & strong-binder zone ─────────────────────────────────
    xlim = ax.get_xlim()
    ylim = (0, max(rank_raw) * 1.15 + 0.5)
    ax.set_ylim(ylim)

    x_cut = 500   # nM — mhcflurry weak-binder cutoff
    y_cut = 2.0   # %Rank cutoff
    ax.fill_betweenx([0, y_cut], xlim[0], x_cut,
                     color="#2A9D8F", alpha=0.09, label="Strong binder zone")
    ax.axvline(x_cut, color="#E63946", linestyle="--", lw=1.3, alpha=0.7,
               label=f"IC50 = {x_cut} nM cutoff")
    ax.axhline(y_cut, color="#457B9D", linestyle="--", lw=1.3, alpha=0.7,
               label=f"%Rank = {y_cut} cutoff")
    ax.set_xlim(xlim)

    ax.set_xlabel("IC50 (nM)  [lower = stronger binding]", fontsize=10)
    ax.set_ylabel("%Rank  [lower = stronger binding]", fontsize=10)
    scale_note = " (log scale)" if use_log else ""
    ax.set_title(
        f"HLA Binding Affinity — IC50{scale_note} vs Percentile Rank\n"
        "Number = composite rank · Dot size = composite score",
        fontsize=11, fontweight="bold",
    )
    ax.grid(True, which="both", alpha=0.25, linestyle=":", zorder=0)
    ax.legend(fontsize=8, loc="upper right", framealpha=0.85)

    # ── Gene colour legend ────────────────────────────────────────────────────
    present_genes = {c.get("gene", "?") for c in valid}
    gene_patches  = [mpatches.Patch(color=GENE_COLORS.get(g, DEFAULT_COLOR), label=g)
                     for g in present_genes if g in GENE_COLORS]
    if gene_patches:
        ax.legend(handles=gene_patches, title="Gene", fontsize=7.5,
                  loc="lower right", framealpha=0.85, title_fontsize=8)

    # ── Right panel: candidate detail table ───────────────────────────────────
    ax_tbl.set_title("Candidate Details", fontsize=10, fontweight="bold",
                     loc="left", pad=4)

    col_labels = ["#", "Peptide", "Gene", "IC50 (nM)", "%Rank", "Score"]
    col_x      = [0.00, 0.09, 0.43, 0.57, 0.73, 0.87]
    col_w      = [0.09, 0.34, 0.14, 0.16, 0.14, 0.13]

    # Header row
    for label, x, w in zip(col_labels, col_x, col_w):
        ax_tbl.text(x + w / 2, 0.96, label, ha="center", va="center",
                    transform=ax_tbl.transAxes,
                    fontsize=8, fontweight="bold", color="white",
                    bbox=dict(boxstyle="round,pad=0.25", facecolor="#2C3E50",
                              edgecolor="none"))

    row_h   = min(0.082, 0.82 / max(len(valid), 1))
    start_y = 0.90

    for i, c in enumerate(valid):
        gene  = c.get("gene", "?")
        color = GENE_COLORS.get(gene, DEFAULT_COLOR)
        pep   = c.get("optimized_peptide", c.get("peptide", "?"))
        ic50  = c.get("ic50")
        rank  = c.get("percentile_rank")
        score = c.get("composite_score", 0.0)

        row_y  = start_y - i * row_h
        row_bg = "#F4F6F7" if i % 2 == 0 else "white"
        ax_tbl.add_patch(mpatches.FancyBboxPatch(
            (0.0, row_y - row_h * 0.48), 1.0, row_h * 0.92,
            boxstyle="round,pad=0.005", transform=ax_tbl.transAxes,
            facecolor=row_bg, edgecolor="#DDDDDD", linewidth=0.4, clip_on=False,
        ))

        cells = [
            (str(i + 1),                     "#444444", "bold"),
            (pep,                             "#222222", "normal"),
            (gene,                            color,     "bold"),
            (f"{ic50:.0f}" if ic50 else "—", "#444444", "normal"),
            (f"{rank:.2f}%" if rank else "—","#444444", "normal"),
            (f"{score:.3f}",                  "#444444", "normal"),
        ]
        for (text, fg, fw), x, w in zip(cells, col_x, col_w):
            ax_tbl.text(x + w / 2, row_y - row_h * 0.02,
                        text, ha="center", va="center",
                        transform=ax_tbl.transAxes,
                        fontsize=7.5, color=fg, fontweight=fw)

    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── 4. Metrics heatmap ────────────────────────────────────────────────────────

def plot_heatmap(top10: List[Dict[str, Any]], out: Path):
    valid = [c for c in top10 if c.get("composite_score") is not None][:10]
    if not valid:
        print("  Skip heatmap: no data")
        return

    row_data = {
        "IC50 (nM)\n[lower=better]":        [c.get("ic50", 0) or 0              for c in valid],
        "%Rank\n[lower=better]":             [c.get("percentile_rank", 100) or 100 for c in valid],
        "MCMC Loss\n[lower=better]":         [c.get("mcmc_loss", 0) or 0          for c in valid],
        "Composite Score\n[higher=better]":  [c.get("composite_score", 0) or 0    for c in valid],
    }

    def _norm_invert(vals):
        arr = np.array(vals, dtype=float)
        rng = arr.max() - arr.min()
        return np.zeros_like(arr) if rng == 0 else (arr.max() - arr) / rng

    def _norm(vals):
        arr = np.array(vals, dtype=float)
        rng = arr.max() - arr.min()
        return np.zeros_like(arr) if rng == 0 else (arr - arr.min()) / rng

    keys = list(row_data.keys())
    matrix = np.array([
        _norm_invert(row_data[keys[0]]),
        _norm_invert(row_data[keys[1]]),
        _norm_invert(row_data[keys[2]]),
        _norm(row_data[keys[3]]),
    ])

    xlabels = [
        f"{c.get('optimized_peptide', c.get('peptide','?'))}\n({c.get('gene','?')})"
        for c in valid
    ]

    fig, ax = plt.subplots(figsize=(max(8, len(valid) * 1.1), 4.5))
    im = ax.imshow(matrix, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)

    ax.set_xticks(range(len(xlabels)))
    ax.set_xticklabels(xlabels, fontsize=8, rotation=30, ha="right")
    ax.set_yticks(range(len(keys)))
    ax.set_yticklabels(keys, fontsize=9)

    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            ax.text(j, i, f"{matrix[i, j]:.2f}",
                    ha="center", va="center", fontsize=8,
                    color="black" if 0.3 < matrix[i, j] < 0.8 else "white")

    plt.colorbar(im, ax=ax, fraction=0.03, label="Normalized Score (green = better)")
    ax.set_title("Multi-Metric Evaluation Heatmap (Normalized)",
                 fontsize=12, fontweight="bold", pad=10)

    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── 5. Agent vs Manual comparison ────────────────────────────────────────────

def plot_agent_advantage(out: Path):
    fig, ax = plt.subplots(figsize=(12, 5.5))
    ax.axis("off")

    ax.text(0.5, 0.97, "AI Agent vs Traditional Manual Workflow",
            ha="center", va="top", transform=ax.transAxes,
            fontsize=14, fontweight="bold", color="#2C3E50")

    cols = ["Dimension", "Traditional Manual Process", "This Project — AI Agent"]
    rows = [
        ["Time to Result",     "Days to weeks",                "Minutes (fully automated)"],
        ["Human Intervention", "Manual operation at each step","Zero — agent orchestrates all tools"],
        ["Scalability",        "One mutation at a time",       "Batch: any number of mutations"],
        ["Consistency",        "Operator-dependent",           "Standardized, reproducible"],
        ["Report Generation",  "Written manually",             "LLM auto-generates report"],
        ["Tool Integration",   "Separate tools, manual hand-off","4 tools unified in one Agent"],
        ["Explainability",     "Requires expert interpretation","Plain-language explanation built-in"],
    ]

    col_x    = [0.02, 0.30, 0.64]
    col_w    = 0.34
    row_h    = 0.10
    header_y = 0.87

    for j, (col, x) in enumerate(zip(cols, col_x)):
        bg = "#2C3E50" if j == 0 else ("#C0392B" if j == 1 else "#1A7A6E")
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, header_y - 0.04), col_w - 0.01, 0.07,
            boxstyle="round,pad=0.01", transform=ax.transAxes,
            facecolor=bg, edgecolor="none", clip_on=False,
        ))
        ax.text(x + (col_w - 0.01) / 2, header_y - 0.005, col,
                ha="center", va="center", transform=ax.transAxes,
                fontsize=9.5, fontweight="bold", color="white")

    for i, row in enumerate(rows):
        y   = header_y - 0.12 - i * row_h   # 0.12 gap keeps rows clear of header
        bg  = "#F4F6F7" if i % 2 == 0 else "white"
        ax.add_patch(mpatches.FancyBboxPatch(
            (0.01, y - 0.035), 0.97, row_h - 0.01,
            boxstyle="round,pad=0.005", transform=ax.transAxes,
            facecolor=bg, edgecolor="#DDDDDD", linewidth=0.5, clip_on=False,
        ))
        colors = ["#2C3E50", "#922B21", "#1A5276"]
        for j, (cell, x) in enumerate(zip(row, col_x)):
            ax.text(x + (col_w - 0.01) / 2, y - 0.010, cell,
                    ha="center", va="center", transform=ax.transAxes,
                    fontsize=8.5, color=colors[j],
                    fontweight="bold" if j == 0 else "normal")

    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── main ──────────────────────────────────────────────────────────────────────

def find_latest_results() -> Path | None:
    reports_dir = ROOT / "data" / "output" / "reports"
    jsons = sorted(reports_dir.glob("*_results.json")) if reports_dir.exists() else []
    return jsons[-1] if jsons else None


def main():
    import datetime

    if len(sys.argv) > 1:
        results_file = Path(sys.argv[1])
    else:
        results_file = find_latest_results()

    top10: List[Dict[str, Any]] = []

    if results_file and results_file.exists():
        data  = json.loads(results_file.read_text(encoding="utf-8"))
        top10 = data.get("top10", [])
        print(f"Loaded: {results_file.name}  ({len(top10)} candidates)")
    else:
        print("No results JSON found — generating static figures only.")

    # Create a timestamped subfolder so each run keeps its own figures
    ts     = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = FIGURES_DIR / ts
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {out_dir}")

    plot_pipeline(out_dir / "01_pipeline_flow.png")
    plot_agent_advantage(out_dir / "05_agent_advantage.png")

    if top10:
        plot_scores(top10,  out_dir / "02_composite_scores.png")
        plot_scatter(top10, out_dir / "03_ic50_rank_scatter.png")
        plot_heatmap(top10, out_dir / "04_metrics_heatmap.png")
    else:
        print("  No candidate data — skipping charts 02/03/04.")
        print("  Run 'python agent/run.py' first to generate results.")

    print(f"\nDone. Figures saved to {out_dir}")


if __name__ == "__main__":
    main()
