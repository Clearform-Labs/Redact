"""
Paste-style context templates. Each function takes a list of (label, value) pairs
and a length mode, and returns realistic prose embedding the entities.

Design rules:
  - At least 12 lexical variants per opener / closer / body line.
  - Length modes: 'short' (50-200 chars), 'medium' (200-600), 'long' (600-2000+).
  - Filler content uses realistic fillers (names, file paths, error types) so
    the surrounding prose is varied even when the same template is reused.
  - Voice modulation applied AFTER template assembly so prose reads consistent
    within a single example.
  - The credential value is wrapped in [value|LABEL] inline annotation for
    parsing back into BIO labels by the training pipeline.
"""

from __future__ import annotations
import random
from typing import Callable

from .formats import annotate
from .fillers import (
    gen_human_first, gen_human_full, gen_filepath, gen_service,
    gen_ticket, gen_short_sha, gen_full_sha, gen_uuid,
    DATE_RELATIVE, ERROR_TYPES, ERROR_MESSAGES,
    CLUSTERS, DEPLOY_TARGETS, LANGUAGES,
)
from .voices import apply_voice

LengthMode = str  # 'short' | 'medium' | 'long'


def _pick(seq):
    return random.choice(seq)

def _maybe(s: str, prob: float = 0.5) -> str:
    return s if random.random() < prob else ""

def _format_var_for_label(label: str) -> str:
    # Truly generic credential var names — these fit any credential value
    # without implying a specific provider or format. Provider-specific names
    # (ANTHROPIC_API_KEY, STRIPE_SECRET_KEY, GITHUB_TOKEN, …) live ONLY in
    # `_format_var_for_value` so they pair with the right value prefix.
    options = {
        "CREDENTIAL": [
            "API_KEY", "SECRET_KEY", "ACCESS_TOKEN", "AUTH_TOKEN",
            "ENCRYPTION_KEY", "WEBHOOK_SECRET", "SESSION_SECRET",
            "APP_SECRET", "SERVICE_TOKEN", "INTEGRATION_KEY",
            "INTERNAL_TOKEN", "ADMIN_TOKEN", "BEARER_TOKEN",
        ],
        "EMAIL": ["ADMIN_EMAIL", "SUPPORT_EMAIL", "FROM_ADDRESS", "ALERT_EMAIL"],
        "PHONE": ["TWILIO_FROM", "ON_CALL_NUMBER", "CONTACT_PHONE"],
        "SSN": ["TEST_SSN", "EXAMPLE_SSN"],
        "CREDIT_CARD": ["TEST_CARD", "EXAMPLE_CC"],
    }
    return _pick(options[label])

def _format_var_for_value(label: str, value: str) -> str:
    """When the value's format is recognizable, pick a var name that matches.
    Falls back to the generic pool for unrecognized formats."""
    if label == "CREDENTIAL":
        if value.startswith(("postgresql://", "postgres://", "mysql://", "mongodb")):
            return _pick(["DATABASE_URL", "DB_URL", "DB_CONNECTION_STRING"])
        if value.startswith(("redis://", "rediss://")):
            return _pick(["REDIS_URL", "CACHE_URL"])
        if value.startswith(("amqp://", "amqps://")):
            return _pick(["AMQP_URL", "RABBITMQ_URL", "BROKER_URL"])
        if value.startswith("-----BEGIN"):
            return _pick(["PRIVATE_KEY", "SIGNING_KEY", "TLS_PRIVATE_KEY"])
        if value.startswith("AKIA") or value.startswith("ASIA"):
            return _pick(["AWS_ACCESS_KEY_ID", "AWS_KEY_ID"])
        if value.startswith("ghp_") or value.startswith("github_pat_"):
            return _pick(["GITHUB_TOKEN", "GH_PAT", "GITHUB_PAT"])
        if value.startswith("sk-ant-"):
            return _pick(["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"])
        if value.startswith("sk-"):
            return _pick(["OPENAI_API_KEY", "OPENAI_KEY"])
        if value.startswith("AIza"):
            return _pick(["GOOGLE_API_KEY", "GCP_API_KEY"])
        if value.startswith(("xoxb-", "xoxp-", "xoxa-")):
            return _pick(["SLACK_BOT_TOKEN", "SLACK_TOKEN"])
        if value.startswith("https://hooks.slack.com"):
            return _pick(["SLACK_WEBHOOK_URL", "ALERT_WEBHOOK"])
        # Stripe: separate secret (sk_*) from publishable (pk_*) and restricted (rk_*)
        if value.startswith(("sk_live", "sk_test")):
            return _pick(["STRIPE_SECRET_KEY", "STRIPE_KEY"])
        if value.startswith(("pk_live", "pk_test")):
            return _pick(["STRIPE_PUBLISHABLE_KEY", "STRIPE_PUB_KEY"])
        if value.startswith(("rk_live", "rk_test")):
            return _pick(["STRIPE_RESTRICTED_KEY", "STRIPE_KEY"])
        if value.startswith("hf_"):
            return "HUGGINGFACE_TOKEN"
        if value.startswith("eyJ"):
            return _pick(["JWT_TOKEN", "AUTH_JWT", "ID_TOKEN", "SUPABASE_KEY"])
        if value.startswith("key-"):
            return _pick(["MAILGUN_API_KEY", "MAILGUN_KEY"])
        if value.startswith("SG."):
            return _pick(["SENDGRID_API_KEY", "SENDGRID_KEY"])
        if value.startswith(("AC", "SK", "PN", "SM")) and len(value) == 34:
            return _pick(["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN"])
        # Cloud
        if value.startswith("GOCSPX-"):
            return _pick(["GOOGLE_OAUTH_CLIENT_SECRET", "GCP_OAUTH_SECRET"])
        if value.startswith("dop_v1_"):
            return _pick(["DIGITALOCEAN_TOKEN", "DO_TOKEN"])
        if value.startswith("rnd_"):
            return _pick(["RENDER_API_TOKEN", "RENDER_TOKEN"])
        if value.startswith("fo1_"):
            return "FLY_API_TOKEN"
        if value.startswith("sv=") and "&sig=" in value:
            return _pick(["AZURE_SAS_TOKEN", "STORAGE_SAS"])
        # SCM
        if value.startswith("glpat-"):
            return _pick(["GITLAB_TOKEN", "GITLAB_PAT", "CI_JOB_TOKEN"])
        # LLM/AI
        if value.startswith("r8_"):
            return _pick(["REPLICATE_API_TOKEN", "REPLICATE_KEY"])
        if value.startswith("gsk_"):
            return _pick(["GROQ_API_KEY", "GROQ_KEY"])
        if value.startswith("pplx-"):
            return _pick(["PERPLEXITY_API_KEY", "PERPLEXITY_KEY"])
        # Dev tools
        if value.startswith("npm_"):
            return _pick(["NPM_TOKEN", "NPM_AUTH_TOKEN"])
        if value.startswith("pypi-"):
            return _pick(["PYPI_TOKEN", "TWINE_PASSWORD"])
        if value.startswith("dckr_pat_"):
            return _pick(["DOCKERHUB_TOKEN", "DOCKER_TOKEN"])
        if value.startswith("https://") and ".ingest.sentry.io/" in value:
            return _pick(["SENTRY_DSN", "SENTRY_AUTH_DSN"])
        if value.startswith("NRAK-"):
            return _pick(["NEW_RELIC_USER_KEY", "NEW_RELIC_KEY"])
        if value.endswith("NRAL"):
            return _pick(["NEW_RELIC_LICENSE_KEY", "NR_LICENSE"])
        if value.startswith("phc_"):
            return _pick(["POSTHOG_API_KEY", "POSTHOG_PROJECT_KEY"])
        # Comms
        if value.startswith("xapp-"):
            return _pick(["SLACK_APP_TOKEN", "SLACK_WS_TOKEN"])
        if value.startswith("lin_api_"):
            return _pick(["LINEAR_API_KEY", "LINEAR_KEY"])
        if value.startswith("secret_") and len(value) >= 50:
            return _pick(["NOTION_API_KEY", "NOTION_TOKEN"])
        if value.startswith("pat") and "." in value and len(value) > 50:
            return _pick(["AIRTABLE_API_KEY", "AIRTABLE_TOKEN"])
        if value.startswith("https://outlook.office.com/webhook/"):
            return _pick(["TEAMS_WEBHOOK_URL", "MS_TEAMS_WEBHOOK"])
        # Payments / financial
        if value.startswith("whsec_"):
            return _pick(["STRIPE_WEBHOOK_SECRET", "WEBHOOK_SIGNING_SECRET"])
        if value.startswith("EAAA") and len(value) > 50:
            return _pick(["SQUARE_ACCESS_TOKEN", "SQUARE_TOKEN"])
        # Email/messaging
        if value.startswith("re_") and "_" in value[3:]:
            return _pick(["RESEND_API_KEY", "RESEND_KEY"])
        if value.startswith("xkeysib-"):
            return _pick(["BREVO_API_KEY", "SENDINBLUE_API_KEY"])
        if value.startswith("smtps://") or value.startswith("smtp://"):
            return _pick(["SMTP_URL", "EMAIL_URL"])
        # Auth
        if value.startswith("00") and len(value) == 42:
            return _pick(["OKTA_API_TOKEN", "OKTA_TOKEN"])
        # Cloudflare tokens are 40-char alnum with _- — hard to disambiguate
        # without a prefix; fall through to generic.
        # JSON service-account snippets — model treats whole snippet as one credential
        if value.startswith('{"type":"service_account"'):
            if "firebase" in value:
                return _pick(["FIREBASE_SERVICE_ACCOUNT", "GOOGLE_APPLICATION_CREDENTIALS"])
            return _pick(["GOOGLE_APPLICATION_CREDENTIALS", "GCP_SERVICE_ACCOUNT_JSON"])
        # PGP private key block
        if value.startswith("-----BEGIN PGP PRIVATE KEY"):
            return _pick(["PGP_PRIVATE_KEY", "GPG_KEY"])
    return _format_var_for_label(label)


