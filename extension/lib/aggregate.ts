// BIO aggregation + character-offset alignment for token-classification output.
//
// Why this file exists: transformers.js v4 finally implements `aggregation_strategy`
// for token-classification, but its pipeline still does NOT return character offsets
// (`// TODO: Add support for start and end` is still in the released source as of
// v4.2.0). We need offsets to do `text.slice(start, end)` for redaction, so we run
// the pipeline with raw per-token output and do alignment + BIO collapse here.
//
// Delete this file the day transformers.js ships offset_mapping for the JS tokenizer.
//
// Algorithm:
//   1. Pipeline returns one row per non-O sub-token: `{ entity, score, index, word }`.
//      `word` is what `tokenizer.decode([id])` produced — already lowercased for
//      uncased BERT, with `##` prefixes for WordPiece continuations.
//   2. Walk a cursor through `text.toLowerCase()`. For each token:
//        - if word starts with '##' → glue: match `word.slice(2)` at cursor (no whitespace skip)
//        - else → skip whitespace, then match `word` at cursor
//      The match advances the cursor and gives us [start, end) for the token.
//   3. Collapse consecutive aligned tokens into spans following the canonical "simple"
//      BIO rule: `B-X` (or any change of tag, defensively) opens a new group; `I-X`
//      with the same tag extends the current group; everything else closes.

export interface AlignedSpan {
  start: number;
  end: number;
  label: string;     // tag without B-/I- prefix (e.g. "CREDENTIAL")
  score: number;     // mean of contributing sub-token scores
}

interface RawToken {
  entity: string;    // e.g. "B-CREDENTIAL", "I-EMAIL", "O"
  score: number;
  index: number;
  word: string;
}

// Split a BIO/BIOES tag into [prefix, label]. Tokens that don't match the BIO
// shape are treated as "I-<entity>" so a model emitting bare class names still
// aggregates sensibly.
function splitTag(entity: string): [prefix: 'B' | 'I', label: string] {
  if (entity.length > 2 && entity[1] === '-' && (entity[0] === 'B' || entity[0] === 'I')) {
    return [entity[0] as 'B' | 'I', entity.slice(2)];
  }
  return ['I', entity];
}

// Align one sub-token to the source text starting from `cursor`.
// Returns the aligned [start, end) range, or null if the word can't be found
// (which signals tokenizer/source drift — the caller should skip the token).
function alignToken(
  source: string,
  sourceLower: string,
  cursor: number,
  word: string,
): { start: number; end: number } | null {
  const isContinuation = word.startsWith('##');
  const needle = isContinuation ? word.slice(2) : word;
  if (!needle) return null;

  // For continuation pieces, match exactly at the cursor (no whitespace skip).
  if (isContinuation) {
    if (sourceLower.startsWith(needle, cursor)) {
      return { start: cursor, end: cursor + needle.length };
    }
    // Tolerate a single misalignment by searching forward a short window.
    const found = sourceLower.indexOf(needle, cursor);
    if (found >= 0 && found - cursor < 8) {
      return { start: found, end: found + needle.length };
    }
    return null;
  }

  // Word-initial pieces: scan forward from cursor for the next match.
  // We use indexOf rather than skipping whitespace by hand because BERT's basic
  // tokenizer also splits on punctuation, so the gap between subwords can be
  // arbitrary characters (spaces, commas, parens, etc.).
  const found = sourceLower.indexOf(needle, cursor);
  if (found < 0) return null;
  return { start: found, end: found + needle.length };
}

// Per-subword confidence floor. Aligned tokens below this score are dropped before
// grouping. Lower than the post-aggregation block/warn thresholds (0.85 / 0.70)
// because those apply to whole-span averages — this one is per-piece and exists
// purely to trim low-confidence drift at span edges. A real entity has its
// interior tokens well above 0.5; the model's confidence sags only when it's
// reaching past the actual value into surrounding context.
const PER_TOKEN_SCORE_FLOOR = 0.5;

