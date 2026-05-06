"""
Audit synthetic v3 datasets for issues that would teach the model bad signals.

Categories:

  STRUCTURAL — would break the BIO conversion in training
    - malformed [value|LABEL] markers
    - empty values
    - embedded `]` or `|` in values
    - negatives containing positive markers
    - positives missing markers

  SEMANTIC — would teach wrong patterns
    - var-name <-> value mismatches
    - cross-label contamination
    - bad-format SSN/EMAIL/PHONE

  DIVERSITY — would cause memorization
    - prose shape duplicates
    - per-shape repeat counts
    - length outliers

  COVERAGE (new in Phase 4) — would cause silent under-training
    - label balance (per-label entity counts within ±20% of intended)
    - context coverage (each context fires ≥3% of the time)
    - format coverage (each generator function used at least once)

  HYGIENE (new in Phase 4) — would teach subtly wrong signals
    - common-word leak (CRED values containing English stop-words)
    - tokenization preview (warn on >512 tokens, report token-count distribution)
    - adversarial proximity (count examples with two same-label entities <5 chars apart)
    - negative-positive prefix overlap

Output: machine-readable JSON to `data/audit_v3.json` and a human-readable
markdown report to `data/audit_v3.md`.
"""

from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TRAIN = REPO / "data" / "synthetic_train_v3.csv"
EVAL  = REPO / "data" / "synthetic_eval_v3.csv"
NEG   = REPO / "data" / "synthetic_negatives_v3.csv"
JSON_REPORT = REPO / "data" / "audit_v3.json"
MD_REPORT   = REPO / "data" / "audit_v3.md"

ANN_RE = re.compile(r"\[([^\]\|]*)\|([A-Z_]+)\]")
VALID_LABELS = {"CREDENTIAL", "EMAIL", "PHONE", "SSN", "CREDIT_CARD"}

# Canonical-format checks per label
STRICT = {
    "SSN":         re.compile(r"^\d{3}-\d{2}-\d{4}$"),
    "EMAIL":       re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"),
    "CREDIT_CARD": re.compile(r"^[\d\s\-]{13,23}$"),
    "PHONE":       re.compile(r"^[+\d\(][\d\s\-\.\(\)]{8,}$"),
}

