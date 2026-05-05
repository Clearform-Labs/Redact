// Per-site DOM adapters. Each chat site mounts inputs differently.

export interface SiteAdapter {
  findInput: () => HTMLElement | null;
  findSendButton: () => HTMLElement | null;
  extractText: (el: HTMLElement) => string;
  insertText: (el: HTMLElement, text: string) => void;
}

// Insert text at the current cursor position, like a normal paste would.
// Does NOT replace existing input contents — preserves what the user already typed.
// Tries methods in order until one works:
//   1. execCommand('insertText') — supported by Lexical, ProseMirror, Slate, plain textareas
//   2. Synthetic ClipboardEvent('paste') — fallback for editors that swallow execCommand
export function insertIntoEditor(el: HTMLElement, text: string): void {
  el.focus();

  // Simple <textarea> / <input>: insert at cursor (or replace selection if any)
  if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
    const t = el as HTMLTextAreaElement;
    const start = t.selectionStart ?? t.value.length;
    const end = t.selectionEnd ?? t.value.length;
    t.value = t.value.slice(0, start) + text + t.value.slice(end);
    t.selectionStart = t.selectionEnd = start + text.length;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    return;
  }

  // Contenteditable: insert at cursor. Don't touch existing content.
  if (document.execCommand) {
    const ok = document.execCommand('insertText', false, text);
    if (ok) return;
  }

  // Fallback: synthetic paste event with the cleaned text
  try {
    const dt = new DataTransfer();
    dt.setData('text/plain', text);
    const evt = new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true });
    el.dispatchEvent(evt);
  } catch {
    // Last resort: nothing more to try; let the editor handle it natively
  }
}

export const ADAPTERS: Record<string, SiteAdapter> = {
  'chatgpt.com': {
    findInput: () =>
      document.querySelector<HTMLElement>('textarea[data-id="root"]') ||
      document.querySelector<HTMLElement>('textarea[placeholder*="Message"]') ||
      document.querySelector<HTMLElement>('div#prompt-textarea[contenteditable="true"]'),
    findSendButton: () =>
      document.querySelector<HTMLElement>('button[data-testid="send-button"]') ||
      document.querySelector<HTMLElement>('button[aria-label*="Send"]'),
    extractText: (el) => (el.tagName === 'TEXTAREA' ? (el as HTMLTextAreaElement).value : el.innerText),
    insertText: (el, text) => insertIntoEditor(el, text),
  },

  'chat.openai.com': {
    findInput: () =>
      document.querySelector<HTMLElement>('textarea[data-id="root"]') ||
      document.querySelector<HTMLElement>('textarea[placeholder*="Message"]'),
    findSendButton: () => document.querySelector<HTMLElement>('button[data-testid="send-button"]'),
    extractText: (el) => (el as HTMLTextAreaElement).value,
    insertText: (el, text) => {
      (el as HTMLTextAreaElement).value = text;
      el.dispatchEvent(new Event('input', { bubbles: true }));
    },
  },

  'claude.ai': {
    findInput: () =>
      document.querySelector<HTMLElement>('div[contenteditable="true"][role="textbox"]') ||
      document.querySelector<HTMLElement>('div[contenteditable="true"]'),
    findSendButton: () => document.querySelector<HTMLElement>('button[aria-label*="Send"]'),
    extractText: (el) => el.innerText,
    insertText: (el, text) => insertIntoEditor(el, text),
  },

  'gemini.google.com': {
    findInput: () =>
      document.querySelector<HTMLElement>('rich-textarea div.ql-editor') ||
      document.querySelector<HTMLElement>('div[contenteditable="true"]'),
    findSendButton: () =>
      document.querySelector<HTMLElement>('button[aria-label*="Send message"]') ||
      document.querySelector<HTMLElement>('button[mat-icon-button][aria-label*="Send"]'),
    extractText: (el) => el.innerText,
    insertText: (el, text) => insertIntoEditor(el, text),
  },
};

export const SUPPORTED_HOSTS = Object.keys(ADAPTERS);

export const HOST_MATCHES = SUPPORTED_HOSTS.map((h) => `https://${h}/*`);

export function getAdapter(): SiteAdapter | null {
  return ADAPTERS[location.hostname] || null;
}

// Re-resolves the input element if the site re-mounts it (React rerenders).
export function waitForInput(adapter: SiteAdapter, timeoutMs = 10000): Promise<HTMLElement> {
  return new Promise((resolve, reject) => {
    const found = adapter.findInput();
    if (found) return resolve(found);

    const observer = new MutationObserver(() => {
      const el = adapter.findInput();
      if (el) {
        observer.disconnect();
        resolve(el);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });

    setTimeout(() => {
      observer.disconnect();
      reject(new Error('Input element never appeared'));
    }, timeoutMs);
  });
}
