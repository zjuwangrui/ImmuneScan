from pathlib import Path

ROOT = Path(__file__).parent

# LLM configuration (OpenAI-compatible format)
LLM_CONFIG = {
    "model":    "qwen3.6-plus",
    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "api_key":  "your-api-key-here",  # replace with actual key or set OPENAI_API_KEY env var
}

CONFIG = {
    # Model checkpoints
    "attabseq_model":       ROOT / "checkpoints/attabseq/best_pcc_model/model",

    # External tools
    "blast_dir":            ROOT / "blast-2.15.0+/bin",

    # Database paths
    "immuneai_data_dir":    ROOT / "data/immuneai",
    "attabseq_data_dir":    ROOT / "data/attabseq",

    # Optional: RNN model for ImmuneAI structure loss (leave None to skip)
    "rnn_model":            None,

    # MCMC hyperparameters
    "mcmc_steps":           500,
    "mcmc_mutation_rate":   "3-1",
    "mcmc_temperature":     0.025,
    "mcmc_half_life":       1000.0,

    # Pipeline parameters
    "peptide_length":       9,
    "top_n_for_mcmc":       30,
    "top_n_output":         10,

    # Temp output directory for MCMC log files
    "output_dir":           str(ROOT / "tmp_output"),
}
