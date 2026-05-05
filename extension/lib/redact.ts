// Text redaction helpers.

import type { DetectionSpan } from './tiers';

export function redactSpans(
  text: string,
  spans: DetectionSpan[],
  mask: (label: string) => string = (label) => `[${label}_REDACTED]`,
): string {
  const sorted = [...spans].sort((a, b) => b.start - a.start);
  let out = text;
  for (const s of sorted) {
    out = out.slice(0, s.start) + mask(s.label) + out.slice(s.end);
  }
  return out;
}

export function blockSpans(detections: DetectionSpan[]): DetectionSpan[] {
  return detections.filter((d) => d.tier === 'block');
}

export function warnSpans(detections: DetectionSpan[]): DetectionSpan[] {
  return detections.filter((d) => d.tier === 'warn');
}
