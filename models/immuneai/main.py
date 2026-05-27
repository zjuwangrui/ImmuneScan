import numpy as np
import os
import sys
from pathlib import Path

from arg_parse import get_args
from Policy import calculate_similarity, one_hot_encoding
from process import (
    init_frequency_matrix,
    print_initial_frequency_matrix,
    Simulated_Annealing,
)
from addition_func import get_freq

args = get_args()

AA_freq = {
    "A": 0.07421620506799341,
    "R": 0.05161448614128464,
    "N": 0.044645808512757915,
    "D": 0.05362600083855441,
    "C": 0.02468745716794485,
    "Q": 0.03425965059141602,
    "E": 0.0543119256845875,
    "G": 0.074146941452645,
    "H": 0.026212984805266227,
    "I": 0.06791736761895376,
    "L": 0.09890786849715096,
    "K": 0.05815568230307968,
    "M": 0.02499019757964311,
    "F": 0.04741845974228475,
    "P": 0.038538003320306206,
    "S": 0.05722902947649442,
    "T": 0.05089136455028703,
    "W": 0.013029956129972148,
    "Y": 0.03228151231375858,
    "V": 0.07291909820561925,
}

# Default DB paths — overridden by run_immuneai() config
_THIS_DIR = Path(__file__).parent
_DATA_DIR = _THIS_DIR.parent.parent / "data" / "immuneai"
dir_tcr = str(_DATA_DIR)
file_tcr = "tcr-specific--peptide.txt"
dir_iedb = str(_DATA_DIR)
file_iedb = "pHLA-A0201--peptide.txt"


class peptide:
    def __init__(self, length, aa_freq_mat):
        self.len = length
        self.freq = aa_freq_mat
        self.init_sequences = {}
        self.dictionary = dict(zip(np.linspace(0, 19, 20, dtype=int), AA_freq.keys()))
        self.seq = self.generate_loc(loc=np.linspace(0, 8, 9, dtype=int))

    def generate_loc(self, loc, seq=None, booster_num=None):
        if booster_num is None:
            booster_num = args.booster_num

        if seq is None:
            seq = []
            if args.start_pep is None:
                for i in loc:
                    seq.append(self.dictionary[np.random.choice(20, p=self.freq[:, i])])
            else:
                for i in args.start_pep:
                    seq.append(i)
        else:
            if args.add_booster:
                seq_init = list(seq.values())
                seq = list(seq.values())
                for cc in range(1000):
                    for i in loc:
                        seq_i = seq[i]
                        while seq_i == seq_init[i] or seq_i == seq[i]:
                            if args.rest_mut_pos is not None:
                                if i in [_ - 1 for _ in list(map(int, args.rest_mut_pos.split("_")))]:
                                    seq_i = self.dictionary[np.random.choice([0, 7, 9, 10, 12, 13, 14, 17, 19])]
                                else:
                                    seq_i = self.dictionary[np.random.choice(20, p=self.freq[:, i])]
                            else:
                                seq_i = self.dictionary[np.random.choice(20, p=self.freq[:, i])]
                        seq[i] = seq_i
                        seq_peptide = one_hot_encoding(seq)
                        databank_file = os.path.join(dir_tcr, file_tcr)
                        target_similarities = max(calculate_similarity(seq_peptide, databank_file))
                    if target_similarities >= booster_num / len(args.TCR_loss_pos.split("_")):
                        break
            else:
                seq = list(seq.values())
                for i in loc:
                    seq_i = seq[i]
                    while seq_i == seq[i]:
                        if args.rest_mut_pos is not None:
                            if i in [_ - 1 for _ in list(map(int, args.rest_mut_pos.split("_")))]:
                                seq_i = self.dictionary[np.random.choice([0, 7, 9, 10, 12, 13, 14, 17, 19])]
                            else:
                                seq_i = self.dictionary[np.random.choice(20, p=self.freq[:, i])]
                        else:
                            seq_i = self.dictionary[np.random.choice(20, p=self.freq[:, i])]
                    seq[i] = seq_i
        return dict(zip(np.linspace(0, 8, 9, dtype=int), seq))

    def select_position(self, n_mutations):
        if args.fre_mut_pos is None:
            raise TypeError("fre_mut_pos should not be None")
        frepos = list(map(int, args.fre_mut_pos.split("_")))
        if args.rest_mut_pos is None:
            mutpos = frepos
        else:
            frepos.extend(list(map(int, args.rest_mut_pos.split("_"))))
            mutpos = frepos
        mut_loc = np.random.choice(list(set(mutpos)), n_mutations, replace=False)
        return [i - 1 for i in mut_loc]

    def mutate(self, mut_loc):
        return self.generate_loc(mut_loc, seq=self.seq)

    def find_key(self, val):
        return list(key for key, value in self.dictionary.items() if value == val)

    def change_freq(self, rate, loc, seq, accepted):
        if accepted:
            for i in loc:
                key = self.find_key(seq[i])
                self.freq[key, loc] *= 1 + rate
        else:
            for i in loc:
                key = self.find_key(seq[i])
                self.freq[key, loc] *= 1 - rate * 0.25


