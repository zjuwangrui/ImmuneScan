"""
CLI entry point for the Neoantigen Screening Agent.

Usage:
    python agent/run.py --hla "HLA-A*02:01" --mutations '[{"gene":"TP53","pos":4,"wt":"R","mut":"W","context":"VVRCPHHERCSDSD"}]'
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from agent.agent import run_agent


def _parse_args():
    p = argparse.ArgumentParser(description="Neoantigen Vaccine Candidate Screener")
    p.add_argument("--hla", required=True,
                   help="Patient HLA type (e.g. HLA-A*02:01 or HLA-A*0201)")
    p.add_argument("--mutations", required=True,
                   help=(
                       'JSON list of mutations. Each entry needs: '
                       'gene, pos (1-indexed in context), wt, mut, context. '
                       'Example: \'[{"gene":"TP53","pos":4,"wt":"R","mut":"W",'
                       '"context":"VVRCPHHERCSDSD"}]\''
                   ))
    return p.parse_args()


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

        print(
            f"{i:<5} "
            f"{peptide:<12} "
            f"{mutation:<12} "
            f"{ddg:>7.3f} " if ddg is not None else f"{'N/A':>8} "
            f"{mcmc:>10.3f} " if mcmc is not None and mcmc != float('inf') else f"{'N/A':>11} "
            f"{ic50:>10.1f} " if ic50 is not None else f"{'N/A':>11} "
            f"{rank:>7.2f} " if rank is not None else f"{'N/A':>8} "
            f"{score:>7.4f}"
        )


def main():
    args = _parse_args()

    try:
        mutations = json.loads(args.mutations)
    except json.JSONDecodeError as exc:
        print(f"Error: invalid mutations JSON — {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\nNeoantigen Screening Agent")
    print(f"  HLA type  : {args.hla}")
    print(f"  Mutations : {len(mutations)}")
    print("-" * 50)

    result = run_agent(hla_type=args.hla, mutations=mutations)

    print("\n" + result["report"])
    _print_table(result["top10"])


if __name__ == "__main__":
    main()
