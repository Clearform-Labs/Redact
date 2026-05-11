import './style.css';
import { DEFAULTS, loadSettings, saveSettings, TIER_CONFIGURABLE, type RedactSettings } from '@/lib/settings';
import { NER_TIER, type Tier } from '@/lib/tiers';

// Pretty names for per-type rows — kept here (not lib/ui) so the popup stays
// self-contained and doesn't pull in DOM-only content-script helpers.
const PRETTY: Record<string, string> = {
  CREDENTIAL: 'API keys / passwords',
  SSN: 'Social Security numbers',
  CREDIT_CARD: 'Credit cards',
  EMAIL: 'Email addresses',
  PHONE: 'Phone numbers',
};

function effectiveTier(label: string, overrides: RedactSettings['tierOverrides']): Tier {
  return overrides?.[label] ?? NER_TIER[label] ?? 'warn';
}

// Inline SVG logo — matches the icon (red square + white R + black redaction bar).
// Sized for the 36px header slot.
const LOGO_SVG = `
  <svg viewBox="0 0 128 128" xmlns="http://www.w3.org/2000/svg">
    <rect width="128" height="128" rx="28" fill="#dc2626"/>
    <path
      d="M 32 32 L 32 100 L 50 100 L 50 74 L 60 74 L 84 100 L 102 100 L 76 72
         C 92 70, 100 60, 100 52 C 100 38, 90 32, 76 32 Z
         M 50 46 L 76 46 C 82 46, 84 49, 84 52 C 84 56, 82 60, 76 60 L 50 60 Z"
      fill="#ffffff" fill-rule="evenodd"
    />
    <rect x="32" y="108" width="64" height="10" rx="2" fill="#0a0a0a"/>
  </svg>
`;

document.querySelector<HTMLDivElement>('#app')!.innerHTML = `
  <header class="rdct-header">
    <div class="rdct-logo">${LOGO_SVG}</div>
    <div class="rdct-title-block">
      <h1 class="rdct-title">Redact</h1>
      <p class="rdct-subtitle">Privacy guard for LLM chats</p>
    </div>
    <span class="rdct-status" id="rdct-status">
      <span class="rdct-status-dot"></span>
      <span class="rdct-status-text">Active</span>
    </span>
    <label class="rdct-switch">
      <input type="checkbox" id="rdct-enabled" />
      <span class="rdct-slider"></span>
    </label>
  </header>

  <section class="rdct-section">
    <h2 class="rdct-section-title">Sensitivity per type</h2>
    <div class="rdct-tier-grid" id="rdct-tier-grid"></div>
  </section>

  <section class="rdct-section">
    <h2 class="rdct-section-title">When a blocked type is detected</h2>

    <label class="rdct-opt">
      <input type="radio" name="block" value="confirm" />
      <span class="rdct-opt-label">Quick prompt <span class="rdct-opt-tag">default</span></span>
    </label>
    <label class="rdct-opt">
      <input type="radio" name="block" value="modal" />
      <span class="rdct-opt-label">Full-screen block</span>
    </label>
    <label class="rdct-opt">
      <input type="radio" name="block" value="cooldown" />
      <span class="rdct-opt-label">Ask once, then auto-redact for</span>
      <span class="rdct-cooldown-inline">
        <input type="number" id="rdct-cooldown" min="1" max="120" /> min
      </span>
    </label>
    <label class="rdct-opt">
      <input type="radio" name="block" value="auto-redact" />
      <span class="rdct-opt-label">Auto-redact silently</span>
    </label>
  </section>

  <section class="rdct-section">
    <h2 class="rdct-section-title">When a warned type is detected</h2>

    <label class="rdct-opt">
      <input type="radio" name="warn" value="banner" />
      <span class="rdct-opt-label">Show a dismissible banner</span>
    </label>
    <label class="rdct-opt">
      <input type="radio" name="warn" value="silent" />
      <span class="rdct-opt-label">Don't notify me</span>
    </label>
  </section>

  <footer class="rdct-footer">
    <span>v1.0.0 · <code>Redact NER v3.1</code></span>
    <a class="rdct-footer-link" id="rdct-reset">Reset defaults</a>
  </footer>
`;

