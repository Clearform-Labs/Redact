# The Generator

**Working name. May rename later (Forge / Loom / Lattice / Ground are candidates).**

A framework for using AI agents to architect deterministic data generators for ML training — combining the realism of human-curated data with the scale, reproducibility, and labeling precision of pure code.

Captured 2026-05-09 from the work that produced Redact v3.

---

## In one sentence

Most ML teams hit a wall where their model performs well on benchmarks but fails on specific real-world patterns they can't easily enumerate. The Generator is a workflow + framework that uses agents to systematically hunt down those failure modes and write deterministic data generators that close them.

## The pattern (the 7-step loop)

```
1. Describe the problem
   ↓ labels, constraints, what model should NOT do (the don't-redact-context principle)
2. Co-design generators with the agent
   ↓ modular Python: formats / contexts / voices / fillers / negatives / audit
3. Generate data deterministically (seeded)
   ↓ tens of thousands of examples in seconds, free, byte-identical reruns
4. Audit structurally + semantically + diversity
   ↓ JSON + Markdown reports per run
5. Train model
   ↓ standard pipeline (HF Trainer or whatever)
6. Build adversarial test set
   ↓ THE killer feature — held-out failure-mode tests
7. Find what the model bombs on
   ↓ per-category failure metrics from the adversarial set
   ↓ agent reasons about WHICH PATTERNS need more coverage
   ↓ agent writes new generator templates to fix them
   → loop back to step 3
```

Three things make this work:

- **Agent does cognitive work, generator does structural work.** Agents reason about *which patterns matter*. Generators produce data with *exact labels*. Neither does the other's job.
- **The artifacts are durable.** What we ship is generator code + audit reports, not "1M rows of data." A team can regenerate at any scale, any seed, any subset.
- **The adversarial set is the spec.** Standard train/eval splits lie about real-world performance. A held-out adversarial set built from articulated failure modes is the actual spec for "is this data good enough."

## Why this is novel

| Existing approach | What it does | Why it isn't enough |
|---|---|---|
| Faker / Mimesis | Generates fake names, addresses, etc. | No domain semantics, no labels, no realistic prose |
| LLM-as-labeler (Snorkel-style) | Apply LLM to label unlabeled data | Doesn't help when you don't have unlabeled data; LLM labels are 5-15% wrong |
| LLM-as-generator (HF Synthetic Data Generator, etc.) | Have LLM produce labeled rows directly | Non-deterministic, expensive, distribution drift, label hallucination at scale |
| GAN-based tabular synth (Gretel.ai, Mostly AI) | Learn distribution of existing data, generate more | Needs training data to bootstrap; tabular only |
| Hand-curated templates | Programmer writes templates manually | Slow, monotonous, hard to systematically cover failure modes |

The Generator is none of these. It's an agent-orchestrated synthesis: agents reason about coverage and write generator code; generators run free + deterministic + at scale; the audit/adversarial loop tells you which patterns are still undercovered.

## The wedge: Redact is the proof

Redact is a Chrome extension that catches credentials, SSNs, credit cards, phones, and emails before developers paste them into LLM chat boxes. Built in ~4 days.

The interesting metrics aren't really about Redact — they're about the methodology:

- **Iteration v1 → v2 → v3** went from F1 0.56 → 0.92 → 0.97
- **Each jump came from agent-driven data improvements**, not architecture changes
- **Specific v2 failures** (model redacting "line 42" as a credential, model over-merging multi-credential `.env` files, model flagging Stripe public IDs as secrets) were each diagnosed via the adversarial test set, then fixed by adding targeted generators — not by any model or hyperparameter change
- **Final dataset is fully reproducible** from a seeded `python -m data.generators.v3` command. Same seed → identical output bytes.

The pitch to ML teams isn't "buy our data tool." It's: "we shipped a model at 0.97 F1 on a hard problem in days using one engineer + Claude. Here's exactly how. Here's the framework. Use it on your problem."

The Redact GitHub repo IS the framework's tutorial.

## What the framework would be (MVP)

Three durable artifacts that compose into a complete workflow:

### 1. Template repo (`generators/` package)

Already exists in Redact at `data/generators/`. Modules:

