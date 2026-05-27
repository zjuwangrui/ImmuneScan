"""
HLA-peptide binding prediction using mhcflurry.
Falls back to None values if mhcflurry is not installed.
"""
from typing import List, Dict


def validate_hla_binding(candidates: List[Dict], hla_type: str) -> List[Dict]:
    """
    Predict HLA binding for each candidate's 'optimized_peptide'.
    Adds: ic50 (nM), percentile_rank (%), presentation_score, binder (bool).
    """
    allele = _normalize_hla(hla_type)
    peptides = [c.get("optimized_peptide", c["peptide"]) for c in candidates]

    try:
        from mhcflurry import Class1PresentationPredictor
        predictor = Class1PresentationPredictor.load()

        result_df = predictor.predict(
            peptides=peptides,
            alleles=[allele] * len(peptides),
            include_affinity_percentile=True,
        )

        for i, candidate in enumerate(candidates):
            row = result_df.iloc[i]
            ic50 = float(row.get("affinity", row.get("presentation_score", 50000)))
            rank = float(row.get("affinity_percentile", 100.0))
            pres = float(row.get("presentation_score", 0.0))
            candidate["ic50"] = ic50
            candidate["percentile_rank"] = rank
            candidate["presentation_score"] = pres
            candidate["binder"] = rank < 2.0

    except ImportError:
        for candidate in candidates:
            candidate["ic50"] = None
            candidate["percentile_rank"] = None
            candidate["presentation_score"] = None
            candidate["binder"] = None

    return candidates


def _normalize_hla(hla_type: str) -> str:
    """Normalize HLA-A*0201 or HLA-A*02:01 → HLA-A*02:01."""
    hla = hla_type.strip()
    if ":" in hla:
        return hla
    if "*" in hla:
        prefix, digits = hla.split("*", 1)
        if len(digits) == 4:
            return f"{prefix}*{digits[:2]}:{digits[2:]}"
    return hla
