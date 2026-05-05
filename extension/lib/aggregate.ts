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

export function aggregateBio(rawOutput: RawToken[], source: string): AlignedSpan[] {
  if (rawOutput.length === 0) return [];

  const sourceLower = source.toLowerCase();
  let cursor = 0;

  // Step 1: align each token, dropping any we can't place.
  type Aligned = { start: number; end: number; prefix: 'B' | 'I'; label: string; score: number };
  const aligned: Aligned[] = [];
  for (const tok of rawOutput) {
    const [prefix, label] = splitTag(tok.entity);
    if (label === 'O') continue;

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

  return groups;
}
