// Severity tiers, regex safety net, and merging of model + regex hits.
//
// The model is the primary detector. The regex patterns here are a small, hand-picked
// safety net for canonical formats with 100% precision (AWS keys, JWTs, etc.) so we
// don't depend on the model recognizing every credential variant. Regex hits are
// only added when they don't overlap an existing model span — model wins on overlap.

import type { AlignedSpan } from './aggregate';

export type Tier = 'block' | 'warn';

export interface DetectionSpan {
  start: number;
  end: number;
  label: string;
  value: string;
  source: string;       // 'ner' | 'ner+luhn-override' | 'ner+format-override' | 'regex:<desc>'
  tier: Tier;
  score: number;
}

// Tier mapping for model labels. Anything not listed defaults to 'warn'.
export const NER_TIER: Record<string, Tier> = {
  CREDENTIAL: 'block',
  SSN: 'block',
  CREDIT_CARD: 'block',
  EMAIL: 'warn',
  PHONE: 'warn',
};

export const BLOCK_PATTERNS: Array<{ re: RegExp; label: string; desc: string }> = [
  { re: /AKIA[0-9A-Z]{16}/g,                                                                              label: 'CREDENTIAL', desc: 'AWS access key' },
  { re: /gh[pousr]_[A-Za-z0-9]{30,}/g,                                                                    label: 'CREDENTIAL', desc: 'GitHub token' },
  { re: /sk-ant-api\d+-[A-Za-z0-9_\-]{30,}/g,                                                             label: 'CREDENTIAL', desc: 'Anthropic API key' },
  { re: /eyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+/g,                                       label: 'CREDENTIAL', desc: 'JWT' },
  { re: /(?:postgresql|postgres|mysql|mongodb(?:\+srv)?|redis|amqp):\/\/[^\s"']+:[^\s"'@]+@[^\s"']+/g,    label: 'CREDENTIAL', desc: 'DB connection string' },
  { re: /-----BEGIN [A-Z ]+PRIVATE KEY-----/g,                                                            label: 'CREDENTIAL', desc: 'Private key' },
];

export const WARN_PATTERNS: Array<{ re: RegExp; label: string; desc: string }> = [
  { re: /\bbc1[a-z0-9]{38,87}\b/g,                                                                        label: 'CRYPTO_ADDRESS', desc: 'Bitcoin SegWit' },
  { re: /\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b/g,                                                           label: 'CRYPTO_ADDRESS', desc: 'Bitcoin legacy' },
  { re: /\b0x[a-fA-F0-9]{40}\b/g,                                                                         label: 'CRYPTO_ADDRESS', desc: 'Ethereum / EVM' },
  { re: /\b(?:25[0-5]|2[0-4]\d|1?\d{1,2})(?:\.(?:25[0-5]|2[0-4]\d|1?\d{1,2})){3}\b/g,                    label: 'IP_ADDRESS',     desc: 'IPv4' },
  { re: /\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b/g,                                                   label: 'MAC_ADDRESS',    desc: 'MAC' },
];

export function regexSpans(text: string): DetectionSpan[] {
  const out: DetectionSpan[] = [];
  for (const { re, label, desc } of BLOCK_PATTERNS) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      out.push({ start: m.index, end: m.index + m[0].length, label, value: m[0], source: `regex:${desc}`, tier: 'block', score: 1.0 });
    }
  }
  for (const { re, label, desc } of WARN_PATTERNS) {
    re.lastIndex = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text)) !== null) {
      out.push({ start: m.index, end: m.index + m[0].length, label, value: m[0], source: `regex:${desc}`, tier: 'warn', score: 0.95 });
    }
  }
  return out;
}

const overlaps = (a: { start: number; end: number }, b: { start: number; end: number }) =>
  !(a.end <= b.start || b.end <= a.start);

export function mergeNerAndRegex(text: string, nerSpans: AlignedSpan[], regexHits: DetectionSpan[]): DetectionSpan[] {
  const ner: DetectionSpan[] = nerSpans.map((s) => ({
    start: s.start,
    end: s.end,
    label: s.label,
    value: text.slice(s.start, s.end),
    source: 'ner',
    tier: NER_TIER[s.label] ?? 'warn',
    score: s.score,
  }));

  // Regex hits are kept only when they don't overlap an existing NER span — the
  // model wins on overlap. Regex is a safety net for canonical formats the model
  // wasn't explicitly trained on, not a boundary corrector for the model.
  const extra = regexHits.filter((r) => !ner.some((n) => overlaps(r, n)));
  return [...ner, ...extra].sort((a, b) => a.start - b.start);
}
