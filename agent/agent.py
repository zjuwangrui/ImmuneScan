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

from config import CONFIG, LLM_CONFIG
from tools.mutation_processor import generate_candidate_peptides
from tools.dl_scorer import score_with_dl_model
from tools.mcmc_optimizer import optimize_with_mcmc
from tools.netmhc_validator import validate_hla_binding

import numpy as np

# ─────────────────────────────────────────────
#  Tool schemas (OpenAI function-calling format)
# ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_candidates",
            "description": (
                "Generate all 9-mer peptide windows from tumor mutation context sequences. "
                "Each window that spans the mutated position becomes a candidate neoantigen."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mutations": {
                        "type": "array",
                        "description": "List of tumor mutations",
                        "items": {
                            "type": "object",
                            "properties": {
                                "gene":    {"type": "string", "description": "Gene name"},
                                "pos":     {"type": "integer", "description": "1-indexed position in context"},
                                "wt":      {"type": "string", "description": "Wildtype amino acid"},
                                "mut":     {"type": "string", "description": "Mutant amino acid"},
                                "context": {"type": "string", "description": "Protein sequence context (>=9 aa)"},
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
                "Score candidate peptides with the AttABseq deep learning model. "
                "Predicts ddG (binding affinity change); higher |ddG| = more significant mutation. "
                "Returns candidates sorted by |ddG| descending."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "candidates": {
                        "type": "array",
                        "description": "Peptide candidates from generate_candidates",
                    },
                },
                "required": ["candidates"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "optimize_with_mcmc",
            "description": (
                "Optimize top candidates with simulated annealing (ImmuneAI-Screener) "
                "to improve T-cell recognition potential. Adds optimized_peptide and mcmc_loss."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "candidates": {
                        "type": "array",
                        "description": "Scored candidates (will optimize top top_n)",
                    },
                    "hla_type": {
                        "type": "string",
                        "description": "Patient HLA allele, e.g. HLA-A*02:01",
                    },
                    "top_n": {
                        "type": "integer",
                        "description": "Number of top candidates to optimize (default 30)",
                    },
                },
                "required": ["candidates", "hla_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_hla_binding",
            "description": (
                "Predict HLA-peptide binding affinity via mhcflurry. "
                "Returns ic50 (nM), percentile_rank (%), and binder flag for each candidate. "
                "Lower IC50 and rank = stronger binder = better vaccine candidate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "candidates": {
                        "type": "array",
                        "description": "Optimized candidates from optimize_with_mcmc",
                    },
                    "hla_type": {
                        "type": "string",
                        "description": "Patient HLA allele",
                    },
                },
                "required": ["candidates", "hla_type"],
            },
        },
    },
]

# ─────────────────────────────────────────────
#  Tool dispatch table
# ─────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "generate_candidates": lambda inp: generate_candidate_peptides(
        mutations=inp["mutations"],
        peptide_length=CONFIG.get("peptide_length", 9),
    ),
    "score_with_dl": lambda inp: score_with_dl_model(
        candidates=inp["candidates"],
        config=CONFIG,
    ),
    "optimize_with_mcmc": lambda inp: optimize_with_mcmc(
        candidates=inp["candidates"],
        hla_type=inp["hla_type"],
        config=CONFIG,
        top_n=inp.get("top_n"),
    ),
    "validate_hla_binding": lambda inp: validate_hla_binding(
        candidates=inp["candidates"],
        hla_type=inp["hla_type"],
    ),
}

# ─────────────────────────────────────────────
#  System prompt
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert neoantigen vaccine design assistant.

Your goal: given a patient's HLA type and a list of tumor mutations, identify the Top 10 peptide candidates for a personalized cancer vaccine.

Pipeline (execute in this order):
1. generate_candidates — produce all 9-mer peptide windows spanning each mutation
2. score_with_dl       — rank by |ddG| using the AttABseq deep learning model
3. optimize_with_mcmc  — improve TCR recognition via simulated annealing (top 30)
4. validate_hla_binding — predict HLA binding with mhcflurry (IC50, %rank)

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
    client = OpenAI(
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
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
    validated_candidates: List[Dict] = []

    while True:
        response = client.chat.completions.create(
            model=LLM_CONFIG["model"],
            max_tokens=4096,
            tools=TOOLS,
            messages=messages,
        )

        msg = response.choices[0].message
        # append as dict so it serializes cleanly in subsequent turns
        messages.append(msg.model_dump(exclude_unset=True))

        finish_reason = response.choices[0].finish_reason

        if finish_reason == "stop":
            break

        if finish_reason != "tool_calls":
            break

        for tool_call in (msg.tool_calls or []):
            print(f"  [agent] → {tool_call.function.name}", flush=True)
            fn  = TOOL_FUNCTIONS.get(tool_call.function.name)
            inp = json.loads(tool_call.function.arguments)

            if fn is None:
                result = {"error": f"unknown tool: {tool_call.function.name}"}
            else:
                try:
                    result = fn(inp)
                    if tool_call.function.name == "validate_hla_binding":
                        validated_candidates = result
                except Exception as exc:
                    result = {"error": str(exc)}

            messages.append({
                "role":         "tool",
                "tool_call_id": tool_call.id,
                "content":      json.dumps(result, default=str),
            })

    report = response.choices[0].message.content or ""

    top10 = _rank_candidates(validated_candidates)[:CONFIG.get("top_n_output", 10)]
    return {"top10": top10, "report": report}


def _rank_candidates(candidates: List[Dict]) -> List[Dict]:
    """Multi-criteria ranking: |ddG|, mcmc_loss, HLA percentile_rank."""
    if not candidates:
        return []

    def _safe_norm(values, invert=False):
        arr = np.array([v if v is not None else (0 if not invert else 1e9)
                        for v in values], dtype=float)
        rng = arr.max() - arr.min()
        if rng == 0:
            return np.zeros_like(arr)
        normed = (arr - arr.min()) / rng
        return 1.0 - normed if invert else normed

    dl  = _safe_norm([c.get("dl_score", 0)          for c in candidates])
    mc  = _safe_norm([c.get("mcmc_loss", 1e9)        for c in candidates], invert=True)
    hla = _safe_norm([c.get("percentile_rank", 100)  for c in candidates], invert=True)

    for i, c in enumerate(candidates):
        c["composite_score"] = round(0.4 * dl[i] + 0.3 * mc[i] + 0.3 * hla[i], 4)

    return sorted(candidates, key=lambda x: x["composite_score"], reverse=True)