```
generators/
├── fillers.py       # realistic non-PII content (names, file paths, etc.)
├── formats.py       # one generator function per entity format
├── voices.py        # tone modulation (lowercase casual, formal, panicked)
├── contexts.py      # paste-style templates with deep variation
├── negatives.py     # explicit hard negatives for failure-mode coverage
├── adversarial.py   # eval-only edge cases (THE adversarial set)
├── audit.py         # structural / semantic / diversity / coverage checks
└── orchestrator.py  # CLI: generate, stratified split, reproducibility
```

Generalizable to any token-classification, classification, or sequence task. Substitute domain-specific contents.

### 2. Agent playbook

The prompts and patterns the agent uses during co-design:

- "Walk me through your problem. What should the model never do?"
- "List the failure modes you've seen v1 hit. We'll generate explicit data to fix each."
- "Look at the v2 adversarial results. Per category, what data is missing?"
- "Read the existing `contexts.py`. Propose three new functions targeting category X."

Plus: structural conventions for how generator code should be written (deterministic, marker-safe, audit-compatible). The audit harness is partly a contract — agents writing new generators must conform to it.

### 3. CLI tooling

```bash
generator init <problem-name>           # scaffold the template repo
generator generate --count 18000        # run all generators, audit, output CSV
generator audit                         # report-only; runs against last generation
generator iterate --failure-report f.json  # agent reads failures, proposes generators
generator regress --against v2/         # compare current vs prior version
```

The `iterate` command is the magic one — it takes a JSON failure report from an adversarial run and asks the agent to propose generator additions. Outputs a PR-shaped diff to the generator code, ready for human review.

## Why a team would pay for it

Three concrete pain points it solves:

**1. Data labeling is the bottleneck for most ML teams.**
Companies spend 30-60% of their ML budget on labeled data. Most of it is hand-curated or paid annotation services. Both produce slow iteration cycles (days to weeks per data refresh). The Generator turns that into hours.

**2. "We don't know why our model fails on X."**
The Generator's adversarial-driven loop is a diagnostic system. You list patterns the model misbehaves on; the framework tells you which of your data categories are undercovered. That's a tool every ML team needs.

**3. Reproducible training data is rare.**
Most teams have data drift — the dataset that produced their best checkpoint is gone, lost, hand-edited, scattered across S3 buckets. The Generator's deterministic seeding means you can always regenerate the exact dataset that produced model X. Critical for audit, regulation, and CI/CD pipelines.

## Open questions / risks

- **Does it generalize beyond NER / classification?** Likely yes for any task with enumerable failure modes (object detection edge cases, speech command failures, anomaly detection rare patterns), but unverified. Computer vision adaptation needs image generators, which is different territory.
- **How much agent work is automate-able vs. how much needs a human?** Right now Redact's iterations were Claude + me in conversation. A pure-agent loop is plausible but unproven. The first version probably requires a human to interpret failure reports.
- **Discoverability vs. extensibility tradeoff in the template repo.** Too rigid a structure → can't fit weird domains. Too loose → agents struggle to extend it consistently.
- **How does this work for problems where you can't articulate failure modes?** (e.g. "the model is bad at sentiment in informal Twitter threads"). Maybe the answer is: the framework helps you define the adversarial set BY exploring model failures, then iterates from there. Inversion of the loop.
- **Is there enough value in the framework alone vs. just hiring smart engineers?** Possibly. But the framework codifies tacit knowledge that most ML teams don't have. That has compounding value across teams.

## What it could look like as a product

**Phase 1 (could ship today):** Open-source template repo + agent playbook. Free.
- Targets: ML researchers, indie ML developers, hobbyists
- Goal: prove the workflow, build community

**Phase 2:** SaaS UI for non-technical PMs / domain experts to define problems
- Visual failure-mode → coverage map
- One-click "generate + train + evaluate" pipeline
- Hosted compute for the iteration loop
- Targets: ML teams at small/mid companies who don't have ML infra
- Pricing: probably per-iteration or per-row generated

**Phase 3:** Enterprise platform with audit, compliance, lineage
- Reproducibility receipts (which generator version + seed produced which model)
- Data sourcing transparency for regulated industries
- Audit trail of agent reasoning during iterations
- Targets: financial services, healthcare, government
- Pricing: enterprise license

