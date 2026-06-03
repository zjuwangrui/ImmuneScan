"""
Neoantigen Screening Agent entry point.

Usage:
    python agent/run.py

Input is read from the file specified by CONFIG["input_file"] (default: data/input.json).
Edit that file to change HLA type or mutations.
"""
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from config import CONFIG
from agent.agent import run_agent


def _load_input() -> tuple[str, list[Any]]:
    path = Path(CONFIG["input_file"])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"Error: input file not found — {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid JSON in {path} — {exc}", file=sys.stderr)
        sys.exit(1)

    if "hla" not in data or "mutations" not in data:
        print('Error: input JSON must have "hla" and "mutations" fields.', file=sys.stderr)
        sys.exit(1)

    return data["hla"], data["mutations"]


def _print_table(top10):
    header = f"{'Rank':<5} {'Peptide':<12} {'Mutation':<12} {'ddG':>7} {'MCMC Loss':>10} {'IC50(nM)':>10} {'%Rank':>7} {'Score':>7}"
    sep = "-" * len(header)
    print("\n" + "=" * len(header))
    print("TOP 10 NEOANTIGEN VACCINE CANDIDATES")
    print("=" * len(header))
    print(header)
    print(sep)
    for i, c in enumerate(top10, 1):
        peptide  = c.get("optimized_peptide", c.get("peptide", "?"))
        mutation = c.get("mutation", "?")
        ddg      = c.get("ddG")
        mcmc     = c.get("mcmc_loss")
        ic50     = c.get("ic50")
        rank     = c.get("percentile_rank")
        score    = c.get("composite_score", 0)

        col_ddg   = f"{ddg:>7.3f}"  if ddg  is not None                          else f"{'N/A':>7}"
        col_mcmc  = f"{mcmc:>10.3f}" if (mcmc is not None and mcmc != float('inf')) else f"{'N/A':>10}"
        col_ic50  = f"{ic50:>10.1f}" if ic50  is not None                         else f"{'N/A':>10}"
        col_rank  = f"{rank:>7.3f}"  if rank  is not None                         else f"{'N/A':>7}"
        col_score = f"{score:>7.4f}"

        print(f"{i:<5} {peptide:<12} {mutation:<12} {col_ddg} {col_mcmc} {col_ic50} {col_rank} {col_score}")


def main():
    hla, mutations = _load_input()

    print(f"\nNeoantigen Screening Agent")
    print(f"  HLA type  : {hla}")
    print(f"  Mutations : {len(mutations)}")
    print(f"  Input     : {CONFIG['input_file']}")
    print("-" * 50)

    result = run_agent(hla_type=hla, mutations=mutations)

    _print_table(result["top10"])


if __name__ == "__main__":
    main()
