// Per-site adapters for the chat hosts we support.
//
// The content script is injected by the browser based on each site's `matches`
// URL patterns (MV3 content_scripts), so it only runs on the chat UI page —
// not the whole domain (marketing, settings, etc.). Once a paste fires, the
// adapter for `location.hostname` is used to re-insert the cleaned text.
//
// Why so little per-site code?
//   - The paste event itself is captured at `document` level and gives us
//     `e.target` (the focused input) directly. No DOM lookup needed for
//     interception.
//   - Re-insertion is handled by `insertIntoEditor()` below, which already
//     covers textarea / contenteditable / Lexical / ProseMirror via a
//     execCommand → DataTransfer fallback chain.
//   - So an adapter typically just needs `findInput` (a fallback for the
//     rare case `e.target` is null) and `insertText` (often just the
//     generic helper). Specific selectors only earn their keep when a site
//     has a quirky editor that benefits from being found directly.

export interface SiteAdapter {
  /** Fallback locator for the chat input when the paste event's `e.target` is missing. */
  findInput: () => HTMLElement | null;
  /** Write the (possibly redacted) text back into the input element. */
  insertText: (el: HTMLElement, text: string) => void;
}

// ── Shared insertion helper ─────────────────────────────────────────────────
// Insert text at the current cursor position, like a normal paste would.
// Does NOT replace existing input contents — preserves what the user already typed.
// Tries methods in order until one works:
//   1. textarea/input — direct value mutation at the selection range
//   2. execCommand('insertText') — supported by Lexical / ProseMirror / Slate
//   3. Synthetic ClipboardEvent('paste') — last-resort fallback for editors
//      that swallow execCommand
export function insertIntoEditor(el: HTMLElement, text: string): void {
  el.focus();

  if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
    const t = el as HTMLTextAreaElement;
    const start = t.selectionStart ?? t.value.length;
    const end = t.selectionEnd ?? t.value.length;
    t.value = t.value.slice(0, start) + text + t.value.slice(end);
    t.selectionStart = t.selectionEnd = start + text.length;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return;
  }

  if (document.execCommand && document.execCommand('insertText', false, text)) return;

  pastePlainText(el, text);
}

// Synthetic ClipboardEvent('paste') fallback. Some editors (Lexical-based
// ones in particular — Perplexity uses one) consume execCommand('insertText')
// but strip embedded newlines because their text-node model doesn't allow them.
// The editor's own paste handler, however, correctly splits multi-line text
// into separate paragraphs/line breaks. So when execCommand would mangle the
// text, dispatching a synthetic paste event preserves structure.
function pastePlainText(el: HTMLElement, text: string): void {
  try {
    const dt = new DataTransfer();
    dt.setData('text/plain', text);
    el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
  } catch {
    // Nothing more we can try — let the editor handle paste natively.
  }
}
// ── Generic input locator ──────────────────────────────────────────────────
// Heuristic used by the shared adapter: pick the visible chat-shaped input
// nearest the bottom of the viewport. Chat inputs are almost always anchored
// to the bottom of the page, so this is a reliable signal across sites.
function findChatInput(): HTMLElement | null {
  const candidates: HTMLElement[] = [];

  // 1. Textareas whose placeholder/aria-label suggests a chat input.
  document.querySelectorAll<HTMLTextAreaElement>('textarea').forEach((t) => {
    const hint = (t.placeholder + ' ' + (t.getAttribute('aria-label') || '')).toLowerCase();
    if (/ask|message|chat|prompt|how can|send|type|reply/.test(hint)) candidates.push(t);
  });

  // 2. Contenteditable with role="textbox" — the modern editor pattern.
  document.querySelectorAll<HTMLElement>('[contenteditable="true"][role="textbox"]')
    .forEach((el) => candidates.push(el));

  // 3. Last resort — any contenteditable.
  if (candidates.length === 0) {
    document.querySelectorAll<HTMLElement>('[contenteditable="true"]')
      .forEach((el) => candidates.push(el));
  }

  let best: HTMLElement | null = null;
  let bestBottom = -Infinity;
  for (const el of candidates) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.bottom > bestBottom) {
      best = el;
      bestBottom = r.bottom;
    }
  }
  return best;
}

// ── Adapters ───────────────────────────────────────────────────────────────
// Hand-tuned: targeted selectors for sites where stable attributes exist.
// Generic: shared fallback that finds the chat input by heuristic.

const GENERIC_ADAPTER: SiteAdapter = {
  findInput: findChatInput,
  insertText: (el, text) => insertIntoEditor(el, text),
};

