import { defineConfig } from 'wxt';
import { viteStaticCopy } from 'vite-plugin-static-copy';
import { HOST_MATCHES } from './lib/sites';

// WXT generates manifest.json from this config + entrypoints/.
// https://wxt.dev/api/config.html
export default defineConfig({
  manifest: {
    name: 'Redact',
    description: 'Catch credentials and PII before pasting into LLM chat boxes (ChatGPT, Claude, Gemini).',
    version: '0.1.0',
    permissions: ['storage'],
    host_permissions: HOST_MATCHES,
    web_accessible_resources: [
      {
        // assets/* and chunks/* — bundled worker + code-split chunks (Vite output).
        // model/*  — ONNX model + tokenizer files we ship in public/model/.
        // wasm/*   — onnxruntime-web wasm runtime (copied at build time below).
        resources: ['model/*', 'wasm/*', 'assets/*', 'chunks/*'],
        matches: ['https://*/*'],
      },
    ],
  },

  // Auto-launch a browser on `npm run dev` is off — user runs Dia (a Chromium fork)
  // and loads `.output/chrome-mv3-dev/` as unpacked manually.
  webExt: {
    disabled: true,
  },

  // Copy the ONNX Runtime WASM pair into the extension at build time so the worker
  // can load it from chrome-extension:// (not a CDN). Replaces the legacy npm
  // `copy-wasm` script — same effect, but driven by the Vite plugin pipeline so it
  // runs automatically with `wxt build` / `wxt dev`. transformers.js v3 ships these
  // two files in its own dist/.
  //
  // resolve.conditions: opts into onnxruntime-web's `onnxruntime-web-use-extern-wasm`
  // export condition. Without this, Vite picks `dist/ort.bundle.min.mjs`, which
  // inlines the entire 21 MB WASM binary as a base64 string in the JS bundle — even
  // though we override `wasmPaths` to load it from chrome-extension://. With it,
  // Vite picks `dist/ort.min.mjs` (external WASM), and the worker chunk shrinks
  // from ~58 MB back to single-digit MB. See onnxruntime-web/package.json.
  vite: () => ({
    resolve: {
      conditions: ['onnxruntime-web-use-extern-wasm'],
    },
    plugins: [
      viteStaticCopy({
        targets: [{
          src: 'node_modules/@huggingface/transformers/dist/ort-wasm-simd-threaded.jsep.{wasm,mjs}',
          dest: 'wasm',
        }],
      }),
    ],
  }),
});
