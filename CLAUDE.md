# Redact — Project Context

CSCI 357 (AI & ML) final project. A Chrome extension that catches credentials and PII in pasted text *before* it reaches LLM chat boxes (ChatGPT, Claude, Gemini). Inference runs entirely client-side via a fine-tuned MiniLM token-classifier compiled to ONNX (INT8 quantized).

## Repo layout

```
Redact/
├── data/                       # synthetic train/eval CSVs
├── notebooks/                  # redact_v1.ipynb, redact_v2.ipynb (training)
├── checkpoints/                # PyTorch checkpoints
├── onnx/                       # exported ONNX (fp32 + int8) — source of truth
├── main.py, pyproject.toml     # uv-managed Python deps for training
└── extension/                  # WXT (Vite) MV3 extension — what ships
```

## Extension

Built with **WXT 0.20** on top of Vite. Uses **@huggingface/transformers v3.8.1** for in-browser ONNX inference. (We considered v4 and rolled back — see "transformers.js version" below.)

Entry points:
- `entrypoints/content.ts` — paste interception, spawns Worker, drives UI flow
- `entrypoints/background.ts` — service worker, currently a no-op
- `entrypoints/popup/` — settings UI

Key libs:
- `lib/inference-worker.ts` — Web Worker; loads model from `public/model/redact-minilm/`, runs `pipeline('token-classification', ...)` with `aggregation_strategy: 'none'`
- `lib/aggregate.ts` — BIO grouping + char-offset alignment (workaround for transformers.js v4 not exposing offsets yet)
- `lib/tiers.ts` — label→tier map (`block` vs `warn`), regex safety net, `mergeNerAndRegex`
- `lib/postprocess.ts` — threshold filter + Luhn / strict-format safety overrides (no heuristic FP-reduction)
- `lib/sites.ts` — per-site DOM adapters; exports `SUPPORTED_HOSTS` / `HOST_MATCHES` (single source of truth)
- `lib/redact.ts` — replace `[start..end]` with `[LABEL_REDACTED]`
- `lib/ui.ts` — banner / modal / toast
- `lib/settings.ts` — `chrome.storage.sync` wrapper

Model labels (BIO, 11 classes):
`O, B-CREDENTIAL, I-CREDENTIAL, B-EMAIL, I-EMAIL, B-SSN, I-SSN, B-CREDIT_CARD, I-CREDIT_CARD, B-PHONE, I-PHONE`

Tier map (`NER_TIER`): CREDENTIAL/SSN/CREDIT_CARD → `block`; EMAIL/PHONE → `warn`.

## transformers.js version

We're on **v3.8.1**, not v4. v4 didn't gain us anything for our pipeline:

- **`aggregation_strategy: 'simple'`** — added in v4.0.0. Silently ignored in v3.x. We don't use it: even on v4, `'simple'` returns the merged group's `word` from `tokenizer.decode(ids)` which whitespace-separates and strips `##`, breaking literal alignment to the source (`tom@example.com` becomes `"tom @ example. com"`). Subword-level alignment is dramatically easier than re-aligning a denormalized merged string.
- **`start` / `end` char offsets** — missing in BOTH v3 and v4 as of v4.2.0. The released v4 source has `// TODO: Add support for start and end` in `packages/transformers/src/pipelines/token-classification.js`. The standalone `@huggingface/tokenizers` v0.1.3 also doesn't return offsets.

So we run the pipeline (with no aggregation), get raw per-subword `{entity, score, index, word}` rows, and feed them into `lib/aggregate.ts` for offset alignment + BIO collapse. That ~120-line aggregator works identically on v3 and v4. The day transformers.js exposes `offset_mapping` from the tokenizer, `lib/aggregate.ts` can be deleted.

This is **not** a "post-processing heuristic." It's the canonical alignment step the library doesn't expose.

## Build / dev

```bash
cd extension
npm install --ignore-scripts          # sharp build fails; not needed
npm run dev                            # WXT dev → .output/chrome-mv3-dev/
npm run build                          # production → .output/chrome-mv3/
```

Then load `.output/chrome-mv3-dev/` as unpacked in `chrome://extensions`.

`webExt.disabled: true` in `wxt.config.ts` — auto-launch is off because user runs Dia.

## WASM copying + bundle size

Two-part setup in `wxt.config.ts`:

1. **`viteStaticCopy`** copies `ort-wasm-simd-threaded.jsep.{wasm,mjs}` from `node_modules/@huggingface/transformers/dist/` to `.output/<target>/wasm/` at build time. No npm scripts.
2. **`resolve.conditions: ['onnxruntime-web-use-extern-wasm']`** opts into `onnxruntime-web`'s magic export condition that swaps `dist/ort.bundle.min.mjs` (WASM inlined as base64 — 28 MB × 2 copies = ~56 MB of dead weight) for `dist/ort.min.mjs` (external WASM). Without this, Vite picks the bundled variant by default and our worker chunk balloons from ~800 kB to 58 MB even though we override `wasmPaths`.

The worker init message sends `wasmPaths` (string, the directory URL); the runtime appends the `ort-wasm-simd-threaded.jsep.{wasm,mjs}` filenames itself. **Don't add v4-style `{wasm, mjs}` object form — v3 takes a string.**

Final extension size: 25 MB total, of which 23 MB is the ONNX model and 21 MB is the external WASM blob loaded at runtime. JS code is ~2 MB.

## Worker bootstrapping (MV3 quirk)

A content script can't directly `new Worker(chrome-extension://...)` — Chrome blocks it as cross-origin. The workaround in `content.ts`: `fetch()` the worker chunk URL (web_accessible_resources lets this through), wrap in a `Blob`, spawn from `URL.createObjectURL(blob)`. Keep this pattern; do not "simplify" by passing the chrome-extension URL directly.

The worker receives `modelUrl` and `wasmPaths` via the first `init` message — it sets `env.localModelPath` and `env.backends.onnx.wasm.wasmPaths` from those, so the ONNX runtime loads from extension URLs, not the HuggingFace Hub.

## Paste flow

`paste` and `beforeinput` (for Lexical/ProseMirror editors that swallow paste, like Claude) are intercepted at `document` capture phase. If text < 20 chars, skip. Otherwise: `preventDefault`, run inference, render banner/modal/toast based on tier and user settings, then re-insert the (possibly redacted) text into the input via `insertIntoEditor` (execCommand → DataTransfer fallback).

## Don'ts

- Don't add per-site special-casing or stoplists — model is supposed to do the work. Heuristics in `postprocess.ts` are limited to safety overrides (Luhn for CC, strict SSN format) and are kept on purpose.
- Don't bypass the worker — running transformers.js on the main thread blocks the host page.
- Don't load the model from the HuggingFace Hub — `env.allowRemoteModels = false` is intentional (privacy + offline).
