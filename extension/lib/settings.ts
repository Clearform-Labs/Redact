// User-configurable behavior. Stored in chrome.storage.sync so it follows
// the user across devices.

import type { Tier } from './tiers';

// All entity types the user can place in either the block or warn bucket.
// Order matters — drives the popup's per-type row layout.
export const TIER_CONFIGURABLE = [
  'CREDENTIAL', 'SSN', 'CREDIT_CARD', 'EMAIL', 'PHONE',
] as const;

export interface RedactSettings {
  enabled: boolean;
  /**
   *  - 'confirm'     — compact top-of-page prompt (default; non-blocking page).
   *  - 'modal'       — full-screen overlay; page is blocked until user chooses.
   *  - 'cooldown'    — prompt once, then auto-redact for `cooldownMinutes`.
   *  - 'auto-redact' — never prompt; redact silently with an undo toast.
   */
  blockBehavior: 'confirm' | 'modal' | 'cooldown' | 'auto-redact';
  cooldownMinutes: number;
  warnBehavior: 'banner' | 'silent';
  warnAutoDismissSec: number;
  // Per-entity tier overrides. Unset entries fall back to NER_TIER defaults in tiers.ts.
  tierOverrides: Partial<Record<string, Tier>>;
  siteOverrides: Record<string, Partial<RedactSettings>>;
}

export const DEFAULTS: RedactSettings = {
  enabled: true,
  blockBehavior: 'confirm',
  cooldownMinutes: 5,
  warnBehavior: 'banner',
  warnAutoDismissSec: 5,
  tierOverrides: {},
  siteOverrides: {},
};

const cooldownState = new Map<string, number>();

// Migrate legacy stored values from earlier extension versions to the current
// schema. Keep this small and forward-only — we just remap to the new value
// for known renames, never write defaults over user choices.
function migrate(stored: Record<string, unknown>): Record<string, unknown> {
  if (stored.blockBehavior === 'inline-confirm') stored.blockBehavior = 'confirm';
  return stored;
}

export async function loadSettings(): Promise<RedactSettings> {
  const stored = await browser.storage.sync.get(Object.keys(DEFAULTS));
  return { ...DEFAULTS, ...migrate(stored) } as RedactSettings;
}

export async function saveSettings(settings: Partial<RedactSettings>): Promise<void> {
  await browser.storage.sync.set(settings);
}

export async function effectiveSettings(hostname: string): Promise<RedactSettings> {
  const base = await loadSettings();
  const override = base.siteOverrides?.[hostname] || {};
  return { ...base, ...override };
}

export function inCooldown(hostname: string, cooldownMinutes: number): boolean {
  const last = cooldownState.get(hostname);
  if (!last) return false;
  return Date.now() - last < cooldownMinutes * 60 * 1000;
}

export function markCooldown(hostname: string): void {
  cooldownState.set(hostname, Date.now());
}
