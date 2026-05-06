# Synthetic-data generators for Redact v3 model training.
#
# Modules:
#   fillers   — realistic names, companies, file paths, error types, etc.
#   formats   — credential value generators (one function per credential type)
#   voices    — tone/casing modulation
#   contexts  — paste-style templates that embed entities in realistic prose
#   negatives — hard-negative paste templates (no PII but lookalike content)
#   v3        — orchestrator / CLI entrypoint
