// Banner, modal, toast rendering. Scoped via .redact- CSS prefix to avoid host-page collisions.

import type { DetectionSpan } from './tiers';

const STYLE_PREFIX = 'redact-';

// ── Label + value formatting ─────────────────────────────────────────────────
// Internal labels (CREDENTIAL, SSN, ...) → human-friendly names for the UI.
const PRETTY_LABEL: Record<string, string> = {
  CREDENTIAL: 'API key / password',
  SSN: 'Social Security number',
  CREDIT_CARD: 'Credit card',
  EMAIL: 'Email address',
  PHONE: 'Phone number',
  IP_ADDRESS: 'IP address',
  MAC_ADDRESS: 'MAC address',
  CRYPTO_ADDRESS: 'Crypto wallet',
};

function prettyLabel(raw: string): string {
  // Strip any stray B-/I- BIO prefix defensively
  const clean = (raw || '').replace(/^[BI]-/, '');
  return PRETTY_LABEL[clean] ?? clean.toLowerCase().replace(/_/g, ' ');
}

// Mask a sensitive value for display: keep enough characters to recognize it,
// hide the middle. "AKIA4F3JWPQ8N2ZX7V9B" → "AKIA4F3J••••••V9B"
function maskValue(value: string): string {
  const v = (value || '').trim();
  if (v.length <= 6) return '•'.repeat(v.length);
  if (v.length <= 14) return v.slice(0, 2) + '•'.repeat(v.length - 4) + v.slice(-2);
  return v.slice(0, 6) + '•'.repeat(6) + v.slice(-4);
}

// Default auto-dismiss timing (ms) when the caller doesn't override.
// Scales with detection count: more items → more time to read; 10+ requires manual dismiss.
// Bumped from earlier (5/8/12s) — banner was disappearing before users noticed it.
function defaultAutoDismissMs(n: number): number {
  if (n <= 1) return 8000;
  if (n <= 3) return 12000;
  if (n <= 9) return 18000;
  return 0;
}

// Pause an auto-dismiss timer while the user hovers the element. Reading a stack of
// chips takes longer than the static budget, so this keeps the panel up as long as
// the cursor is over it; it resumes on mouseleave with the remaining time.
function attachHoverPause(el: HTMLElement, ms: number, onDismiss: () => void) {
  if (ms <= 0) return;
  let remaining = ms;
  let startedAt = Date.now();
  let timer = window.setTimeout(onDismiss, remaining);
  el.addEventListener('mouseenter', () => {
    window.clearTimeout(timer);
    remaining -= Date.now() - startedAt;
  });
  el.addEventListener('mouseleave', () => {
    if (remaining <= 0) return;
    startedAt = Date.now();
    timer = window.setTimeout(onDismiss, remaining);
  });
}

// ── Loading indicator ────────────────────────────────────────────────────────
export function showLoadingIndicator(): void {
  removeLoadingIndicator();
  const el = document.createElement('div');
  el.id = STYLE_PREFIX + 'loading';
  el.className = STYLE_PREFIX + 'loading';
  el.textContent = 'Redact: scanning paste…';
  document.body.appendChild(el);
}

export function removeLoadingIndicator(): void {
  document.getElementById(STYLE_PREFIX + 'loading')?.remove();
}

