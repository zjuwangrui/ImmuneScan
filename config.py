import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent

CONFIG: dict[str, Any] = {
    # ── LLM (OpenAI-compatible) ──────────────────────────────────────────
    "llm_model":    "qwen3.6-plus",
    "llm_base_url": "https://napi.moretoken.ai/v1",
    "llm_api_key":  os.environ["DASHSCOPE_API_KEY"],

    # ── Model checkpoints ────────────────────────────────────────────────
    "attabseq_model":       ROOT / "checkpoints/attabseq/best_pcc_model/model",

    # ── External tools ───────────────────────────────────────────────────
    "blast_dir":            ROOT / "blast-2.15.0+/bin",

    # ── Database paths ───────────────────────────────────────────────────
    "immuneai_data_dir":    ROOT / "data/immuneai",
    "attabseq_data_dir":    ROOT / "data/attabseq",

    # ── Optional: RNN model for ImmuneAI structure loss ──────────────────
    "rnn_model":            None,

    # ── MCMC hyperparameters ─────────────────────────────────────────────
    "mcmc_steps":           500,
    "mcmc_mutation_rate":   "3-1",
    "mcmc_temperature":     0.025,
    "mcmc_half_life":       1000.0,

    # ── Pipeline parameters ──────────────────────────────────────────────
    "peptide_length":       9,
    "top_n_for_mcmc":       30,
    "top_n_output":         10,

    # ── Input / Output ───────────────────────────────────────────────────
    "input_file":           str(ROOT / "data/input.json"),
    "output_dir":           str(ROOT / "data/output"),
}
