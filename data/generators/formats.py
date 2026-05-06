"""
Credential value generators — one function per format. Each returns the literal
credential value with no surrounding context. Realism goal: lengths, prefixes,
and character classes match what's in the wild (verified against vendor docs and
gitleaks rule sets).
"""

import random
import string
from typing import Callable

ALNUM = string.ascii_letters + string.digits
HEX = string.hexdigits.lower()


def _alnum(n: int, alphabet: str = ALNUM) -> str:
    # NOTE: random.choice (not secrets.choice). The seed must control all
    # randomness for reproducibility. `secrets` uses OS crypto RNG which
    # bypasses the seed.
    return "".join(random.choice(alphabet) for _ in range(n))


# ── AWS ───────────────────────────────────────────────────────────────────────
def gen_aws_access_key() -> str:
    prefix = random.choice(["AKIA", "ASIA", "AROA"])  # ASIA = session, AROA = role
    return prefix + _alnum(16, string.ascii_uppercase + string.digits)

def gen_aws_secret() -> str:
    return _alnum(40, ALNUM + "/+")

def gen_aws_session_token() -> str:
    # session tokens are long base64-ish blobs
    return _alnum(random.randint(150, 250), ALNUM + "/+=")


# ── GitHub ────────────────────────────────────────────────────────────────────
def gen_github_pat() -> str:
    prefix = random.choice(["ghp_", "gho_", "ghu_", "ghs_", "ghr_"])
    return prefix + _alnum(36)

def gen_github_fine_grained() -> str:
    # github_pat_<11>_<59> format
    return f"github_pat_{_alnum(11)}_{_alnum(59)}"


# ── LLM provider keys ─────────────────────────────────────────────────────────
def gen_anthropic_key() -> str:
    return f"sk-ant-api{random.randint(1, 9):02d}-" + _alnum(random.randint(80, 95), ALNUM + "_-")

def gen_openai_key() -> str:
    # Both legacy and project-scoped (sk-proj-) variants
    if random.random() < 0.5:
        return "sk-" + _alnum(48)
    return "sk-proj-" + _alnum(58)

def gen_google_api_key() -> str:
    return "AIza" + _alnum(35)

def gen_cohere_key() -> str:
    return _alnum(40)  # cohere keys are unprefixed alnum

def gen_huggingface_token() -> str:
    return "hf_" + _alnum(34)


# ── SaaS keys ─────────────────────────────────────────────────────────────────
def gen_slack_token() -> str:
    kind = random.choice(["xoxb", "xoxp", "xoxa", "xoxr", "xoxe"])
    return f"{kind}-{random.randint(10**11, 10**12-1)}-{random.randint(10**11, 10**12-1)}-{_alnum(24)}"

def gen_slack_webhook() -> str:
    return f"https://hooks.slack.com/services/T{_alnum(10, string.ascii_uppercase + string.digits)}/B{_alnum(10, string.ascii_uppercase + string.digits)}/{_alnum(24)}"

def gen_stripe_key() -> str:
    kind = random.choice(["sk_live", "sk_test", "pk_live", "pk_test", "rk_live", "rk_test"])
    return f"{kind}_" + _alnum(random.randint(24, 32))

def gen_twilio_sid() -> str:
    prefix = random.choice(["AC", "SK", "PN", "SM"])
    return prefix + _alnum(32, HEX)

def gen_sendgrid_key() -> str:
    return f"SG.{_alnum(22)}.{_alnum(43)}"

def gen_mailgun_key() -> str:
    return f"key-{_alnum(32, HEX)}"

def gen_datadog_key() -> str:
    return _alnum(32, HEX)


# ── Generic / token formats ───────────────────────────────────────────────────
def gen_jwt() -> str:
    return f"eyJ{_alnum(random.randint(20, 30), ALNUM + '-_')}.eyJ{_alnum(random.randint(40, 80), ALNUM + '-_')}.{_alnum(random.randint(43, 64), ALNUM + '-_')}"

def gen_bearer_opaque() -> str:
    # opaque bearer tokens: long random alnum
    return _alnum(random.randint(40, 64))

def gen_uuid_token() -> str:
    g = random.getrandbits
    return f"{g(32):08x}-{g(16):04x}-{g(16):04x}-{g(16):04x}-{g(48):012x}"


