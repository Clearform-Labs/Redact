# Redact v3 — Synthetic Data Engine

Generates training, evaluation, and adversarial test data for the Redact NER model.

The model targets developer-paste contexts in LLM chat boxes. Detects 5 entity types:
`CREDENTIAL`, `EMAIL`, `SSN`, `CREDIT_CARD`, `PHONE`. Two-tier severity (BLOCK / WARN) is
applied at inference time in the extension; the data generator labels every entity uniformly.

## Quick start

```bash
# Generate full dataset (default 18K examples + 500 adversarial)
python -m data.generators.v3 --count 18000 --include-adversarial --seed 42

# Audit the generated data
python -m data.generators.audit

# Print 12 samples without writing files
python -m data.generators.v3 --sample-only
```

Outputs (gitignored — regeneratable):

| File | Rows | Purpose |
|---|---:|---|
| `data/synthetic_train_v3.csv` | ~11,400 | Training positives, stratified |
| `data/synthetic_eval_v3.csv`  | ~1,150  | Held-out positives, stratified |
| `data/synthetic_negatives_v3.csv` | ~5,400 | Hard negatives (no PII, lookalike content) |
| `data/synthetic_adversarial_v3.csv` | ~500 | Eval-only edge cases targeting v2 failures |
| `data/audit_v3.json` | — | Machine-readable audit report |
| `data/audit_v3.md`   | — | Human-readable audit report |

## Architecture

```
data/generators/
├── __init__.py        # package marker
├── fillers.py         # realistic names, file paths, error types, dates, ticket IDs
├── formats.py         # 70+ credential value generators (one per format)
├── voices.py          # tone modulation (lowercase, terse, panicked) — marker-safe
├── contexts.py        # 18 paste-style templates (env, code, support, k8s, terraform, ...)
├── negatives.py       # 18 hard-negative categories with random-framing wrappers
├── adversarial.py     # 6 categories of edge cases for held-out evaluation
├── audit.py           # 5 categories of quality checks (structural / semantic / diversity / coverage / hygiene)
└── v3.py              # CLI orchestrator + stratified train/eval split
```

Data flow:

```
v3.py
 │
 ├─→ for each positive example:
 │   1. pick length mode (short / medium / long) by weight
 │   2. pick entity count by length mode
 │   3. for each entity: pick label by weight, generate value via formats.py
 │   4. pick a context that supports the length, render via contexts.py
 │   5. occasionally apply voice modulation (skipped for code-shaped contexts)
 │   6. emit (text, context_name, length, primary_label) for stratification
 │
 ├─→ stratified split by (context, length, primary_label) bucket
 │
 ├─→ for each negative: pick category by weight, render via negatives.py,
 │   optionally wrap with random framing prefix/suffix
 │
 └─→ optionally generate adversarial set via adversarial.py
```

## How to extend

### Add a new credential format

1. Add a generator function to `formats.py` that returns the literal value:

   ```python
   def gen_my_provider_token() -> str:
       return "myprov_" + _alnum(40)
   ```

2. Register it in the `FORMATS` dict at the bottom of `formats.py`:

   ```python
   FORMATS["CREDENTIAL"].append(gen_my_provider_token)
   ```

3. Add a prefix → var-name mapping in `contexts.py`'s `_format_var_for_value`:

   ```python
   if value.startswith("myprov_"):
       return _pick(["MYPROVIDER_TOKEN", "MYPROVIDER_API_KEY"])
   ```

4. Add the var-name → expected-prefix rule in `audit.py`'s `VAR_VALUE_RULES`:

   ```python
   "MYPROVIDER_TOKEN": ("starts_with", ("myprov_",)),
   ```

5. Regenerate and audit:

   ```bash
   python -m data.generators.v3 --seed 42
   python -m data.generators.audit
   ```

### Add a new context template

1. Write a function `ctx_my_paste(items, length: str) -> str` in `contexts.py` that
   takes a list of `(label, value)` tuples and a length mode, returns text with
   `[value|LABEL]` markers embedded.

2. Register it in the `CONTEXTS` list with the length modes it supports:

   ```python
   (ctx_my_paste, ['short', 'medium', 'long']),
   ```

