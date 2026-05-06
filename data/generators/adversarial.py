"""
Adversarial / hard test cases for v3 model evaluation.

These are eval-only — they're written to `data/synthetic_adversarial_v3.csv`
and consumed by the training notebook as a held-out hard test set, NEVER
used in training.

6 categories targeting v2's known failure modes:

  1. boundary    — credential immediately followed by URL path/punct/word
  2. proximity   — two credentials separated by ' and ' / ' or ' / ' - '
  3. nested      — credential inside code-fence inside markdown inside email
  4. multiline   — multi-line credentials (private key blocks, multi-line .env)
  5. ambiguity   — well-known test value adjacent to a real credential
  6. sentinel    — direct ports of v2 failure cases from extension/TESTING.md

Used by v3.py via `--include-adversarial` flag, or run standalone:
  python -m data.generators.adversarial --count 500
"""

from __future__ import annotations
import argparse
import csv
import random
from pathlib import Path

from .formats import (
    sample as sample_credential, gen_aws_access_key, gen_aws_secret,
    gen_github_pat, gen_anthropic_key, gen_openai_key, gen_db_uri,
    gen_jwt, gen_private_key_block, gen_password, annotate,
)
from .fillers import gen_human_first, gen_short_sha, gen_uuid, gen_ticket

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "data" / "synthetic_adversarial_v3.csv"

CAT_BOUNDARY  = "boundary"
CAT_PROXIMITY = "proximity"
CAT_NESTED    = "nested"
CAT_MULTILINE = "multiline"
CAT_AMBIGUITY = "ambiguity"
CAT_SENTINEL  = "sentinel"

CATEGORIES = [CAT_BOUNDARY, CAT_PROXIMITY, CAT_NESTED, CAT_MULTILINE, CAT_AMBIGUITY, CAT_SENTINEL]


def _pick(seq):
    return random.choice(seq)


# ── 1. Boundary cases ────────────────────────────────────────────────────────
# Credential immediately followed by URL path, punctuation, or another word.
# v2's failure: included the trailing '/api/v1' in the credential span.

def make_boundary() -> str:
    cred = _pick([gen_aws_access_key, gen_anthropic_key, gen_openai_key,
                  gen_github_pat, gen_password])()
    val = annotate(cred, "CREDENTIAL")
    template = _pick([
        f"the auth url is https://api.example.com/v1/users?token={val}&page=1 — does this work?",
        f"got 401 from https://service.io/api/v2/auth/{val}, anyone else?",
        f"check this: token={val}, that's what the docs say.",
        f"my .env has API_KEY={val}; the deploy fails. is the syntax wrong?",
        f"set Authorization: Bearer {val}. do i need to URL-encode it?",
        f'export API_KEY="{val}" && ./run.sh — what am i missing?',
        f"the value is {val}. please rotate.",
        f"in the header it's `Authorization: Bearer {val}` and that's it.",
        f"`auth_token = {val}` (literal in the source).",
        f"saw {val} in the dump, is this still active?",
        f"using key={val}; passing as a query param.",
        f"the token {val}, valid until next tuesday.",
    ])
    return template


# ── 2. Proximity (two credentials separated by connector words) ──────────────
# v2's failure: collapsed two distinct credentials into one giant span.

def make_proximity() -> str:
    cred1 = annotate(_pick([gen_aws_access_key, gen_aws_secret, gen_github_pat,
                            gen_anthropic_key])(), "CREDENTIAL")
    cred2 = annotate(_pick([gen_anthropic_key, gen_openai_key, gen_github_pat,
                            gen_password])(), "CREDENTIAL")
    connector = _pick([" and ", " or ", " then ", " — ", ", ", "; "])
    template = _pick([
        f"i need {cred1}{connector}{cred2} for the migration.",
        f"the keys are {cred1}{connector}{cred2}.",
        f"set OPENAI_API_KEY={cred1}{connector}DATABASE_URL={cred2} in your .env.",
        f"rotate {cred1}{connector}{cred2} immediately.",
        f"both {cred1}{connector}{cred2} got committed — pulling from history now.",
        f"old key was {cred1}{connector}new key is {cred2}.",
        f"prod {cred1}{connector}staging {cred2}, both rotated this morning.",
    ])
    return template


# ── 3. Nested structures ─────────────────────────────────────────────────────

def make_nested() -> str:
    cred = annotate(_pick([gen_aws_access_key, gen_anthropic_key, gen_db_uri])(), "CREDENTIAL")
    template = _pick([
        f"forwarded thread:\n\n> Hey, can you check this script?\n>\n> ```python\n> API_KEY = \"{cred}\"\n> ```\n>\n> It's failing in CI.\n\nLet me know what you see.",
        f"From: alex@team.com\nSubject: Auth issue\n\n## Summary\nWe're seeing 401s. The token used is below:\n\n```\n{cred}\n```\n\n## Steps to reproduce\n1. Set API_KEY\n2. Run the integration test\n3. Observe failure",
        f"# Incident postmortem\n\nDuring the rollout we discovered the leaked credential was:\n\n```yaml\nstringData:\n  api_key: {cred}\n```\n\nRotation completed at 14:32 PT.",
    ])
    return template


# ── 4. Multi-line credentials ────────────────────────────────────────────────