# ── DB connection strings ─────────────────────────────────────────────────────
def gen_db_uri() -> str:
    proto = random.choice([
        "postgresql", "postgres", "mysql", "mongodb", "mongodb+srv",
        "redis", "rediss", "amqp", "amqps",
    ])
    user = random.choice([
        "app", "api", "service", "prod_user", "admin", "ro_user", "writer",
        "etl", "analytics", "migrator", "cache_user",
    ])
    pw = _alnum(random.randint(12, 28), ALNUM + "_-")
    host = random.choice([
        "db.prod.internal",
        "primary.cluster-cba9.us-east-1.rds.amazonaws.com",
        "db-replica.staging.svc.cluster.local",
        "10.0.4.12", "172.21.5.88",
        "redis-master.cache.amazonaws.com",
        f"db-{random.randint(1,9)}.internal",
    ])
    port = random.choice([5432, 3306, 27017, 6379, 5672, 5439])
    name = random.choice(["orders", "users", "events", "main", "app", "audit",
                          "warehouse", "billing", "sessions", "graph"])
    return f"{proto}://{user}:{pw}@{host}:{port}/{name}"


# ── Private keys ──────────────────────────────────────────────────────────────
def gen_private_key_block() -> str:
    body_lines = "\n".join(
        _alnum(64, ALNUM + "+/=") for _ in range(random.randint(3, 8))
    )
    kind = random.choice(["RSA ", "OPENSSH ", "EC ", "DSA ", ""])
    return f"-----BEGIN {kind}PRIVATE KEY-----\n{body_lines}\n-----END {kind}PRIVATE KEY-----"

def gen_ssh_public_key() -> str:
    # Public key pasted as a value — model should NOT block, since publishing
    # public keys is normal. We don't include this in CREDENTIAL training.
    return f"ssh-rsa {_alnum(372, ALNUM + '+/=')} user@host"


# ── Passwords (literal, in-the-wild distribution) ─────────────────────────────
PW_WORDS = [
    "sun", "rocket", "blue", "tiger", "neon", "river", "atlas", "nova",
    "delta", "cobra", "phoenix", "shadow", "panda", "echo", "lemon", "wolf",
    "winter", "marble", "comet", "fjord", "amber",
]

def gen_password() -> str:
    style = random.choice(["wordnum", "wordnumsym", "twoword", "phrase", "leet"])
    if style == "wordnum":
        return random.choice(PW_WORDS) + str(random.randint(1, 9999))
    if style == "wordnumsym":
        return random.choice(PW_WORDS) + str(random.randint(1, 9999)) + random.choice("!$#*@-_")
    if style == "twoword":
        return random.choice(PW_WORDS).capitalize() + random.choice(PW_WORDS).capitalize() + str(random.randint(10, 99))
    if style == "phrase":
        return "-".join(random.choice(PW_WORDS) for _ in range(random.randint(3, 5))) + str(random.randint(10, 99))
    # leet
    s = random.choice(PW_WORDS) + random.choice(PW_WORDS)
    return s.replace("e", "3").replace("o", "0").replace("i", "1") + "!"


# ── Email / phone / SSN / CC ──────────────────────────────────────────────────
EMAIL_USERS = [
    "jane.smith", "alex", "k.tanaka", "support", "d.morales", "billing",
    "noreply", "j.kim", "marco", "team", "ops", "security", "admin",
    "m.patel", "rwilliams", "n.chen", "info", "contact", "hello",
]
EMAIL_DOMAINS = [
    "example.com", "company.io", "acme.co", "internal.corp",
    "gmail.com", "outlook.com", "protonmail.com", "yahoo.com",
    "fastmail.com", "icloud.com", "duck.com",
    "stripe.com", "twilio.com", "cloudflare.com",  # mid-realistic SaaS
]

def gen_email() -> str:
    user = random.choice(EMAIL_USERS)
    if random.random() < 0.2:
        user += str(random.randint(1, 99))
    return f"{user}@{random.choice(EMAIL_DOMAINS)}"

