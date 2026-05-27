"""
Generate 9-mer neoantigen candidate peptides from tumor mutations.
"""
from typing import List, Dict

_VALID_AAS = set("ACDEFGHIKLMNPQRSTVWY")


def generate_candidate_peptides(
    mutations: List[Dict],
    peptide_length: int = 9,
) -> List[Dict]:
    """
    Slide a window of `peptide_length` over each mutation's context sequence,
    generating all windows that contain the mutated position.

    Each mutation dict must have:
        - context (str): protein sequence region containing the mutation
        - pos     (int): 1-indexed position of the mutated residue within context
        - wt      (str): wildtype amino acid (single letter)
        - mut     (str): mutant amino acid (single letter)
        - gene    (str, optional): gene name

    Returns list of dicts with fields:
        peptide, wt_peptide, gene, mutation, context_pos (0-indexed in peptide)
    """
    candidates = []

    for mut in mutations:
        context = mut["context"].upper()
        pos = mut.get("pos", len(context) // 2 + 1)   # 1-indexed
        wt_aa = mut["wt"].upper()
        mut_aa = mut["mut"].upper()
        gene = mut.get("gene", "unknown")

        context_idx = pos - 1  # convert to 0-indexed
        if context_idx < 0 or context_idx >= len(context):
            continue

        mut_context = context[:context_idx] + mut_aa + context[context_idx + 1:]

        # All windows of `peptide_length` that include the mutation site
        start_min = max(0, context_idx - peptide_length + 1)
        start_max = min(len(context) - peptide_length, context_idx)

        for start in range(start_min, start_max + 1):
            end = start + peptide_length
            mut_pep = mut_context[start:end]
            wt_pep = context[start:end]

            if not all(aa in _VALID_AAS for aa in mut_pep):
                continue

            candidates.append({
                "peptide":     mut_pep,
                "wt_peptide":  wt_pep,
                "gene":        gene,
                "mutation":    f"{wt_aa}{pos}{mut_aa}",
                "context_pos": context_idx - start,
            })

    return candidates
