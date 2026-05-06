"""
Hard-negative templates. These produce realistic prose that contains things
which LOOK like credentials or PII but are NOT and should not be redacted.

18 categories now, each with deep variation:

  Existing (expanded to 15+ templates each):
   1. Stack traces / file paths / line numbers
   2. Code review prose (variable names, function names, refactor talk)
   3. Documentation with placeholders
   4. Version strings, commit hashes, build IDs
   5. UUIDs / tracking numbers / postal codes
   6. Innocuous chat prose (no entities at all)
   7. Code talking ABOUT credentials without containing them
   8. Numeric IDs that look like SSN/CC

  New:
   9. Well-known test values (Stripe test cards, AWS sample keys, test SSNs)
  10. Public IDs that look private (Stripe cus_/prod_, GitHub URLs, public account SIDs)
  11. Hashes (SHA-256, MD5, image digests, ETag values)
  12. License keys / product keys / coupon codes
  13. Tracking / analytics IDs (UA-, GTM-, Pixel IDs, public anon keys)
  14. Public certs / public keys (X.509, SSH public keys, DKIM TXT records)
  15. Doc placeholders (extended: ${VAR}, {{ var }}, <%= ENV %>)
  16. ARN / cloud resource names
  17. Type signatures / function declarations (no values)
  18. Log format lookalikes (request_id=, trace_id=, span_id=)
"""

import random
from .fillers import (
    gen_human_first, gen_human_full, gen_filepath, gen_short_sha, gen_full_sha,
    gen_uuid, gen_ticket, gen_service,
    DATE_RELATIVE, ERROR_TYPES, ERROR_MESSAGES, FILE_PATHS,
)


def _pick(seq):
    return random.choice(seq)


# ── 1. Stack traces / file paths / line numbers ──────────────────────────────

def neg_stack_trace() -> str:
    err = _pick(ERROR_TYPES)
    msg = _pick(ERROR_MESSAGES)
    n_frames = random.randint(2, 12)
    frames = [f"  at {gen_filepath()}" for _ in range(n_frames)]
    intro = _pick([
        "got this from prod, anyone seen it before:",
        "our integration test is throwing this:",
        "intermittent failure in the worker, full trace:",
        "sentry just paged on this:",
        "failed run on ci, here's the trace:",
        "prod is throwing this and i'm not finding it on stackoverflow:",
        "first time seeing this in prod. happens once every ~50 requests:",
        "datadog flagged this run, anyone know what it means:",
        "log dump from the last failed run:",
        "rolling back didn't fix it. trace from after the rollback:",
        "this just started failing 30 min ago:",
        "alert fired, here's the trace:",
        "stack trace from the worker, looks like the auth piece:",
        "happened during the last deploy, fully reproducible:",
        "anyone seen this in the queue worker?",
    ])
    extras = []
    if random.random() < 0.5:
        extras.append(f"build hash: {gen_short_sha()}")
    if random.random() < 0.4:
        extras.append(f"request id: {gen_uuid()}")
    if random.random() < 0.3:
        extras.append(f"job: {gen_ticket()}")

    parts = [intro, "", f"{err}: {msg}", *frames]
    if extras:
        parts.extend(["", *extras])
    if random.random() < 0.5:
        parts.append("")
        parts.append(_pick([
            "is this the rds outage from earlier?",
            f"reverting the {gen_short_sha()} commit, see if that helps.",
            f"only reproducible after the v2.{random.randint(1,9)}.{random.randint(0,30)} deploy.",
            "going to bisect after lunch.",
            "anyone got a clue?",
            "filing an INC if this happens again in the next hour.",
            "thinking it's the new middleware — going to revert that piece.",
            "ping @oncall.",
        ]))
    return "\n".join(parts)


# ── 2. Code review prose ─────────────────────────────────────────────────────

def neg_code_review() -> str:
    return _pick([
        "The TypeError on the auth callback is happening because the middleware redirect handler isn't handling the OAuth state parameter when it comes back URL-encoded. Anyone want to pair on this?",
        "Q4 deliverables ship by mid-November. Sarah will lead the backend redesign. Stack trace at line 42 of payments.py shows the same Postgres timeout from last week.",
        f"Renaming `fetchUser` to `fetchCurrentUser` across the codebase. About {random.randint(20, 80)} callsites. PR up in 30 min.",
        "Review comment: the loop on line 88 has an off-by-one — should be `i < len(items)` not `<=`. Otherwise LGTM.",
        f"Refactoring the auth module: pulling `validateToken` out of `lib/auth.ts` into its own file. Touches {random.randint(8, 30)} files. CI is happy.",
        f"Reviewed {gen_human_first()}'s PR #{random.randint(100, 9999)}. Two questions: why are we passing `null` here instead of `undefined`, and is the new SignalHandler class supposed to extend EventEmitter?",
        f"Sprint planning: {gen_human_first()} takes the search-indexer ticket, {gen_human_first()} does the migration, I'll cover the auth-gateway refactor.",
        "small nit on the PR — can we rename `usr` to `user`? otherwise looks great",
        f"the regression in {gen_filepath()} is real but the fix in this PR papers over it. think we should revert and properly debug.",
        f"merge conflict in {gen_filepath()}. tagging {gen_human_first()} since they touched it last.",
        "noticed `processOrder` has 14 params now. extracting to a struct in next PR.",
        f"approving once you address the eslint warning on {gen_filepath()} line {random.randint(20, 200)}.",
        "ok i changed my mind on the trait approach. let's go with composition like you suggested originally.",
        "the test for `validateInput` passes locally but hangs in ci. wondering if it's the new mock setup.",
        "renamed the variable from `data` to `requestPayload` for clarity.",
        f"{gen_human_first()} reviewed your PR — left {random.randint(2, 12)} comments. mostly nits.",
        "splitting the migration into two PRs: schema change first, then data backfill. safer rollback.",
        f"the new endpoint `/api/v{random.randint(1,3)}/users` takes 200ms p95 — within budget.",
        "deprecation warning on `python 3.8`. moving to 3.11 in the dockerfile.",
        f"the test failure in {gen_filepath()} is flaky. retrying confirms.",
    ])


