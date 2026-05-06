# Changelog

## v0.3 (2026-05-06) — Enterprise data engine

Massive expansion across all dimensions of the synthetic data engine.

### Credential format generators (24 → 100+)

Added 76 new generators across:
- **Cloud:** GCP OAuth, GCP service-account JSON, Azure storage/SAS/AD, Cloudflare, DigitalOcean, Linode, Heroku, Render, Vercel, Netlify, Fly.io, Railway
- **SCM/CI:** GitLab PAT/pipeline token, Bitbucket app password, CircleCI, Drone, Buildkite
- **LLM/AI:** Mistral, Together, Replicate, Groq, Fireworks, Perplexity
- **Dev tools:** npm, PyPI, Docker Hub, Sentry DSN, New Relic license/user keys, Honeycomb, Splunk, PagerDuty, Bugsnag, PostHog
- **Comms:** Slack signing secret + app token, Discord, Telegram, MS Graph, Teams webhook, Zoom, Linear, Notion, Airtable
- **Payments:** Stripe webhook secret (`whsec_*`), Plaid client+secret, Square, PayPal, Braintree, Adyen
- **Email:** Mailchimp, Postmark, Resend, Brevo, SMTP URL
- **Auth:** Auth0, Okta, Clerk, Keycloak, Firebase service account
- **DB/storage:** Supabase, MongoDB Atlas, Snowflake, Algolia, Elastic Cloud
- **Crypto:** WireGuard private key, PGP private key block, generic webhook signing secret, DKIM

### Context templates (8 → 18)

Added 10 new contexts: yaml_config, dockerfile, terraform, curl_request, sql_query,
diff_paste, log_lines, runbook_postmortem, slack_thread, jupyter_notebook.

### Hard negatives (8 → 18 categories)

Added 10 new categories targeting v2 failure modes:
- well-known test values (Stripe test cards, AWS sample keys, test SSNs/emails)
- public IDs lookalikes (Stripe `cus_`, Twilio account SIDs, GitHub URLs)
- hashes (SHA-256, MD5, image digests, ETags)
- license keys (software, Steam, Microsoft, JetBrains)
- tracking analytics IDs (UA-, GTM-, Pixel)
- public certs/keys (X.509 public, SSH public, DKIM public)
- doc placeholders extended (`${VAR}`, `{{ var }}`, `<%= ENV %>`)
- ARN / cloud resource names
- type signatures / function declarations
- log format lookalikes (request_id, trace_id, span_id)

Plus: random framing wrappers (`FYI: …`, `…(ref: BUG-1234)`) push negative prose
diversity from 39% → 72%.

### Audit overhaul

New checks:
- Label balance (each label ±20% of intended distribution)
- Format coverage (each generator used at least once)
- Common-word leak (CRED values containing English stop-words)
- Tokenization preview (warn on >512 tokens, p1/p50/p99 distribution)
- Adversarial proximity count
- Negative-positive prefix overlap
- Cross-split overlap (train/eval/neg)
- JSON + Markdown report output

### Stratified train/eval split

Replaces random 90/10 with bucket-based split: every (context, length, label)
combo with ≥10 train examples is guaranteed eval coverage.

### Adversarial test set

New `adversarial.py` generates 500 hard cases across 6 categories:
boundary, proximity, nested, multiline, ambiguity, sentinel (direct ports of v2
failure cases from `extension/TESTING.md`).

### Quality metrics (v3 dataset, 18K examples, seed=42)

| Metric | Value |
|---|---|
| Train rows | 11,444 |
| Eval rows | 1,156 |
| Negative rows | 5,400 |
| Adversarial rows | 498 |
| Train prose diversity | 93.9% |
| Negative prose diversity | 72.3% |
| Cross-split overlap | 0 / 0 / 0 |
| Label balance deviation | all within ±5% |
| Length p1 / p50 / p99 | 114 / 396 / 2095 chars |
| Stratification buckets | 225 |

---

## v0.2 (2026-05-05) — Initial generator

First version of the modular generator (`fillers`, `formats`, `voices`,
`contexts`, `negatives`, `audit`, `v3`). 24 credential format generators,
8 paste contexts, 8 negative categories. Audit catches structural and
semantic issues. Voice modulation introduced (with marker-safe protection).

## v0.1 (pre-2026-05-05) — Hand-curated CSV

Original `synthetic_train_v2.csv` / `synthetic_eval_v2.csv` were
hand-curated single-line examples with `[value|LABEL]` inline annotation.
~960 examples. Trained the v2 model to F1 0.92.
