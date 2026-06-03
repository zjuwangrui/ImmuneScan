"""
Neoantigen Screening Agent — OpenAI-compatible API with tool_use.

Usage:
    from agent.agent import run_agent
    result = run_agent(hla_type="HLA-A*02:01", mutations=[...])
"""
import json
import sys
from pathlib import Path
from typing import List, Dict

from openai import OpenAI

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import CONFIG
from tools.mutation_processor import generate_candidate_peptides
from tools.dl_scorer import score_with_dl_model
from tools.mcmc_optimizer import optimize_with_mcmc
from tools.netmhc_validator import validate_hla_binding

import numpy as np

# ─────────────────────────────────────────────
#  Session store — tools read/write here so the
#  LLM never has to echo large candidate lists.
# ─────────────────────────────────────────────

_STORE: Dict[str, list] = {}


def _summary(candidates: list, n: int = 3) -> dict:
    """Return a compact summary for the LLM (not the full list)."""
    sample = [
        {k: v for k, v in c.items()
         if k in ("peptide", "optimized_peptide", "gene", "mutation",
                  "ddG", "dl_score", "mcmc_loss", "ic50", "percentile_rank")}
        for c in candidates[:n]
    ]
    return {"count": len(candidates), "top_sample": sample}


# ─────────────────────────────────────────────
#  Tool schemas (OpenAI function-calling format)
#  Subsequent steps read candidates from the
#  session store — no need to pass them as args.
# ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_candidates",
            "description": (
                "Generate all 9-mer peptide windows from tumor mutation context sequences. "
                "Results are stored internally for the next step."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mutations": {
                        "type": "array",
                        "description": "List of tumor mutations (pass the full list from the user input)",
                        "items": {
                            "type": "object",
                            "properties": {
                                "gene":    {"type": "string"},
                                "pos":     {"type": "integer"},
                                "wt":      {"type": "string"},
                                "mut":     {"type": "string"},
                                "context": {"type": "string"},
                            },
                            "required": ["pos", "wt", "mut", "context"],
                        },
                    },
                },
                "required": ["mutations"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "score_with_dl",
            "description": (
                "Score the candidates from the previous step with the AttABseq deep learning model. "
                "Reads candidates internally — no arguments needed."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_with_mcmc",
            "description": (
                "Optimize all candidates with simulated annealing to improve T-cell recognition. "
                "Reads scored candidates internally."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hla_type": {
                        "type": "string",
                        "description": "Patient HLA allele, e.g. HLA-A*02:01",
                    },
                },
                "required": ["hla_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_hla_binding",
            "description": (
                "Predict HLA-peptide binding affinity via mhcflurry (IC50, %rank, binder flag). "
                "Reads optimized candidates internally."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "hla_type": {
                        "type": "string",
                        "description": "Patient HLA allele",
                    },
                },
                "required": ["hla_type"],
            },
        },
    },
]

# ─────────────────────────────────────────────
#  Tool dispatch table (reads/writes _STORE)
# ─────────────────────────────────────────────

def _tool_generate_candidates(inp: dict) -> dict:
    candidates = generate_candidate_peptides(
        mutations=inp["mutations"],
        peptide_length=CONFIG.get("peptide_length", 9),
    )
    _STORE["raw"] = candidates
    return _summary(candidates)


def _tool_score_with_dl(inp: dict) -> dict:
    candidates = score_with_dl_model(
        candidates=_STORE.get("raw", []),
        config=CONFIG,
    )
    _STORE["scored"] = candidates
    return _summary(candidates)


def _tool_optimize_with_mcmc(inp: dict) -> dict:
    candidates = optimize_with_mcmc(
        candidates=_STORE.get("scored", []),
        hla_type=inp["hla_type"],
        config=CONFIG,
        top_n=inp.get("top_n"),
    )
    _STORE["optimized"] = candidates
    return _summary(candidates)


def _tool_validate_hla_binding(inp: dict) -> dict:
    try:
        candidates = validate_hla_binding(
            candidates=_STORE.get("optimized", []),
            hla_type=inp["hla_type"],
        )
        _STORE["validated"] = candidates
        return _summary(candidates)
    except Exception as exc:
        import traceback as _tb
        print(f"  [validate ERROR] {exc}", flush=True)
        _tb.print_exc()
        return {"error": str(exc), "count": 0}


TOOL_FUNCTIONS = {
    "generate_candidates":  _tool_generate_candidates,
    "score_with_dl":        _tool_score_with_dl,
    "optimize_with_mcmc":   _tool_optimize_with_mcmc,
    "validate_hla_binding": _tool_validate_hla_binding,
}

# ─────────────────────────────────────────────
#  System prompt
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert neoantigen vaccine design assistant.