# ── 3. Documentation with placeholders ───────────────────────────────────────

def neg_documentation() -> str:
    return _pick([
        "To configure, set OPENAI_API_KEY=<your-key-here> and DATABASE_URL=postgres://user:password@host:5432/dbname in your environment.",
        "Replace `YOUR_TOKEN_HERE` with the value from your dashboard. The format is `xxxx-xxxx-xxxx-xxxx`.",
        "Example .env (do NOT use these literal values in production):\nAPI_KEY=example_key_replace_me\nSECRET=changeme\nDATABASE_URL=postgres://user:pass@host:5432/db",
        "In step 3, the API_KEY environment variable is required. Generate one at https://console.example.com/keys and paste it into your .env file.",
        "Quick start:\n  1. Get an API key at https://example.com/dashboard\n  2. Set OPENAI_API_KEY=sk-... in your environment\n  3. Run `npm start`",
        "Curl example (replace TOKEN with your actual token):\n  curl -H 'Authorization: Bearer TOKEN' https://api.example.com/v1/users",
        "Configuration:\n  - `apiKey` (string, required) — your API key, see https://example.com/keys\n  - `endpoint` (string, optional) — defaults to https://api.example.com\n  - `timeout` (number, ms) — defaults to 30000",
        "The `Authorization` header must be of the form `Bearer <token>` where `<token>` is your personal access token.",
        "For local development, copy `.env.example` to `.env` and replace the placeholders with actual values from 1password.",
        "Required env vars (see `.env.example`):\n  STRIPE_SECRET_KEY\n  STRIPE_WEBHOOK_SECRET\n  STRIPE_PUBLISHABLE_KEY",
        "When integrating, you'll need: an API key (from settings → integrations), a webhook URL (from settings → webhooks), and the customer ID (returned at signup).",
        "First-time setup: visit /setup, generate a key, copy it to your `.env`, then run `make migrate` to initialize the database.",
        "The signing secret follows the format `whsec_` followed by 32 hex characters. You can find yours at https://dashboard.example.com/webhooks.",
        "If you see `401 Unauthorized`, double-check that your bearer token is current (they expire after 24h).",
        "POST /v1/charge\nHeaders:\n  Authorization: Bearer <token>\n  Content-Type: application/json\nBody:\n  { \"amount\": 1000, \"currency\": \"usd\" }",
        "Use `${API_KEY}` for shell substitution. In CI, set the secret in repository settings → secrets and reference it as `${{ secrets.API_KEY }}`.",
        "In Helm values, secrets are referenced as `{{ .Values.secrets.apiKey }}` and templated at install time.",
        "Set the credential via terraform variable: `tf apply -var='api_key=YOUR_KEY'`. Don't put it in `.tfvars` since that file ends up in version control.",
        "ERB template: `<%= ENV[\"DATABASE_URL\"] %>`. The actual value is loaded from Rails credentials at boot.",
        "When debugging, log the masked credential like `mask(api_key)` — never log the raw value.",
    ])


# ── 4. Version strings, commit hashes, build IDs ─────────────────────────────

def neg_version_or_hash() -> str:
    return _pick([
        f"Released v{random.randint(2,9)}.{random.randint(0,12)}.{random.randint(0,30)} to staging — commit {gen_short_sha()}. Build #{random.randint(1000,9999)}, took {random.randint(2,12)}m {random.randint(10,59)}s.",
        f"Pinned dependency: lodash@{random.randint(3,5)}.{random.randint(0,30)}.{random.randint(0,30)}, sha256 {gen_full_sha()}.",
        f"Docker image digest: sha256:{gen_full_sha()}",
        f"uuid: {gen_uuid()} — used in test fixtures, safe to share.",
        f"Build artifact: {gen_service()}:{gen_short_sha()} pushed to registry at {random.choice(['ecr', 'gcr', 'ghcr', 'quay'])}.io",
        f"Reverting from {gen_short_sha()} → {gen_short_sha()}. Bisect found the regression in commit {gen_short_sha()}.",
        f"Locking go.mod to v0.{random.randint(1,30)}.{random.randint(0,9)} (commit {gen_short_sha()}). Newer versions break our use of `context.WithCancel`.",
        f"Image layers:\n  base: alpine@sha256:{gen_full_sha()}\n  runtime: distroless@sha256:{gen_full_sha()}",
        f"Etag: \"{gen_short_sha()}\". Last-Modified: Mon, 28 Apr 2026 14:32:08 GMT.",
        f"Migration {random.randint(20240101, 20261231)}_{random.choice(['add_user_table', 'rename_orders', 'drop_legacy_index', 'add_billing_columns'])} applied successfully.",
        f"git log --oneline | head:\n  {gen_short_sha()} fix: handle null in {gen_service()}\n  {gen_short_sha()} chore: bump deps\n  {gen_short_sha()} feat: add export endpoint",
        f"build {random.randint(1000, 9999)} ({_pick(['main', 'release-2026-04', 'feat-billing'])}) — {random.randint(2,15)}m{random.randint(10,59)}s — green",
        f"image SHA mismatch: expected {gen_short_sha()}, got {gen_short_sha()}. retrying pull.",
        f"npm package integrity: sha512-{gen_full_sha()}{gen_full_sha()[:24]}",
        f"GnuPG signing key fingerprint: {' '.join(gen_short_sha().upper() for _ in range(5))}",
    ])