def gen_phone() -> str:
    formats = [
        lambda: f"+1-{random.randint(200,999)}-{random.randint(200,999)}-{random.randint(1000,9999)}",
        lambda: f"+1 ({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
        lambda: f"({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
        lambda: f"{random.randint(200,999)}.{random.randint(200,999)}.{random.randint(1000,9999)}",
        lambda: f"{random.randint(200,999)}-{random.randint(200,999)}-{random.randint(1000,9999)}",
        lambda: f"+44 {random.randint(20,79)} {random.randint(1000,9999)} {random.randint(1000,9999)}",
        lambda: f"+33 {random.randint(1,9)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}",
        lambda: f"+81 {random.randint(3,9)} {random.randint(1000,9999)} {random.randint(1000,9999)}",
    ]
    return random.choice(formats)()

def gen_ssn() -> str:
    return f"{random.randint(100, 899)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"

def gen_credit_card() -> str:
    """Visa-prefix CC with valid Luhn check digit."""
    digits = [random.randint(0, 9) for _ in range(15)]
    digits[0] = 4  # Visa prefix
    s = sum(d if i % 2 else (d * 2 if d * 2 < 10 else d * 2 - 9)
            for i, d in enumerate(reversed(digits)))
    check = (10 - (s % 10)) % 10
    full = digits + [check]
    sep = random.choice(["-", " ", ""])
    return sep.join("".join(str(d) for d in full[i:i+4]) for i in range(0, 16, 4))


# ── Cloud providers (extended) ────────────────────────────────────────────────
def gen_gcp_oauth_secret() -> str:
    # GCP OAuth client secrets are 24-char alnum, often prefixed GOCSPX-
    return "GOCSPX-" + _alnum(28)

def gen_gcp_service_account_snippet() -> str:
    # A short JSON snippet that contains the private_key field — what people paste
    # when sharing a service account
    pk = _alnum(64, ALNUM + "+/=")
    return (
        '{"type":"service_account","project_id":"prod-' + _alnum(8).lower() + '",'
        '"private_key_id":"' + _alnum(40, HEX) + '",'
        '"private_key":"-----BEGIN PRIVATE KEY-----\\n' + pk + '\\n-----END PRIVATE KEY-----\\n"}'
    )

def gen_azure_storage_key() -> str:
    return _alnum(88, ALNUM + "+/=")

def gen_azure_sas_token() -> str:
    sig = _alnum(43, ALNUM + "%/+")
    return f"sv=2022-11-02&ss=b&srt=sco&sp=rwdlacx&se=2026-12-31T23:59:00Z&sig={sig}"

def gen_azure_ad_secret() -> str:
    return _alnum(40, ALNUM + "._~-")

def gen_cloudflare_api_token() -> str:
    return _alnum(40, ALNUM + "_-")

def gen_cloudflare_global_key() -> str:
    return _alnum(37, HEX)

def gen_digitalocean_token() -> str:
    return "dop_v1_" + _alnum(64, HEX)

def gen_linode_pat() -> str:
    return _alnum(64, HEX)

def gen_heroku_api_key() -> str:
    g = random.getrandbits
    return f"{g(32):08x}-{g(16):04x}-{g(16):04x}-{g(16):04x}-{g(48):012x}"

def gen_render_token() -> str:
    return "rnd_" + _alnum(28)

def gen_vercel_token() -> str:
    return _alnum(24, ALNUM)

def gen_netlify_token() -> str:
    return _alnum(40, ALNUM + "_-")

def gen_fly_token() -> str:
    return "fo1_" + _alnum(43, ALNUM + "_-")

def gen_railway_token() -> str:
    g = random.getrandbits
    return f"{g(32):08x}-{g(16):04x}-{g(16):04x}-{g(16):04x}-{g(48):012x}"


# ── SCM / CI (extended) ───────────────────────────────────────────────────────
def gen_gitlab_pat() -> str:
    return "glpat-" + _alnum(20, ALNUM + "_-")

def gen_gitlab_pipeline_token() -> str:
    return _alnum(20, ALNUM + "_-")

def gen_bitbucket_app_password() -> str:
    return _alnum(32, ALNUM)

def gen_circleci_token() -> str:
    return _alnum(40, HEX)

def gen_drone_token() -> str:
    return _alnum(32, ALNUM)

def gen_buildkite_agent_token() -> str:
    return _alnum(40, ALNUM)