Your goal: given a patient's HLA type and a list of tumor mutations, identify the Top 10 peptide candidates for a personalized cancer vaccine.

Pipeline (execute in this order):
1. generate_candidates — pass the full mutations list from the user input
2. score_with_dl       — no arguments needed; reads previous results internally
3. optimize_with_mcmc  — pass hla_type (and optionally top_n); reads previous results internally
4. validate_hla_binding — pass hla_type; reads previous results internally

Each tool returns only a compact summary. The full candidate list is managed internally.

After all four steps, rank the validated candidates using a composite score:
  composite = 0.4 × norm(|ddG|) + 0.3 × norm(1/mcmc_loss) + 0.3 × norm(1/percentile_rank)

Output a concise, structured Top-10 report with columns:
  Rank | Peptide | Gene/Mutation | ddG | MCMC Loss | IC50 (nM) | %Rank | Score
"""

# ─────────────────────────────────────────────
#  Agent loop
# ─────────────────────────────────────────────

def run_agent(hla_type: str, mutations: List[Dict]) -> Dict:
    """
    Run the neoantigen screening agent.

    Returns:
        {
            "top10":  list of top-10 candidate dicts,
            "report": final text report from the LLM,
        }
    """
    _STORE.clear()

    client = OpenAI(
        api_key=CONFIG["llm_api_key"],
        base_url=CONFIG["llm_base_url"],
    )

    task = (
        f"Screen the following tumor mutations for neoantigen vaccine candidates.\n\n"
        f"Patient HLA type: {hla_type}\n"
        f"Tumor mutations:\n{json.dumps(mutations, indent=2)}\n\n"
        f"Run the full pipeline and output the Top 10 vaccine candidates."
    )

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": task},
    ]

    while True:
        response = client.chat.completions.create(
            model=CONFIG["llm_model"],
            max_tokens=4096,
            tools=TOOLS,
            messages=messages,
        )

        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_unset=True))

        finish_reason = response.choices[0].finish_reason

        if finish_reason == "stop":
            break

        if finish_reason != "tool_calls":
            break

        for tool_call in (msg.tool_calls or []):
            name = tool_call.function.name
            print(f"  [agent] → {name}", flush=True)

            fn = TOOL_FUNCTIONS.get(name)
            try:
                inp = json.loads(tool_call.function.arguments) if tool_call.function.arguments.strip() else {}
            except json.JSONDecodeError as exc:
                print(f"  [agent] ⚠ bad arguments JSON for {name}: {exc}", flush=True)
                inp = {}

            if fn is None:
                result = {"error": f"unknown tool: {name}"}
            else:
                try:
                    result = fn(inp)
                except Exception as exc:
                    result = {"error": str(exc)}

            messages.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "content":      json.dumps(result, default=str),
            })

        # All four pipeline steps done — exit immediately, skip LLM summary
        if "validated" in _STORE:
            break

    print(f"  [agent] store keys after run: {list(_STORE.keys())}", flush=True)
    for k, v in _STORE.items():
        print(f"    {k}: {len(v)} candidates", flush=True)

    # Fallback chain: use the furthest-completed step
    candidates = (
        _STORE.get("validated")
        or _STORE.get("optimized")
        or _STORE.get("scored")
        or _STORE.get("raw")
        or []
    )
    top10 = _rank_candidates(candidates)[:CONFIG.get("top_n_output", 10)]
    return {"top10": top10}


def _rank_candidates(candidates: List[Dict]) -> List[Dict]:
    """Multi-criteria ranking: |ddG|, mcmc_loss, HLA percentile_rank."""
    if not candidates:
        return []

    def _safe_norm(values, invert=False):
        arr = np.array([v if (v is not None and np.isfinite(v)) else (0.0 if not invert else 0.0)
                        for v in values], dtype=float)
        # Replace inf with max finite value (or 0 if none)
        finite_mask = np.isfinite(arr)
        if not finite_mask.any():
            return np.zeros_like(arr)
        arr[~finite_mask] = arr[finite_mask].max() if not invert else arr[finite_mask].max()
        rng = arr.max() - arr.min()
        if rng == 0 or not np.isfinite(rng):
            return np.zeros_like(arr)
        normed = (arr - arr.min()) / rng
        return 1.0 - normed if invert else normed

    dl  = _safe_norm([c.get("dl_score", 0)          for c in candidates])
    mc  = _safe_norm([c.get("mcmc_loss", 1e9)        for c in candidates], invert=True)
    hla = _safe_norm([c.get("percentile_rank", 100)  for c in candidates], invert=True)

    for i, c in enumerate(candidates):
        c["composite_score"] = round(0.4 * dl[i] + 0.3 * mc[i] + 0.3 * hla[i], 4)

    return sorted(candidates, key=lambda x: x["composite_score"], reverse=True)