# ── 5. UUIDs in URLs, tracking numbers, postal codes ─────────────────────────

def neg_postal_or_id() -> str:
    return _pick([
        f"Order #{random.randint(4000,5999):04d}-0000-0000-0000 was processed twice in the queue — duplicate by ID, not a card number.",
        "Customer ID 234-56-7890 is in our test fixtures. Not a real SSN, just a synthetic ID we use in seed data.",
        f"Tracking number 1Z{random.randint(100,999)}AA{random.randint(10**9, 10**10-1)} — UPS, expected delivery Tuesday.",
        f"Postal code {random.randint(10000, 99999)}, ZIP+4 {random.randint(10000, 99999)}-{random.randint(1000, 9999)} — for the shipping address.",
        f"Permalink: https://app.example.com/users/{gen_uuid()}/orders",
        f"Webhook URL pattern: https://api.example.com/webhooks/{gen_uuid()}",
        f"Internal tracking: ORDER-{random.randint(100000, 999999)} (different from the external order ID).",
        f"DOI: 10.{random.randint(1000, 9999)}/{gen_short_sha()} for the paper we cited.",
        f"ISBN: 978-{random.randint(0,9)}-{random.randint(10,99)}-{random.randint(100000,999999)}-{random.randint(0,9)}",
        f"Coupon code BLACK{random.randint(20,30)}{random.choice(['FRI', 'CYBER', 'SALE'])} — ends Friday.",
        "Bank account 1234-5678-9012-3456 in the docs example is the official 'do not use' value (well-known test number).",
        f"Bug bounty payout: ${random.randint(500, 25000)}, reference {gen_ticket()}.",
        "Phone format spec: NNN-NNN-NNNN where N is 0-9. Example string in the docs: 555-555-5555 (the 555 prefix is reserved for fiction).",
        f"Internal employee ID: E{random.randint(10000, 99999)}.",
        f"Loyalty number: LNX-{random.randint(1000000, 9999999)}.",
    ])


# ── 6. Innocuous chat prose ──────────────────────────────────────────────────

def neg_innocuous_chat() -> str:
    return _pick([
        "Confirming the meeting Tuesday at 3pm PT. Conference room B, agenda attached. No prep needed.",
        "Coffee chat moved to Thursday — same time. Adding it to your calendar.",
        "Sprint retrospective notes from last week are on Notion. TL;DR: we're on track but blocked on the API redesign.",
        "Just shipped the search feature — early metrics show 12% engagement lift. Will share the full breakdown Friday.",
        f"thanks {gen_human_first()}, that fixed it!",
        "anyone know if the office has good wifi tomorrow? working remote and want to come in if it's stable.",
        "nice work on the launch yesterday everyone. 0 incidents, all greens.",
        f"i'm going to be off thursday-friday next week. {gen_human_first()} is covering on-call.",
        "lunch order goes in at 11:30 if anyone wants to add to it.",
        "small thing — the design review notes are missing the accessibility section. can someone add that?",
        f"{gen_human_first()}'s farewell drinks tomorrow, 6pm at the usual place. invite forthcoming.",
        "moved standup to 10:15 starting next week — works better with the london team.",
        "PSA: there's a security training due by EOM. if you haven't done it, please don't make me chase you.",
        "the conference talk recording is up. linked in the project channel.",
        "office is closed monday for the holiday. on-call still applies, paging works as usual.",
        f"hey just realized i broke the build with my last commit. fixing now, sorry. ETA {random.randint(5,15)} min.",
        "btw the new logo looks great. who designed it?",
        "lol that's the third time this week",
        f"@{gen_human_first().lower()} did you ever get the staging env working?",
        "going to grab coffee, anyone want anything?",
        f"reminder: design crit at 2pm in {_pick(['stadium', 'observatory', 'lighthouse', 'capitol'])} room.",
        f"the {_pick(['marketing', 'product', 'eng'])} team is offsite next week, don't expect quick replies.",
    ])


# ── 7. Code talking ABOUT credentials without containing them ────────────────