# ── LLM / AI (extended) ───────────────────────────────────────────────────────
def gen_mistral_key() -> str:
    return _alnum(32, ALNUM)

def gen_together_key() -> str:
    return _alnum(64, HEX)

def gen_replicate_key() -> str:
    return "r8_" + _alnum(40, ALNUM)

def gen_groq_key() -> str:
    return "gsk_" + _alnum(52, ALNUM)

def gen_fireworks_key() -> str:
    return _alnum(40, ALNUM)

def gen_perplexity_key() -> str:
    return "pplx-" + _alnum(48, ALNUM)


# ── Dev tools / observability ─────────────────────────────────────────────────
def gen_npm_token() -> str:
    g = random.getrandbits
    return f"npm_" + _alnum(36, ALNUM)

def gen_pypi_token() -> str:
    # Real PyPI tokens: pypi-AgEIcHlwaS5vcmc...{long base64ish}
    return "pypi-AgEIcHlwaS5vcmc" + _alnum(random.randint(120, 180), ALNUM + "_-")

def gen_dockerhub_pat() -> str:
    g = random.getrandbits
    return f"dckr_pat_" + _alnum(36, ALNUM + "_-")

def gen_sentry_dsn() -> str:
    key = _alnum(32, HEX)
    proj = random.randint(100000, 9999999)
    org = random.randint(10000, 999999)
    return f"https://{key}@o{org}.ingest.sentry.io/{proj}"

def gen_newrelic_license() -> str:
    return _alnum(36, ALNUM) + "NRAL"

def gen_newrelic_user_key() -> str:
    return "NRAK-" + _alnum(27, string.ascii_uppercase + string.digits)

def gen_honeycomb_key() -> str:
    return _alnum(64, HEX)

def gen_splunk_hec_token() -> str:
    g = random.getrandbits
    return f"{g(32):08x}-{g(16):04x}-{g(16):04x}-{g(16):04x}-{g(48):012x}"

def gen_pagerduty_key() -> str:
    return _alnum(32, ALNUM)

def gen_bugsnag_key() -> str:
    return _alnum(32, HEX)

def gen_posthog_project_key() -> str:
    return "phc_" + _alnum(43, ALNUM)


# ── Comms / SaaS (extended) ───────────────────────────────────────────────────
def gen_slack_signing_secret() -> str:
    return _alnum(32, HEX)

def gen_slack_app_token() -> str:
    return f"xapp-1-" + _alnum(11, string.ascii_uppercase + string.digits) + "-" + _alnum(13, string.digits) + "-" + _alnum(64, ALNUM)

def gen_discord_bot_token() -> str:
    # Format: <base64 user id>.<base64 timestamp>.<base64 hmac>
    return f"{_alnum(24, ALNUM + '-_')}.{_alnum(6, ALNUM + '-_')}.{_alnum(38, ALNUM + '-_')}"

def gen_telegram_bot_token() -> str:
    return f"{random.randint(10**8, 10**10)}:" + _alnum(35, ALNUM + "-_")

def gen_msgraph_token() -> str:
    # MS Graph tokens are JWTs but extra long
    return f"eyJ0eXAi{_alnum(180, ALNUM + '-_.')}.eyJ{_alnum(800, ALNUM + '-_.')}.{_alnum(342, ALNUM + '-_')}"

def gen_teams_webhook() -> str:
    return f"https://outlook.office.com/webhook/{gen_uuid_token()}/IncomingWebhook/{_alnum(32, HEX)}/{gen_uuid_token()}"

def gen_zoom_jwt() -> str:
    return gen_jwt()  # Zoom uses standard JWTs

def gen_linear_api_key() -> str:
    return "lin_api_" + _alnum(40, ALNUM)

def gen_notion_token() -> str:
    return "secret_" + _alnum(43, ALNUM)

def gen_airtable_token() -> str:
    return "pat" + _alnum(14, ALNUM) + "." + _alnum(64, HEX)


# ── Payments (extended) ───────────────────────────────────────────────────────
def gen_stripe_webhook_secret() -> str:
    return "whsec_" + _alnum(32, ALNUM)

def gen_plaid_secret() -> str:
    return _alnum(30, HEX)