# ─────────────────────────────────────────────────────────────────────────────
# 1. .env / config paste
# Real .env pastes: many lines, mix of secrets and non-secrets, comments, sometimes
# `export` prefixes, sometimes commented-out lines.

ENV_OPENERS_DEBUG = [
    "trying to figure out why my prod deploy keeps timing out. here's my docker env:",
    "anyone seen this? our staging container won't start with this config:",
    "double-checking my .env before pushing — does this look right?",
    "deploy failed on render, suspecting env vars. relevant ones:",
    "container exits immediately on startup. this is what i'm passing in:",
    "lambda cold-start is throwing 500s. env block:",
    "fly.io build went green but the app crashes on first request. config:",
    "k8s pod CrashLoopBackOff. configmap dump:",
    "vercel deploy is failing health check. .env.production:",
    "ci is green locally but breaks in prod. env diff suggests these:",
    "before i hand this off to ops — does this env look sane?",
    "trying to repro a bug locally. exporting prod-shaped env:",
]

ENV_OPENERS_REVIEW = [
    "PR review — flagging the env changes in this commit:",
    "added these to the helm values, does the format look right?",
    "migrating from heroku → fly. these are the env vars i need to set:",
    "code review: the new service needs these to boot. anything missing?",
    "redeploying staging with these vars, double-checking before i hit go:",
]

ENV_OPENERS = ENV_OPENERS_DEBUG + ENV_OPENERS_REVIEW

ENV_NON_SECRET_VARS = [
    ("NODE_ENV", "production"), ("NODE_ENV", "staging"), ("NODE_ENV", "development"),
    ("PORT", "3000"), ("PORT", "8080"), ("PORT", "4000"), ("PORT", "5000"),
    ("LOG_LEVEL", "info"), ("LOG_LEVEL", "debug"), ("LOG_LEVEL", "warn"),
    ("AWS_REGION", "us-east-1"), ("AWS_REGION", "eu-west-2"),
    ("AWS_REGION", "ap-south-1"),
    ("CORS_ORIGINS", "https://app.example.com"),
    ("RATE_LIMIT", "100"), ("MAX_RETRIES", "3"),
    ("REQUEST_TIMEOUT_MS", "30000"),
    ("FEATURE_FLAGS", "billing,search,export"),
    ("REDIS_TTL_SECONDS", "3600"),
    ("BUCKET_NAME", "prod-uploads-east"),
    ("REGION", "us-east-1"),
    ("APP_NAME", "checkout-service"),
    ("VERSION", "2.4.7"),
    ("BUILD_ID", "1842"),
    ("DEPLOY_TIMESTAMP", "2026-04-23T14:32:08Z"),
]

ENV_COMMENTS = [
    "# rotated last week",
    "# from 1password — vault: prod-keys",
    "# ops generated this on 03/14",
    "# DO NOT COMMIT",
    "# placeholder until terraform applies",
    "# new for v2.4 release",
    "# scoped to read-only",
]

ENV_CLOSERS = [
    "the app starts up fine but every request fails with 401. anyone hit this?",
    "is there something wrong with the format here?",
    "first time touching this service, no idea what's correct.",
    "container exits immediately with exit code 1. logs aren't useful.",
    "env vars seem right but the health check 502s.",
    "anyone have a working version of this i can compare against?",
    "if i missed one let me know.",
    "going to deploy this to staging in 10, shout if i shouldn't.",
    "ops, can you sanity-check?",
    "",  # sometimes no closer
]

