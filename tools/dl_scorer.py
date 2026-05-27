"""
Wrapper around AttABseq for ddG scoring of neoantigen candidates.
"""
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent / "models" / "attabseq"))
from predict_api import predict_ddg_batch


def score_with_dl_model(candidates: List[Dict], config: dict) -> List[Dict]:
    """
    Add 'ddG' and 'dl_score' (= |ddG|) fields to each candidate.
    Returns candidates sorted by dl_score descending.

    Each candidate must have 'peptide' and 'wt_peptide' fields.
    """
    samples = [
        {
            "wt_ab":  c["wt_peptide"],
            "mut_ab": c["peptide"],
            "wt_ag":  c["wt_peptide"],
            "mut_ag": c["peptide"],
        }
        for c in candidates
    ]

    ddg_values = predict_ddg_batch(samples, config)

    for c, ddg in zip(candidates, ddg_values):
        c["ddG"] = ddg
        c["dl_score"] = abs(ddg)

    return sorted(candidates, key=lambda x: x["dl_score"], reverse=True)