def gen_plaid_client_id() -> str:
    return _alnum(24, HEX)

def gen_square_access_token() -> str:
    return f"EAAA{_alnum(60, ALNUM + '_-')}"

def gen_paypal_client_secret() -> str:
    return f"E{_alnum(79, ALNUM + '_-')}"

def gen_braintree_merchant_key() -> str:
    return _alnum(32, ALNUM)

def gen_adyen_api_key() -> str:
    return f"AQE{_alnum(140, ALNUM + '+/=')}"


# ── Email / messaging (extended) ──────────────────────────────────────────────
def gen_mailchimp_key() -> str:
    return _alnum(32, HEX) + "-us" + str(random.randint(1, 21))

def gen_postmark_token() -> str:
    g = random.getrandbits
    return f"{g(32):08x}-{g(16):04x}-{g(16):04x}-{g(16):04x}-{g(48):012x}"

def gen_resend_key() -> str:
    return "re_" + _alnum(32, ALNUM + "_")

def gen_brevo_key() -> str:
    return "xkeysib-" + _alnum(64, HEX) + "-" + _alnum(16, ALNUM)

def gen_smtp_url() -> str:
    user = random.choice(["postmaster", "smtp", "mailer", "relay"])
    pw = _alnum(random.randint(16, 28), ALNUM)
    host = random.choice(["smtp.sendgrid.net", "smtp.mailgun.org", "smtp.postmarkapp.com",
                          "email-smtp.us-east-1.amazonaws.com"])
    return f"smtps://{user}:{pw}@{host}:587"


# ── Auth / identity ───────────────────────────────────────────────────────────
def gen_auth0_client_secret() -> str:
    return _alnum(64, ALNUM + "_-")

def gen_okta_token() -> str:
    return "00" + _alnum(40, ALNUM + "_-")

def gen_clerk_secret() -> str:
    # Clerk uses sk_live_* and sk_test_* — note: format clashes with Stripe sk_*
    # Differentiated by the var name being CLERK_SECRET_KEY vs STRIPE_SECRET_KEY.
    kind = random.choice(["sk_live", "sk_test"])
    return f"{kind}_" + _alnum(48, ALNUM)

def gen_keycloak_secret() -> str:
    g = random.getrandbits
    return f"{g(32):08x}-{g(16):04x}-{g(16):04x}-{g(16):04x}-{g(48):012x}"

def gen_firebase_service_account_snippet() -> str:
    pk = _alnum(64, ALNUM + "+/=")
    return (
        '{"type":"service_account","project_id":"firebase-' + _alnum(8).lower() + '",'
        '"private_key":"-----BEGIN PRIVATE KEY-----\\n' + pk + '\\n-----END PRIVATE KEY-----\\n",'
        '"client_email":"firebase-adminsdk-' + _alnum(5).lower() + '@firebase.iam.gserviceaccount.com"}'
    )


# ── DB / storage (extended) ───────────────────────────────────────────────────
def gen_supabase_anon_key() -> str:
    # Supabase keys are JWTs
    return gen_jwt()

def gen_supabase_service_role_key() -> str:
    return gen_jwt()

def gen_mongodb_atlas_key() -> str:
    return _alnum(32, HEX)

def gen_snowflake_creds() -> str:
    user = random.choice(["ANALYTICS_USER", "ETL_USER", "ADMIN", "READER"])
    pw = _alnum(20, ALNUM)
    account = _alnum(8, string.ascii_lowercase) + ".us-east-1"
    return f"{user}:{pw}@{account}.snowflakecomputing.com"

def gen_algolia_admin_key() -> str:
    return _alnum(32, HEX)

def gen_elastic_cloud_key() -> str:
    # Format: <id>:<base64 of host:apikey>
    payload = _alnum(80, ALNUM + "+/=")
    return _alnum(20, ALNUM) + ":" + payload


# ── Generic / cryptographic (extended) ────────────────────────────────────────
def gen_wireguard_private_key() -> str:
    # WireGuard private keys: 32 bytes, base64 = 44 chars ending with =
    return _alnum(43, ALNUM + "+/") + "="