def neg_code_about_creds() -> str:
    return _pick([
        "I'm refactoring the auth flow. The current code reads the API key from `process.env.API_KEY` and passes it as a Bearer token. Should I switch to vault?",
        "The credential rotation script lives at scripts/rotate.py. It pulls the new value from 1password CLI and updates the relevant Kubernetes secret. Runs nightly via cron.",
        "Implementing a class `SecretManager` that wraps Vault. Methods: `getSecret(name)`, `rotateSecret(name)`, `auditAccess(name)`. Audit log goes to datadog.",
        "Question for security team: when we revoke a JWT, does the existing connection drop immediately or only at next handshake? Our current behavior assumes immediate.",
        "The `Authorization` header parsing is in middleware/auth.ts. We strip the `Bearer ` prefix and validate the token with the auth service before passing to the handler.",
        "PR #4521 changes the encryption used for stored API keys from AES-128-CBC to AES-256-GCM. No values change, just the storage encoding.",
        "Why is the secret check in three places? `lib/auth.ts`, `middleware/verify.ts`, and `services/admin.py`. Looks like consolidation work.",
        "There's a function called `obscureSecret` in lib/log.ts that masks credential-shaped values in log output. We should make sure new logger calls go through it.",
        "Onboarding doc tip: never paste API keys into the chat. Use 1password share links instead, they expire after 30 minutes.",
        "Refactor proposal: move all secret loading to a dedicated `loadConfig()` function called once at startup. Right now we read env vars in 12 different files.",
        "Spec: the rate-limiter should reject any request whose Authorization header is older than 24h. Token age is encoded in the JWT exp claim.",
        "Lint rule idea: warn on any string literal that looks like an AWS key (matches /AKIA[A-Z0-9]{16}/) inside a non-test file.",
        "Function signature: `def authenticate(token: str, *, scope: list[str] = None) -> User: ...`",
        "Type alias: `type ApiKey = string;` — opaque branded type, only created by `parseApiKey(raw: string)`.",
        "Variable declarations without values: `let apiKey: string; let token: string | null = null;` — both populated by the bootstrap step.",
        "Architecture note: the auth header is set by the SDK; client code never sees it. We pass `apiKey` to `Client.init()` and that's it.",
        "Linting comment: this `secret_key` parameter should be moved to a fixture, not a literal string.",
        "Docstring: `:param api_key: API key from your dashboard. Loaded from $API_KEY env var if not provided.`",
        "TypeScript narrowing: `if (typeof token === 'string' && token.length > 0) { ... }` — gates the api call.",
        "Snyk found the dependency `keytar@7.9.0` has a CVE related to credential storage. Bumping to 7.9.1.",
    ])


# ── 8. Numeric IDs that look like SSN/CC ─────────────────────────────────────

def neg_numeric_lookalikes() -> str:
    return _pick([
        f"Bug ID 234-56-{random.randint(1000,9999)}, opened by QA this morning. Reproducible on every dev branch.",
        f"PRD numbering: 5{random.randint(0,5)}{random.randint(0,5)}-{random.randint(10,99)}-{random.randint(1000,9999)} for this quarter's roadmap.",
        f"Internal ticket #{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)} — not a real SSN, just our auto-numbering scheme.",
        f"Test card 4{'0'*15} was processed correctly (it's an industry-standard test value, not a real card).",
        "the load test card numbers are 4242-4242-4242-4242 and 5555-5555-5555-4444 — well-known stripe test values.",
        f"document IDs use the pattern XXX-XX-XXXX where X is 0-9. example: {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}",
        f"transaction ids start with TX-: TX-{gen_short_sha().upper()}",
        f"new naming for invoices: INV-{random.randint(2024,2026)}-{random.randint(100000,999999)}",
        "the postal code format we accept is NNNNN or NNNNN-NNNN. examples in the test suite: 90210, 90210-1234, 02139, 02139-4307.",
        f"phone-shaped error code: 555-{random.randint(100,999)}-{random.randint(1000,9999)}. it's a hash of the request id, not an actual phone number.",
        f"asset tag: AST-{random.randint(1000,9999)}-{random.randint(10,99)}-{random.randint(1000,9999)}, marked for retirement.",
        f"jira board ticket numbering: PROJ-{random.randint(100,9999)}-{random.randint(10,99)}-{random.randint(1000,9999)}.",
        f"audit log row id: {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}.",
        f"random reference number for the customer to quote: {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}.",
        f"survey id format: SUR-{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}.",
    ])


# ── 9. Well-known test values (NEW — highest priority FP fix) ────────────────

