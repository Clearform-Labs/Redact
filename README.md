# Redact

On-device neural redaction for safe LLM pasting. A Chrome extension that detects and replaces sensitive entities in text before it reaches an LLM chat — entirely in-browser, nothing leaves your machine.

## What it does

Paste text into the extension before sending it to ChatGPT, Claude, etc. A fine-tuned DistilBERT model runs locally and replaces sensitive spans with consistent, type-appropriate pseudonyms ("Sarah" → "Alice", "Acme Corp" → "Northwind") so the conversation stays readable.

Detected entity types:
- Standard NER: `PERSON`, `ORG`, `LOC`
- Extended: `PROJECT`, `INTERNAL_SYSTEM`, `CREDENTIAL`, `FINANCIAL_FIGURE`

## Architecture

- **Model**: DistilBERT fine-tuned for token classification (BIO tagging), then knowledge-distilled and INT8-quantized via ONNX Runtime for browser inference
- **Why token classification**: deterministic spans, reversible redaction, no hallucinated entities, cheap inference
- **Runtime**: `onnxruntime-web` inside a Chrome Manifest V3 extension

## Data

| Source | Purpose |
|---|---|
| CoNLL-2003 | Standard NER baseline |
| AI4Privacy PII-Masking-200k | Broad PII coverage |
| Microsoft Presidio datasets | Structured PII (SSN, credit cards, phone numbers) |
| Synthetic corporate corpus (~3K train / ~300 eval) | Extended labels; eval split uses a different generator than train |

## Stack

PyTorch · HuggingFace Transformers · ONNX Runtime · Chrome Extension Manifest V3

## Status

CSCI 357 final project — in development.
