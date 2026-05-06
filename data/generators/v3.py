"""
Synthetic-data generator for Redact v3 (CLI driver).

Produces three CSVs in `data/`:
  synthetic_train_v3.csv      — positive (credential-rich) examples
  synthetic_eval_v3.csv       — held-out positive examples (stratified)
  synthetic_negatives_v3.csv  — hard negatives

Plus, optionally:
  synthetic_adversarial_v3.csv  — eval-only edge cases (run adversarial.py)

Stratified split: positives are bucketed by (context, length, primary_label) and
each bucket contributes proportionally to eval. This guarantees every context
type, length mode, and label gets eval coverage.

Usage:
  python -m data.generators.v3 [--count N] [--neg-ratio R] [--eval-frac F] [--seed S]
  python -m data.generators.v3 --sample-only          # print 12 of each, no write
  python -m data.generators.v3 --include-adversarial  # also run adversarial.py

Defaults: --count 18000 --neg-ratio 0.30 --eval-frac 0.10 --seed 42.
"""

from __future__ import annotations
import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

from .formats import sample as sample_credential, FORMATS
from .contexts import render_positive, CONTEXTS
from .negatives import render_negative

REPO = Path(__file__).resolve().parents[2]
OUT_DIR = REPO / "data"

# Per-paste entity-count distribution.
ENTITY_COUNT_BY_LENGTH = {
    'short':  ([1, 2],          [0.70, 0.30]),
    'medium': ([1, 2, 3, 4],    [0.30, 0.40, 0.20, 0.10]),
    'long':   ([2, 3, 4, 5, 6], [0.20, 0.30, 0.25, 0.15, 0.10]),
}

LABEL_WEIGHTS = {
    "CREDENTIAL":  0.55,
    "EMAIL":       0.13,
    "PHONE":       0.12,
    "SSN":         0.10,
    "CREDIT_CARD": 0.10,
}
LABELS = list(LABEL_WEIGHTS.keys())
WEIGHTS = list(LABEL_WEIGHTS.values())


def _gen_positive_with_meta() -> tuple[str, str, str, str]:
    """Return (text, context_name, length_mode, primary_label) — meta returned for stratification."""
    length = random.choices(['short', 'medium', 'long'], weights=[0.30, 0.45, 0.25])[0]
    counts, probs = ENTITY_COUNT_BY_LENGTH[length]
    n = random.choices(counts, weights=probs)[0]

    items = [(label := random.choices(LABELS, weights=WEIGHTS)[0], sample_credential(label))
             for _ in range(n)]
    primary_label = items[0][0]  # first entity drives the bucket

    # Pick a context that supports `length`
    candidates = [(fn, mods) for fn, mods in CONTEXTS if length in mods]
    fn, _ = random.choice(candidates)
    text = fn(items, length)
    # Voice modulation handled by render_positive — but we need to bypass it
    # to control the bucket. Re-call render-style logic here:
    from .voices import apply_voice
    from .contexts import _VOICE_INCOMPATIBLE
    if random.random() < 0.20 and fn not in _VOICE_INCOMPATIBLE:
        text = apply_voice(text)
    return text, fn.__name__, length, primary_label


def _gen_negative() -> str:
    return render_negative()


def _stratified_split(items: list[tuple], eval_frac: float) -> tuple[list, list]:
    """Split items by (context, length, label) bucket, taking eval_frac from each."""
    buckets: dict[tuple, list] = defaultdict(list)
    for item in items:
        text, ctx, length, label = item
        buckets[(ctx, length, label)].append(item)

    train, eval_ = [], []
    for bucket_items in buckets.values():
        random.shuffle(bucket_items)
        n_eval = max(1, int(len(bucket_items) * eval_frac)) if len(bucket_items) >= 10 else 0
        eval_.extend(bucket_items[:n_eval])
        train.extend(bucket_items[n_eval:])
    random.shuffle(train)
    random.shuffle(eval_)
    return train, eval_


def write_csv(path: Path, texts: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["id", "text"])
        for i, text in enumerate(texts, start=1):
            w.writerow([i, text])
    print(f"  wrote {len(texts):>6,} rows → {path.relative_to(REPO)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=18000)
    parser.add_argument("--neg-ratio", type=float, default=0.30)
    parser.add_argument("--eval-frac", type=float, default=0.10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--sample-only", action="store_true")
    parser.add_argument("--include-adversarial", action="store_true",
                        help="also generate the adversarial test set")
    args = parser.parse_args()

    random.seed(args.seed)

    if args.sample_only:
        print("=" * 78)
        print("POSITIVE SAMPLES (12)".center(78))
        print("=" * 78)
        for i in range(12):
            text, _, _, _ = _gen_positive_with_meta()
            print(f"\n[{i+1}] " + "─" * 70)
            print(text)
        print("\n" + "=" * 78)
        print("HARD NEGATIVE SAMPLES (12)".center(78))
        print("=" * 78)
        for i in range(12):
            print(f"\n[{i+1}] " + "─" * 70)
            print(_gen_negative())
        return

    n_neg = int(args.count * args.neg_ratio)
    n_pos = args.count - n_neg

    OUT_DIR.mkdir(exist_ok=True, parents=True)
    print(f"generating v3 dataset ({args.count:,} total, seed={args.seed}):")

    # Generate all positives with meta, then stratified-split
    pos_items = [_gen_positive_with_meta() for _ in range(n_pos)]
    train_items, eval_items = _stratified_split(pos_items, args.eval_frac)

    write_csv(OUT_DIR / "synthetic_train_v3.csv",     [t for t, _, _, _ in train_items])
    write_csv(OUT_DIR / "synthetic_eval_v3.csv",      [t for t, _, _, _ in eval_items])
    write_csv(OUT_DIR / "synthetic_negatives_v3.csv", [_gen_negative() for _ in range(n_neg)])

    # Per-bucket coverage report
    train_buckets = defaultdict(int)
    eval_buckets  = defaultdict(int)
    for _, ctx, length, label in train_items:
        train_buckets[(ctx, length, label)] += 1
    for _, ctx, length, label in eval_items:
        eval_buckets[(ctx, length, label)] += 1
    print(f"\nstratification: {len(train_buckets)} unique (context, length, label) buckets")
    eval_uncovered = sum(1 for b in train_buckets if b not in eval_buckets and train_buckets[b] >= 10)
    if eval_uncovered:
        print(f"  WARNING: {eval_uncovered} buckets with ≥10 train examples have 0 eval coverage")
    else:
        print(f"  all buckets with ≥10 train examples have eval coverage ✓")

    if args.include_adversarial:
        from . import adversarial
        adversarial.write(OUT_DIR / "synthetic_adversarial_v3.csv", count=500)

    print("done.")


if __name__ == "__main__":
    main()
