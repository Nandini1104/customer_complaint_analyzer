"""Text preprocessing for complaints.

Negation words (not, no, never, n't) are deliberately KEPT because
"not working" and "working" have opposite sentiment.
"""
import hashlib
import html
import re

# Small stop-word list. Negations and intensity words are NOT included on purpose.
STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "am", "i", "me", "my",
    "we", "our", "you", "your", "it", "its", "this", "that", "these", "those", "to",
    "of", "in", "on", "at", "for", "with", "and", "or", "as", "by", "from", "so",
    "has", "have", "had", "do", "does", "did", "will", "would", "can", "could",
    "just", "also", "then", "there", "they", "them", "their", "he", "she", "his", "her",
}

CONTRACTIONS = [
    (r"\bwon't\b", "will not"), (r"\bcan't\b", "can not"), (r"\bcannot\b", "can not"),
    (r"n't\b", " not"), (r"'re\b", " are"), (r"'ve\b", " have"), (r"'ll\b", " will"),
    (r"'m\b", " am"), (r"'s\b", ""), (r"'d\b", " would"),
]

URL_RE = re.compile(r"https?://\S+|www\.\S+")
TAG_RE = re.compile(r"<[^>]+>")
MENTION_RE = re.compile(r"@\w+")
REPEAT_RE = re.compile(r"(.)\1{2,}")          # sooooo -> soo
NON_TEXT_RE = re.compile(r"[^a-z0-9\s]")       # symbols and emojis


def clean_text(text):
    """Lowercase, strip HTML/URLs/mentions/symbols, expand contractions, tidy spaces."""
    if text is None:
        return ""
    t = html.unescape(str(text))
    t = TAG_RE.sub(" ", t)
    t = URL_RE.sub(" ", t)
    t = MENTION_RE.sub(" ", t)
    t = t.replace("’", "'").lower()
    t = t.replace("#", " ")                    # keep the hashtag word, drop the symbol
    for pattern, repl in CONTRACTIONS:
        t = re.sub(pattern, repl, t)
    t = REPEAT_RE.sub(r"\1\1", t)
    t = NON_TEXT_RE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def tokenize(text, remove_stop_words=True):
    """Split cleaned text into tokens, optionally dropping stop words."""
    tokens = clean_text(text).split()
    if remove_stop_words:
        tokens = [w for w in tokens if w not in STOP_WORDS]
    return tokens


def preprocess_for_model(text):
    """Text given to the ML models: cleaned, stop words removed, negations kept."""
    return " ".join(tokenize(text))


def fingerprint(text):
    """Stable hash used for duplicate detection (same wording => same hash)."""
    return hashlib.sha1(clean_text(text).encode("utf-8")).hexdigest()
