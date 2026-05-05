// Web Worker — runs the ONNX token-classifier off the main thread.
//
// Lifecycle: content script sends one `init` message with extension URLs for
// the model and WASM runtime; subsequent `infer` messages return detection spans.
// We keep the worker singleton (one model load per page) by memoizing `nerPipeline`.

import { pipeline, env } from '@huggingface/transformers';
import { aggregateBio, type AlignedSpan } from './aggregate';
import { regexSpans, mergeNerAndRegex, type DetectionSpan } from './tiers';
import { postprocessSpans } from './postprocess';

let modelUrl: string | null = null;
let nerPipeline: any = null;
let initPromise: Promise<any> | null = null;

async function ensureModel() {
  if (nerPipeline) return nerPipeline;
  if (initPromise) return initPromise;

  initPromise = (async () => {
    if (!modelUrl) throw new Error('worker: modelUrl not set — content script must send {type:"init"}');

    // Force everything through extension URLs — never hit the HuggingFace Hub or any CDN.
    env.allowRemoteModels = false;
    env.allowLocalModels = true;
    env.localModelPath = modelUrl;
    env.useBrowserCache = false;

    nerPipeline = await pipeline('token-classification', 'redact-minilm', {
      // q8 → loads `model_quantized.onnx`, our INT8 export. Matches our public/model layout.
      dtype: 'q8',
    });
    return nerPipeline;
  })();

  return initPromise;
}

// Long pastes are chunked to stay under the 512-token model limit. Overlap lets
// an entity straddling a chunk boundary still be detected by at least one chunk.
const CHUNK_CHARS = 1500;
const OVERLAP = 200;

// Pipeline options. transformers.js v3 only accepts `ignore_labels` here — passing
// `aggregation_strategy: 'simple'` is silently ignored (option dropped on the floor).
// That's actually fine for us: we want raw per-subword output anyway, because we do
// BIO grouping ourselves in `aggregateBio` to preserve character offsets, which the
// pipeline does not return. `ignore_labels: []` keeps "O" tokens so cursor alignment
// can advance through non-entity text without losing the trail.
const PIPE_OPTS = { ignore_labels: [] as string[] };

async function inferText(text: string): Promise<DetectionSpan[]> {
  const pipe = await ensureModel();

  let nerSpans: AlignedSpan[];
  if (text.length <= CHUNK_CHARS) {
    const raw = await pipe(text, PIPE_OPTS);
    nerSpans = aggregateBio(raw, text);
  } else {
    const collected: AlignedSpan[] = [];
    let pos = 0;
    while (pos < text.length) {
      const chunk = text.slice(pos, pos + CHUNK_CHARS);
      const raw = await pipe(chunk, PIPE_OPTS);
      const spans = aggregateBio(raw, chunk);
      for (const s of spans) collected.push({ ...s, start: s.start + pos, end: s.end + pos });
      pos += CHUNK_CHARS - OVERLAP;
    }
    nerSpans = dedupeOverlapping(collected);
  }

  const merged = mergeNerAndRegex(text, nerSpans, regexSpans(text));
  return postprocessSpans(merged);
}

// Drops chunk-overlap duplicates: if two same-label spans overlap, keep the
// higher-scoring one. (Aligned spans have real offsets, so this is meaningful.)
function dedupeOverlapping(spans: AlignedSpan[]): AlignedSpan[] {
  spans.sort((a, b) => a.start - b.start || b.score - a.score);
  const out: AlignedSpan[] = [];
  for (const s of spans) {
    const last = out[out.length - 1];
    if (last && last.label === s.label && last.end > s.start) continue;
    out.push(s);
  }
  return out;
}

self.addEventListener('message', async (e: MessageEvent) => {
  const msg = e.data;
  if (msg?.type === 'init') {
    modelUrl = msg.modelUrl;
    if (msg.wasmPaths && env.backends?.onnx?.wasm) {
      // v3 takes wasmPaths as a directory URL (string). The runtime appends the
      // matching `ort-wasm-simd-threaded.jsep.{wasm,mjs}` filenames at load time.
      env.backends.onnx.wasm.wasmPaths = msg.wasmPaths;
    }
    return;
  }
  if (msg?.type === 'infer') {
    try {
      const detections = await inferText(msg.text);
      (self as any).postMessage({ id: msg.id, detections });
    } catch (err: any) {
      (self as any).postMessage({ id: msg.id, error: err?.message || String(err) });
    }
  }
});
