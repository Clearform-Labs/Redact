# Redact — Chrome Extension (WXT)

Catches credentials and PII before pasting into LLM chat boxes (ChatGPT, Claude, Gemini). Runs entirely client-side using a fine-tuned MiniLM model.

Built with [WXT](https://wxt.dev) — modern Manifest V3 framework on top of Vite. Uses [`@huggingface/transformers`](https://www.npmjs.com/package/@huggingface/transformers) v4 for in-browser ONNX inference.

---

## Quick start

```bash
# Install deps. Use --ignore-scripts because transformers.js's sharp dependency
# fails on native build, and we don't need it for browser inference.
npm install --ignore-scripts

# Dev build with auto-rebuild on save. Outputs to .output/chrome-mv3-dev/
npm run dev

# OR a one-time production build
npm run build

# Zip for Chrome Web Store submission
npm run zip
```

After `npm run dev` (or `build`):

1. Open `chrome://extensions` (or your Chromium fork's equivalent — Dia, Brave, Arc all work)
2. Toggle "Developer mode"
3. Click "Load unpacked"
4. Select `extension/.output/chrome-mv3/` (or `chrome-mv3-dev/` if you ran `dev`)
5. Open `chatgpt.com` and paste an AWS key. The BLOCK modal should appear.

---

## Project structure

```
extension/
├── wxt.config.ts             # manifest config, host permissions, runner options
├── package.json
├── tsconfig.json             # extends WXT's auto-generated TS config
├── entrypoints/
│   ├── background.ts         # service worker (placeholder)
│   ├── content.ts            # paste interception + UI (per-site)
│   ├── content.css           # banner + modal styles, prefixed .redact-
│   └── popup/
│       ├── index.html
│       ├── main.ts           # settings UI logic
│       └── style.css         # red-branded popup styles
├── lib/
│   ├── sites.ts              # per-site DOM adapters + SUPPORTED_HOSTS / HOST_MATCHES
│   ├── tiers.ts              # severity tiers, regex safety net, NER+regex merge
│   ├── settings.ts           # chrome.storage.sync wrapper, cooldown state
│   ├── aggregate.ts          # BIO grouping + char-offset alignment for token-cls output
│   ├── postprocess.ts        # threshold + Luhn / strict-format safety overrides
│   ├── redact.ts             # text redaction helpers
│   ├── ui.ts                 # banner / modal / toast rendering
│   └── inference-worker.ts   # Web Worker — loads ONNX model, runs inference
├── public/
│   ├── icon/                 # 16/32/48/128 PNGs (auto-loaded by WXT)
│   ├── wasm/                 # onnxruntime-web runtime (auto-copied by Vite plugin)
│   └── model/redact-minilm/  # trained model + tokenizer (you copy these in)
├── .output/                  # build output (gitignored)
└── .wxt/                     # WXT cache (gitignored)
```

## How it works

1. WXT scans `entrypoints/` and generates `manifest.json` automatically — `content.ts`'s `defineContentScript({ matches: [...] })` becomes the manifest's `content_scripts` entry.
2. The content script runs on the configured chat sites, finds the input element via the per-site adapter in `lib/sites.ts`, and listens for `paste` events.
3. On paste, it spawns a Web Worker (`lib/inference-worker.ts`) — Vite bundles the worker as a separate chunk and resolves its URL at build time.
4. The worker loads the ONNX model from `public/model/redact-minilm/` and the WASM files from `public/wasm/`. transformers.js does the rest.
5. Pipeline returns raw per-token labels → `aggregate.ts` reconstructs BIO spans with char offsets → `tiers.ts` merges in regex safety-net hits → `postprocess.ts` applies threshold + format overrides → rendered as banner/modal/toast based on tier and user settings.

> The aggregator exists because transformers.js v4's pipeline still doesn't return character offsets for token classification (`// TODO: Add support for start and end` in the released source). When that lands upstream, `lib/aggregate.ts` can be deleted in favor of `aggregation_strategy: 'simple'`.

## Model files

The extension expects:

```
public/model/redact-minilm/
├── config.json
├── tokenizer.json
├── tokenizer_config.json
└── onnx/model_quantized.onnx
```

The `onnx/model_quantized.onnx` path matches `dtype: 'q8'` in the pipeline call.

After training, copy from your project root:

```bash
cp checkpoints/best/tokenizer.json \
   checkpoints/best/tokenizer_config.json \
   checkpoints/best/config.json \
   public/model/redact-minilm/
cp ../onnx/redact_minilm_int8.onnx \
   public/model/redact-minilm/onnx/model_quantized.onnx
```

## Settings (popup)

Click the extension icon to configure:

- **Master toggle** — enable/disable Redact globally
- **Block-tier behavior** — confirm every paste / cooldown after first / auto-redact silently
- **Warn-tier behavior** — banner / silent
- **Cooldown duration** — how long auto-redact lasts after first confirm

Settings persist via `chrome.storage.sync` (cross-device).

## Adding a new chat site

Add a new entry to `ADAPTERS` in `lib/sites.ts`. That's it — `host_permissions` (in `wxt.config.ts`) and the content-script `matches` are both derived from `Object.keys(ADAPTERS)` via the exported `HOST_MATCHES`. Restart `npm run dev`.

See [WXT docs on content scripts](https://wxt.dev/guide/key-concepts/content-scripts.html).

## Production build for Chrome Web Store

```bash
npm run build
npm run zip
# Outputs: .output/redact-extension-0.1.0-chrome.zip
```

Upload the zip to https://chrome.google.com/webstore/devconsole. Fill out store listing, submit. Review usually takes 1-3 days.