def make_multiline() -> str:
    pk = annotate(gen_private_key_block(), "CREDENTIAL")
    style = _pick(["env", "yaml", "code"])
    if style == "env":
        return (
            "trying to load this from .env:\n"
            f"PRIVATE_KEY={pk}\n"
            "but the parser keeps failing on the newlines. how do you escape multi-line values in .env?"
        )
    elif style == "yaml":
        return (
            "k8s secret manifest:\n"
            "```yaml\n"
            "apiVersion: v1\n"
            "kind: Secret\n"
            "metadata:\n"
            "  name: signing-key\n"
            "stringData:\n"
            f"  key: |\n    {pk.replace(chr(10), chr(10) + '    ')}\n"
            "```"
        )
    else:
        return (
            "loading from disk in python:\n"
            "```python\n"
            f'PRIVATE_KEY = """{pk}"""\n'
            "```"
        )


# ── 5. Ambiguity — test value adjacent to real value ─────────────────────────

def make_ambiguity() -> str:
    real = annotate(_pick([gen_aws_access_key, gen_anthropic_key, gen_password])(), "CREDENTIAL")
    test_value = _pick([
        "AKIAIOSFODNN7EXAMPLE",
        "4242 4242 4242 4242",
        "test@example.com",
        "123-45-6789",
        "555-555-5555",
        "00000000-0000-0000-0000-000000000000",
    ])
    template = _pick([
        f"in our test fixtures we use {test_value} (the public test value), but production uses {real}.",
        f"{test_value} is the docs example. our actual key is {real}, please don't share.",
        f"replaced {test_value} (placeholder) with {real} (real) in the env file.",
        f"the canonical AWS sample is {test_value} but ours is {real}.",
        f"don't confuse the test value {test_value} with the live one: {real}.",
    ])
    return template


# ── 6. Sentinel — direct ports of v2 failures ────────────────────────────────

def make_sentinel() -> str:
    """Each of these is patterned on a specific v2 failure from TESTING.md."""
    return _pick([
        # v2 case #16: "line 42" got redacted as cred
        "Sarah will lead the backend redesign. Stack trace at line 42 of payments.py shows the same Postgres timeout we saw last week.",

        # v2 case #17: documentation placeholders over-redacted
        "set OPENAI_API_KEY=<your-key-here> and DATABASE_URL=postgres://user:password@host:5432/dbname in your environment",

        # v2 case #4: AWS key span included the var name
        "AWS_ACCESS_KEY_ID=" + annotate(gen_aws_access_key(), "CREDENTIAL"),

        # v2 case #7: JWT split into two redactions
        "Authorization: Bearer " + annotate(gen_jwt(), "CREDENTIAL"),

        # Doc placeholder + real cred
        "replace `YOUR_TOKEN` with the actual value, e.g. " + annotate(gen_anthropic_key(), "CREDENTIAL"),

        # Inline code-fenced cred preceded by prose
        "the bug is here:\n```python\napi_key = \"" + annotate(gen_openai_key(), "CREDENTIAL") + "\"\n```\nfix?",

        # Customer support style with mixed real PII
        f"ticket {gen_ticket()}: customer email is " +
        annotate("jane.smith@example.com", "EMAIL") + " — please respond by EOD.",

        # Order ID that looks like CC but fails Luhn
        "Order ID 4532-0000-0000-0000 was processed twice in the queue — duplicate by ID, not a card number.",

        # Var name with placeholder value (must NOT redact var name OR placeholder)
        "in the docs we say `STRIPE_SECRET_KEY=<your-secret-here>` — replace before deploying.",

        # Multiple var=value pairs separated by ` and `
        f"set API_KEY={annotate(gen_anthropic_key(), 'CREDENTIAL')} and DATABASE_URL={annotate(gen_db_uri(), 'CREDENTIAL')} for the staging env.",
    ])


# ──────────────────────────────────────────────────────────────────────────────
# Driver

GENERATORS = {
    CAT_BOUNDARY:  make_boundary,
    CAT_PROXIMITY: make_proximity,
    CAT_NESTED:    make_nested,
    CAT_MULTILINE: make_multiline,
    CAT_AMBIGUITY: make_ambiguity,
    CAT_SENTINEL:  make_sentinel,
}


def generate(count: int = 500) -> list[tuple[str, str]]:
    """Return list of (category, text). Distributes evenly across 6 categories."""
    per_cat = count // len(CATEGORIES)
    rows = []
    for cat in CATEGORIES:
        for _ in range(per_cat):
            rows.append((cat, GENERATORS[cat]()))
    random.shuffle(rows)
    return rows


def write(path: Path, count: int = 500) -> None:
    rows = generate(count)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["id", "category", "text"])
        for i, (cat, text) in enumerate(rows, start=1):
            w.writerow([i, cat, text])
    print(f"  wrote {len(rows):>4,} rows → {path.relative_to(REPO)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default=str(DEFAULT_OUT))
    parser.add_argument("--sample", action="store_true",
                        help="print 2 from each category, don't write")
    args = parser.parse_args()

    random.seed(args.seed)

    if args.sample:
        for cat in CATEGORIES:
            print(f"\n=== {cat.upper()} ===")
            for i in range(2):
                print(f"\n[{i+1}]")
                print(GENERATORS[cat]())
        return

    write(Path(args.output), count=args.count)


if __name__ == "__main__":
    main()