// ── Warn banner (top of page) ────────────────────────────────────────────────
// `autoDismissMs` overrides the count-based default; pass 0 to require manual dismiss.
export function showWarnBanner(warnHits: DetectionSpan[], autoDismissMs?: number): void {
  removeWarnBanner();
  const el = document.createElement('div');
  el.id = STYLE_PREFIX + 'warn';
  el.className = STYLE_PREFIX + 'banner ' + STYLE_PREFIX + 'banner-warn';

  const items = warnHits.slice(0, 3).map((h) =>
    `<span class="${STYLE_PREFIX}chip">
       <span class="${STYLE_PREFIX}chip-label">${escapeHtml(prettyLabel(h.label))}</span>
       <code class="${STYLE_PREFIX}chip-value">${escapeHtml(maskValue(h.value))}</code>
     </span>`
  ).join('');
  const more = warnHits.length > 3 ? `<span class="${STYLE_PREFIX}banner-more">+${warnHits.length - 3} more</span>` : '';

  el.innerHTML = `
    <span class="${STYLE_PREFIX}banner-icon">⚠️</span>
    <div class="${STYLE_PREFIX}banner-text">
      <strong>Redact noticed ${warnHits.length} item${warnHits.length === 1 ? '' : 's'} you might want to review</strong>
      <div class="${STYLE_PREFIX}chip-row">${items}${more}</div>
    </div>
    <button class="${STYLE_PREFIX}banner-close" aria-label="Dismiss">×</button>
  `;
  el.querySelector<HTMLButtonElement>(`.${STYLE_PREFIX}banner-close`)!.onclick = () => el.remove();

  // Click banner body (not close button) to expand into details modal
  if (warnHits.length > 3) {
    el.style.cursor = 'pointer';
    el.addEventListener('click', (e) => {
      if ((e.target as HTMLElement).closest(`.${STYLE_PREFIX}banner-close`)) return;
      el.remove();
      showDetailsModal(warnHits, 'WARN — these are flagged but not blocked');
    });
  }

  // If a block toast is already on screen, stack the banner below it so neither
  // covers the other. (CSS handles the actual offset via .redact-stacked.)
  if (document.querySelector(`.${STYLE_PREFIX}toast`)) {
    el.classList.add(`${STYLE_PREFIX}stacked`);
  }

  document.body.appendChild(el);
  const dismissMs = autoDismissMs ?? defaultAutoDismissMs(warnHits.length);
  attachHoverPause(el, dismissMs, () => el.remove());
}

export function removeWarnBanner(): void {
  document.getElementById(STYLE_PREFIX + 'warn')?.remove();
}

// ── Auto-redact toast (bottom-right) ─────────────────────────────────────────
export function showRedactionToast(blockHits: DetectionSpan[]): Promise<'undo' | 'dismissed'> {
  const el = document.createElement('div');
  el.className = STYLE_PREFIX + 'toast ' + STYLE_PREFIX + 'toast-block';

  const items = blockHits.slice(0, 3).map((h) =>
    `<div class="${STYLE_PREFIX}toast-item">
       <span class="${STYLE_PREFIX}chip-label">${escapeHtml(prettyLabel(h.label))}</span>
       <code class="${STYLE_PREFIX}chip-value">${escapeHtml(maskValue(h.value))}</code>
     </div>`
  ).join('');
  const more = blockHits.length > 3 ? `<div class="${STYLE_PREFIX}toast-more">…and ${blockHits.length - 3} more — click to see all</div>` : '';

  el.innerHTML = `
    <div class="${STYLE_PREFIX}toast-header">
      <span class="${STYLE_PREFIX}toast-icon">🚫</span>
      <strong>Auto-redacted ${blockHits.length} item${blockHits.length === 1 ? '' : 's'}</strong>
      <button class="${STYLE_PREFIX}toast-undo">Undo</button>
    </div>
    <div class="${STYLE_PREFIX}toast-list">${items}${more}</div>
  `;

  return new Promise((resolve) => {
    el.querySelector<HTMLButtonElement>(`.${STYLE_PREFIX}toast-undo`)!.onclick = (e) => {
      e.stopPropagation();
      el.remove();
      resolve('undo');
    };
    if (blockHits.length > 3) {
      el.style.cursor = 'pointer';
      el.addEventListener('click', (e) => {
        if ((e.target as HTMLElement).closest(`.${STYLE_PREFIX}toast-undo`)) return;
        el.remove();
        showDetailsModal(blockHits, 'These items were redacted from your paste');
        resolve('dismissed');
      });
    }
    document.body.appendChild(el);
    attachHoverPause(el, defaultAutoDismissMs(blockHits.length), () => {
      if (el.isConnected) {
        el.remove();
        resolve('dismissed');
      }
    });
  });
}