const $  = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const $$ = (sel: string) => document.querySelectorAll(sel);

function renderTierGrid(overrides: RedactSettings['tierOverrides']) {
  const host = $('rdct-tier-grid');
  host.innerHTML = TIER_CONFIGURABLE.map((label) => {
    const tier = effectiveTier(label, overrides);
    return `
      <div class="rdct-tier-row" data-label="${label}">
        <span class="rdct-tier-name">${PRETTY[label] ?? label}</span>
        <div class="rdct-seg" role="radiogroup" aria-label="${PRETTY[label]} sensitivity">
          <button type="button" class="rdct-seg-btn ${tier === 'block' ? 'is-active' : ''}" data-tier="block">Block</button>
          <button type="button" class="rdct-seg-btn ${tier === 'warn'  ? 'is-active' : ''}" data-tier="warn">Warn</button>
        </div>
      </div>
    `;
  }).join('');
}

async function refresh() {
  const s = await loadSettings();

  $<HTMLInputElement>('rdct-enabled').checked = s.enabled;

  const status = $('rdct-status');
  const statusText = status.querySelector('.rdct-status-text')!;
  status.classList.toggle('is-off', !s.enabled);
  statusText.textContent = s.enabled ? 'Active' : 'Off';

  for (const r of $$('input[name="block"]')) (r as HTMLInputElement).checked = (r as HTMLInputElement).value === s.blockBehavior;
  for (const r of $$('input[name="warn"]'))  (r as HTMLInputElement).checked = (r as HTMLInputElement).value === s.warnBehavior;
  $<HTMLInputElement>('rdct-cooldown').value = String(s.cooldownMinutes);

  renderTierGrid(s.tierOverrides || {});
}

function bind() {
  $<HTMLInputElement>('rdct-enabled').addEventListener('change', async (e) => {
    await saveSettings({ enabled: (e.target as HTMLInputElement).checked });
    refresh();
  });

  for (const r of $$('input[name="block"]')) {
    r.addEventListener('change', async (e) => {
      const t = e.target as HTMLInputElement;
      if (t.checked) await saveSettings({ blockBehavior: t.value as RedactSettings['blockBehavior'] });
    });
  }

  for (const r of $$('input[name="warn"]')) {
    r.addEventListener('change', async (e) => {
      const t = e.target as HTMLInputElement;
      if (t.checked) await saveSettings({ warnBehavior: t.value as RedactSettings['warnBehavior'] });
    });
  }

  $<HTMLInputElement>('rdct-cooldown').addEventListener('change', async (e) => {
    const t = e.target as HTMLInputElement;
    const n = Math.max(1, Math.min(120, parseInt(t.value) || 5));
    t.value = String(n);
    await saveSettings({ cooldownMinutes: n });
  });

  $('rdct-reset').addEventListener('click', async (e) => {
    e.preventDefault();
    await saveSettings(DEFAULTS);
    refresh();
  });

  // Per-type tier segmented buttons. Delegate from the grid container — rows
  // are rerendered on every refresh, so handlers attached per-button would leak.
  $('rdct-tier-grid').addEventListener('click', async (e) => {
    const btn = (e.target as HTMLElement).closest('.rdct-seg-btn') as HTMLButtonElement | null;
    if (!btn) return;
    const row = btn.closest('.rdct-tier-row') as HTMLElement;
    const label = row.dataset.label!;
    const tier = btn.dataset.tier as Tier;

    const s = await loadSettings();
    const next = { ...(s.tierOverrides || {}) };
    // Only persist an override when it differs from the built-in default;
    // matching the default → delete the override so future default changes propagate.
    if (NER_TIER[label] === tier) {
      delete next[label];
    } else {
      next[label] = tier;
    }
    await saveSettings({ tierOverrides: next });
    renderTierGrid(next);
  });
}

refresh();
bind();