# ─────────────────────────────────────────────
#  Programmatic entry point (used by tools/mcmc_optimizer.py)
# ─────────────────────────────────────────────

def run_immuneai(start_pep: str, hla_type: str, steps: int, config: dict) -> dict:
    """
    Run ImmuneAI simulated-annealing optimization without CLI.

    Returns:
        {"final_sequence": str, "final_loss": float}
    """
    from types import SimpleNamespace
    import importlib

    # Ensure immuneai dir is on sys.path
    immuneai_dir = str(Path(__file__).parent)
    if immuneai_dir not in sys.path:
        sys.path.insert(0, immuneai_dir)

    # Build custom args object
    custom_args = SimpleNamespace(
        l=9,
        start_pep=start_pep,
        start_fre=None,
        frequency_weight="1_1",
        rest_mut_pos=None,
        fre_mut_pos="1_2_3_4_5_6_7_8_9",
        o=str(Path(config.get("output_dir", "/tmp/immuneai_out")) / start_pep),
        verbose=False,
        mutation_rate=config.get("mcmc_mutation_rate", "3-1"),
        T_init=float(config.get("mcmc_temperature", 0.025)),
        half_life=float(config.get("mcmc_half_life", 1000.0)),
        steps=int(steps),
        mutant_times=10,
        metropolis_hasting=False,
        add_booster=False,
        booster_num=3,
        nomemory=False,
        freqnotchange=False,
        TCR_loss_pos="1_2_3_4_5_6_7_8_9",
        cdr_sequence=None,
        weight_cdr_dis=0.1,
        weight_cdr=2.0,
        weight_iedb=0.05,
        frequence_change_rate=0.1,
        tolerance=None,
    )

    # Inject custom args into module globals
    import Loss as loss_mod
    import process as process_mod
    import main as main_mod
    loss_mod.args = custom_args
    process_mod.args = custom_args
    main_mod.args = custom_args

    # Resolve data directory
    data_dir = Path(config.get("immuneai_data_dir",
                               Path(__file__).parent.parent.parent / "data" / "immuneai"))

    os.makedirs(custom_args.o, exist_ok=True)

    # Load frequency matrices
    iedb_freqmat, _ = get_freq(str(data_dir), "pHLA-A0201--peptide.txt", custom_args.l)
    prob_ref_freqmat, _ = get_freq(str(data_dir), "tcr-specific--peptide.txt", custom_args.l)

    AA_freq_mat = init_frequency_matrix(custom_args, AA_freq, iedb_freqmat)

    pep = peptide(length=custom_args.l, aa_freq_mat=AA_freq_mat)

    logfilename = os.path.join(custom_args.o, f"{start_pep}_Details_logfile.txt")
    freqmatfilename = os.path.join(custom_args.o, f"{start_pep}_Frequencymap.txt")

    print_initial_frequency_matrix(custom_args, AA_freq_mat, AA_freq.keys(), logfilename)

    final_seq, final_loss = Simulated_Annealing(
        custom_args, pep, iedb_freqmat, prob_ref_freqmat, logfilename, freqmatfilename,
        verbose=False,
    )

    return {"final_sequence": final_seq, "final_loss": float(final_loss)}


def main():
    if not os.path.exists(args.o):
        os.makedirs(args.o)

    logfile_dir = os.path.join(args.o)
    finame = args.start_pep if args.start_pep else "random"
    logfilename = os.path.join(logfile_dir, finame + "_Details_logfile.txt")
    freqmat_dir = logfile_dir
    freqmatfilename = os.path.join(freqmat_dir, finame + "_Frequencymap.txt")

    iedb_freqmat, _ = get_freq(dir_iedb, file_iedb, args.l)
    prob_ref_freqmat, _ = get_freq(dir_tcr, file_tcr, args.l)

    AA_freq_mat = init_frequency_matrix(args, AA_freq, iedb_freqmat)
    print_initial_frequency_matrix(args, AA_freq_mat, AA_freq.keys(), logfilename)

    pep = peptide(length=args.l, aa_freq_mat=AA_freq_mat)
    Simulated_Annealing(args, pep, iedb_freqmat, prob_ref_freqmat, logfilename, freqmatfilename)


if __name__ == "__main__":
    main()