// ── Block modal (interactive — user must choose) ─────────────────────────────
export function showBlockModal(text: string, blockHits: DetectionSpan[]): Promise<'cancel' | 'redact' | 'send-anyway'> {
  return new Promise((resolve) => {
    const modal = document.createElement('div');
    modal.className = STYLE_PREFIX + 'modal-backdrop';
    modal.innerHTML = `
      <div class="${STYLE_PREFIX}modal">
        <h2 class="${STYLE_PREFIX}modal-title">🚫 Sensitive content detected</h2>
        <p class="${STYLE_PREFIX}modal-body">
          This paste contains <strong>${blockHits.length} item${blockHits.length === 1 ? '' : 's'}</strong> that look like secrets or
          personally-identifying values. Sending them to a chatbot can leak them permanently.
        </p>
        <ul class="${STYLE_PREFIX}modal-list">
          ${blockHits.map((h) => `
            <li>
              <span class="${STYLE_PREFIX}modal-label">${escapeHtml(prettyLabel(h.label))}</span>
              <code class="${STYLE_PREFIX}modal-value">${escapeHtml(maskValue(h.value))}</code>
            </li>
          `).join('')}
        </ul>
        <div class="${STYLE_PREFIX}modal-actions">
          <button class="${STYLE_PREFIX}btn ${STYLE_PREFIX}btn-cancel">Cancel paste</button>
          <button class="${STYLE_PREFIX}btn ${STYLE_PREFIX}btn-redact">Redact &amp; paste</button>
          <button class="${STYLE_PREFIX}btn ${STYLE_PREFIX}btn-confirm">Send anyway</button>
        </div>
      </div>
    `;
    const close = (decision: 'cancel' | 'redact' | 'send-anyway') => {
      modal.remove();
      resolve(decision);
    };
    modal.querySelector<HTMLButtonElement>(`.${STYLE_PREFIX}btn-cancel`)!.onclick = () => close('cancel');
    modal.querySelector<HTMLButtonElement>(`.${STYLE_PREFIX}btn-redact`)!.onclick = () => close('redact');
    modal.querySelector<HTMLButtonElement>(`.${STYLE_PREFIX}btn-confirm`)!.onclick = () => close('send-anyway');
    modal.addEventListener('click', (e) => {
      if (e.target === modal) close('cancel');
    });
    document.body.appendChild(modal);
  });
}

// ── Details modal (read-only, used by "click toast/banner to expand") ───────
function showDetailsModal(hits: DetectionSpan[], subtitle: string): void {
  const modal = document.createElement('div');
  modal.className = STYLE_PREFIX + 'modal-backdrop';
  modal.innerHTML = `
    <div class="${STYLE_PREFIX}modal">
      <h2 class="${STYLE_PREFIX}modal-title">Detected ${hits.length} item${hits.length === 1 ? '' : 's'}</h2>
      <p class="${STYLE_PREFIX}modal-body">${escapeHtml(subtitle)}</p>
      <ul class="${STYLE_PREFIX}modal-list">
        ${hits.map((h) => `
          <li>
            <span class="${STYLE_PREFIX}modal-label">${escapeHtml(prettyLabel(h.label))}</span>
            <code class="${STYLE_PREFIX}modal-value">${escapeHtml(maskValue(h.value))}</code>
          </li>
        `).join('')}
      </ul>
      <div class="${STYLE_PREFIX}modal-actions">
        <button class="${STYLE_PREFIX}btn ${STYLE_PREFIX}btn-cancel">Close</button>
      </div>
    </div>
  `;
  modal.querySelector<HTMLButtonElement>(`.${STYLE_PREFIX}btn-cancel`)!.onclick = () => modal.remove();
  modal.addEventListener('click', (e) => { if (e.target === modal) modal.remove(); });
  document.body.appendChild(modal);
}

// ── Helpers ──────────────────────────────────────────────────────────────────
function escapeHtml(s: string): string {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c] as string));
}
