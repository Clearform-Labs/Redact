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

## References (where in Redact this pattern appears concretely)

- The 7-step loop is implicit in commits `005bd76` (initial v3 generator), `bafcd6b` (data-driven v2 fixes), `a33edd2` (v3.1 targeting v3.0 adversarial failures).
- Generator architecture: `data/generators/`
- Audit harness: `data/generators/audit.py` + JSON/MD reports
- Adversarial set: `data/generators/adversarial.py`
- Iteration loop in action: the v2 → v3.0 → v3.1 progression in `data/generators/CHANGELOG.md`
- Failure-mode-driven additions: `ctx_env_multi`, `ctx_proximity_chain`, `ctx_test_and_real_mix` in `data/generators/contexts.py` (added specifically to fix v3.0 adversarial gaps)

This document is the artifact pinning the meta-insight. Redact is the artifact pinning the pattern. Both are in the same repo, dated, intentional.
