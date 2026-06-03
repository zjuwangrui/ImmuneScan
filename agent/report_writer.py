"""
Report writer — generates Markdown and JSON reports with no LLM involvement.
All content is derived directly from pipeline inputs and outputs.
"""
import json
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def write_report(
    hla: str,
    mutations: List[Dict],
    top10: List[Dict],
    config: Dict[str, Any],
    run_duration_s: Optional[float] = None,
) -> Path:
    """
    Write <timestamp>_report.md and <timestamp>_results.json to output_dir/reports/.
    Returns the path to the Markdown report.
    """
    ts     = datetime.datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S")

    out_dir = Path(config.get("output_dir", "data/output")) / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "meta": {
            "timestamp":      ts.isoformat(),
            "hla":            hla,
            "llm_model":      config.get("llm_model", "N/A"),
            "mcmc_steps":     config.get("mcmc_steps"),
            "peptide_length": config.get("peptide_length"),
            "top_n_output":   config.get("top_n_output"),
            "run_duration_s": run_duration_s,
            "input_file":     config.get("input_file"),
            "output_dir":     config.get("output_dir"),
        },
        "input": {
            "hla":       hla,
            "mutations": mutations,
        },
        "top10": top10,
    }

    json_path = out_dir / f"{ts_str}_results.json"
    json_path.write_text(
        json.dumps(payload, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )

    md_path = out_dir / f"{ts_str}_report.md"
    md_path.write_text(_build_markdown(payload), encoding="utf-8")

    return md_path


# ── helpers ───────────────────────────────────────────────────────────────────

def _f(val: Any, fmt: str, fallback: str = "N/A") -> str:
    """Format a value safely; return fallback on None / inf / error."""
    if val is None:
        return fallback
    if isinstance(val, float) and (val != val or val == float("inf")):   # nan or inf
        return fallback
    try:
        return format(val, fmt)
    except (ValueError, TypeError):
        return str(val)


def _hi_context(context: str, pos: Any) -> str:
    """Bold the mutated residue inside the context string (Markdown)."""
    if not isinstance(pos, int) or not (1 <= pos <= len(context)):
        return f"`{context}`"
    return f"`{context[:pos - 1]}**{context[pos - 1]}**{context[pos:]}`"


# ── Markdown builder ──────────────────────────────────────────────────────────

def _build_markdown(data: dict) -> str:
    meta  = data["meta"]
    inp   = data["input"]
    top10 = data["top10"]

    ts_fmt   = datetime.datetime.fromisoformat(meta["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    duration = (f"{meta['run_duration_s']:.1f} s"
                if meta.get("run_duration_s") is not None else "N/A")
    n_mut    = len(inp["mutations"])

    L: List[str] = []

    # ── Title ─────────────────────────────────────────────────────────────────
    L += [
        "# Neoantigen Screening Report",
        "",
        f"> Generated: {ts_fmt}  ·  HLA: `{inp['hla']}`  "
        f"·  Mutations: {n_mut}  ·  Duration: {duration}",
        "",
        "---",
        "",
    ]

    # ── 1. Run metadata ───────────────────────────────────────────────────────
    L += [
        "## 1. Run Metadata",
        "",
        "| Field | Value |",
        "|---|---|",
        f"| Timestamp | {ts_fmt} |",
        f"| Run Duration | {duration} |",
        f"| Input File | `{meta.get('input_file', 'N/A')}` |",
        f"| Output Directory | `{meta.get('output_dir', 'N/A')}` |",
        f"| LLM Orchestrator | `{meta.get('llm_model', 'N/A')}` |",
        f"| MCMC Steps / Peptide | {meta.get('mcmc_steps', 'N/A')} |",
        f"| Peptide Length | {meta.get('peptide_length', 9)} aa |",
        f"| Top-N Output | {meta.get('top_n_output', 10)} |",
        "",
        "---",
        "",
    ]

    # ── 2. Input ──────────────────────────────────────────────────────────────
    L += [
        "## 2. Input",
        "",
        f"**Patient HLA type:** `{inp['hla']}`  ",
        f"**Tumor mutations ({n_mut} total):**",
        "",
        "| # | Gene | Protein Change | WT | Mut | Context (mut position bolded) | Pos in Context |",
        "|---|------|---------------|----|----|-------------------------------|----------------|",
    ]
    for i, m in enumerate(inp["mutations"], 1):
        gene    = m.get("gene", "?")
        wt      = m.get("wt", "?")
        mut_aa  = m.get("mut", "?")
        pos     = m.get("pos", "?")
        context = m.get("context", "?")
        change  = f"{wt}→{mut_aa}"
        L.append(
            f"| {i} | **{gene}** | `{change}` | {wt} | {mut_aa} "
            f"| {_hi_context(context, pos)} | {pos} |"
        )

    L += ["", "---", ""]

    # ── 3. Pipeline ───────────────────────────────────────────────────────────
    L += [
        "## 3. Pipeline Steps",
        "",
        "| Step | Module | Role |",
        "|------|--------|------|",
        "| 1 | `mutation_processor` | Slide 9-mer windows over each mutation context |",
        "| 2 | `AttABseq` (DL) | Predict binding affinity change Δ(ddG) per peptide |",
        "| 3 | `ImmuneAI` (MCMC) | Simulated annealing — optimise for TCR recognition |",
        "| 4 | `mhcflurry` | Predict HLA-peptide IC50 and percentile rank |",
        "| 5 | `rank_candidates` | Multi-criteria composite score |",
        "",
        "**Composite score formula:**",
        "```",
        "composite = 0.4 × norm(|ddG|)  +  0.3 × norm(1/MCMC_loss)  +  0.3 × norm(1/%Rank)",
        "```",
        "",
        "---",
        "",
    ]

    # ── 4. Results table ──────────────────────────────────────────────────────
    n_binders = sum(1 for c in top10 if c.get("binder"))

    L += [
        f"## 4. Top {len(top10)} Vaccine Candidates",
        "",
        f"**Strong HLA binders (IC50 < 500 nM, %Rank < 2%):** {n_binders} / {len(top10)}",
        "",
        "| Rank | Peptide | Gene | ddG | MCMC Loss | IC50 (nM) | %Rank | Binder | Score |",
        "|------|---------|------|-----|-----------|-----------|-------|--------|-------|",
    ]
    for i, c in enumerate(top10, 1):
        pep_opt  = c.get("optimized_peptide", c.get("peptide", "?"))
        pep_orig = c.get("peptide", pep_opt)
        gene     = c.get("gene", "?")
        ddg      = _f(c.get("ddG"), ".3f")
        mcmc     = _f(c.get("mcmc_loss"), ".3f")
        ic50     = _f(c.get("ic50"), ".1f")
        rank     = _f(c.get("percentile_rank"), ".3f") + "%"
        score    = _f(c.get("composite_score", 0), ".4f")
        binder   = "✓" if c.get("binder") else ("?" if c.get("ic50") is None else "✗")

        pep_cell = (f"`{pep_opt}`" if pep_opt == pep_orig
                    else f"`{pep_opt}` *(was `{pep_orig}`)*")

        L.append(
            f"| **{i}** | {pep_cell} | {gene} "
            f"| {ddg} | {mcmc} | {ic50} | {rank} | {binder} | **{score}** |"
        )

    L += ["", "---", ""]

    # ── 5. Per-candidate detail ───────────────────────────────────────────────
    L += ["## 5. Candidate Detail", ""]
    for i, c in enumerate(top10, 1):
        pep   = c.get("optimized_peptide", c.get("peptide", "?"))
        gene  = c.get("gene", "?")
        score = _f(c.get("composite_score", 0), ".4f")
        L += [
            f"### Rank {i} — `{pep}` ({gene})  Score: {score}",
            "",
            f"- **Original peptide:** `{c.get('peptide', pep)}`",
            f"- **Optimized peptide:** `{pep}`",
            f"- **Mutation:** {c.get('mutation', 'N/A')}",
            f"- **ddG (DL model):** {_f(c.get('ddG'), '.4f')}",
            f"- **MCMC loss:** {_f(c.get('mcmc_loss'), '.4f')}",
            f"- **IC50:** {_f(c.get('ic50'), '.2f')} nM",
            f"- **%Rank:** {_f(c.get('percentile_rank'), '.4f')}%",
            f"- **Presentation score:** {_f(c.get('presentation_score'), '.4f')}",
            f"- **Strong binder:** {'Yes' if c.get('binder') else 'No'}",
            "",
        ]

    L += ["---", ""]

    # ── 6. Score reference ────────────────────────────────────────────────────
    L += [
        "## 6. Metric Reference",
        "",
        "| Metric | Better | Clinical Threshold |",
        "|--------|--------|--------------------|",
        "| `ddG` | Higher \\|ddG\\| | — (model limitation: values near 0 for short peptides) |",
        "| `MCMC Loss` | Lower | < 2.0 good, < 1.5 excellent |",
        "| `IC50 (nM)` | Lower | < 50 strong binder · < 500 binder · > 5000 non-binder |",
        "| `%Rank` | Lower | < 0.5% strong · < 2.0% binder · > 2% weak/non-binder |",
        "| `Composite` | Higher | > 0.6 promising · > 0.8 excellent |",
        "",
        "---",
        "",
        "*Report generated automatically — no LLM text generation.*",
    ]

    return "\n".join(L)
