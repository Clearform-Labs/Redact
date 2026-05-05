import './style.css';
import { DEFAULTS, loadSettings, saveSettings, type RedactSettings } from '@/lib/settings';

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
  </header>

  <div class="rdct-master">
    <div>
      <div class="rdct-master-label">Enabled</div>
      <div class="rdct-master-host" id="rdct-host"></div>
    </div>
    <label class="rdct-switch">
      <input type="checkbox" id="rdct-enabled" />
      <span class="rdct-slider"></span>
    </label>
  </div>

  <section class="rdct-section">
    <h2 class="rdct-section-title">When credentials, SSNs, or cards are detected</h2>

    <label class="rdct-opt">
      <input type="radio" name="block" value="confirm" />
      <span class="rdct-opt-text">
        <span class="rdct-opt-label">Always ask me to confirm</span>
        <span class="rdct-opt-desc">Modal pops up every paste. Safest, most interruptive.</span>
      </span>
    </label>

    <label class="rdct-opt">
      <input type="radio" name="block" value="cooldown" />
      <span class="rdct-opt-text">
        <span class="rdct-opt-label">Ask once, then auto-redact for a while</span>
        <span class="rdct-opt-desc">Modal first time. After confirming, future pastes are auto-redacted.</span>
      </span>
    </label>
    <div class="rdct-cooldown-row">
      Cooldown <input type="number" id="rdct-cooldown" min="1" max="120" /> min
    </div>

    <label class="rdct-opt">
      <input type="radio" name="block" value="auto-redact" />
      <span class="rdct-opt-text">
        <span class="rdct-opt-label">Auto-redact silently</span>
        <span class="rdct-opt-desc">No modal. Detected values are replaced with [LABEL_REDACTED] and a toast appears.</span>
      </span>
    </label>
  </section>

  <section class="rdct-section">
    <h2 class="rdct-section-title">When emails, phones, or IPs are detected</h2>

    <label class="rdct-opt">
      <input type="radio" name="warn" value="banner" />
      <span class="rdct-opt-text">
        <span class="rdct-opt-label">Show a dismissible banner</span>
        <span class="rdct-opt-desc">Auto-dismisses; lets you see what was flagged without blocking.</span>
      </span>
    </label>

    <label class="rdct-opt">
      <input type="radio" name="warn" value="silent" />
      <span class="rdct-opt-text">
        <span class="rdct-opt-label">Don't notify me</span>
        <span class="rdct-opt-desc">Detections still logged to console, no UI shown.</span>
      </span>
    </label>
  </section>

  <footer class="rdct-footer">
    <span>v0.1.0 · <code>Redact-NER-v1</code></span>
    <a class="rdct-footer-link" id="rdct-reset">Reset defaults</a>
  </footer>
`;

const $  = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const $$ = (sel: string) => document.querySelectorAll(sel);

async function refresh() {
  const s = await loadSettings();

  $<HTMLInputElement>('rdct-enabled').checked = s.enabled;

  const status = $('rdct-status');
  const statusText = status.querySelector('.rdct-status-text')!;
  status.classList.toggle('is-off', !s.enabled);
  statusText.textContent = s.enabled ? 'Active' : 'Off';

  const host = window.location.hostname || 'all sites';
  $('rdct-host').textContent = `On every supported site`;

  for (const r of $$('input[name="block"]')) (r as HTMLInputElement).checked = (r as HTMLInputElement).value === s.blockBehavior;
  for (const r of $$('input[name="warn"]'))  (r as HTMLInputElement).checked = (r as HTMLInputElement).value === s.warnBehavior;
  $<HTMLInputElement>('rdct-cooldown').value = String(s.cooldownMinutes);
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
}

refresh();
bind();