def neg_well_known_test_values() -> str:
    """Test values that appear in docs/tutorials and must NEVER be redacted."""
    return _pick([
        # Stripe test cards
        "Standard Stripe test card numbers in our test fixtures: 4242-4242-4242-4242 (Visa), 4000-0000-0000-0002 (declined), 5555-5555-5555-4444 (Mastercard), 4111-1111-1111-1111 (legacy).",
        "Use 4242 4242 4242 4242 with any future expiry date and CVV — that's the standard Stripe test card.",
        "Test card matrix:\n  Visa success: 4242 4242 4242 4242\n  Mastercard success: 5555 5555 5555 4444\n  Visa decline: 4000 0000 0000 0002\n  Visa CVC fail: 4000 0000 0000 0127",
        "We use 4242-4242-4242-4242 in the load test scenario. Stripe ignores it — it's their canonical fake card.",
        # AWS sample keys
        "AWS sample creds from the official docs: access key AKIAIOSFODNN7EXAMPLE, secret wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY. These are public examples, not real credentials.",
        "If you see AKIAIOSFODNN7EXAMPLE anywhere, it's the public AWS example key — every AWS doc uses it.",
        "AWS example region/key fixture: AKIAIOSFODNN7EXAMPLE / wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY. Safe to commit in test files.",
        # Test SSNs
        "We use 123-45-6789 as the canonical test SSN in our seed data. Standard fixture across the industry.",
        "Test SSN 000-00-0000 will fail validation by design — we use it to test the rejection path.",
        "The IRS specifies 111-11-1111 and 999-99-9999 as well-known fictional SSNs. Both are safe in documentation.",
        # Test phone numbers
        "All our test phone numbers use the 555 area code (reserved for fictional use): 555-867-5309, 555-555-5555.",
        "Twilio's magic test numbers like +1-555-555-5555 won't actually send SMS. Free to use in tests.",
        # Test emails
        "test@example.com, foo@example.org, noreply@example.net — IETF-reserved test emails. Use in fixtures, not real customers.",
        "user@example.com is the canonical test email. RFC 2606 reserves example.com / .org / .net for documentation.",
        # Null UUIDs
        "Null UUID: 00000000-0000-0000-0000-000000000000. Used as a sentinel for 'no value yet'.",
        "Test UUIDs in our test fixtures: 11111111-1111-1111-1111-111111111111, 22222222-2222-2222-2222-222222222222.",
        # JWT.io example
        "Standard JWT.io example token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c — used in every JWT tutorial.",
        # Stripe test webhook secrets
        "Test webhook secret: whsec_test_secret. The test mode uses this for signature verification.",
        # Test API keys
        "OpenAI test key from the docs: sk-proj-replace-with-real-key. Substitute when you actually deploy.",
        "Anthropic example: sk-ant-api03-EXAMPLE-replace-with-real. Visible in the SDK docs.",
        "GitHub doc example PAT: ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx. Never a real key.",
        # Generic test values
        "In our test config: API_KEY=test-key-do-not-use, DATABASE_URL=postgres://test:test@localhost:5432/test.",
        "Mock auth header in our Postman collection: 'Authorization: Bearer mock-token'. Pre-request script swaps it for a real one in the staging env.",
        "Placeholder in the example: API_KEY=changeme. Devs replace this in their local .env.",
        "Default seed credentials for the dev database: admin / admin. Reset on every `make seed`.",
        "Default test webhook URL the integration tests hit: https://example.com/webhooks/test.",
        "Snapshot test fixture password: Password123!. Same across all environments — we never use it in prod.",
    ])


# ── 10. Public IDs that look private (NEW) ───────────────────────────────────

def neg_public_ids_lookalikes() -> str:
    return _pick([
        f"Stripe customer id: cus_{_alnum(14)}. Public, safe to share in support tickets.",
        f"Stripe payment intent: pi_{_alnum(24)}. Webhooks reference these — public IDs.",
        f"Stripe charge id: ch_{_alnum(24)}, evt_{_alnum(24)} for the linked event.",
        f"Stripe product id prod_{_alnum(14)} and price_{_alnum(24)} for the new tier.",
        f"Stripe subscription sub_{_alnum(14)} — visible in the dashboard, public-safe.",
        f"Twilio Account SID AC{_alnum(32)} — this is PUBLIC. The auth token is the secret one.",
        f"Twilio Messaging Service SID: MG{_alnum(32)}. Public identifier.",
        f"Slack workspace ID T0{_alnum(8, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')}, channel ID C0{_alnum(8, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')}. Both public.",
        f"GitHub PR URL: https://github.com/myorg/{gen_service()}/pull/{random.randint(100, 9999)}. Path contains ID, not a secret.",
        f"GitHub issue: https://github.com/myorg/{gen_service()}/issues/{random.randint(100, 9999)}.",
        f"GitLab MR: https://gitlab.com/myorg/{gen_service()}/-/merge_requests/{random.randint(100, 9999)}.",
        f"Google Doc URL: https://docs.google.com/document/d/{_alnum(44, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')}/edit. The document ID is not a credential.",
        f"Notion page URL contains a UUID: https://www.notion.so/My-Page-{_alnum(32, 'abcdef0123456789')}. Public sharing, not a secret.",
        f"Linear ticket id: ENG-{random.randint(100, 9999)}, FEAT-{random.randint(100, 9999)}.",
        f"Jira: PROJ-{random.randint(100, 9999)}, INFRA-{random.randint(100, 9999)} — public ticket numbers.",
        f"Discord channel snowflake: {random.randint(10**17, 10**18 - 1)}. Public, anyone with the URL has it.",
        f"AWS account id: {random.randint(10**11, 10**12 - 1)} — visible in ARNs, not sensitive on its own.",
        f"GCP project id: my-project-{random.randint(100000, 999999)}. Public.",
        f"OpenAI organization id: org-{_alnum(24)}. Visible in headers, not secret.",
        f"Anthropic workspace id: ws_{_alnum(24)}. Public identifier.",
        f"Mixpanel project token (public client-side key): {_alnum(32, 'abcdef0123456789')} — different from the API secret.",
    ])


# Helper for above (need _alnum from formats.py-style helper)
def _alnum(n: int, alphabet=None) -> str:
    import string
    alphabet = alphabet or (string.ascii_letters + string.digits)
    return "".join(random.choices(alphabet, k=n))


# ── 11. Hashes (NEW) ─────────────────────────────────────────────────────────

