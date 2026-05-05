// Safety-critical post-processing for NER spans.
//
// Two jobs only:
//   1. Threshold filter — drop low-confidence model spans before they reach the UI.
//   2. Format overrides — if a span's literal value matches a stricter pattern than
//      the model's label suggests (SSN regex, Luhn-valid credit card), promote the
//      label/tier to the safer one. Conversely, if a span is *labeled* SSN/CC/PHONE
//      but the value can't possibly be that format, drop it as a model mistake.
//
// We deliberately do NOT do any heuristic FP-reduction (stoplists, doc-context
// detection, "looks like an example" checks) — that's the model's job. These rules
// only adjust tier or drop obviously-wrong-shape predictions.

import { NER_TIER, type DetectionSpan } from './tiers';

export const THRESHOLDS = {
  block: 0.85,
  warn: 0.70,
};

const STRICT_SSN = /^\d{3}-\d{2}-\d{4}$/;
const STRICT_CC_DASHED = /^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$/;
const STRICT_CC_UNBROKEN = /^\d{15,16}$/;
const PHONE_LIKE = /(\+\d{1,3}[\s-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}/;

function luhnValid(digitsOnly: string): boolean {
  if (!/^\d{12,19}$/.test(digitsOnly)) return false;
  let sum = 0;
  let double = false;
  for (let i = digitsOnly.length - 1; i >= 0; i--) {
    let d = +digitsOnly[i];
    if (double) {
      d *= 2;
      if (d > 9) d -= 9;
    }
    sum += d;
    double = !double;
  }
  return sum % 10 === 0;
}

// Returns false only for SSN/CC/PHONE values that don't match the canonical shape;
// other labels (CREDENTIAL, EMAIL, regex hits) are accepted as-is.
function matchesExpectedFormat(label: string, value: string): boolean {
  const v = value.trim();
  const digits = v.replace(/[^\d]/g, '');
  switch (label) {
    case 'SSN':         return STRICT_SSN.test(v) || /^\d{9}$/.test(digits);
    case 'CREDIT_CARD': return (STRICT_CC_DASHED.test(v) || STRICT_CC_UNBROKEN.test(v)) && luhnValid(digits);
    case 'PHONE':       return PHONE_LIKE.test(v) || (digits.length >= 10 && digits.length <= 15);
    default:            return true;
  }
}

export function postprocessSpans(spans: DetectionSpan[]): DetectionSpan[] {
  const result: DetectionSpan[] = [];

  for (const s of spans) {
    // Threshold filter applies to NER spans only — regex hits are 100% precision.
    if (s.source.startsWith('ner') && s.score < (THRESHOLDS[s.tier] ?? 0.7)) continue;

    let span = { ...s };

    // Format override: if value clearly matches a stricter category, promote.
    // This catches the model labeling "234-56-7890" as PHONE (warn) when it should
    // be SSN (block) — a silent demotion would be a privacy leak.
    if (span.source === 'ner') {
      const v = span.value.trim();
      const digits = v.replace(/[^\d]/g, '');
      if (STRICT_SSN.test(v)) {
        span.label = 'SSN';
        span.tier = 'block';
        span.source = 'ner+format-override';
      } else if ((STRICT_CC_DASHED.test(v) || STRICT_CC_UNBROKEN.test(v)) && luhnValid(digits)) {
        span.label = 'CREDIT_CARD';
        span.tier = 'block';
        span.source = 'ner+luhn-override';
      }
    }

    // Drop spans whose value can't be the label they claim — model mistake.
    if (span.source.startsWith('ner') && !matchesExpectedFormat(span.label, span.value)) continue;

    span.tier = NER_TIER[span.label] ?? span.tier;
    result.push(span);
  }

  return result;
}