The 0 → 1 product is Phase 1. Open-source it, build a community around the workflow, dogfood it on a few high-visibility projects (Redact is one). The SaaS layer comes when there's pull.

## Next steps if we wanted to spin this out

1. **Validate the pattern beyond Redact.** Apply the same workflow to a non-NER problem (image classification with rare categories? speech command recognition? table understanding?) — see if the same loop converges. ~2 weeks for one validation case.
2. **Strip out Redact-specific assumptions** from `data/generators/`, repackage as a generic template at `github.com/[user]/the-generator-template`. ~1 week.
3. **Write the agent playbook formally.** What prompts do you give Claude to design generators? What conventions does generated code need to follow? ~3-5 days.
4. **Build the `iterate` CLI command.** This is the unique differentiator — automated loop closure. ~1-2 weeks.
5. **Pick a second showcase problem** that isn't NER. Build the dataset using the framework, train a model, demonstrate it. ~2-3 weeks.
6. **Open source release** with all of the above + writeup explaining the workflow. Distribution via Show HN, technical Twitter, ML newsletters. ~1 week.

Total: ~6-8 weeks to a credible open-source release. Could compress to 4 weeks with focus.

## Why this matters now

The synthetic data space has billions in investment but is dominated by GANs (tabular), simulation engines (autonomous driving), and ad-hoc LLM scripts. None of them solve the iteration problem — closing the gap between in-distribution metrics and real-world performance through agent-driven failure-mode hunting. That's a green field.

Agentic coding tools (Claude, Cursor, Cline, etc.) have exploded in 2025-2026 but mostly target software engineering. ML training data is one of the highest-value problem domains for agent automation, and barely anyone is building there.

Timing is right.

---

## Insights refined during v3.1 (2026-05-09)

After the initial doc was captured, I went one more cycle around the loop — iterating on Redact's adversarial set and training pipeline. New things became clear:

### 1. The adversarial set has two tiers, and the framework should make this explicit

In the original write-up the "adversarial set" was treated as one bucket of held-out edge cases. v3.1 split it into:

- **Tier 1 — failure-mode coverage.** "Did we fix the v2 bug where line 42 got redacted?" One category per articulated failure. Short, focused, surgical. Pass/fail.
- **Tier 2 — user-persona realism.** "Does this work for someone vibe-coding in Cursor at midnight?" Long, messy, multi-paragraph. Mimics what a real user actually pastes — IDE chat snippets, terminal sessions, runbook docs with creds buried in section 4.

Tier 1 measures *correctness against known-bad behaviors*. Tier 2 measures *correctness against the actual deployment distribution*. Both matter; they're separable; treating them as one number ("adversarial F1") obscures whether you're losing on bug-fixes or on realism.

The framework should ship both as scaffolding and force the user to define their target persona for Tier 2.

### 2. The framework isn't just about data — it's about the whole training-eval-deploy loop being well-formed

When reviewing v3.1's training notebook, the gaps weren't in data. They were boring ML-hygiene checklist items:
- No `EarlyStoppingCallback`
- No `classifier_dropout` on the head
- No post-training train-vs-eval curves

These are exactly the things that an experienced ML engineer always adds and a beginner always forgets. The framework's template notebook should include them by default. **The Generator's value isn't only "agents write data generators"; it's also "the scaffolding includes the training-loop hygiene most teams skip."**

This expands the artifacts list:
- ~~Two artifacts: generator code + audit harness~~
- **Three artifacts: generator code, audit harness, AND template notebook with full training/eval/deploy hygiene baked in.**

The notebook is what makes the workflow end-to-end. Without it, "the dataset is reproducible" is true but "the model is reproducible" is not.

### 3. The audit harness is a type system for synthetic data

Throughout v3.1, every generator change was validated by re-running `audit.py`. The audit's checks (label balance, prose diversity, structural validity, common-word leaks) act as a contract: any new generator must produce data that passes these checks.

This is the same role tests play in code, or types play in a typed language: agents can write whatever generators they want, but the audit decides whether the output is acceptable. **The audit harness is the framework's "compiler."**

Implication: the audit checks should be the *first thing* a user defines for their problem, before any generators. They're the spec the generators implement.