3. If your context produces structured output (code/JSON/YAML), add it to
   `_VOICE_INCOMPATIBLE` so voice modulation doesn't mangle the syntax.

### Add a new negative category

1. Write a function `neg_my_category() -> str` in `negatives.py` returning a
   random template string. Include 15+ templates with `random.choice`.

2. Register in `NEGATIVES` with a weight (1.0 = baseline):

   ```python
   (neg_my_category, 1.5),
   ```

### Add a new audit check

Add a function `check_my_thing(rows) -> dict` in `audit.py` and call it from
`main()`. The result goes into the JSON/markdown report under a top-level key.

## Decisions log

### Why these 5 labels?

v1 had 13 labels (PERSON, ORG, LOC, PROJECT, INTERNAL_SYSTEM, etc.). F1 0.56.
Cutting to 5 (CREDENTIAL, EMAIL, SSN, CREDIT_CARD, PHONE) jumped F1 to 0.92.

The principle: **redacting a label should never destroy useful debugging context**.
Names, organizations, file paths fail this test — strip them and the LLM has
nothing to debug. The 5 labels we keep are unambiguously dangerous to leak.

### Why credentials-first vs general DLP?

Credentials are the differentiator. Most DLP tools (Nightfall, Bearer) cover PII
well but credential coverage is shallow. Devs are the buyer. Going wide on PII
dilutes the pitch.

### Why US-only?

Keeps the data engine focused. International PII (IBAN, CPF, Aadhaar, NHS) requires
its own format library and audit rules. Verticalize when the demand is there.

### Why ~70+ credential generators?

Real LLM pastes contain credentials from across the entire SaaS/cloud landscape. A
model trained on only AWS + GitHub + a few LLM providers will miss the long tail.
The model learns the general "credential-shape" pattern from the format diversity,
not from any one specific format.

### Why 18 contexts?

Goal: match the distribution of what a developer actually pastes, not just code.
The 8 v2 contexts were dev-flavored but limited (env, error log, code, chat,
bug report, CI log, email, support). v3 adds: yaml/k8s, dockerfile, terraform,
curl request, sql, diff, log lines, runbook/postmortem, slack thread, jupyter
notebook. Better coverage of what real pastes look like.

### Why hard negatives?

The model needs to learn the *boundary* between credential-shaped and credential.
Without explicit negatives:
- Line numbers in stack traces (`line 42`) get redacted
- Doc placeholders (`<your-key-here>`) get redacted
- Public IDs (`cus_abc123`) get redacted
- Hashes (SHA-256, ETags) get redacted

5,400 negatives across 18 categories with random framing wrappers gives the model
strong "this exact pattern is OK" signal across the most common false-positive sources.

### Why stratified eval?

Random 90/10 split risks under-representing rare contexts in eval. With 18 contexts
× 3 length modes × 5 labels = 270 possible buckets, a random split could leave
multiple buckets with zero eval coverage. Stratified bucket-based split ensures
every (context, length, label) combo gets eval examples.

### Why an adversarial test set?

The eval set measures average performance on the same distribution as train.
The adversarial set measures performance on the specific failure modes v2
exhibited. It's the regression target for v3 — if v3 doesn't beat v2 on the
adversarial set, we haven't solved the problem we set out to solve.

## Acceptance criteria for shipping a new dataset version

- All structural and semantic audit checks pass (zero failures)
- Train prose diversity ≥90%
- Negative prose diversity ≥60%
- Label balance: each label within ±20% of intended distribution
- Cross-split overlap (train ∩ eval, train ∩ neg, eval ∩ neg): 0
- Single seeded regeneration produces byte-identical output
- All buckets with ≥10 train examples have at least 1 eval example

## Reproducibility

```bash
# Two runs of the same command should produce byte-identical output:
python -m data.generators.v3 --seed 42 --count 18000
sha256sum data/synthetic_*.csv > /tmp/run1.sha256
python -m data.generators.v3 --seed 42 --count 18000
sha256sum data/synthetic_*.csv > /tmp/run2.sha256
diff /tmp/run1.sha256 /tmp/run2.sha256
# (no output = reproducible)
```

## Versioning

See `CHANGELOG.md` for version history.