const CHATGPT_ADAPTER: SiteAdapter = {
  findInput: () =>
    document.querySelector<HTMLElement>('textarea[data-id="root"]') ||
    document.querySelector<HTMLElement>('textarea[placeholder*="Message"]') ||
    document.querySelector<HTMLElement>('div#prompt-textarea[contenteditable="true"]') ||
    findChatInput(),
  insertText: (el, text) => insertIntoEditor(el, text),
};

const CLAUDE_ADAPTER: SiteAdapter = {
  findInput: () =>
    document.querySelector<HTMLElement>('div[contenteditable="true"][role="textbox"]') ||
    document.querySelector<HTMLElement>('div[contenteditable="true"]') ||
    findChatInput(),
  insertText: (el, text) => insertIntoEditor(el, text),
};

const GEMINI_ADAPTER: SiteAdapter = {
  findInput: () =>
    document.querySelector<HTMLElement>('rich-textarea div.ql-editor') ||
    document.querySelector<HTMLElement>('div[contenteditable="true"]') ||
    findChatInput(),
  insertText: (el, text) => insertIntoEditor(el, text),
};

// Perplexity's editor (Lexical-based) strips newlines from execCommand-inserted
// text. Using the synthetic paste event path preserves multi-line structure
// because the editor's own paste handler treats \n as a paragraph break.
const PERPLEXITY_ADAPTER: SiteAdapter = {
  findInput: findChatInput,
  insertText: (el, text) => {
    el.focus();
    pastePlainText(el, text);
  },
};

// ── Site registry ──────────────────────────────────────────────────────────
// Single source of truth: each entry declares the hostnames it covers, the
// MV3 URL match patterns to inject the content script on, and which adapter
// to use. Adding a new site is a one-entry edit.

interface Site {
  /** Human-readable name — used in console logs and comments only. */
  name: string;
  /** `location.hostname` values that route to this adapter at runtime. */
  hostnames: string[];
  /** MV3 `content_scripts.matches` patterns — controls which URLs the
   *  content script is injected on. Narrow these to the chat UI path if
   *  the domain hosts unrelated content (settings, marketing, docs). */
  matches: string[];
  adapter: SiteAdapter;
}

const SITES: Site[] = [
  {
    name: 'ChatGPT',
    hostnames: ['chatgpt.com', 'chat.openai.com'],
    matches: ['https://chatgpt.com/*', 'https://chat.openai.com/*'],
    adapter: CHATGPT_ADAPTER,
  },
  {
    name: 'Claude',
    hostnames: ['claude.ai'],
    matches: ['https://claude.ai/*'],
    adapter: CLAUDE_ADAPTER,
  },
  {
    name: 'Gemini',
    hostnames: ['gemini.google.com'],
    matches: ['https://gemini.google.com/*'],
    adapter: GEMINI_ADAPTER,
  },
  {
    name: 'Perplexity',
    hostnames: ['www.perplexity.ai', 'perplexity.ai'],
    matches: ['https://www.perplexity.ai/*', 'https://perplexity.ai/*'],
    adapter: PERPLEXITY_ADAPTER,
  },
  {
    name: 'Microsoft Copilot',
    hostnames: ['copilot.microsoft.com'],
    matches: ['https://copilot.microsoft.com/*'],
    adapter: GENERIC_ADAPTER,
  },
  {
    name: 'Grok',
    hostnames: ['grok.com'],
    matches: ['https://grok.com/*'],
    adapter: GENERIC_ADAPTER,
  },
  {
    name: 'DeepSeek',
    hostnames: ['chat.deepseek.com'],
    matches: ['https://chat.deepseek.com/*'],
    adapter: GENERIC_ADAPTER,
  },
  {
    name: 'Mistral Le Chat',
    hostnames: ['chat.mistral.ai'],
    matches: ['https://chat.mistral.ai/*'],
    adapter: GENERIC_ADAPTER,
  },
  {
    name: 'Poe',
    hostnames: ['poe.com'],
    matches: ['https://poe.com/*'],
    adapter: GENERIC_ADAPTER,
  },
];

// ── Derived exports (for manifest + runtime) ───────────────────────────────

/** URL patterns for MV3 `host_permissions` and `content_scripts.matches`. */
export const HOST_MATCHES: string[] = SITES.flatMap((s) => s.matches);

const ADAPTER_BY_HOST = new Map<string, SiteAdapter>();
for (const site of SITES) {
  for (const host of site.hostnames) ADAPTER_BY_HOST.set(host, site.adapter);
}

/** Returns the adapter for the current `location.hostname`, or null if unsupported. */
export function getAdapter(): SiteAdapter | null {
  return ADAPTER_BY_HOST.get(location.hostname) ?? null;
}
