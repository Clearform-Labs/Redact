"""
Adversarial / hard test cases for v3 model evaluation.

These are eval-only — they're written to `data/synthetic_adversarial_v3.csv`
and consumed by the training notebook as a held-out hard test set, NEVER
used in training.

Two tiers of categories:

  Tier 1 — failure modes (targeting v2's known issues):
    1. boundary    — credential immediately followed by URL path/punct/word
    2. proximity   — two credentials separated by ' and ' / ' or ' / ' - '
    3. nested      — credential inside code-fence inside markdown inside email
    4. multiline   — multi-line credentials (private key blocks, multi-line .env)
    5. ambiguity   — well-known test value adjacent to a real credential
    6. sentinel    — direct ports of v2 failure cases from extension/TESTING.md

  Tier 2 — vibe-coder realism (added in v3.1):
    7. cursor_paste     — IDE-style mid-debug snippet (Cursor / Cline / Claude Code style)
    8. terminal_session — pasted shell session with command + output + env vars
    9. api_request      — Postman / curl / DevTools-style HTTP request with auth header
   10. runbook_buried   — long technical doc with credentials buried in section N

Tier 2 cases are deliberately MESSIER and LONGER than tier 1 — closer to what
non-adversarial real users actually paste. Tier 1 measures "does it fix the
v2 bugs"; tier 2 measures "does it work for actual humans."

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
    gen_jwt, gen_private_key_block, gen_password, gen_stripe_key,
    gen_stripe_webhook_secret, gen_sentry_dsn, gen_slack_token,
    gen_email, gen_phone, gen_ssn, gen_credit_card,
    annotate,
)
from .fillers import (
    gen_human_first, gen_human_full, gen_short_sha, gen_uuid,
    gen_ticket, gen_filepath, gen_service,
)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO / "data" / "synthetic_adversarial_v3.csv"

CAT_BOUNDARY  = "boundary"
CAT_PROXIMITY = "proximity"
CAT_NESTED    = "nested"
CAT_MULTILINE = "multiline"
CAT_AMBIGUITY = "ambiguity"
CAT_SENTINEL  = "sentinel"
# v3.1 vibe-coder reality additions
CAT_CURSOR    = "cursor_paste"
CAT_TERMINAL  = "terminal_session"
CAT_API_REQ   = "api_request"
CAT_RUNBOOK   = "runbook_buried"

CATEGORIES = [
    CAT_BOUNDARY, CAT_PROXIMITY, CAT_NESTED, CAT_MULTILINE,
    CAT_AMBIGUITY, CAT_SENTINEL,
    CAT_CURSOR, CAT_TERMINAL, CAT_API_REQ, CAT_RUNBOOK,
]


def _pick(seq):
    return random.choice(seq)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Boundary cases (TIER 1)
# Credential immediately followed by URL path, punctuation, or another word.

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


# ─────────────────────────────────────────────────────────────────────────────
# 2. Proximity (TIER 1)

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


# ─────────────────────────────────────────────────────────────────────────────
# 3. Nested structures (TIER 1)

def make_nested() -> str:
    cred = annotate(_pick([gen_aws_access_key, gen_anthropic_key, gen_db_uri])(), "CREDENTIAL")
    template = _pick([
        f"forwarded thread:\n\n> Hey, can you check this script?\n>\n> ```python\n> API_KEY = \"{cred}\"\n> ```\n>\n> It's failing in CI.\n\nLet me know what you see.",
        f"From: alex@team.com\nSubject: Auth issue\n\n## Summary\nWe're seeing 401s. The token used is below:\n\n```\n{cred}\n```\n\n## Steps to reproduce\n1. Set API_KEY\n2. Run the integration test\n3. Observe failure",
        f"# Incident postmortem\n\nDuring the rollout we discovered the leaked credential was:\n\n```yaml\nstringData:\n  api_key: {cred}\n```\n\nRotation completed at 14:32 PT.",
    ])
    return template


# ─────────────────────────────────────────────────────────────────────────────
# 4. Multi-line credentials (TIER 1)

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


# ─────────────────────────────────────────────────────────────────────────────
# 5. Ambiguity (TIER 1)

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


# ─────────────────────────────────────────────────────────────────────────────
# 6. Sentinel — direct ports of v2 failures (TIER 1)

def make_sentinel() -> str:
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
        # Var name with placeholder value
        "in the docs we say `STRIPE_SECRET_KEY=<your-secret-here>` — replace before deploying.",
        # Multiple var=value pairs separated by ` and `
        f"set API_KEY={annotate(gen_anthropic_key(), 'CREDENTIAL')} and DATABASE_URL={annotate(gen_db_uri(), 'CREDENTIAL')} for the staging env.",
    ])


# ─────────────────────────────────────────────────────────────────────────────
# 7. Cursor paste (TIER 2 — vibe coder reality)
# IDE-style chat where the user is mid-debug. Pastes a small focused snippet
# to ask one specific question. Often includes surrounding code context, an
# error message, AND the credential they're using to authenticate.

def make_cursor_paste() -> str:
    cred = annotate(_pick([gen_anthropic_key, gen_openai_key, gen_aws_access_key,
                           gen_stripe_key, gen_github_pat])(), "CREDENTIAL")
    template = _pick([
        # Style 1: chat with selected code attached
        f"@codebase why is this 401-ing?\n\n"
        f"```python\n"
        f"import anthropic\n"
        f"client = anthropic.Anthropic(api_key=\"{cred}\")\n"
        f"resp = client.messages.create(\n"
        f"    model=\"claude-sonnet-4-7\",\n"
        f"    max_tokens=1024,\n"
        f"    messages=[{{\"role\": \"user\", \"content\": \"hi\"}}]\n"
        f")\n"
        f"```\n\n"
        f"i'm getting `anthropic.AuthenticationError: invalid x-api-key`. is the model name wrong or the key?",

        # Style 2: error + minimal repro
        f"running into an error:\n"
        f"```\n"
        f"requests.exceptions.HTTPError: 403 Client Error: Forbidden for url: https://api.stripe.com/v1/customers\n"
        f"```\n\n"
        f"my code is:\n"
        f"```python\n"
        f"r = requests.get(\"https://api.stripe.com/v1/customers\",\n"
        f"                 headers={{\"Authorization\": \"Bearer {cred}\"}})\n"
        f"r.raise_for_status()\n"
        f"```\n\n"
        f"is the auth header format wrong?",

        # Style 3: vibey/casual, just yeet it in
        f"why this no work\n\n```\nfetch('/api/v1/auth', {{\n  headers: {{ Authorization: 'Bearer {cred}' }}\n}})\n```\n\n"
        f"console says 401 but the key is fresh, just made it 5 min ago",

        # Style 4: refactoring help
        f"i want to refactor this auth stuff. currently:\n\n```typescript\n"
        f"const API_KEY = '{cred}'\n"
        f"async function callApi(path: string) {{\n"
        f"  return fetch(`https://api.example.com${{path}}`, {{\n"
        f"    headers: {{ 'X-Api-Key': API_KEY }}\n"
        f"  }})\n"
        f"}}\n```\n\n"
        f"how should i make this testable? i want to mock the api in tests but use real key in dev.",

        # Style 5: paste from cursor agent that "fixed" something
        f"cursor wrote this for me. is it safe?\n\n```js\n"
        f"const auth = `Bearer {cred}`\n"
        f"export const apiClient = axios.create({{\n"
        f"  baseURL: 'https://api.example.com',\n"
        f"  headers: {{ Authorization: auth }}\n"
        f"}})\n```\n\n"
        f"it committed this to git already lol",
    ])
    return template


# ─────────────────────────────────────────────────────────────────────────────
# 8. Terminal session (TIER 2)
# User pastes a shell session — multiple commands, output, env dump from
# `env | grep`, `printenv`, `cat .env`, etc. This is what people copy-paste
# from their terminal when asking "why is this happening on my machine?"

def make_terminal_session() -> str:
    cred1 = annotate(_pick([gen_aws_access_key, gen_aws_secret])(), "CREDENTIAL")
    cred2 = annotate(_pick([gen_anthropic_key, gen_openai_key, gen_stripe_key])(), "CREDENTIAL")
    template = _pick([
        # Style 1: env grep
        f"running `env | grep -i key` in the failing container:\n\n"
        f"```\n"
        f"$ env | grep -i key\n"
        f"AWS_ACCESS_KEY_ID={cred1}\n"
        f"OPENAI_API_KEY={cred2}\n"
        f"NODE_OPTIONS=--max-old-space-size=4096\n"
        f"```\n\n"
        f"why is the openai client still failing? key looks right",

        # Style 2: cat .env + run
        f"```bash\n"
        f"$ cat .env\n"
        f"NODE_ENV=production\n"
        f"DATABASE_URL={annotate(gen_db_uri(), 'CREDENTIAL')}\n"
        f"STRIPE_SECRET_KEY={cred1}\n"
        f"PORT=3000\n\n"
        f"$ npm start\n"
        f"> myapp@1.0.0 start\n"
        f"> node dist/index.js\n\n"
        f"connecting to db... ECONNREFUSED\n"
        f"Error: connect ECONNREFUSED 127.0.0.1:5432\n"
        f"```\n\n"
        f"the db url has the right host though?",

        # Style 3: docker logs
        f"docker logs from the failing container:\n\n"
        f"```\n"
        f"$ docker logs api-prod-1 --tail 30\n"
        f"[2026-04-23 14:32:08] starting up...\n"
        f"[2026-04-23 14:32:08] config loaded:\n"
        f"  AWS_REGION=us-east-1\n"
        f"  AWS_SECRET_ACCESS_KEY={cred1}\n"
        f"  ANTHROPIC_API_KEY={cred2}\n"
        f"[2026-04-23 14:32:09] connecting to anthropic...\n"
        f"[2026-04-23 14:32:09] ERROR: AuthenticationError\n"
        f"[2026-04-23 14:32:09] exit code 1\n"
        f"```",

        # Style 4: ssh session debugging
        f"ssh'd into the box:\n\n"
        f"```\n"
        f"$ ssh deploy@10.0.4.12\n"
        f"$ cd /var/app\n"
        f"$ cat config.yaml | head -10\n"
        f"production:\n"
        f"  database_url: {annotate(gen_db_uri(), 'CREDENTIAL')}\n"
        f"  api_key: {cred2}\n"
        f"  region: us-east-1\n"
        f"$ systemctl status myapp\n"
        f"  Active: failed (Result: exit-code) since Tue 2026-04-23 14:30:11 UTC\n"
        f"```\n\n"
        f"why is it failing if all the config is there?",
    ])
    return template


# ─────────────────────────────────────────────────────────────────────────────
# 9. API request (TIER 2)
# User pastes a Postman / curl / DevTools-style HTTP request export. Real
# API debugging looks like this — full request including auth header.

def make_api_request() -> str:
    cred = _pick([gen_anthropic_key, gen_openai_key, gen_stripe_key,
                  gen_github_pat])()
    val = annotate(cred, "CREDENTIAL")
    template = _pick([
        # Style 1: curl
        f"this curl works in postman but fails from my server:\n\n"
        f"```bash\n"
        f"curl -X POST 'https://api.openai.com/v1/chat/completions' \\\n"
        f"  -H 'Authorization: Bearer {val}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{{\n"
        f'    "model": "gpt-4",\n'
        f'    "messages": [{{ "role": "user", "content": "hi" }}]\n'
        f"  }}'\n"
        f"```\n\n"
        f"response is 401 unauthorized when called from node, 200 from postman. cors? user agent?",

        # Style 2: DevTools network tab paste
        f"chrome devtools network tab — request headers:\n\n"
        f"```\n"
        f"POST /v1/payment_intents HTTP/1.1\n"
        f"Host: api.stripe.com\n"
        f"Authorization: Bearer {val}\n"
        f"Content-Type: application/x-www-form-urlencoded\n"
        f"Content-Length: 47\n"
        f"User-Agent: stripe-node/13.0.0\n"
        f"\n"
        f"amount=1000&currency=usd&customer=cus_ABCdef\n"
        f"```\n\n"
        f"does Authorization need to be a Basic auth instead of Bearer for Stripe?",

        # Style 3: Postman collection JSON
        f"postman exported this collection. is it safe to commit?\n\n"
        f"```json\n"
        f"{{\n"
        f'  "info": {{ "name": "My API", "schema": "https://schema.postman.com/json/collection/v2.1.0/collection.json" }},\n'
        f'  "auth": {{\n'
        f'    "type": "bearer",\n'
        f'    "bearer": [{{ "key": "token", "value": "{val}", "type": "string" }}]\n'
        f"  }},\n"
        f'  "item": []\n'
        f"}}\n"
        f"```",

        # Style 4: httpie / insomnia
        f"```\n"
        f"http POST https://api.example.com/v1/users \\\n"
        f"  Authorization:\"Bearer {val}\" \\\n"
        f"  name=test\n"
        f"```\n"
        f"\nresponse: HTTP/1.1 403 Forbidden",
    ])
    return template


# ─────────────────────────────────────────────────────────────────────────────
# 10. Runbook buried (TIER 2)
# Long technical doc — runbook, postmortem, internal wiki — with credentials
# buried in section N. Tests whether the model can find creds even when most
# of the document is non-credential prose. v2 sometimes missed creds in long
# docs because attention was diluted across the prose.

def make_runbook_buried() -> str:
    cred1 = annotate(_pick([gen_aws_access_key, gen_anthropic_key])(), "CREDENTIAL")
    cred2 = annotate(_pick([gen_db_uri, gen_stripe_key, gen_sentry_dsn])(), "CREDENTIAL")
    service = gen_service()
    template = _pick([
        # Style 1: incident postmortem with creds in "what got rotated"
        f"# Postmortem: {service} outage, 2026-04-23\n\n"
        f"**Severity:** SEV2\n"
        f"**Duration:** 47 minutes\n"
        f"**Author:** {gen_human_full()}\n\n"
        f"## Summary\n"
        f"At 14:32 UTC on 2026-04-23, the {service} API began returning 502s for all authenticated requests. "
        f"Investigation traced the root cause to an expired AWS IAM role used by the production "
        f"deployment. The role's session token had not been refreshed during the previous deploy.\n\n"
        f"## Timeline\n"
        f"- 14:32 — alerts fire in #incidents-{gen_short_sha()[:6]}\n"
        f"- 14:35 — {gen_human_first()} acknowledges, starts investigating\n"
        f"- 14:48 — root cause identified: expired session token\n"
        f"- 14:55 — credential rotation initiated\n"
        f"- 15:19 — service recovered, alert clears\n\n"
        f"## Affected credentials\n"
        f"The following credentials were rotated as part of the response:\n\n"
        f"```\n"
        f"AWS_SECRET_ACCESS_KEY={cred1}\n"
        f"DATABASE_URL={cred2}\n"
        f"```\n\n"
        f"## Action items\n"
        f"- [ ] Add monitoring for IAM role expiration (owner: {gen_human_first()})\n"
        f"- [ ] Document rotation procedure in runbook (owner: ops)\n"
        f"- [ ] Schedule quarterly review of long-lived credentials\n\n"
        f"## Lessons learned\n"
        f"We had assumed IAM role credentials would auto-renew via the SDK. They don't if "
        f"the underlying AWS_PROFILE has been removed.",

        # Style 2: long onboarding doc with creds in "Setup" section
        f"# {service} — Engineer Onboarding\n\n"
        f"Welcome! This doc walks through getting set up with the {service} codebase.\n\n"
        f"## Prerequisites\n"
        f"- Python 3.12+\n"
        f"- Docker Desktop\n"
        f"- A GitHub account with access to the org\n"
        f"- A 1Password account (talk to {gen_human_first()} for an invite)\n\n"
        f"## Step 1: Clone the repo\n"
        f"```\ngit clone git@github.com:our-org/{service}.git\ncd {service}\n```\n\n"
        f"## Step 2: Install dependencies\n"
        f"```\nuv sync\nsource .venv/bin/activate\n```\n\n"
        f"## Step 3: Set up local environment\n"
        f"Create `.env.local` with these values (you can find them in 1Password under 'Dev Credentials'):\n\n"
        f"```\n"
        f"DATABASE_URL={cred2}\n"
        f"ANTHROPIC_API_KEY={cred1}\n"
        f"NODE_ENV=development\n"
        f"PORT=3000\n"
        f"```\n\n"
        f"## Step 4: Run the test suite\n"
        f"```\nuv run pytest\n```\n\n"
        f"## Step 5: Start the dev server\n"
        f"```\nmake dev\n```\n\n"
        f"You should now be able to hit http://localhost:3000.\n\n"
        f"## Common gotchas\n"
        f"- If migrations fail with 'role does not exist', run `make db-init` first.\n"
        f"- The {service} API requires VPN for staging/prod — talk to ops for setup.\n"
        f"- Don't commit .env.local. It's gitignored but be careful with copy-paste.",

        # Style 3: runbook with creds in "if X happens, run Y"
        f"# Runbook: {service} — Stripe webhook failures\n\n"
        f"## Symptoms\n"
        f"- PagerDuty alert: 'stripe webhook 5xx rate > 1%'\n"
        f"- Customer reports of orders not completing\n"
        f"- Datadog dashboard shows webhook event_received metric flat\n\n"
        f"## Triage\n"
        f"1. Check Stripe dashboard for webhook event delivery status (https://dashboard.stripe.com/webhooks)\n"
        f"2. Check service logs in datadog: `service:{service} env:prod webhook`\n"
        f"3. Verify webhook signing secret matches what's deployed\n\n"
        f"## Recovery\n"
        f"If signing secret mismatch is suspected:\n\n"
        f"```\n"
        f"# In the deployment env:\n"
        f"export STRIPE_WEBHOOK_SECRET={cred1}\n"
        f"export STRIPE_API_KEY={cred2}\n"
        f"\n"
        f"# Restart the worker:\n"
        f"kubectl rollout restart deployment/{service}-webhook-worker -n production\n"
        f"```\n\n"
        f"Verify recovery by checking the dashboard for delivered webhook events. "
        f"If still failing after 5 min, escalate to {gen_human_first()} (oncall).\n\n"
        f"## References\n"
        f"- Stripe webhook signing docs: https://stripe.com/docs/webhooks/signatures\n"
        f"- Internal architecture diagram: https://wiki.our-org.com/{service}\n"
        f"- Last incident: {gen_ticket()}",
    ])
    return template


# ──────────────────────────────────────────────────────────────────────────────
# Driver

GENERATORS = {
    CAT_BOUNDARY:  make_boundary,
    CAT_PROXIMITY: make_proximity,
    CAT_NESTED:    make_nested,
    CAT_MULTILINE: make_multiline,
    CAT_AMBIGUITY: make_ambiguity,
    CAT_SENTINEL:  make_sentinel,
    CAT_CURSOR:    make_cursor_paste,
    CAT_TERMINAL:  make_terminal_session,
    CAT_API_REQ:   make_api_request,
    CAT_RUNBOOK:   make_runbook_buried,
}


def generate(count: int = 800) -> list[tuple[str, str]]:
    """Return list of (category, text). Distributes evenly across categories."""
    per_cat = count // len(CATEGORIES)
    rows = []
    for cat in CATEGORIES:
        for _ in range(per_cat):
            rows.append((cat, GENERATORS[cat]()))
    random.shuffle(rows)
    return rows


def write(path: Path, count: int = 800) -> None:
    rows = generate(count)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["id", "category", "text"])
        for i, (cat, text) in enumerate(rows, start=1):
            w.writerow([i, cat, text])
    print(f"  wrote {len(rows):>4,} rows → {path.relative_to(REPO)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=800,
                        help="total rows (split evenly across categories). default 800 = 80/category")
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
                print()
        return

    write(Path(args.output), count=args.count)


if __name__ == "__main__":
    main()
