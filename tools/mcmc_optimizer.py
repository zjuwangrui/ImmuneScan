"""
Wrapper around ImmuneAI-Screener's simulated annealing for peptide optimization.
"""
import importlib.util
import sys
from pathlib import Path
from typing import List, Dict, Optional

_IMMUNEAI_DIR = Path(__file__).parent.parent / "models" / "immuneai"

# Load immuneai/main.py by absolute path to avoid sys.path collisions
# with models/attabseq/main.py which shares the same module name.
_immuneai_mod = None

def _get_run_immuneai():
    global _immuneai_mod
    if _immuneai_mod is None:
        immuneai_str = str(_IMMUNEAI_DIR)
        if immuneai_str not in sys.path:
            sys.path.insert(0, immuneai_str)
        spec = importlib.util.spec_from_file_location(
            "immuneai_main", str(_IMMUNEAI_DIR / "main.py")
        )
        mod = importlib.util.module_from_spec(spec)
        sys.modules["immuneai_main"] = mod
        spec.loader.exec_module(mod)
        _immuneai_mod = mod
    return _immuneai_mod.run_immuneai


def optimize_with_mcmc(
    candidates: List[Dict],
    hla_type: str,
    config: dict,
    top_n: Optional[int] = None,
) -> List[Dict]:
    """
    Run simulated-annealing optimization on all candidates.
    Adds 'optimized_peptide' and 'mcmc_loss' fields to each candidate.
    """
    run_immuneai = _get_run_immuneai()

    steps = config.get("mcmc_steps", 500)

    for candidate in candidates:
        try:
            result = run_immuneai(
                start_pep=candidate["peptide"],
                hla_type=hla_type,
                steps=steps,
                config=config,
            )
            candidate["optimized_peptide"] = result["final_sequence"]
            candidate["mcmc_loss"] = result["final_loss"]
        except Exception:
            candidate["optimized_peptide"] = candidate["peptide"]
            candidate["mcmc_loss"] = float("inf")

    return candidates
