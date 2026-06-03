# Redact

On-device neural redaction for safe LLM pasting. A Chrome extension that catches sensitive content in pasted text **before** it reaches ChatGPT, Claude, or Gemini — entirely in-browser, nothing leaves your machine.

**Website:** [redact.clearformlabs.com](https://redact.clearformlabs.com)

## Design principle

Redacting too aggressively is worse than redacting too little. If we strip file paths, function names, library names, or error messages from a stack trace, the LLM has nothing left to debug with — the product becomes useless. Every label the model detects has to pass one test: **redacting it should never destroy useful debugging context.**

## What it catches

Five high-signal entity types, mapped to a two-tier UX:

| Tier | Behavior | Labels |
|---|---|---|
| **BLOCK** | Modal — must confirm to proceed | `CREDENTIAL`, `SSN`, `CREDIT_CARD` |
| **WARN** | Banner — auto-dismisses, default-allow | `EMAIL`, `PHONE` |

A small regex safety net (extension-side) adds canonical formats the model wasn't explicitly trained on — `IP_ADDRESS`, `MAC_ADDRESS`, `CRYPTO_ADDRESS`, plus high-precision backstops for AWS keys, GitHub tokens, JWTs, and DB connection strings.

## Architecture

- **Primary detector:** fine-tuned MiniLM token classifier (BIO tagging), 5 entity types × 2 BIO prefixes + O = 11 labels.
- **Regex safety net:** small set of universal-format patterns. Backstop only.
- **Runtime:** ONNX Runtime Web + transformers.js v3 inside a Manifest V3 Chrome extension. Model loads from `chrome-extension://`, never from a CDN.

## Model

| | |
|---|---|
| Base | [`nreimers/MiniLM-L6-H384-uncased`](https://huggingface.co/nreimers/MiniLM-L6-H384-uncased) |
| Params | 22M (6 transformer layers, 384-dim hidden) |
| Architecture | `BertForTokenClassification` |
| Deployed format | ONNX Runtime, INT8 dynamic quantization |
| Deployed size | **23.4 MB** (down from 91.1 MB FP32) |

## Data

Two sources combined into a 19,446-example corpus (17,503 train / 1,943 eval, 90/10 stratified by label):

| Source | Examples | Purpose |
|---|---|---|
| [AI4Privacy PII-Masking-200k](https://huggingface.co/datasets/ai4privacy/pii-masking-200k) | 18,487 | Real-world PII distribution. Filtered to English; only examples with ≥1 of our 5 target labels kept. |
| Synthetic credential corpus | 959 (874 + 85) | Modern API-key formats (`sk-ant-`, `ghp_`, `AKIA`, JWTs, DB URIs) that public NER datasets don't cover. |

The two sources are complementary — AI4Privacy alone has weak credential coverage (its `PASSWORD` label is bank-account-style values, not API tokens); synthetic alone lacks ground-truth distribution for SSN/CC/EMAIL.

## Training

| | |
|---|---|
| Loss | Class-weighted cross-entropy (inverse-frequency, capped at 5×) |
| Epochs | 3 |
| Batch size | 32 (CUDA) / 16 (CPU) |
| Learning rate | 2e-5, weight decay 0.01 |
| Warmup | 10% of total steps |
| Mixed precision | fp16 on CUDA |
| Best-checkpoint metric | F1 (seqeval) |
| Tracking | Weights & Biases (`redact` project) |

## Results

Eval split, AI4Privacy + synthetic combined:

| Step | F1 | Size |
|---|---:|---:|
| `dslim/distilbert-NER` baseline (different task — CoNLL 4-label) | 0.9217 | 264 MB |
| **Fine-tuned MiniLM-L6 (FP32)** | **0.9247** | 91.1 MB |
| ONNX FP32 (max logit Δ vs PyTorch: 4e-6) | — | 91.1 MB |
| **ONNX INT8 (deployed)** | — | **23.4 MB** |

Per-label F1:

| Label | Tier | F1 |
|---|---|---:|
| EMAIL | warn | 0.9772 |
| PHONE | warn | 0.9597 |
| SSN | block | 0.9330 |
| CREDIT_CARD | block | 0.9291 |
| CREDENTIAL | block | 0.8808 |

`CREDENTIAL` is the hardest label — wide format diversity (API keys, passwords, account numbers, connection strings) — and the one most reliant on the synthetic corpus.

## Iteration

| | v1 | v2 (current) |
|---|---|---|
| Labels | 13 | **5** |
| Data | AI4Privacy + broad synthetic | AI4Privacy filtered + credential-rich synthetic |
| F1 | ~0.56 | **0.9247** |
| Failure mode | Dead labels, over-redaction of context (names, IPs) | — |

The v1 → v2 jump came from cutting labels, not from architecture — every label that fails the "redacting it should never destroy useful debugging context" test was removed. v1 is preserved as `notebooks/redact_v1.ipynb` for reference.

## Repo layout

```
Redact/
├── notebooks/
│   ├── redact_v1.ipynb      # Earlier 13-label attempt (reference)
│   └── redact_v2.ipynb      # Current training pipeline
├── data/                    # Synthetic train/eval CSVs
├── checkpoints/             # PyTorch best-of-run weights
├── onnx/                    # FP32 + INT8 ONNX exports
├── extension/               # WXT/Vite Chrome extension (MV3)
└── main.py, pyproject.toml  # uv-managed Python deps
```

The extension is a self-contained subproject — see `extension/README.md` for build instructions.

## Stack

PyTorch · HuggingFace Transformers · seqeval · ONNX Runtime · transformers.js · WXT · Vite · Manifest V3

## Status

CSCI 357 (AI & ML) final project.
