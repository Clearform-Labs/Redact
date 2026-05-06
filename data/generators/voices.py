"""
Voice / tone modulation. Real chat ranges from "lowercase tired Slack DM" to
"formal incident-postmortem prose." Every paste should pick a voice and stick to
it for that example. We don't mix mid-paragraph — that's what makes synthetic
data feel uncanny.

Each voice is a transformation function: takes plain prose, returns
voice-shaped prose. They're idempotent at small scale and probabilistic, so the
same input under the same voice produces small variations.

CRITICAL: voices must preserve the [value|LABEL] inline annotation markers
EXACTLY — both casing and content — because the training pipeline parses these
with a case-sensitive regex (`\\[...\\|[A-Z_]+\\]`). We protect markers by
swapping them for placeholders before any case transformation, then restoring.
"""

import random
import re
import string

# Marker pattern — matches our annotation syntax exactly.
_MARKER_RE = re.compile(r"\[[^\]\|]*\|[A-Z_]+\]")

def _apply_outside_markers(text: str, fn) -> str:
    """Apply `fn(str) -> str` to the prose between [value|LABEL] markers, leaving
    markers themselves byte-identical. Avoids placeholder schemes that any of our
    voice transformations might mangle (lowercase, typos, whitespace collapse)."""
    out = []
    last = 0
    for m in _MARKER_RE.finditer(text):
        if m.start() > last:
            out.append(fn(text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    if last < len(text):
        out.append(fn(text[last:]))
    return "".join(out)

# ── Voices ────────────────────────────────────────────────────────────────────

def _lowercase_contract(s: str) -> str:
    s = s.lower()
    for full, contracted in [
        ("do not", "don't"), ("does not", "doesn't"), ("did not", "didn't"),
        ("is not", "isn't"), ("was not", "wasn't"), ("are not", "aren't"),
        ("cannot", "can't"), ("could not", "couldn't"), ("would not", "wouldn't"),
        ("should not", "shouldn't"), ("will not", "won't"),
        ("i am", "i'm"), ("you are", "you're"), ("they are", "they're"),
        ("we are", "we're"), ("it is", "it's"), ("that is", "that's"),
    ]:
        s = s.replace(full, contracted)
    return s

def voice_lowercase_casual(text: str) -> str:
    """slack-dm energy. lowercase, contractions, drop terminal periods sometimes."""
    out = _apply_outside_markers(text, _lowercase_contract)
    if out.endswith(".") and random.random() < 0.3:
        out = out[:-1]
    return out

def voice_normal(text: str) -> str:
    """Standard sentence case, no transformation."""
    return text

def _terse_transform(s: str) -> str:
    # Drop "the" probabilistically — but be careful around code blocks where
    # `the` might be part of a string. We only operate on whitespace-tokenized
    # words here, which is fine for prose; voice modulation isn't applied to
    # code/bug-report/CI-log contexts (filtered upstream).
    parts = []
    for word in s.split(" "):
        if word.lower() == "the" and random.random() < 0.4:
            continue
        parts.append(word)
    out = " ".join(parts)
    for full, abbr in [
        ("repository", "repo"), ("documentation", "docs"), ("environment", "env"),
        ("development", "dev"), ("production", "prod"), ("staging", "stg"),
        ("configuration", "config"), ("application", "app"),
    ]:
        if random.random() < 0.5:
            out = out.replace(full, abbr)
    return out

def voice_terse(text: str) -> str:
    """Devspeak: drop articles, abbreviate, no fluff."""
    return _apply_outside_markers(text, _terse_transform)

def _panicked_transform(s: str) -> str:
    out = s
    if random.random() < 0.5:
        for word in ["urgent", "now", "broken", "down", "leaked", "exposed"]:
            if word in out.lower():
                out = out.replace(word, word.upper())
                break
    return out

def voice_panicked(text: str) -> str:
    """Production is on fire energy. Caps emphasis, repeated punctuation."""
    out = _apply_outside_markers(text, _panicked_transform)
    if out.endswith("?") and random.random() < 0.4:
        out = out[:-1] + "??"
    elif out.endswith(".") and random.random() < 0.3:
        out = out[:-1] + "!!"
    return out


VOICES = [
    voice_lowercase_casual,
    voice_normal,
    voice_normal,           # weight normal higher — most pastes are standard
    voice_normal,
    voice_terse,
    voice_panicked,
]


def apply_voice(text: str, voice=None) -> str:
    """Apply a randomly-chosen voice to plain text."""
    return (voice or random.choice(VOICES))(text)


# ── Realistic noise ───────────────────────────────────────────────────────────
# Subtle imperfection. Don't go overboard — too many typos look like a bot
# trying to mimic typos. Keep this rare.

ADJ_KEYS = {
    "a": "sq", "s": "ad", "d": "sf", "f": "dg", "g": "fh", "h": "gj",
    "j": "hk", "k": "jl", "l": "k",
    "q": "wa", "w": "qe", "e": "wr", "r": "et", "t": "ry", "y": "tu",
    "u": "yi", "i": "uo", "o": "ip", "p": "o",
    "z": "x", "x": "zc", "c": "xv", "v": "cb", "b": "vn", "n": "bm", "m": "n",
}

def maybe_typo(text: str, rate: float = 0.005) -> str:
    """Substitute a small fraction of letters with adjacent-key typos. Skips
    characters inside [value|LABEL] markers so credential values stay verbatim."""
    def _typo(s: str) -> str:
        out = []
        for ch in s:
            if ch.lower() in ADJ_KEYS and random.random() < rate:
                replacement = random.choice(ADJ_KEYS[ch.lower()])
                out.append(replacement.upper() if ch.isupper() else replacement)
            else:
                out.append(ch)
        return "".join(out)
    return _apply_outside_markers(text, _typo)
