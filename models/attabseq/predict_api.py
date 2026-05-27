"""
Clean inference API for AttABseq model.

Usage:
    from models.attabseq.predict_api import predict_ddg_batch
    results = predict_ddg_batch([{"wt_ab": "...", "mut_ab": "...", "wt_ag": "...", "mut_ag": "..."}], config)
"""
import sys
from pathlib import Path
from typing import List, Dict

import torch
import numpy as np

_ATTABSEQ_DIR = Path(__file__).parent
if str(_ATTABSEQ_DIR) not in sys.path:
    sys.path.insert(0, str(_ATTABSEQ_DIR))

from model import (
    Encoder, Decoder, Predictor, DecoderLayer,
    SelfAttention, PositionwiseFeedforward, pack, Tester,
)

_model_cache: Dict[str, object] = {}

AAS = "ARNDCQEGHILKMFPSTWYV"
_AA_TO_IDX = {aa: i for i, aa in enumerate(AAS)}


def _sequence_to_onehot(sequence: str) -> np.ndarray:
    """One-hot encode a protein sequence (20-dim per residue). Used as PSSM fallback."""
    arr = np.zeros((len(sequence), 20), dtype=np.float32)
    for i, aa in enumerate(sequence.upper()):
        if aa in _AA_TO_IDX:
            arr[i, _AA_TO_IDX[aa]] = 1.0
    return arr


def _load_model(model_path: str, device) -> object:
    key = str(model_path)
    if key not in _model_cache:
        hid_dim = 256
        encoder = Encoder(
            protein_dim=20, hid_dim=hid_dim, n_layers=3,
            kernel_size=7, dropout=0.1, device=device,
        )
        decoder = Decoder(
            atom_dim=20, hid_dim=hid_dim, n_layers=3, n_heads=8,
            pf_dim=64, decoder_layer=DecoderLayer,
            self_attention=SelfAttention,
            positionwise_feedforward=PositionwiseFeedforward,
            dropout=0.1, device=device,
        )
        model = Predictor(encoder, decoder, device, ags_dim=20)
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.to(device)
        model.eval()
        _model_cache[key] = model
    return _model_cache[key]


def predict_ddg_batch(samples: List[Dict], config: dict) -> List[float]:
    """
    Predict ddG for a batch of wildtype/mutant sequence pairs.

    Args:
        samples: list of dicts, each with keys "wt_ab", "mut_ab", "wt_ag", "mut_ag"
        config: project CONFIG dict (must have "attabseq_model" key)

    Returns:
        list of float ddG values (one per sample)
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model_path = str(config["attabseq_model"])
    model = _load_model(model_path, device)
    tester = Tester(model)

    dataset = [
        (
            _sequence_to_onehot(s["wt_ag"]),
            _sequence_to_onehot(s["wt_ab"]),
            _sequence_to_onehot(s["mut_ag"]),
            _sequence_to_onehot(s["mut_ab"]),
            0.0,
        )
        for s in samples
    ]

    _, _, _, _, _, _, _, y_pred = tester.test(dataset, itera=0)
    return [float(v) for v in y_pred]


def predict_ddg(
    wt_ab_sequence: str,
    mut_ab_sequence: str,
    wt_ag_sequence: str,
    mut_ag_sequence: str,
    config: dict,
) -> float:
    """Single-sample convenience wrapper around predict_ddg_batch."""
    results = predict_ddg_batch(
        [{"wt_ab": wt_ab_sequence, "mut_ab": mut_ab_sequence,
          "wt_ag": wt_ag_sequence, "mut_ag": mut_ag_sequence}],
        config,
    )
    return results[0]