// Connector words that appear inside over-grouped spans but rarely inside a real
// entity. When the model labels "OPENAI_KEY=foo and DATABASE_URL=bar" as one
// CREDENTIAL span, the literal " and " is a strong signal that two unrelated
// regions got fused. We split the span there. Whitespace padding is required so
// we don't false-trigger on substrings (e.g. "andrew", "foreign").
const CONNECTOR_RE = /\s+(?:and|or|then|with|plus)\s+|\s+-\s+/gi;

export function aggregateBio(rawOutput: RawToken[], source: string): AlignedSpan[] {
  if (rawOutput.length === 0) return [];

  const sourceLower = source.toLowerCase();
  let cursor = 0;

  // Step 1: align each token, dropping any we can't place AND any whose
  // confidence is below the per-token floor (see above).
  type Aligned = { start: number; end: number; prefix: 'B' | 'I'; label: string; score: number };
  const aligned: Aligned[] = [];
  for (const tok of rawOutput) {
    const [prefix, label] = splitTag(tok.entity);
    if (label === 'O') continue;
    if (tok.score < PER_TOKEN_SCORE_FLOOR) continue;

    const span = alignToken(source, sourceLower, cursor, tok.word);
    if (!span) continue;

    aligned.push({ start: span.start, end: span.end, prefix, label, score: tok.score });
    cursor = span.end;
  }

  // Step 2: BIO collapse. Open a new group on B-* or label change; otherwise extend.
  const groups: AlignedSpan[] = [];
  let scoreSum = 0;
  let scoreCount = 0;

  for (const tok of aligned) {
    const open = groups[groups.length - 1];
    const continues = open && tok.prefix === 'I' && tok.label === open.label;

    if (continues) {
      open.end = tok.end;
      scoreSum += tok.score;
      scoreCount += 1;
      open.score = scoreSum / scoreCount;
    } else {
      scoreSum = tok.score;
      scoreCount = 1;
      groups.push({ start: tok.start, end: tok.end, label: tok.label, score: tok.score });
    }
  }

  // Step 3: trim each span's edges. The model frequently includes adjacent
  // whitespace, equals signs, or colons in its predicted span (e.g. labeling
  // `KEY=value` as one CREDENTIAL when only `value` is the secret). Trimming
  // is purely cosmetic — it doesn't drop tokens, just narrows the [start, end)
  // to the inner literal so the redaction marker sits where the user expects.
  for (const g of groups) {
    while (g.start < g.end && /[\s=:,;"']/.test(source[g.start])) g.start += 1;
    while (g.end > g.start && /[\s=:,;"']/.test(source[g.end - 1])) g.end -= 1;
  }

  // Step 4: split spans on English connector words. The model occasionally fuses
  // two unrelated entities into one span when they sit in similar contexts
  // ("KEY=foo and OTHER_KEY=bar"). A literal " and "/" or "/" - " inside a
  // span is a much stronger signal of mis-grouping than of a real multi-word
  // credential, so we cut there and let edge-trim re-tighten each piece.
  const split: AlignedSpan[] = [];
  for (const g of groups) {
    const inner = source.slice(g.start, g.end);
    CONNECTOR_RE.lastIndex = 0;
    let lastCut = 0;
    let m: RegExpExecArray | null;
    const cuts: Array<{ start: number; end: number }> = [];
    while ((m = CONNECTOR_RE.exec(inner)) !== null) {
      cuts.push({ start: lastCut, end: m.index });
      lastCut = m.index + m[0].length;
    }
    if (cuts.length === 0) {
      split.push(g);
      continue;
    }
    cuts.push({ start: lastCut, end: inner.length });
    for (const c of cuts) {
      let s = g.start + c.start;
      let e = g.start + c.end;
      while (s < e && /[\s=:,;"']/.test(source[s])) s += 1;
      while (e > s && /[\s=:,;"']/.test(source[e - 1])) e -= 1;
      if (e > s) split.push({ start: s, end: e, label: g.label, score: g.score });
    }
  }

  return split.filter((g) => g.end > g.start);
}