def ctx_env(items, length: LengthMode = 'medium') -> str:
    opener = _pick(ENV_OPENERS)
    n_filler = {'short': random.randint(0, 1), 'medium': random.randint(2, 5), 'long': random.randint(8, 18)}[length]

    # Build env-var lines, interleaving real secrets with non-secrets
    lines = [opener, ""]
    if length != 'short' and random.random() < 0.5:
        lines.append(_pick([
            "# ---- " + _pick(["app", "db", "auth", "cache", "external"]) + " ----",
            "# from .env.production",
            "# (copy-pasted from helm values)",
        ]))

    # Mix entities and filler
    use_export = random.random() < 0.25
    rows = list(items)
    fillers = random.sample(ENV_NON_SECRET_VARS, min(n_filler, len(ENV_NON_SECRET_VARS)))

    interleaved = []
    pool = rows + [None] * len(fillers)
    random.shuffle(pool)
    fi = 0
    for slot in pool:
        if slot is None:
            k, v = fillers[fi]; fi += 1
            line = f"{k}={v}"
        else:
            label, value = slot
            line = f"{_format_var_for_value(label, value)}={annotate(value, label)}"
        if use_export:
            line = "export " + line
        # 10% chance of inline comment
        if random.random() < 0.10:
            line += "  " + _pick(ENV_COMMENTS)
        interleaved.append(line)

    lines.extend(interleaved)
    if random.random() < 0.6:
        lines.append("")
        lines.append(_pick(ENV_CLOSERS))
    return "\n".join(l for l in lines if l is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Error log / stack trace
# Real stack traces: error type + message, then frames. App frames mixed with
# library frames. Sometimes context fields (request_id, user_id, version).

ERR_OPENERS = [
    "got this in prod, can't repro locally:",
    "stack trace from sentry, wtf is going on:",
    "datadog flagged this run, anyone know what it means:",
    "this just started failing 30 min ago. only difference is the deploy at 2pm:",
    "alert fired, here's the trace:",
    "first time seeing this in prod. happens once every ~50 requests:",
    "log dump from the last failed run:",
    "prod is throwing this and i'm not finding it on stackoverflow:",
    "intermittent failure since the postgres upgrade. relevant trace:",
    "rolling back didn't fix it. trace from after the rollback:",
    "found this in the worker logs. pretty sure it's the auth piece:",
    "the test job failed but ci passed — race condition? trace:",
]

ERR_CLOSERS = [
    "anyone got a clue?",
    "is this the rds outage from earlier or something else?",
    "thinking it's the new middleware — going to revert that piece.",
    "filing an INC if this happens again in the next hour.",
    "going home, leaving this for the on-call.",
    "ping @oncall.",
    "",
]

def _stack_frame() -> str:
    return f"  at {gen_filepath()} in " + _pick([
        "handle_request", "process_message", "authenticate", "validate_input",
        "fetch_user", "apply_filter", "send_email", "encode_response",
        "open_session", "rollback", "commit_transaction", "publish_event",
    ])

def _context_field_line(label: str, value: str) -> str:
    field_name = _pick({
        "CREDENTIAL": ["secret", "auth_header", "token", "api_key_used", "session"],
        "EMAIL":      ["user_email", "from", "actor"],
        "PHONE":      ["phone", "contact"],
        "SSN":        ["ssn", "id_number"],
        "CREDIT_CARD":["card", "payment_method"],
    }[label])
    return f"  {field_name}={annotate(value, label)}"

def ctx_error_log(items, length: LengthMode = 'medium') -> str:
    opener = _pick(ERR_OPENERS)
    err_type = _pick(ERROR_TYPES)
    err_msg = _pick(ERROR_MESSAGES)
    n_frames = {'short': random.randint(2, 3), 'medium': random.randint(4, 8), 'long': random.randint(10, 25)}[length]

    lines = [opener, "", f"{err_type}: {err_msg}"]
    for _ in range(n_frames):
        lines.append(_stack_frame())

    # Interleave context fields
    if length in ('medium', 'long'):
        lines.append("")
        lines.append("context:")
        for label, value in items:
            lines.append(_context_field_line(label, value))
    else:
        # short: just append context fields after the trace
        for label, value in items:
            lines.append(_context_field_line(label, value))

    if length == 'long':
        lines.extend([
            "",
            f"request_id: {gen_uuid()}",
            f"build: {gen_short_sha()} ({_pick(DEPLOY_TARGETS)})",
            f"region: {_pick(CLUSTERS)}",
            f"version: 2.{random.randint(1,9)}.{random.randint(0,30)}",
        ])

    if random.random() < 0.7:
        lines.append("")
        lines.append(_pick(ERR_CLOSERS))
    return "\n".join(l for l in lines if l is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Support ticket / customer escalation

SUPPORT_OPENERS = [
    "Hey team, picking up the ticket from {name}.",
    "FYI escalating this one, customer is upset.",
    "Customer reached out twice now, need to resolve today.",
    "Got this from the inbox, looks blocked on us:",
    "Forwarding the latest from {name}'s thread:",
    "Came in via the support form 20 min ago:",
    "Phone call with this customer just now, sharing the highlights:",
    "Account migration question — passing to whoever's on rotation:",
    "Following up on {ticket} — they replied:",
    "VIP customer, please prioritize:",
    "Anyone free to take a stab at this? {ticket}:",
]

SUPPORT_CLOSERS = [
    "Anyone want to take this over?",
    "Pinging on-call.",
    "I'll keep them posted.",
    "Filing the refund myself unless objections.",
    "Closing as duplicate of {ticket}.",
    "Looping in @billing.",
    "Will follow up by EOD.",
    "Resolving once the cs replies.",
    "",
]

def _support_sentence(label: str, value: str) -> str:
    sentences = {
        "CREDENTIAL": [
            f"They had a session token leak — {annotate(value, label)} was visible in their browser console.",
            f"The auth cookie they shared in the screenshot is {annotate(value, label)}, please rotate.",
            f"Customer pasted this in chat: {annotate(value, label)}. We need to invalidate.",
            f"Their app key was exposed in the public repo: {annotate(value, label)}.",
            f"The webhook secret they're using is {annotate(value, label)} — mismatched with what we issued.",
        ],
        "EMAIL": [
            f"Their email is {annotate(value, label)} for follow-up.",
            f"Reply to {annotate(value, label)} with the resolution.",
            f"Login email on the account: {annotate(value, label)}.",
            f"Sending the receipt to {annotate(value, label)}.",
            f"They asked us to confirm via {annotate(value, label)}.",
        ],
        "PHONE": [
            f"Best contact is {annotate(value, label)} — they prefer SMS.",
            f"Call back at {annotate(value, label)} after 3pm PT.",
            f"Phone on the account: {annotate(value, label)}.",
            f"Voicemail box: {annotate(value, label)}.",
        ],
        "SSN": [
            f"Refund requires SSN verification: {annotate(value, label)}.",
            f"They sent SSN {annotate(value, label)} to confirm identity.",
            f"For tax docs, SSN on file is {annotate(value, label)}.",
        ],
        "CREDIT_CARD": [
            f"The card on file is {annotate(value, label)} — got double-charged Tuesday.",
            f"Customer's card {annotate(value, label)} was declined three times.",
            f"Refund pending to {annotate(value, label)}, will post in 3-5 days.",
            f"They updated payment method to {annotate(value, label)}.",
        ],
    }
    return _pick(sentences[label])

def ctx_support(items, length: LengthMode = 'medium') -> str:
    # Support tickets use proper-case names, even though the data pool includes
    # lowercase casual variants for chat contexts.
    name = gen_human_first().capitalize()
    ticket = gen_ticket()
    opener = _pick(SUPPORT_OPENERS).format(name=name, ticket=ticket)
    n_filler = {'short': 0, 'medium': random.randint(1, 2), 'long': random.randint(3, 6)}[length]

    lines = [opener, ""]

    # Random pre-context paragraph for medium/long
    if length in ('medium', 'long') and random.random() < 0.6:
        lines.append(_pick([
            f"Customer has been with us since 2022 — never had issues before this.",
            f"This is the third escalation about the same thing this week.",
            f"They're on the {_pick(['Pro', 'Team', 'Enterprise', 'Starter'])} plan, so we should respond fast.",
            f"Original ticket {gen_ticket()} from {_pick(DATE_RELATIVE)}.",
            f"They mentioned {gen_human_first().capitalize()} from our team helped them last time.",
        ]))
        lines.append("")

    for label, value in items:
        lines.append(_support_sentence(label, value))

    # Filler middle
    for _ in range(n_filler):
        lines.append(_pick([
            f"Looped in {gen_human_first()} from billing.",
            f"Logs from their session show no errors before the timeout.",
            f"Their last login was {_pick(DATE_RELATIVE)}.",
            f"Already issued a courtesy credit on the account.",
            f"Marked the case as P1.",
            f"Asked legal whether we can share the audit log with them.",
        ]))

    if random.random() < 0.7:
        lines.append("")
        lines.append(_pick(SUPPORT_CLOSERS).format(ticket=gen_ticket()))
    return "\n".join(l for l in lines if l is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Code with hardcoded values

CODE_OPENERS = [
    "is this safe to commit? my coworker says no but i don't see the issue:",
    "found this in legacy code, do we need to rotate?",
    "auth flow refactor — is the old version still in use anywhere?",
    "ported the integration from python to go, sanity check:",
    "old test fixture, can it be deleted?",
    "spot-checking the security review feedback:",
    "found this in the seed file. is the value real or fake?",
    "hardcoded fallback in the config loader, gross but works:",
    "migration script from intern's PR. flagging this:",
    "code from a past employee, want to know if i can rip it out:",
]

def ctx_code(items, length: LengthMode = 'medium') -> str:
    # Code-paste templates only make sense for CREDENTIAL — embedding an SSN or
    # CC into a `headers` dict produces nonsense ("X-Api-Key: <ccnum>"). Filter
    # to CREDENTIAL; if the caller passed only non-credentials, the orchestrator
    # should have routed elsewhere, but as a fallback we generate a fresh
    # CREDENTIAL value to avoid an empty body.
    items = [(l, v) for l, v in items if l == "CREDENTIAL"]
    if not items:
        from .formats import sample as _s
        items = [("CREDENTIAL", _s("CREDENTIAL"))]

    opener = _pick(CODE_OPENERS)
    # Restrict to languages with full handling here
    lang = _pick(["python", "typescript", "go"])
    n_pre = {'short': random.randint(0, 1), 'medium': random.randint(2, 4), 'long': random.randint(6, 12)}[length]

    pre_lines, post_lines = [], []
    if lang == "python":
        pre_lines = [
            "import os", "import requests", "from typing import Optional", "import json",
            "import logging", "from datetime import datetime",
        ][:n_pre]
        body = ["def authenticate(request):", "    headers = {"]
        for label, value in items:
            key = _pick(["Authorization", "X-Api-Key", "X-Token", "X-Auth"])
            body.append(f'        "{key}": "{annotate(value, label)}",')
        body.append("    }")
        body.append("    return requests.post(API_URL, headers=headers)")
        post_lines = [
            "    # TODO: rotate this monthly",
            "    # FIXME: use vault, not hardcoded",
            "",
        ][:random.randint(0, 2)]
    elif lang == "typescript":
        pre_lines = [
            "import { fetch } from 'undici';",
            "import { z } from 'zod';",
            "import type { Request } from './types';",
        ][:n_pre]
        body = ["async function authenticate(req: Request) {", "  const headers = {"]
        for label, value in items:
            key = _pick(["Authorization", "X-Api-Key", "X-Token"])
            body.append(f'    "{key}": "{annotate(value, label)}",')
        body.append("  };")
        body.append("  return fetch(API_URL, { headers });")
        body.append("}")
    else:  # go
        # Keep the import block atomic — slicing it would leave an unclosed paren
        pre_lines = ['import (', '    "net/http"', '    "fmt"', ')'] if n_pre > 0 else []
        body = ["func authenticate(r *http.Request) error {"]
        for label, value in items:
            key = _pick(["Authorization", "X-API-Key", "X-Token"])
            body.append(f'    r.Header.Set("{key}", "{annotate(value, label)}")')
        body.append("    return nil")
        body.append("}")

    fence = "```" + lang
    parts = [opener, ""]
    if pre_lines:
        parts.extend([fence, *pre_lines, "", *body, "```"])
    else:
        parts.extend([fence, *body, "```"])

    if length == 'long' and random.random() < 0.5:
        parts.extend(["", _pick([
            "i know hardcoding is bad. is there an easy fix without redeploying?",
            "context: this was added before we had vault. moving it now would touch ~12 callsites.",
            "the original author says it's only used in tests, but i'm seeing it imported by lib/server.py.",
        ])])

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Slack/Discord-style chat

CHAT_OPENERS = [
    "@{name} accidentally pasted this in #general 30s ago, deleted but might be in cache:",
    "forwarded from @{name}, fyi:",
    "@{name} flagged this in a PR comment:",
    "from the leak channel, looks like this needs rotation:",
    "ok don't @ me but i think i committed this. checking now:",
    "@{name} just pinged me about this, sharing here:",
    "ops sent this in dm, putting it here so it's findable:",
    "scrubbing chat for the audit, found this from {date}:",
    "{name} found this in an old slack thread. still active?",
    "csv export of leaked stuff from the bot:",
]

CHAT_BODIES_CRED = [
    "the value is {marker} — please rotate.",
    "check this: {marker}",
    "i used {marker} for the test run",
    "{marker} got committed to the repo, can someone revoke?",
    "found {marker} in the logs, who has access to revoke?",
    "what's the deal with {marker}? still in use?",
    "test creds: {marker} — fine to share?",
    "noticed {marker} in the screenshot, FYI",
    "this any good: {marker}",
    "yeah it's {marker}, we changed it last sprint",
]

CHAT_BODIES_PII = [
    "the contact is {marker} — pinging you in case you talk to them.",
    "saw {marker} in the screenshot, redacting before forwarding.",
    "their info: {marker}",
    "for your records, {marker}",
    "noticed {marker} in the audit log, fyi",
    "fwiw the customer's {marker} is on the ticket",
    "{marker} — shared in the channel by accident",
]

def ctx_chat(items, length: LengthMode = 'short') -> str:
    name = gen_human_first()
    date = _pick(DATE_RELATIVE)
    opener = _pick(CHAT_OPENERS).format(name=name, date=date)
    n_filler = {'short': 0, 'medium': random.randint(1, 2), 'long': random.randint(3, 6)}[length]

    lines = [opener, ""]
    for label, value in items:
        marker = annotate(value, label)
        body_pool = CHAT_BODIES_CRED if label == "CREDENTIAL" else CHAT_BODIES_PII
        lines.append(_pick(body_pool).format(marker=marker))

    for _ in range(n_filler):
        lines.append(_pick([
            f"@{gen_human_first().lower()} you saw this right?",
            "going to file an incident.",
            "lol who put this in plain text",
            "the audit is going to flag this for sure",
            "rotate first ask questions later",
            f"thread continues in #incidents-{gen_short_sha()[:4]}",
            "wtf",
            "ok fixing now",
        ]))
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Bug report / GitHub issue

BUG_TEMPLATES = [
    """## Bug
{summary}

## Reproduction
1. {step1}
2. {step2}
3. {step3}

## Environment
{env_block}

## Logs
{log_block}""",

    """### Description
{summary}

### Steps to reproduce
{step1}
{step2}
{step3}

### Expected
{expected}

### Actual
{actual}

### Config
{env_block}""",
]

BUG_SUMMARIES = [
    "Webhook delivery returns 401 even with a valid signature.",
    "Auth flow times out on the second factor when MFA is enabled.",
    "Session cookie is invalidated mid-request after the v2.4 deploy.",
    "Rate-limiter rejects the first request after the worker boots.",
    "Stripe payment intent confirmation 502s intermittently.",
    "OAuth state mismatch on the redirect when using the iOS app.",
    "Database connection pool exhaustion under low load.",
]

def ctx_bug_report(items, length: LengthMode = 'medium') -> str:
    template = _pick(BUG_TEMPLATES)
    summary = _pick(BUG_SUMMARIES)
    step1 = _pick([
        "Open the dashboard at https://app.example.com/orders",
        "Send POST to /api/v1/charge with valid params",
        "Trigger a webhook via the test panel",
        "Run `npm test integration/auth.test.ts`",
    ])
    step2 = _pick([
        "Wait for the response",
        "Open browser devtools → Network tab",
        "Check the queue worker logs",
        "Tail the application log",
    ])
    step3 = _pick([
        "Observe the 500 in the network panel",
        "See the error in the console",
        "Notice the duplicate row in the orders table",
        "Confirm the request never reaches the handler",
    ])
    expected = _pick([
        "200 OK with the resource body",
        "201 Created with the new ID",
        "Webhook delivered with status delivered=true",
        "Job processed and removed from queue",
    ])
    actual = _pick([
        "500 Internal Server Error every time",
        "401 Unauthorized after the first 3 retries",
        "Request hangs and eventually times out",
        "Resource is created but the response is empty",
    ])

    env_lines = []
    for label, value in items:
        env_lines.append(f"{_format_var_for_value(label, value)}={annotate(value, label)}")
    if length in ('medium', 'long'):
        env_lines.extend([
            f"NODE_ENV=production",
            f"REGION={_pick(CLUSTERS)}",
            f"BUILD={gen_short_sha()}",
        ])
    env_block = "\n".join(env_lines)

    log_block = "\n".join([
        f"{_pick(ERROR_TYPES)}: {_pick(ERROR_MESSAGES)}",
        f"  at {gen_filepath()}",
        f"  at {gen_filepath()}",
    ])

    return template.format(
        summary=summary, step1=step1, step2=step2, step3=step3,
        expected=expected, actual=actual,
        env_block=env_block, log_block=log_block,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. CI / deploy log paste

CI_OPENERS = [
    "ci run dumped env vars in the log, pasting the relevant bit:",
    "found this in the github actions output. is this exposed publicly?",
    "buildkite logged the secrets, here's what leaked:",
    "circle ci forgot to mask these. asking ops to invalidate:",
    "deploy job printed env on failure, snippet:",
    "k8s job logs show the env was dumped on crash. relevant lines:",
]

CI_CLOSERS = [
    "going to mark these as compromised.",
    "asking github to purge the run logs.",
    "@security what's the rotation playbook for this?",
    "filing INC.",
    "",
]

def ctx_ci_log(items, length: LengthMode = 'medium') -> str:
    opener = _pick(CI_OPENERS)
    n_pre = {'short': random.randint(1, 2), 'medium': random.randint(4, 8), 'long': random.randint(12, 25)}[length]

    job_id = random.randint(10**8, 10**9)
    lines = [opener, ""]
    lines.append(f"run #{job_id} ({_pick(DEPLOY_TARGETS)})")
    lines.append("")

    pre_filler = [
        "+ npm install --production",
        "+ go build ./...",
        "+ pip install -r requirements.txt",
        f"+ docker build -t {gen_service()}:{gen_short_sha()} .",
        "+ pytest -x --maxfail=1",
        "+ npm run typecheck",
        "✓ tests passed (124/124)",
        "✓ build artifact pushed",
        f"+ deploying to {_pick(CLUSTERS)}",
        "+ rolling restart in progress",
    ]
    for _ in range(n_pre):
        lines.append(_pick(pre_filler))

    lines.append("--- env ---")
    for label, value in items:
        lines.append(f"{_format_var_for_value(label, value)}={annotate(value, label)}")
    lines.append("--- end env ---")

    if length == 'long':
        lines.extend([
            "✗ healthcheck failed (5xx response)",
            "✗ rolling back to previous revision",
            f"✓ rollback complete in {random.randint(8,40)}s",
        ])

    if random.random() < 0.6:
        lines.append("")
        lines.append(_pick(CI_CLOSERS))
    return "\n".join(l for l in lines if l is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 8. Forwarded email / quoted message

EMAIL_FWD_OPENERS = [
    "fwd from {name} — sharing here for visibility:",
    "this just landed in my inbox, copying for the team:",
    "{name} forwarded this customer email, looping you in:",
    "got this from a partner over email. {name} wants to respond by EOD:",
    "leaving this here so it's findable. forwarded thread:",
]

def ctx_email_fwd(items, length: LengthMode = 'medium') -> str:
    name = gen_human_first().capitalize()
    opener = _pick(EMAIL_FWD_OPENERS).format(name=name)

    # Sender name needs to be properly cased for an email signature
    sender_first = gen_human_first().capitalize()
    sender = f"{sender_first} {gen_human_full().split()[1]}"
    sender_email = _pick(["s.lee@partner.io", "ops@vendor.com", "support@stripe.com",
                          f"{name.lower()}@external.co"])
    subject = _pick([
        "Re: production incident, our keys",
        "URGENT: account takeover suspected",
        "Re: API integration issue",
        "FYI — exposed credentials in your repo",
        "Following up on yesterday's call",
    ])

    lines = [
        opener,
        "",
        f"From: {sender} <{sender_email}>",
        f"Subject: {subject}",
        f"Date: {_pick(DATE_RELATIVE)}",
        "",
    ]

    body_template = _pick([
        "Hi team,\n\nWriting about the issue we discussed. The relevant values from our side:",
        "Hi,\n\nThanks for the quick turnaround. As discussed, here's what we have on file:",
        "Folks,\n\nFollowing up on the audit. The credentials in question:",
        "Hello,\n\nQuick note about the integration. The values currently in use:",
    ])
    lines.append(body_template)
    for label, value in items:
        lines.append(f"  • {annotate(value, label)}")

    if length in ('medium', 'long'):
        lines.append("")
        lines.append(_pick([
            "Let me know what you need from us to move forward.",
            "Available for a call this afternoon if helpful.",
            "Will rotate on our side once you confirm.",
            "Replying-all so the security team is in the loop.",
        ]))

    lines.extend(["", f"— {sender}"])
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 9. YAML / k8s / helm config

YAML_OPENERS = [
    "k8s secret before i kubectl apply — does this look ok?",
    "helm values for the prod release. flagging the secrets section:",
    "trying to reproduce the staging config locally. relevant values:",
    "configmap dump from the cluster, the auth piece:",
    "first time deploying to gke. is this the right shape for the secret?",
    "argo-cd is showing the secret as out-of-sync. local file:",
    "skaffold profile for dev — pulling secrets from `.env`:",
    "secret manifest review, please double-check the b64 values:",
    "values.yaml diff from the last release. credential changes:",
    "writing a sealed-secret. plaintext for review before sealing:",
]

YAML_CLOSERS = [
    "going to apply in 5 min unless someone says otherwise.",
    "is the namespace right or should this be in `infra`?",
    "we still on helm 3 or did infra move us to flux?",
    "this needs to roll out tonight, the deploy is queued.",
    "",
]

def ctx_yaml_config(items, length: LengthMode = 'medium') -> str:
    opener = _pick(YAML_OPENERS)
    n_filler = {'short': 1, 'medium': random.randint(3, 6), 'long': random.randint(8, 15)}[length]
    style = _pick(["k8s_secret", "helm_values", "compose_env"])

    lines = [opener, ""]

    if style == "k8s_secret":
        ns = _pick(["prod", "staging", "infra", "default", "platform"])
        name = _pick(["app-secrets", "db-creds", "third-party-keys", "stripe-prod", "auth-config"])
        lines.append("```yaml")
        lines.append("apiVersion: v1")
        lines.append("kind: Secret")
        lines.append(f"metadata:")
        lines.append(f"  name: {name}")
        lines.append(f"  namespace: {ns}")
        lines.append("type: Opaque")
        lines.append("stringData:")
        for label, value in items:
            var = _format_var_for_value(label, value).lower().replace("_", "-")
            lines.append(f"  {var}: {annotate(value, label)}")
        # Filler non-secret config
        for k, v in random.sample([
            ("log-level", "info"), ("port", "8080"), ("region", "us-east-1"),
            ("max-connections", "100"), ("timeout-seconds", "30"),
        ], min(n_filler, 5)):
            lines.append(f"  {k}: \"{v}\"")
        lines.append("```")

    elif style == "helm_values":
        lines.append("```yaml")
        lines.append(f"# values-{_pick(['prod', 'staging', 'dev'])}.yaml")
        lines.append("replicaCount: 3")
        lines.append("")
        lines.append("image:")
        lines.append(f"  repository: {gen_service()}")
        lines.append(f"  tag: {_pick(['1.4.7', '2.0.1', 'main', 'release-2026-04'])}")
        lines.append("")
        lines.append("env:")
        for label, value in items:
            var = _format_var_for_value(label, value)
            lines.append(f"  {var}: {annotate(value, label)}")
        if length == 'long':
            lines.append("")
            lines.append("resources:")
            lines.append("  requests:")
            lines.append("    cpu: 200m")
            lines.append("    memory: 512Mi")
            lines.append("  limits:")
            lines.append("    cpu: 1000m")
            lines.append("    memory: 2Gi")
        lines.append("```")

    else:  # compose_env
        lines.append("```yaml")
        lines.append("services:")
        lines.append(f"  {gen_service()}:")
        lines.append(f"    image: {gen_service()}:{_pick(['latest', 'main', '2.4.7'])}")
        lines.append("    environment:")
        for label, value in items:
            var = _format_var_for_value(label, value)
            lines.append(f"      {var}: {annotate(value, label)}")
        for k, v in [("LOG_LEVEL", "info"), ("REGION", "us-east-1")][:n_filler]:
            lines.append(f"      {k}: {v}")
        if length == 'long':
            lines.append("    ports:")
            lines.append("      - \"3000:3000\"")
            lines.append("    depends_on:")
            lines.append("      - postgres")
            lines.append("      - redis")
        lines.append("```")

    if random.random() < 0.5:
        lines.append("")
        lines.append(_pick(YAML_CLOSERS))
    return "\n".join(l for l in lines if l is not None)


# ─────────────────────────────────────────────────────────────────────────────
# 10. Dockerfile / docker-compose

DOCKER_OPENERS = [
    "trying to debug why the container can't auth at runtime. dockerfile:",
    "is it bad practice to bake secrets into the image like this?",
    "docker-compose for local dev — am i missing anything?",
    "container image build is failing on the auth step. relevant lines:",
    "moving from a Dockerfile to a multi-stage build, want to make sure i don't leak the build-time secret:",
]

def ctx_dockerfile(items, length: LengthMode = 'medium') -> str:
    opener = _pick(DOCKER_OPENERS)
    style = _pick(["dockerfile", "compose"])
    lines = [opener, ""]
    if style == "dockerfile":
        lines.append("```dockerfile")
        lines.append(_pick(["FROM node:20-alpine", "FROM python:3.11-slim", "FROM golang:1.22"]))
        lines.append("WORKDIR /app")
        lines.append("COPY . .")
        for label, value in items:
            var = _format_var_for_value(label, value)
            lines.append(f"ARG {var}")
            lines.append(f"ENV {var}={annotate(value, label)}")
        lines.append("RUN " + _pick(["npm ci", "pip install -r requirements.txt", "go mod download"]))
        lines.append("CMD " + _pick(["[\"node\", \"index.js\"]", "[\"python\", \"app.py\"]", "[\"./server\"]"]))
        lines.append("```")
    else:
        lines.append("```yaml")
        lines.append("# docker-compose.yml")
        lines.append("services:")
        lines.append(f"  {gen_service()}:")
        lines.append("    build: .")
        lines.append("    environment:")
        for label, value in items:
            var = _format_var_for_value(label, value)
            lines.append(f"      - {var}={annotate(value, label)}")
        lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 11. Terraform

TERRAFORM_OPENERS = [
    "terraform plan output is showing diff on this. before applying:",
    "first pass at the terraform module — is the secret block ok?",
    "migrating from random_password resources to externally-managed secrets:",
    "the plan failed in CI but local apply works. relevant snippet:",
    "what's the right way to pass these into the provider block?",
]

def ctx_terraform(items, length: LengthMode = 'medium') -> str:
    opener = _pick(TERRAFORM_OPENERS)
    lines = [opener, "", "```hcl"]
    style = _pick(["provider", "resource", "tfvars"])
    if style == "provider":
        lines.append('terraform {')
        lines.append('  required_providers {')
        lines.append('    aws = { source = "hashicorp/aws" }')
        lines.append('  }')
        lines.append('}')
        lines.append("")
        lines.append('provider "aws" {')
        lines.append(f'  region = "us-east-1"')
        for label, value in items:
            var = _format_var_for_value(label, value).lower()
            lines.append(f'  {var} = "{annotate(value, label)}"')
        lines.append('}')
    elif style == "resource":
        lines.append(f'resource "kubernetes_secret" "{_pick(["app", "stripe", "auth", "db"])}" {{')
        lines.append('  metadata {')
        lines.append(f'    name = "{_pick(["app-secrets", "third-party"])}"')
        lines.append('  }')
        lines.append('  data = {')
        for label, value in items:
            var = _format_var_for_value(label, value).lower()
            lines.append(f'    {var} = "{annotate(value, label)}"')
        lines.append('  }')
        lines.append('}')
    else:  # tfvars
        lines.append(f"# terraform.tfvars (do not commit)")
        lines.append(f'environment = "{_pick(["prod", "staging"])}"')
        lines.append(f'region      = "us-east-1"')
        for label, value in items:
            var = _format_var_for_value(label, value).lower()
            lines.append(f'{var} = "{annotate(value, label)}"')
    lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 12. curl / HTTP request

CURL_OPENERS = [
    "this curl 401s every time. the token is fresh, what am i missing?",
    "trying to repro the integration test failure. exact request:",
    "auth flow — the request goes through but the response body is empty:",
    "postman gives 200 but my curl gives 403. comparing headers:",
    "stripped down the failing curl to the minimum:",
    "the api docs say this should work, but i'm getting 502:",
]

def ctx_curl_request(items, length: LengthMode = 'medium') -> str:
    opener = _pick(CURL_OPENERS)
    method = _pick(["GET", "POST", "PUT"])
    endpoint = _pick([
        "https://api.example.com/v1/users", "https://api.stripe.com/v1/charges",
        "https://hooks.slack.com/services/T0/B0/abc", "https://api.openai.com/v1/chat/completions",
        f"https://{gen_service()}.internal/api/v2/{_pick(['users', 'orders', 'webhooks'])}",
    ])
    lines = [opener, "", "```bash"]
    cmd = [f"curl -X {method} '{endpoint}' \\"]
    for label, value in items:
        header = _pick(["Authorization: Bearer", "X-Api-Key:", "X-Auth-Token:", "Authorization:"])
        if header.endswith("Bearer"):
            cmd.append(f"  -H '{header} {annotate(value, label)}' \\")
        else:
            cmd.append(f"  -H '{header} {annotate(value, label)}' \\")
    if method != "GET":
        cmd.append("  -H 'Content-Type: application/json' \\")
        cmd.append("  -d '{\"amount\": 1000, \"currency\": \"usd\"}'")
    else:
        cmd[-1] = cmd[-1].rstrip(" \\")  # drop trailing backslash
    lines.extend(cmd)
    lines.append("```")
    if length in ('medium', 'long'):
        lines.append("")
        lines.append(_pick([
            "Response:",
            "Output:",
            "Got back:",
        ]))
        lines.append("```")
        lines.append(_pick([
            '{"error": {"message": "Invalid credentials", "code": "auth_failed"}}',
            '{"error": "Forbidden", "details": "Token expired"}',
            '{"status": "ok", "data": {...}}',
        ]))
        lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 13. SQL query / database operations

SQL_OPENERS = [
    "running this from a one-off script. is the connection string format right?",
    "data team needs me to spin up a temp user. flagging before i run:",
    "migration script — checking the credential setup:",
    "psql session output, the bit where i set up the new role:",
    "found this in an old runbook, want to know if it's still valid:",
]

def ctx_sql_query(items, length: LengthMode = 'medium') -> str:
    opener = _pick(SQL_OPENERS)
    lines = [opener, "", "```sql"]
    cred_items = [(l, v) for l, v in items if l == "CREDENTIAL"]
    pii_items = [(l, v) for l, v in items if l != "CREDENTIAL"]

    if cred_items:
        for label, value in cred_items:
            user = _pick(["app_user", "etl_user", "readonly", "writer", "analytics"])
            lines.append(f"CREATE USER {user} WITH PASSWORD '{annotate(value, label)}';")
            lines.append(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {user};")

    if pii_items:
        # Query results showing PII in rows
        lines.append("")
        lines.append("-- query result:")
        cols = " | ".join(["id", "email", "phone", "ssn", "card"])
        lines.append(f"-- {cols}")
        for label, value in pii_items:
            lines.append(f"-- {random.randint(1000, 9999)} | {annotate(value, label)}")

    lines.append("```")
    if length in ('medium', 'long') and random.random() < 0.5:
        lines.append("")
        lines.append(_pick([
            "this is for a one-off backfill. the user gets dropped after.",
            "is GRANT SELECT on `public` too broad?",
            "should i restrict by row-level security too?",
        ]))
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 14. Git diff paste

DIFF_OPENERS = [
    "PR review — looking at the env changes, this seems off:",
    "diff from the security audit branch, leaving comments inline:",
    "what got committed in the last merge — please review:",
    "before i merge, anyone want to flag the credential block:",
    "git diff between staging and main, env changes:",
]

def ctx_diff_paste(items, length: LengthMode = 'medium') -> str:
    opener = _pick(DIFF_OPENERS)
    fname = _pick([".env", ".env.production", "config/secrets.yml", "values.yaml", "infra/main.tf"])
    lines = [opener, "", "```diff"]
    lines.append(f"--- a/{fname}")
    lines.append(f"+++ b/{fname}")
    lines.append(f"@@ -{random.randint(1, 50)},{random.randint(3, 8)} +{random.randint(1, 50)},{random.randint(3, 8)} @@")
    # Some unchanged context lines
    lines.append(f" NODE_ENV=production")
    lines.append(f" PORT=8080")
    # The added (credential) lines
    for label, value in items:
        var = _format_var_for_value(label, value)
        lines.append(f"+{var}={annotate(value, label)}")
    # Maybe a removed line
    if random.random() < 0.5:
        lines.append(f"-OLD_API_KEY=dummy")
    lines.append(f" REGION=us-east-1")
    lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 15. Structured log lines

LOG_OPENERS = [
    "datadog pulled these log lines for the failed requests:",
    "loki query result for `{app=\"auth-gateway\"} |= \"401\"`:",
    "cloudwatch logs around the spike, headers field is concerning:",
    "json structured logs from the worker, the auth middleware piece:",
    "syslog format from the legacy service, sanitizing before sharing:",
]

def ctx_log_lines(items, length: LengthMode = 'medium') -> str:
    opener = _pick(LOG_OPENERS)
    n_lines = {'short': random.randint(2, 4), 'medium': random.randint(5, 10), 'long': random.randint(12, 25)}[length]
    lines = [opener, "", "```"]
    # Place items spread among filler log lines
    item_indices = sorted(random.sample(range(n_lines), min(len(items), n_lines)))
    item_iter = iter(items)
    for i in range(n_lines):
        ts = f"2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:{random.randint(0,59):02d}Z"
        if i in item_indices:
            try:
                label, value = next(item_iter)
                field = _pick(["authorization", "x_api_key", "session_token", "user_email", "phone", "card", "ssn"])
                lines.append(f'{{"ts":"{ts}","level":"warn","msg":"auth_attempt","{field}":"{annotate(value, label)}"}}')
            except StopIteration:
                pass
        else:
            lines.append(_pick([
                f'{{"ts":"{ts}","level":"info","msg":"request received","method":"GET","path":"/api/v1/users","status":200}}',
                f'{{"ts":"{ts}","level":"info","msg":"db connection","pool_size":10,"active":3}}',
                f'{{"ts":"{ts}","level":"warn","msg":"slow query","duration_ms":{random.randint(500, 2500)}}}',
                f'{{"ts":"{ts}","level":"info","msg":"cache hit","key":"user:{random.randint(1000,9999)}"}}',
            ]))
    lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 16. Internal runbook / postmortem

RUNBOOK_OPENERS = [
    "draft of the incident postmortem, can someone proof it before i publish:",
    "writing the runbook for the new on-call rotation. the auth section:",
    "wiki page for the new hire — credentials section:",
    "incident response doc, the credentials we rotated section:",
    "sre runbook for the {service} service. flagging the secret bits:",
]

def ctx_runbook_postmortem(items, length: LengthMode = 'medium') -> str:
    service = gen_service()
    opener = _pick(RUNBOOK_OPENERS).format(service=service)
    lines = [opener, ""]
    lines.append(f"# {_pick(['Postmortem', 'Runbook', 'Incident Report'])}: {service} {_pick(['outage', 'auth failure', 'credential leak'])}")
    lines.append("")
    lines.append(f"**Date:** 2026-{random.randint(1,12):02d}-{random.randint(1,28):02d}")
    lines.append(f"**Severity:** {_pick(['SEV1', 'SEV2', 'SEV3'])}")
    lines.append(f"**Author:** {gen_human_full()}")
    lines.append("")
    lines.append("## Summary")
    lines.append(_pick([
        f"At approximately {random.randint(1,12)}:{random.randint(0,59):02d} {_pick(['AM','PM'])} PT, {service} began returning 401s for all authenticated requests. Root cause was credential rotation that didn't propagate to the secret store.",
        f"A credential leak was discovered in the {service} repo. Affected credentials were rotated within {random.randint(15,90)} minutes of detection.",
        f"Customer reports of failed logins began at {random.randint(1,12)}:{random.randint(0,59):02d}. Investigation traced the issue to expired credentials in the {service} integration.",
    ]))
    lines.append("")
    lines.append("## Affected Credentials")
    lines.append("```")
    for label, value in items:
        var = _format_var_for_value(label, value)
        lines.append(f"{var}={annotate(value, label)}")
    lines.append("```")
    lines.append("")
    if length == 'long':
        lines.append("## Timeline")
        for i in range(random.randint(4, 8)):
            t = f"{random.randint(1,12):02d}:{random.randint(0,59):02d}"
            channel = _pick(['incidents', 'oncall', 'engineering'])
            event = _pick([
                f"{gen_human_first()} paged",
                f"alert fired in #{channel}",
                "rolled back",
                "rotated credentials",
                "ack received",
                "customer impact stopped",
            ])
            lines.append(f"- **{t}** — {event}")
        lines.append("")
        lines.append("## Action items")
        for _ in range(random.randint(2, 4)):
            action = _pick(['Add monitoring', 'Update runbook', 'Set up alert', 'Schedule rotation', 'Document'])
            lines.append(f"- [ ] {action} — owner: {gen_human_first()}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 17. Slack thread (multi-author)

SLACK_THREAD_OPENERS = [
    "thread from #incidents, sharing here for visibility:",
    "from the leak channel earlier, anonymizing names:",
    "context for the new oncall — read this before your shift:",
    "scrubbed thread before adding to the postmortem doc:",
    "this got buried, want eyes on it:",
]

def ctx_slack_thread(items, length: LengthMode = 'medium') -> str:
    opener = _pick(SLACK_THREAD_OPENERS)
    lines = [opener, ""]
    n_msgs = {'short': 2, 'medium': random.randint(4, 7), 'long': random.randint(8, 15)}[length]
    authors = [gen_human_first().capitalize() for _ in range(min(4, n_msgs))]
    item_idx = sorted(random.sample(range(n_msgs), min(len(items), n_msgs)))
    item_iter = iter(items)

    for i in range(n_msgs):
        author = _pick(authors)
        ts = f"{random.randint(1,12):02d}:{random.randint(0,59):02d}"
        if i in item_idx:
            try:
                label, value = next(item_iter)
                msg = _pick([
                    f"the value is `{annotate(value, label)}`. rotated yet?",
                    f"i found it: {annotate(value, label)}",
                    f"confirmed it's `{annotate(value, label)}` from the `.env`",
                    f"yeah it's {annotate(value, label)} — already pinged @security",
                    f"copy-pasting from the incident doc: `{annotate(value, label)}`",
                ])
            except StopIteration:
                msg = "lol nvm"
        else:
            msg = _pick([
                "any update?", "ack", "looking", "pulling logs now", ":eyes:",
                "thread continues", "anyone else seeing this?", "rolling back", "👀",
                "this was working an hour ago", "what changed in the last deploy?",
                "let me check", f"@{_pick(authors).lower()} can you take this?",
                "rotated. confirming impact.", "all clear from my end",
            ])
        lines.append(f"**{author}** [{ts}] {msg}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# 18. Jupyter notebook (markdown + code cells)

NB_OPENERS = [
    "notebook for the data sync job. flagging the auth cell:",
    "adapting an internal notebook for the public docs — checking what's safe:",
    "data team's exploratory notebook, the connection setup:",
    "EDA notebook with the api auth at the top — is the secret pattern fine here?",
    "training notebook, the data-loading section uses these creds:",
]

def ctx_jupyter_notebook(items, length: LengthMode = 'medium') -> str:
    opener = _pick(NB_OPENERS)
    lines = [opener, ""]
    lines.append("```")
    lines.append("# %% [markdown]")
    lines.append("# # Data sync — auth setup")
    lines.append("# Pulling from the prod data warehouse. Run cell-by-cell.")
    lines.append("")
    lines.append("# %%")
    lines.append("import os")
    lines.append("import requests")
    lines.append("import pandas as pd")
    lines.append("")
    lines.append("# %% [markdown]")
    lines.append("# ## Configure credentials")
    lines.append("")
    lines.append("# %%")
    for label, value in items:
        var = _format_var_for_value(label, value)
        lines.append(f'{var} = "{annotate(value, label)}"')
    lines.append("")
    lines.append("# %%")
    lines.append("response = requests.get('https://api.example.com/v1/users', headers={")
    lines.append("    'Authorization': f'Bearer {API_KEY}'")
    lines.append("})")
    lines.append("response.raise_for_status()")
    lines.append("```")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# Public registry: list of (context_fn, allowed_length_modes)

CONTEXTS: list[tuple[Callable, list[str]]] = [
    (ctx_env,                  ['short', 'medium', 'long']),
    (ctx_error_log,            ['short', 'medium', 'long']),
    (ctx_support,              ['short', 'medium', 'long']),
    (ctx_code,                 ['short', 'medium', 'long']),
    (ctx_chat,                 ['short', 'medium']),
    (ctx_bug_report,           ['medium', 'long']),
    (ctx_ci_log,               ['medium', 'long']),
    (ctx_email_fwd,            ['medium', 'long']),
    (ctx_yaml_config,          ['short', 'medium', 'long']),
    (ctx_dockerfile,           ['short', 'medium']),
    (ctx_terraform,            ['short', 'medium', 'long']),
    (ctx_curl_request,         ['short', 'medium', 'long']),
    (ctx_sql_query,            ['short', 'medium']),
    (ctx_diff_paste,           ['short', 'medium']),
    (ctx_log_lines,            ['short', 'medium', 'long']),
    (ctx_runbook_postmortem,   ['medium', 'long']),
    (ctx_slack_thread,         ['short', 'medium', 'long']),
    (ctx_jupyter_notebook,     ['medium', 'long']),
]


# Contexts whose body is structured (code, JSON, YAML, etc.) — voice modulation
# would mangle keywords or syntax. Skip them.
_VOICE_INCOMPATIBLE = {
    ctx_code, ctx_bug_report, ctx_ci_log, ctx_yaml_config, ctx_dockerfile,
    ctx_terraform, ctx_curl_request, ctx_sql_query, ctx_diff_paste,
    ctx_log_lines, ctx_jupyter_notebook,
}

def render_positive(items, length: LengthMode | None = None, voice: bool = True) -> str:
    """Pick a context that supports `length` and render."""
    if length is None:
        length = random.choices(['short', 'medium', 'long'], weights=[0.30, 0.45, 0.25])[0]
    candidates = [(fn, mods) for fn, mods in CONTEXTS if length in mods]
    fn, _ = random.choice(candidates)
    text = fn(items, length)
    if voice and random.random() < 0.20 and fn not in _VOICE_INCOMPATIBLE:
        text = apply_voice(text)
    return text