def gen_pgp_private_key_block() -> str:
    body = "\n".join(_alnum(64, ALNUM + "+/=") for _ in range(random.randint(8, 16)))
    return (
        "-----BEGIN PGP PRIVATE KEY BLOCK-----\n"
        "Version: GnuPG v2\n\n"
        f"{body}\n"
        "-----END PGP PRIVATE KEY BLOCK-----"
    )

def gen_generic_webhook_secret() -> str:
    return "whsec_" + _alnum(random.randint(28, 40), ALNUM)

def gen_dkim_private_selector() -> str:
    # DKIM private keys are RSA usually; this returns the private form
    return gen_private_key_block()


# ── Public registry ───────────────────────────────────────────────────────────
# label → list of generator callables
FORMATS: dict[str, list[Callable[[], str]]] = {
    "CREDENTIAL": [
        # Existing
        gen_aws_access_key, gen_aws_secret, gen_aws_session_token,
        gen_github_pat, gen_github_fine_grained,
        gen_anthropic_key, gen_openai_key, gen_google_api_key,
        gen_cohere_key, gen_huggingface_token,
        gen_slack_token, gen_slack_webhook, gen_stripe_key,
        gen_twilio_sid, gen_sendgrid_key, gen_mailgun_key, gen_datadog_key,
        gen_jwt, gen_bearer_opaque, gen_uuid_token,
        gen_db_uri, gen_private_key_block,
        # Cloud
        gen_gcp_oauth_secret, gen_gcp_service_account_snippet,
        gen_azure_storage_key, gen_azure_sas_token, gen_azure_ad_secret,
        gen_cloudflare_api_token, gen_cloudflare_global_key,
        gen_digitalocean_token, gen_linode_pat, gen_heroku_api_key,
        gen_render_token, gen_vercel_token, gen_netlify_token,
        gen_fly_token, gen_railway_token,
        # SCM/CI
        gen_gitlab_pat, gen_gitlab_pipeline_token,
        gen_bitbucket_app_password, gen_circleci_token,
        gen_drone_token, gen_buildkite_agent_token,
        # LLM/AI
        gen_mistral_key, gen_together_key, gen_replicate_key,
        gen_groq_key, gen_fireworks_key, gen_perplexity_key,
        # Dev tools / observability
        gen_npm_token, gen_pypi_token, gen_dockerhub_pat,
        gen_sentry_dsn, gen_newrelic_license, gen_newrelic_user_key,
        gen_honeycomb_key, gen_splunk_hec_token, gen_pagerduty_key,
        gen_bugsnag_key, gen_posthog_project_key,
        # Comms/SaaS
        gen_slack_signing_secret, gen_slack_app_token,
        gen_discord_bot_token, gen_telegram_bot_token,
        gen_msgraph_token, gen_teams_webhook, gen_zoom_jwt,
        gen_linear_api_key, gen_notion_token, gen_airtable_token,
        # Payments
        gen_stripe_webhook_secret, gen_plaid_secret, gen_plaid_client_id,
        gen_square_access_token, gen_paypal_client_secret,
        gen_braintree_merchant_key, gen_adyen_api_key,
        # Email/messaging
        gen_mailchimp_key, gen_postmark_token, gen_resend_key,
        gen_brevo_key, gen_smtp_url,
        # Auth/identity
        gen_auth0_client_secret, gen_okta_token, gen_clerk_secret,
        gen_keycloak_secret, gen_firebase_service_account_snippet,
        # DB/storage
        gen_supabase_anon_key, gen_supabase_service_role_key,
        gen_mongodb_atlas_key, gen_snowflake_creds,
        gen_algolia_admin_key, gen_elastic_cloud_key,
        # Generic / cryptographic
        gen_wireguard_private_key, gen_pgp_private_key_block,
        gen_generic_webhook_secret, gen_dkim_private_selector,
        # Passwords (weighted higher because they're the most common
        # in-the-wild credential type)
        gen_password, gen_password, gen_password, gen_password,
    ],
    "EMAIL":       [gen_email],
    "PHONE":       [gen_phone],
    "SSN":         [gen_ssn],
    "CREDIT_CARD": [gen_credit_card],
}


def sample(label: str) -> str:
    return random.choice(FORMATS[label])()


def annotate(value: str, label: str) -> str:
    return f"[{value}|{label}]"