def neg_hashes() -> str:
    return _pick([
        f"File checksum (SHA-256): {gen_full_sha()}{gen_full_sha()[:24]}. Verify before installing.",
        f"MD5 of the upload: {_alnum(32, 'abcdef0123456789')}. Match to confirm integrity.",
        f"Container image digest: sha256:{gen_full_sha()}{gen_full_sha()[:24]}. Pinned for reproducibility.",
        f"ETag header: \"{gen_short_sha()}\". Used for HTTP cache validation.",
        f"Git commit SHAs to bisect: {gen_full_sha()} → {gen_full_sha()}.",
        f"Subresource integrity for the script tag: integrity=\"sha384-{_alnum(64, 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')}\".",
        f"Tarball checksum: {gen_full_sha()}{gen_full_sha()[:24]}  helm-v3.13.0-linux-amd64.tar.gz",
        f"S3 ETag for multipart upload: \"{gen_short_sha()}-{random.randint(2, 50)}\". The dash + count is the multipart marker.",
        f"Merkle root: {gen_full_sha()}{gen_full_sha()[:24]} — auditable proof, not a secret.",
        f"BLAKE2 hash of the artifact: {gen_full_sha()}{gen_full_sha()[:24]}.",
        f"PGP fingerprint: {' '.join(gen_short_sha().upper() for _ in range(5))}. Public, used for signature verification.",
        f"Cache key: hash:{_alnum(40, 'abcdef0123456789')}. Used internally by the build system.",
        f"Bcrypt cost-factor reference: $2b$12${_alnum(53, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789./')}. The hashed value of a placeholder password used in unit tests.",
        f"X.509 certificate fingerprint (SHA-256): {':'.join(gen_short_sha()[:2].upper() for _ in range(32))}. Public.",
    ])


# ── 12. License keys / product keys (NEW) ────────────────────────────────────

def neg_license_keys() -> str:
    def block(n=4, k=5):
        import string
        return "-".join("".join(random.choices(string.ascii_uppercase + string.digits, k=k)) for _ in range(n))

    return _pick([
        f"Software license key for the on-prem install: {block(5, 5)}. From sales — valid through 2026.",
        f"Microsoft product key sample format: {block(5, 5)}. Real keys are obtained from the volume licensing portal.",
        f"Steam key gift: {block(3, 5)}. Redeem on Steam, single-use.",
        f"Atlassian Marketplace license: AAABbb{_alnum(60, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789+/=')}. Issued per-instance.",
        f"Adobe serial number: {block(5, 4)}. From the volume licensing console.",
        f"Vendor license key in our docs example: {block(4, 4)}.",
        f"JetBrains license key (heredoc form):\n  KEY: {_alnum(70, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-')}\n  type: PERSONAL",
        f"Red Hat subscription key: {_alnum(36, 'abcdef0123456789-')}.",
        "Coupon for the conference: PROMO-EARLYBIRD-2026 — share freely.",
        f"Promotional code: BLACK{random.randint(20,30)}OFF.",
        f"Beta access invite code: BETA-{_alnum(8)}.",
        f"Discount code: DEV{random.randint(20,30)}-FREE-{_alnum(4)}.",
    ])


# ── 13. Tracking / analytics IDs (NEW) ───────────────────────────────────────

def neg_tracking_analytics_ids() -> str:
    return _pick([
        f"GA4 measurement ID: G-{_alnum(10, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')}. Universal Analytics: UA-{random.randint(10000000, 99999999)}-{random.randint(1, 9)}. Both are public, embedded in the page HTML.",
        f"Google Tag Manager: GTM-{_alnum(7, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')}. Public.",
        f"Meta Pixel ID: {random.randint(10**14, 10**15 - 1)}. Set on the website, public.",
        f"Adobe Analytics report suite: myorg-prod-{_alnum(6, 'abcdefghijklmnopqrstuvwxyz')}.",
        f"Hotjar site ID: {random.randint(1000000, 9999999)}.",
        f"Mixpanel public token (client-side): {_alnum(32, 'abcdef0123456789')}.",
        f"PostHog project API key (public anon, OK to commit): phc_{_alnum(43)}.",
        f"Sentry public DSN (the project_id is public): https://{_alnum(32, 'abcdef0123456789')}@oXXX.ingest.sentry.io/{random.randint(100000, 9999999)} — the hex chunk is the public project key, not a secret.",
        f"Segment write key (public, embedded in client code): {_alnum(32)}.",
        f"Amplitude API key (public): {_alnum(32, 'abcdef0123456789')}.",
        f"Datadog RUM client token (public, embedded in browser): pubeed{_alnum(28, 'abcdef0123456789')}.",
        "These tracking IDs (UA-, G-, GTM-, FB Pixel) are public by design — they're loaded by the browser and visible in DevTools.",
    ])


# ── 14. Public certs / public keys (NEW) ─────────────────────────────────────

