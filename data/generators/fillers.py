"""
Realistic filler content — used to vary surrounding context in templates without
introducing PII. Keep these grounded in plausible developer-world vocabulary;
avoid placeholder-y stuff like "John Doe" or "Acme Corp" that screams synthetic.
"""

import random

# Diverse first names. NOT used as PII labels — these appear in surrounding prose
# (e.g. "Sarah said the deploy broke") and are intentionally not redacted by our
# label set, since names destroy debugging context if redacted.
FIRST_NAMES = [
    "Sarah", "Marcus", "Yuki", "Amara", "Kwame", "Priya", "Diego", "Anya",
    "Rohan", "Maria", "Kai", "Naomi", "Taro", "Chen", "Aisha", "Henrik",
    "Lina", "Jamal", "Olu", "Mei", "Ravi", "Sofia", "Theo", "Jin",
    "Dani", "Asha", "Felipe", "Nadia", "Omar", "Eva", "Sam", "Riya",
    "Tomás", "Adaeze", "Lucas", "Hina", "Nico", "Imani", "Bao", "Tara",
    "alex", "jen", "morgan", "rae", "kris",  # lowercase ones for casual chat
]

LAST_NAMES = [
    "Chen", "Patel", "Okafor", "Rodríguez", "Tanaka", "Kim", "Singh",
    "Johansson", "Mensah", "Alvarez", "Liu", "Nakamura", "Adebayo",
    "Brennan", "Volkov", "Achebe", "Kowalski", "Park", "Diallo", "Reyes",
]

# Internal-sounding service / repo names. Used in stack traces and incident reports.
SERVICE_NAMES = [
    "payments-service", "auth-gateway", "notifications-api", "billing-worker",
    "inventory-sync", "user-service", "order-processor", "search-indexer",
    "ml-pipeline", "checkout-api", "fraud-detector", "report-generator",
    "webhooks-relay", "session-store", "media-uploader", "analytics-ingest",
    "feature-flags", "scheduler", "edge-router", "audit-log",
]

# Realistic file paths across languages. Mix of monorepo and single-package layouts.
FILE_PATHS = [
    "services/uploader.py", "api/middleware.py", "lib/auth.ts",
    "src/payments/processor.go", "internal/queue/dispatcher.rs",
    "app/controllers/orders_controller.rb", "pkg/db/conn.go",
    "src/components/Checkout.tsx", "scripts/migrate.py",
    "lib/stripe_client.js", "core/auth/jwt.py", "handlers/webhook.go",
    "services/email.py", "src/utils/logger.ts", "internal/api/routes.go",
    "app/models/user.rb", "lib/signing.py", "src/middleware/auth.ts",
    "workers/email_worker.py", "src/lib/db.ts",
]

# Error types — mix of language-flavored and protocol-level.
ERROR_TYPES = [
    "ConnectionError", "TimeoutError", "AuthorizationError",
    "ValidationError", "PermissionError", "NotFoundError", "ConflictError",
    "RateLimitError", "InternalServerError", "BadRequestError",
    "ECONNREFUSED", "ETIMEDOUT", "EHOSTUNREACH", "ENOTFOUND",
    "TypeError", "ReferenceError", "RuntimeError", "ValueError",
    "NullPointerException", "IllegalStateException", "OutOfMemoryError",
    "401 Unauthorized", "403 Forbidden", "404 Not Found",
    "500 Internal Server Error", "502 Bad Gateway", "503 Service Unavailable",
    "504 Gateway Timeout",
]

ERROR_MESSAGES = [
    "failed to connect to upstream",
    "request exceeded 30s deadline",
    "invalid credentials",
    "secret rotation pending",
    "downstream returned 502",
    "session expired during request",
    "missing required field 'user_id'",
    "could not parse response body",
    "context deadline exceeded",
    "max retries reached (3/3)",
    "circuit breaker is open",
    "lock acquisition timed out",
    "schema validation failed at index 4",
    "request body too large (max 10MB)",
]

# Ticket / issue tracker prefixes.
TICKET_PREFIXES = ["INC", "T", "BUG", "OPS", "PROJ", "ENG", "INFRA", "SUP"]

def gen_ticket() -> str:
    return f"{random.choice(TICKET_PREFIXES)}-{random.randint(100, 9999)}"

# Relative date references.
DATE_RELATIVE = [
    "yesterday", "this morning", "last week", "30 min ago",
    "earlier today", "just now", "around 2 PM", "Tuesday",
    "around midnight", "during last night's deploy", "right after lunch",
    "since the last release", "Friday afternoon", "the other day",
]

# Realistic but innocuous git commit hash. NOT a credential — appears in negatives.
def gen_short_sha() -> str:
    return "".join(random.choices("0123456789abcdef", k=7))

def gen_full_sha() -> str:
    return "".join(random.choices("0123456789abcdef", k=40))

def gen_uuid() -> str:
    g = random.getrandbits
    return f"{g(32):08x}-{g(16):04x}-{g(16):04x}-{g(16):04x}-{g(48):012x}"

# Container / runtime info — appears as innocuous context.
CLUSTERS = ["prod-us-east-1", "staging-eu-west-2", "dev-local",
            "prod-ap-south-1", "staging-us-west-2"]
DEPLOY_TARGETS = ["render", "fly.io", "railway", "vercel", "netlify",
                  "ecs-prod", "k8s-staging", "lambda"]
LANGUAGES = ["python", "typescript", "go", "ruby", "rust"]

def gen_human_first() -> str:
    return random.choice(FIRST_NAMES)

def gen_human_full() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def gen_filepath() -> str:
    base = random.choice(FILE_PATHS)
    return f"{base}:{random.randint(8, 320)}"

def gen_service() -> str:
    return random.choice(SERVICE_NAMES)
