// User-configurable behavior. Stored in chrome.storage.sync so it follows
// the user across devices.

export interface RedactSettings {
  enabled: boolean;
  blockBehavior: 'confirm' | 'cooldown' | 'auto-redact';
  cooldownMinutes: number;
  warnBehavior: 'banner' | 'silent';
  warnAutoDismissSec: number;
  siteOverrides: Record<string, Partial<RedactSettings>>;
}

export const DEFAULTS: RedactSettings = {
  enabled: true,
  blockBehavior: 'confirm',
  cooldownMinutes: 5,
  warnBehavior: 'banner',
  warnAutoDismissSec: 5,
  siteOverrides: {},
};

const cooldownState = new Map<string, number>();

export async function loadSettings(): Promise<RedactSettings> {
  const stored = await browser.storage.sync.get(Object.keys(DEFAULTS));
  return { ...DEFAULTS, ...stored } as RedactSettings;
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

export function resetCooldown(hostname: string): void {
  cooldownState.delete(hostname);
}