def neg_public_certs_keys() -> str:
    body = "\n".join("".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=", k=64)) for _ in range(random.randint(8, 16)))
    return _pick([
        f"Server certificate (public, safe to share):\n-----BEGIN CERTIFICATE-----\n{body}\n-----END CERTIFICATE-----",
        f"Public SSH key for {gen_human_first().lower()}@laptop: ssh-rsa {_alnum(372, 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')} {gen_human_first().lower()}@hostname",
        f"ed25519 deploy key (public): ssh-ed25519 {_alnum(68, 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')} deploy@ci",
        f"DKIM public key (DNS TXT record): selector1._domainkey.example.com IN TXT \"v=DKIM1; k=rsa; p={_alnum(216, 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=')}\"",
        f"SPF record: example.com IN TXT \"v=spf1 include:_spf.google.com include:mailgun.org ~all\"",
        f"CAA record: example.com IN CAA 0 issue \"letsencrypt.org\"",
        f"Host fingerprint (RSA): {':'.join(gen_short_sha()[:2] for _ in range(16))}",
        f"PGP public key (no private material):\n-----BEGIN PGP PUBLIC KEY BLOCK-----\nVersion: GnuPG\n\n{body}\n-----END PGP PUBLIC KEY BLOCK-----",
        "The deploy key is *public* — only used to fetch the repo. The private half stays on the build machine.",
        "Note: public keys are safe to commit. Private keys are not. The directory `secrets/` is for the latter.",
    ])


# ── 15. Doc placeholders extended (NEW templates added to existing concept) ──

def neg_doc_placeholders_extended() -> str:
    return _pick([
        "Set the env var via shell substitution: `export API_KEY=${API_KEY}` — the right-side `${API_KEY}` references the parent env, not a literal value.",
        "ERB syntax in our config.yml.erb: `api_key: <%= ENV[\"API_KEY\"] %>`. Templated at boot.",
        "In the helm chart, secrets are `{{ .Values.secrets.apiKey }}` — refs are templated, never literals in the chart.",
        "Use `{{API_KEY}}` in your Postman environment, not the literal value.",
        "Replace `<your-key>` with the actual value when you set up the project.",
        "The Makefile uses `$(API_KEY)` to interpolate the value from the env. Set it before running `make deploy`.",
        "$ENV{API_KEY} in our perl scripts pulls from the environment.",
        "Powershell: `$env:API_KEY` — set it via the System Properties dialog or `setx`.",
        "Configuration file uses `%API_KEY%` (Windows-style env var ref) — substituted at runtime.",
        "The doc says \"replace `<TOKEN>` with your bearer token\" — leave the literal `<TOKEN>` in if you're just reading.",
        "your API key looks like sk-XXXX where XXXX is 48 random chars",
        "your bearer token looks like eyJ... followed by two more dot-separated base64 segments",
        "the format is always: `<prefix>_<base32>_<digits>` — see docs for current prefix",
    ])


# ── 16. ARN / cloud resource names (NEW) ─────────────────────────────────────

def neg_arn_resource_names() -> str:
    return _pick([
        f"AWS IAM role ARN: arn:aws:iam::{random.randint(10**11, 10**12-1)}:role/{_pick(['app-prod','etl-runner','data-pipeline','admin'])} — public identifier, not a credential.",
        f"S3 bucket ARN: arn:aws:s3:::{gen_service()}-prod-uploads. Public, anyone can reference; access is gated by IAM.",
        f"Secrets Manager ARN (the *path*, not the secret value): arn:aws:secretsmanager:us-east-1:{random.randint(10**11, 10**12-1)}:secret:prod/db/master-{_alnum(6, 'abcdef0123456789')}.",
        f"Lambda function ARN: arn:aws:lambda:us-east-1:{random.randint(10**11, 10**12-1)}:function:my-handler.",
        f"GCP secret ref: projects/my-prod-{random.randint(100, 999)}/secrets/db-password/versions/{random.randint(1, 50)}. The path is not the secret value.",
        f"Azure resource ID: /subscriptions/{gen_uuid()}/resourceGroups/prod-rg/providers/Microsoft.KeyVault/vaults/prod-kv.",
        f"Cloudflare account ID: {_alnum(32, 'abcdef0123456789')} — public, visible in the dashboard URL.",
        f"AWS resource id (Lambda layer): arn:aws:lambda:us-east-1:{random.randint(10**11, 10**12-1)}:layer:my-runtime:{random.randint(1, 30)}.",
        f"AWS account id: {random.randint(10**11, 10**12-1)} — public on its own, sensitive only in combination.",
        f"K8s service account: serviceaccount:platform:secret-reader. RBAC-bound, the binding is stored separately.",
    ])


# ── 17. Type signatures / function declarations (NEW) ────────────────────────

def neg_type_signatures() -> str:
    return _pick([
        "function signature: `async function authenticate(token: string, scope: string[] = []): Promise<User>`",
        "type alias: `type ApiKey = string & { __brand: 'ApiKey' }` — branded type, prevents passing a raw string.",
        "interface: `interface Credentials { apiKey: string; secret: string; expiresAt: Date; }`",
        "class signature: `class SecretManager { private apiKey: string; constructor(apiKey: string) { this.apiKey = apiKey; } }`",
        "Python: `def authenticate(token: str, *, scope: list[str] | None = None) -> User: ...`",
        "Go: `func Authenticate(token string, scope []string) (*User, error)`",
        "Rust: `pub fn authenticate(token: &str, scope: &[Scope]) -> Result<User, AuthError>`",
        "Java: `public User authenticate(String token, List<String> scope) throws AuthException`",
        "Ruby: `def authenticate(token, scope: [])` — scope is a kwarg with default empty array.",
        "C#: `public async Task<User> AuthenticateAsync(string token, string[] scope = null)`",
        "OpenAPI schema:\n  type: object\n  required: [apiKey]\n  properties:\n    apiKey:\n      type: string\n      description: API key from your dashboard",
        "GraphQL: `authenticate(token: String!, scope: [String!]): User!`",
    ])


# ── 18. Log format lookalikes (NEW) ──────────────────────────────────────────

def neg_log_format_lookalikes() -> str:
    return _pick([
        f"GET /api/v1/users 200 {random.randint(20, 5000)}ms request_id={gen_short_sha()} trace_id={gen_uuid()} span_id={gen_short_sha()[:16]}",
        f"datadog event: id={gen_uuid()} severity=info source={_pick(['api','worker','db'])} timestamp=2026-04-23T14:32:08Z",
        f"sentry event_id: {gen_short_sha()}{gen_short_sha()[:8]} environment=production release={gen_short_sha()}",
        f"opentelemetry span: trace_id={_alnum(32, 'abcdef0123456789')} span_id={_alnum(16, 'abcdef0123456789')} parent_id={_alnum(16, 'abcdef0123456789')}",
        f"nginx access log: 127.0.0.1 - - [23/Apr/2026:14:32:08 +0000] \"POST /api/v1/charge HTTP/1.1\" 200 1234 \"-\" \"curl/7.85.0\"",
        f"apache: 192.168.1.1 - - [23/Apr/2026:14:32:08 +0000] \"GET /healthz HTTP/1.1\" 200 21 \"-\" \"kube-probe/1.27\" req_id={gen_short_sha()}",
        f"k8s event: namespace=prod pod=auth-gateway-{_alnum(5)} reason=Started node=ip-10-0-1-{random.randint(1,255)}",
        f"json log: {{\"ts\":\"2026-04-23T14:32:08Z\",\"level\":\"info\",\"msg\":\"request\",\"req_id\":\"{gen_short_sha()}\",\"user_id\":{random.randint(10000, 99999)}}}",
        f"trace: {gen_uuid()} → {gen_uuid()} → {gen_uuid()} (3 hops)",
        f"correlation_id={gen_uuid()} session_id={_alnum(40)} — both internal, neither sensitive.",
        f"nginx upstream timeout: upstream={gen_service()}.svc:8080 client=10.0.{random.randint(1,255)}.{random.randint(1,255)}:{random.randint(20000, 65535)}",
        f"haproxy: stats={gen_short_sha()} backend={gen_service()} servers_up=3 sessions={random.randint(100, 9999)}",
    ])


# ──────────────────────────────────────────────────────────────────────────────
# Public registry — list of (function, weight). Higher weight → more samples.
# Weights bias toward categories that match the highest-impact false-positive
# patterns we've observed in production testing.

NEGATIVES: list[tuple] = [
    (neg_stack_trace,                 2.0),
    (neg_code_review,                 1.5),
    (neg_documentation,               2.0),  # docs placeholders are #1 FP source
    (neg_version_or_hash,             1.5),
    (neg_postal_or_id,                1.5),
    (neg_innocuous_chat,              1.0),
    (neg_code_about_creds,            1.5),
    (neg_numeric_lookalikes,          1.5),
    # New categories
    (neg_well_known_test_values,      2.5),  # critical — the test-card-redaction problem
    (neg_public_ids_lookalikes,       2.0),  # cus_/prod_/Twilio SIDs are constantly pasted
    (neg_hashes,                      1.5),
    (neg_license_keys,                1.0),
    (neg_tracking_analytics_ids,      1.5),
    (neg_public_certs_keys,           1.0),
    (neg_doc_placeholders_extended,   1.5),
    (neg_arn_resource_names,          1.0),
    (neg_type_signatures,             1.0),
    (neg_log_format_lookalikes,       1.5),
]


# Lightweight prefixes/suffixes that wrap static negative templates with varied
# surrounding prose. CRITICAL: these must NOT call random functions at import
# time — that would make the framing pool depend on import order rather than
# the runtime seed, breaking reproducibility. Functions like `gen_ticket()` are
# resolved at call time inside `_render_suffix` below.

_PREFIXES_STATIC = [
    "", "", "",  # 30% of the time, no prefix
    "FYI: ", "context: ", "for the docs: ", "saving for the new hire: ",
    "from the runbook: ", "@team — ", "quick note: ",
    "from yesterday's discussion: ", "from the wiki: ", "for posterity: ",
    "noting this here: ", "small thing — ", "btw — ", "heads up: ",
    "friendly reminder: ",
]

# Suffixes are tagged: 'lit' is a literal string, 'tkt' interpolates a fresh
# ticket id at call time. Resolved by `_render_suffix`.
_SUFFIXES_TAGGED = [
    ('lit', ""), ('lit', ""), ('lit', ""),  # 30% no suffix
    ('lit', " — pinned for visibility."),
    ('tkt', " (ref: {})"),
    ('lit', " — leaving here for the audit."),
    ('lit', " (from the security review)."),
    ('lit', " — fyi."),
    ('lit', " — closing this thread."),
    ('lit', " (link in the doc)."),
    ('lit', " — please do not delete."),
    ('lit', " — added to the runbook."),
    ('tkt', " — see also {}."),
]

def _render_suffix() -> str:
    kind, template = random.choice(_SUFFIXES_TAGGED)
    if kind == 'lit':
        return template
    return template.format(gen_ticket())


def render_negative() -> str:
    fns, weights = zip(*NEGATIVES)
    fn = random.choices(fns, weights=weights)[0]
    body = fn()
    if random.random() < 0.5:
        return random.choice(_PREFIXES_STATIC) + body + _render_suffix()
    return body