### 4. Reproducibility is a side effect of the architecture, not a design goal

The v3.1 dataset is byte-identical across regenerations. This isn't because we were careful about determinism. It's because:
- Generators are pure functions of `(seed, params)`
- Agents writing generators only know how to write template strings + `random` calls
- Composition (orchestrator) seeds once at the top

Determinism falls out for free. **The framework should preserve this property by limiting what generator code is *allowed* to do** (no LLM calls, no `time.time()`, no network). Agents can write anything that fits the audit contract; they can't smuggle in nondeterminism even if they wanted to.

This is a stronger guarantee than most synthetic-data tools offer, and it's worth marketing.

### 5. The failure-mode → generator → adversarial → metric loop is concrete and traceable

v3.1 added these traces explicitly:
- Failure: "v2 over-redacts when .env file has multiple credentials"
- Generator: `ctx_env_multi` in `contexts.py`
- Adversarial test: `make_terminal_session` in `adversarial.py` (`env | grep` style paste)
- Metric: per-category detection rate + tight-boundary rate on the adversarial set

The framework should formalize this as a **traceability artifact**. For each known failure mode, you should be able to point to exactly which generator addresses it and which adversarial cases verify the fix. This is what regulated industries call "lineage." It's also just good engineering.

CLI implication: `generator trace --failure "<id>"` shows the generator(s) and adversarial cases linked to that failure. Editing a generator without updating its traceability link emits a warning.

### 6. "Vibe-coder realism" is a useful named concept

Tier 2 of the adversarial set has a coherent unifying principle: what does it look like when a developer is mid-debug, panicking, copy-pasting from Cursor at 11pm to ask Claude for help?

This is a *user persona* — and personas generalize. For other ML problems:
- *Sentiment analysis*: "angry tweet at 2am" persona vs "marketer drafting copy" persona
- *Code review*: "junior dev's first PR" vs "senior dev's massive refactor"
- *Medical imaging*: "rural clinic with 2010-era scanner" vs "academic hospital with phantom calibration"

The framework should let users define one or more **target personas** and have agents generate Tier-2 adversarial cases targeted at each. This converts a vague "make the data realistic" into concrete, testable adversarial subsets.

### 7. The notebook is the project's true source of truth

It's tempting to treat the model checkpoint or the dataset CSV as the artifact. But the notebook — with the bootstrap cell, sanity checks, training args, early stopping, curve plots, and ONNX export — is what re-runs make ANY of those things reproducible.

The framework's killer demo is: "clone the repo, run one notebook, get the same model." Not "here's a dataset" or "here's a checkpoint." The notebook is the recipe; everything else is intermediate.

---

## Updated 0→1 product positioning

Based on the above, the framework as a *product* now has a cleaner story:

**"A repo template + agent playbook that gives small teams the ML hygiene of a senior team. You define your problem and your failure modes; the framework gives you back a reproducible model with full lineage."**

The components:
1. Template repo with `generators/`, `audit.py`, `adversarial.py`, and a notebook that already includes training-loop best practices.
2. Agent playbook that knows how to extend the template within the audit's type system.
3. CLI for the iteration loop (`init`, `generate`, `audit`, `iterate`, `trace`, `regress`).

That's enough for an open-source v1. Tier-2 persona generation, traceability tooling, and the SaaS UI are Phase 2+.

---

## References (where in Redact this pattern appears concretely)

- The 7-step loop is implicit in commits `005bd76` (initial v3 generator), `bafcd6b` (data-driven v2 fixes), `a33edd2` (v3.1 targeting v3.0 adversarial failures).
- Generator architecture: `data/generators/`
- Audit harness: `data/generators/audit.py` + JSON/MD reports
- Adversarial set: `data/generators/adversarial.py`
- Iteration loop in action: the v2 → v3.0 → v3.1 progression in `data/generators/CHANGELOG.md`
- Failure-mode-driven additions: `ctx_env_multi`, `ctx_proximity_chain`, `ctx_test_and_real_mix` in `data/generators/contexts.py` (added specifically to fix v3.0 adversarial gaps)

This document is the artifact pinning the meta-insight. Redact is the artifact pinning the pattern. Both are in the same repo, dated, intentional.