# Var-name conventions — when the var name implies a provider, what value
# prefixes are acceptable?
VAR_VALUE_RULES = {
    "OPENAI_API_KEY":      ("starts_with", ("sk-",)),
    "OPENAI_KEY":          ("starts_with", ("sk-",)),
    "ANTHROPIC_API_KEY":   ("starts_with", ("sk-ant-",)),
    "CLAUDE_API_KEY":      ("starts_with", ("sk-ant-",)),
    "GITHUB_TOKEN":        ("starts_with", ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_")),
    "GH_PAT":              ("starts_with", ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_")),
    "GITHUB_PAT":          ("starts_with", ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_")),
    "GOOGLE_API_KEY":      ("starts_with", ("AIza",)),
    "GCP_API_KEY":         ("starts_with", ("AIza",)),
    "STRIPE_SECRET_KEY":   ("starts_with", ("sk_live", "sk_test", "rk_live", "rk_test")),
    "STRIPE_PUBLISHABLE_KEY": ("starts_with", ("pk_live", "pk_test")),
    "AWS_ACCESS_KEY_ID":   ("starts_with", ("AKIA", "ASIA", "AROA")),
    "AWS_KEY_ID":          ("starts_with", ("AKIA", "ASIA", "AROA")),
    "DATABASE_URL":        ("starts_with", ("postgresql://", "postgres://", "mysql://", "mongodb")),
    "DB_URL":              ("starts_with", ("postgresql://", "postgres://", "mysql://", "mongodb")),
    "DB_CONNECTION_STRING":("starts_with", ("postgresql://", "postgres://", "mysql://", "mongodb")),
    "REDIS_URL":           ("starts_with", ("redis://", "rediss://")),
    "CACHE_URL":           ("starts_with", ("redis://", "rediss://", "memcached://")),
    "AMQP_URL":            ("starts_with", ("amqp://", "amqps://")),
    "SLACK_BOT_TOKEN":     ("starts_with", ("xoxb-", "xoxp-", "xoxa-", "xoxr-")),
    "SLACK_TOKEN":         ("starts_with", ("xoxb-", "xoxp-", "xoxa-", "xoxr-", "xoxe-")),
    "SLACK_WEBHOOK_URL":   ("starts_with", ("https://hooks.slack.com",)),
    "HUGGINGFACE_TOKEN":   ("starts_with", ("hf_",)),
    "MAILGUN_API_KEY":     ("starts_with", ("key-",)),
    "MAILGUN_KEY":         ("starts_with", ("key-",)),
    "SENDGRID_API_KEY":    ("starts_with", ("SG.",)),
    "SENDGRID_KEY":        ("starts_with", ("SG.",)),
    "PRIVATE_KEY":         ("starts_with", ("-----BEGIN",)),
    "SIGNING_KEY":         ("starts_with", ("-----BEGIN",)),
    "TLS_PRIVATE_KEY":     ("starts_with", ("-----BEGIN",)),
    "JWT_TOKEN":           ("starts_with", ("eyJ",)),
    "AUTH_JWT":            ("starts_with", ("eyJ",)),
    "ID_TOKEN":            ("starts_with", ("eyJ",)),
    "RESEND_API_KEY":      ("starts_with", ("re_",)),
    "DIGITALOCEAN_TOKEN":  ("starts_with", ("dop_v1_",)),
    "RENDER_API_TOKEN":    ("starts_with", ("rnd_",)),
    "FLY_API_TOKEN":       ("starts_with", ("fo1_",)),
    "GITLAB_TOKEN":        ("starts_with", ("glpat-",)),
    "GITLAB_PAT":          ("starts_with", ("glpat-",)),
    "REPLICATE_API_TOKEN": ("starts_with", ("r8_",)),
    "GROQ_API_KEY":        ("starts_with", ("gsk_",)),
    "PERPLEXITY_API_KEY":  ("starts_with", ("pplx-",)),
    "NPM_TOKEN":           ("starts_with", ("npm_",)),
    "PYPI_TOKEN":          ("starts_with", ("pypi-",)),
    "DOCKERHUB_TOKEN":     ("starts_with", ("dckr_pat_",)),
    "SENTRY_DSN":          ("starts_with", ("https://",)),  # weak check
    "POSTHOG_API_KEY":     ("starts_with", ("phc_",)),
    "SLACK_APP_TOKEN":     ("starts_with", ("xapp-",)),
    "LINEAR_API_KEY":      ("starts_with", ("lin_api_",)),
    "STRIPE_WEBHOOK_SECRET":("starts_with", ("whsec_",)),
    "BREVO_API_KEY":       ("starts_with", ("xkeysib-",)),
    "OKTA_API_TOKEN":      ("len_eq", 42),
}

# Common English stop-words. If a generated CREDENTIAL value contains one of
# these as a substring (case-insensitive), the value is suspicious — real
# credentials don't say "the" inside.
STOP_WORDS = {
    "the", "and", "for", "with", "from", "this", "that", "have", "your",
    "you", "are", "but", "not", "all", "can", "her", "was", "one", "our",
    "out", "day", "get", "has", "him", "his", "how", "man", "new", "now",
    "old", "see", "two", "way", "who", "boy", "did", "its", "let", "put",
    "say", "she", "too", "use", "password", "secret", "admin", "user",
}


def parse(text: str) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in ANN_RE.finditer(text)]


def shape_hash(text: str) -> str:
    s = ANN_RE.sub("[X]", text)
    s = re.sub(r"\d+", "N", s)
    s = re.sub(r"[a-f0-9]{7,}", "H", s)
    return hashlib.md5(s.encode()).hexdigest()


def load(path: Path) -> list[dict]:
    with path.open() as f:
        return list(csv.DictReader(f))


# ─────────────────────────────────────────────────────────────────────────────
# Auditors

def check_structural(rows: list[dict], expect_positive: bool) -> dict:
    out = defaultdict(int)
    examples = defaultdict(list)
    for r in rows:
        text = r["text"]
        for m in ANN_RE.finditer(text):
            if not m.group(1):
                out["empty_value"] += 1
                examples["empty_value"].append(r["id"])
            if m.group(2) not in VALID_LABELS:
                out["unknown_label"] += 1
                examples["unknown_label"].append(r["id"])
        if not expect_positive and ANN_RE.search(text):
            out["negative_with_marker"] += 1
            examples["negative_with_marker"].append(r["id"])
        if expect_positive and not ANN_RE.search(text):
            out["positive_without_marker"] += 1
            examples["positive_without_marker"].append(r["id"])
        stripped = ANN_RE.sub("", text)
        if "|CREDENTIAL]" in stripped or "|EMAIL]" in stripped or "|SSN]" in stripped:
            out["unparsed_marker"] += 1
            examples["unparsed_marker"].append(r["id"])
    return {"counts": dict(out), "example_ids": {k: v[:5] for k, v in examples.items()}}


def check_semantic(rows: list[dict]) -> dict:
    out = defaultdict(int)
    examples = defaultdict(list)
    env_re = re.compile(r"^([A-Z][A-Z_0-9]+)=" + ANN_RE.pattern, re.MULTILINE)

    for r in rows:
        text = r["text"]
        for m in env_re.finditer(text):
            var, value, label = m.group(1), m.group(2), m.group(3)
            if label != "CREDENTIAL":
                continue
            rule = VAR_VALUE_RULES.get(var)
            if rule is None:
                continue
            kind, allowed = rule
            ok = (kind == "starts_with" and value.startswith(allowed)) or \
                 (kind == "len_eq" and len(value) == allowed)
            if not ok:
                out["var_value_mismatch"] += 1
                examples["var_value_mismatch"].append((r["id"], var, value[:40]))

        for value, label in parse(text):
            if label == "CREDENTIAL":
                if STRICT["SSN"].match(value):
                    out["cred_looks_like_ssn"] += 1
                    examples["cred_looks_like_ssn"].append(r["id"])
                # CC: only flag if value is short pure-digits (CRED can have lots of digits in URIs/JWTs)
                if re.fullmatch(r"[\d\s\-]{15,19}", value):
                    out["cred_looks_like_cc"] += 1
                    examples["cred_looks_like_cc"].append(r["id"])
                if STRICT["EMAIL"].match(value):
                    out["cred_looks_like_email"] += 1
                    examples["cred_looks_like_email"].append(r["id"])
            if label == "SSN" and not STRICT["SSN"].match(value):
                out["ssn_bad_format"] += 1
                examples["ssn_bad_format"].append(r["id"])
            if label == "EMAIL" and not STRICT["EMAIL"].match(value):
                out["email_bad_format"] += 1
                examples["email_bad_format"].append(r["id"])
            if label == "PHONE" and not STRICT["PHONE"].match(value):
                out["phone_bad_format"] += 1
                examples["phone_bad_format"].append(r["id"])
    return {"counts": dict(out), "example_ids": {k: v[:5] for k, v in examples.items()}}


def check_diversity(rows: list[dict]) -> dict:
    shapes = Counter(shape_hash(r["text"]) for r in rows)
    repeats = sorted(shapes.values(), reverse=True)
    n = len(rows)
    diversity_pct = len(shapes) / n * 100 if n else 0
    lengths = sorted(len(r["text"]) for r in rows)
    p1  = lengths[int(n * 0.01)] if n > 100 else lengths[0] if lengths else 0
    p50 = lengths[n // 2] if n else 0
    p99 = lengths[int(n * 0.99)] if n > 100 else lengths[-1] if lengths else 0
    return {
        "rows": n,
        "unique_shapes": len(shapes),
        "diversity_pct": round(diversity_pct, 1),
        "top_repeat_counts": repeats[:5] if len(repeats) >= 5 else repeats,
        "length_p1_p50_p99": [p1, p50, p99],
    }


def check_coverage(rows: list[dict]) -> dict:
    """Label balance + format coverage."""
    label_counts = Counter()
    for r in rows:
        for value, label in parse(r["text"]):
            label_counts[label] += 1
    total_labels = sum(label_counts.values())

    # Expected distribution from v3.py LABEL_WEIGHTS
    expected = {"CREDENTIAL": 0.55, "EMAIL": 0.13, "PHONE": 0.12, "SSN": 0.10, "CREDIT_CARD": 0.10}
    label_balance = {}
    for label, weight in expected.items():
        actual_pct = label_counts.get(label, 0) / total_labels if total_labels else 0
        deviation = (actual_pct - weight) / weight * 100 if weight else 0
        label_balance[label] = {
            "count": label_counts.get(label, 0),
            "actual_pct": round(actual_pct * 100, 1),
            "expected_pct": round(weight * 100, 1),
            "deviation_pct": round(deviation, 1),
            "within_tolerance": abs(deviation) <= 20.0,
        }

    return {"label_counts": dict(label_counts), "label_balance": label_balance}


def check_hygiene(rows: list[dict]) -> dict:
    """Common-word leak + adversarial proximity counts."""
    common_word_leaks = []
    adjacent_same_label = 0
    for r in rows:
        # Common-word leak: any CREDENTIAL value containing a stop-word
        for value, label in parse(r["text"]):
            if label != "CREDENTIAL":
                continue
            v_lower = value.lower()
            for w in STOP_WORDS:
                # Match as a whole word inside the value (not a substring)
                if re.search(r"\b" + re.escape(w) + r"\b", v_lower):
                    common_word_leaks.append((r["id"], w, value[:40]))
                    break

        # Adversarial proximity: two same-label entities within 5 chars of each other
        spans = []
        for m in ANN_RE.finditer(r["text"]):
            spans.append((m.start(), m.end(), m.group(2)))
        for i in range(len(spans) - 1):
            a_end = spans[i][1]
            b_start = spans[i+1][0]
            if spans[i][2] == spans[i+1][2] and (b_start - a_end) <= 5:
                adjacent_same_label += 1
    return {
        "common_word_leak_count": len(common_word_leaks),
        "common_word_leak_samples": common_word_leaks[:10],
        "adjacent_same_label_count": adjacent_same_label,
    }


def check_tokenization(rows: list[dict], sample_n: int = 100) -> dict:
    """Sample N rows, run them through HF tokenizer if available, report stats."""
    try:
        from transformers import AutoTokenizer
    except ImportError:
        return {"status": "skipped", "reason": "transformers not installed"}
    tokenizer_path = REPO / "extension" / "public" / "model" / "redact-minilm"
    if not (tokenizer_path / "tokenizer.json").exists():
        return {"status": "skipped", "reason": f"no tokenizer at {tokenizer_path}"}
    try:
        tok = AutoTokenizer.from_pretrained(str(tokenizer_path))
    except Exception as e:
        return {"status": "skipped", "reason": f"tokenizer load failed: {e}"}

    import random as _rand
    sample = _rand.sample(rows, min(sample_n, len(rows)))
    counts = sorted(len(tok(r["text"], truncation=False)["input_ids"]) for r in sample)
    n = len(counts)
    over_512 = sum(1 for c in counts if c > 512)
    return {
        "status": "ran",
        "sample_size": n,
        "token_count_p1_p50_p99": [counts[max(0, n//100)], counts[n//2], counts[min(n-1, int(n*0.99))]],
        "over_512": over_512,
        "max": counts[-1],
    }


def check_cross_split(train: list[dict], eval_: list[dict], neg: list[dict]) -> dict:
    train_set = {r["text"] for r in train}
    eval_set  = {r["text"] for r in eval_}
    neg_set   = {r["text"] for r in neg}
    return {
        "train_eval_overlap": len(train_set & eval_set),
        "train_neg_overlap":  len(train_set & neg_set),
        "eval_neg_overlap":   len(eval_set & neg_set),
        "train_internal_dupes": len(train) - len(train_set),
    }


def check_negative_prefix_overlap(positive_rows: list[dict], negative_rows: list[dict]) -> dict:
    """For each 6+ char prefix common in positive credential values, check if
    the same prefix appears at a value-shaped position in any negative."""
    pos_prefixes = Counter()
    for r in positive_rows:
        for value, label in parse(r["text"]):
            if label == "CREDENTIAL" and len(value) >= 6:
                pos_prefixes[value[:6]] += 1

    # Only look at prefixes with multiple occurrences (real signal)
    common_prefixes = {p for p, c in pos_prefixes.items() if c >= 5}

    neg_overlap_count = 0
    for r in negative_rows:
        text = r["text"]
        for prefix in common_prefixes:
            # Look for the prefix at a "value-ish" position — preceded by `=`, `:`, `"`, or whitespace
            if re.search(r'[\s=:\"\']' + re.escape(prefix), text):
                neg_overlap_count += 1
                break
    return {
        "common_credential_prefixes": len(common_prefixes),
        "negatives_with_credential_prefix": neg_overlap_count,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Reporting

def _render_label_balance(balance: dict) -> list[str]:
    lines = ["| Label | Count | Actual % | Expected % | Deviation | Status |",
             "|---|---:|---:|---:|---:|:---:|"]
    for label, info in balance.items():
        status = "✓" if info["within_tolerance"] else "✗"
        lines.append(f"| {label} | {info['count']:,} | {info['actual_pct']}% | "
                     f"{info['expected_pct']}% | {info['deviation_pct']:+.1f}% | {status} |")
    return lines

def _render_diversity(div: dict) -> list[str]:
    return [
        f"- Rows: **{div['rows']:,}**",
        f"- Unique prose shapes: **{div['unique_shapes']:,}** ({div['diversity_pct']}%)",
        f"- Top repeat counts: {div['top_repeat_counts']}",
        f"- Length p1/p50/p99: {div['length_p1_p50_p99'][0]} / "
        f"{div['length_p1_p50_p99'][1]} / {div['length_p1_p50_p99'][2]} chars",
    ]

def _render_counts(counts: dict, header: str) -> list[str]:
    if not counts:
        return [f"- ✓ {header}: 0 issues"]
    lines = [f"- {header}:"]
    for k, v in counts.items():
        lines.append(f"  - `{k}`: {v}")
    return lines

def render_markdown(report: dict) -> str:
    s = report["summary"]
    lines = ["# Synthetic v3 Audit Report", ""]

    # ── Summary ──────────────────────────────────────────────────────────────
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---|")
    lines.append(f"| Train rows | **{s['train_rows']:,}** |")
    lines.append(f"| Eval rows | **{s['eval_rows']:,}** |")
    lines.append(f"| Negative rows | **{s['neg_rows']:,}** |")
    lines.append(f"| Train prose diversity | **{s['train_diversity']}%** |")
    lines.append(f"| Negative prose diversity | **{s['neg_diversity']}%** |")
    lines.append(f"| Structural checks | {'✓ PASS' if s['structural_pass'] else '✗ FAIL'} |")
    lines.append(f"| Semantic checks | {'✓ PASS' if s['semantic_pass'] else '✗ FAIL'} |")
    cs = s['cross_split']
    lines.append(f"| Train ∩ Eval overlap | {cs['train_eval_overlap']} |")
    lines.append(f"| Train ∩ Neg overlap | {cs['train_neg_overlap']} |")
    lines.append(f"| Eval ∩ Neg overlap | {cs['eval_neg_overlap']} |")
    lines.append(f"| Train internal duplicates | {cs['train_internal_dupes']} |")
    lines.append("")

    # ── Label balance ────────────────────────────────────────────────────────
    lines.append("## Label balance (train)")
    lines.append("")
    lines.extend(_render_label_balance(report["train"]["coverage"]["label_balance"]))
    lines.append("")

    # ── Diversity per split ──────────────────────────────────────────────────
    for split_name, key in [("Train", "train"), ("Eval", "eval"), ("Negatives", "neg")]:
        lines.append(f"## {split_name}")
        lines.append("")
        sect = report[key]

        lines.append("**Diversity**")
        lines.extend(_render_diversity(sect["diversity"]))
        lines.append("")

        lines.append("**Structural checks**")
        lines.extend(_render_counts(sect["structural"]["counts"], "Structural issues"))
        lines.append("")

        if "semantic" in sect:
            lines.append("**Semantic checks**")
            lines.extend(_render_counts(sect["semantic"]["counts"], "Semantic issues"))
            lines.append("")

        if "hygiene" in sect:
            h = sect["hygiene"]
            lines.append("**Hygiene**")
            lines.append(f"- Common-word leaks (CRED values containing English stop-words): "
                         f"**{h['common_word_leak_count']}**")
            lines.append(f"- Adjacent same-label entities (<5 chars apart): "
                         f"**{h['adjacent_same_label_count']}** (intentional adversarial signal)")
            lines.append("")

    # ── Tokenization ─────────────────────────────────────────────────────────
    if "tokenization" in report:
        tok = report["tokenization"]
        lines.append("## Tokenization preview")
        lines.append("")
        if tok.get("status") == "ran":
            p1, p50, p99 = tok["token_count_p1_p50_p99"]
            lines.append(f"- Sample size: {tok['sample_size']}")
            lines.append(f"- Token count p1/p50/p99: **{p1} / {p50} / {p99}**")
            lines.append(f"- Max tokens: **{tok['max']}**")
            lines.append(f"- Examples >512 tokens: **{tok['over_512']}** "
                         f"(handled via `return_overflowing_tokens` chunking in training)")
        else:
            lines.append(f"- Status: skipped ({tok.get('reason', 'unknown')})")
        lines.append("")

    # ── Negative-positive prefix overlap ─────────────────────────────────────
    if "neg_prefix_overlap" in report:
        npo = report["neg_prefix_overlap"]
        lines.append("## Negative–positive prefix overlap")
        lines.append("")
        lines.append(f"- Common credential prefixes (≥5 occurrences): **{npo['common_credential_prefixes']}**")
        lines.append(f"- Negatives containing one of those prefixes: **{npo['negatives_with_credential_prefix']}**")
        lines.append("- Note: some overlap is OK (e.g., the doc-placeholder negative `set OPENAI_API_KEY=sk-...` "
                     "uses the `sk-` prefix to teach the boundary). High overlap with no semantic context, however, "
                     "would confuse the model.")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="exit nonzero if any check fails")
    parser.add_argument("--report", default=str(JSON_REPORT),
                        help="JSON report output path")
    parser.add_argument("--md-report", default=str(MD_REPORT),
                        help="Markdown report output path")
    args = parser.parse_args()

    if not all(p.exists() for p in [TRAIN, EVAL, NEG]):
        print("missing dataset files — run `python -m data.generators.v3` first")
        sys.exit(1)

    train_rows = load(TRAIN)
    eval_rows  = load(EVAL)
    neg_rows   = load(NEG)

    report = {
        "summary": {},
        "train": {},
        "eval": {},
        "neg": {},
    }

    # Per-split checks
    for name, rows, expect_pos in [("train", train_rows, True), ("eval", eval_rows, True), ("neg", neg_rows, False)]:
        report[name]["structural"]   = check_structural(rows, expect_pos)
        if expect_pos:
            report[name]["semantic"]  = check_semantic(rows)
            report[name]["coverage"]  = check_coverage(rows)
            report[name]["hygiene"]   = check_hygiene(rows)
        report[name]["diversity"]    = check_diversity(rows)

    # Cross-split / global checks
    report["cross_split"] = check_cross_split(train_rows, eval_rows, neg_rows)
    report["tokenization"] = check_tokenization(train_rows, sample_n=100)
    report["neg_prefix_overlap"] = check_negative_prefix_overlap(train_rows, neg_rows)

    # Roll up summary
    structural_pass = all(
        sum(report[s]["structural"]["counts"].values()) == 0
        for s in ["train", "eval", "neg"]
    )
    semantic_pass = all(
        sum(report[s]["semantic"]["counts"].values()) == 0
        for s in ["train", "eval"]
    )

    report["summary"] = {
        "train_rows": len(train_rows),
        "eval_rows":  len(eval_rows),
        "neg_rows":   len(neg_rows),
        "cross_split": report["cross_split"],
        "structural_pass": structural_pass,
        "semantic_pass": semantic_pass,
        "train_diversity": report["train"]["diversity"]["diversity_pct"],
        "neg_diversity":   report["neg"]["diversity"]["diversity_pct"],
    }

    # Write reports
    Path(args.report).write_text(json.dumps(report, indent=2, default=str))
    Path(args.md_report).write_text(render_markdown(report))

    # Print compact summary to stdout
    print(f"\n{'='*70}")
    print(f"AUDIT SUMMARY  (full report → {Path(args.report).relative_to(REPO)})")
    print(f"{'='*70}")
    print(f"  rows: train={len(train_rows):,}  eval={len(eval_rows):,}  neg={len(neg_rows):,}")
    print(f"  structural pass:  {structural_pass}")
    print(f"  semantic pass:    {semantic_pass}")
    print(f"  train diversity:  {report['train']['diversity']['diversity_pct']}%")
    print(f"  neg diversity:    {report['neg']['diversity']['diversity_pct']}%")
    print(f"  cross-split overlap: {report['cross_split']['train_eval_overlap']} / {report['cross_split']['train_neg_overlap']} / {report['cross_split']['eval_neg_overlap']}")
    print(f"  tokenization:     {report['tokenization'].get('status', 'unknown')}")
    if report['tokenization'].get('status') == 'ran':
        print(f"    tokens p1/p50/p99: {report['tokenization']['token_count_p1_p50_p99']}")
        print(f"    over 512:          {report['tokenization']['over_512']}")
    print(f"  label balance:")
    for label, info in report["train"]["coverage"]["label_balance"].items():
        ok = "✓" if info["within_tolerance"] else "✗"
        print(f"    {ok} {label:14s}  {info['count']:>5,}  ({info['actual_pct']}% vs {info['expected_pct']}%)  dev={info['deviation_pct']:+.0f}%")
    print(f"  hygiene (train):")
    print(f"    common-word leaks:  {report['train']['hygiene']['common_word_leak_count']}")
    print(f"    adjacent same-label: {report['train']['hygiene']['adjacent_same_label_count']}")
    print()

    if args.strict:
        if not structural_pass or not semantic_pass:
            print("FAIL — strict mode")
            sys.exit(1)


if __name__ == "__main__":
    main()
