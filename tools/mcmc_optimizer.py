"""
Wrapper around ImmuneAI-Screener's simulated annealing for peptide optimization.
"""
import sys
from pathlib import Path
from typing import List, Dict, Optional

_IMMUNEAI_DIR = str(Path(__file__).parent.parent / "models" / "immuneai")
if _IMMUNEAI_DIR not in sys.path:
    sys.path.insert(0, _IMMUNEAI_DIR)


def optimize_with_mcmc(
    candidates: List[Dict],
    hla_type: str,
    config: dict,
    top_n: Optional[int] = None,
) -> List[Dict]:
    """
    Run simulated-annealing optimization on the top `top_n` candidates.
    Adds 'optimized_peptide' and 'mcmc_loss' fields to each candidate.

    Candidates not in the top_n retain their original peptide sequence.
    """
    from main import run_immuneai

    top_n = top_n or config.get("top_n_for_mcmc", 30)
    steps = config.get("mcmc_steps", 500)

    for candidate in candidates[:top_n]:
        try:
            result = run_immuneai(
                start_pep=candidate["peptide"],
                hla_type=hla_type,
                steps=steps,
                config=config,
            )
            candidate["optimized_peptide"] = result["final_sequence"]
            candidate["mcmc_loss"] = result["final_loss"]
        except Exception as e:
            candidate["optimized_peptide"] = candidate["peptide"]
            candidate["mcmc_loss"] = float("inf")

    for candidate in candidates[top_n:]:
        candidate.setdefault("optimized_peptide", candidate["peptide"])
        candidate.setdefault("mcmc_loss", float("inf"))

    return candidates
