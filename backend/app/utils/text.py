"""Text helpers used across cleaning, style analysis and profile extraction.

Includes light heuristics for language detection (English / Urdu / Roman
Urdu) since chat data from Pakistan/South Asia is often mixed-language.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Sequence

# ---- Emoji / unicode helpers ----
EMOJI_PATTERN = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027B0\U0001F1E0-\U0001F1FF\u00a9\u00ae\u3030\u303d]"
)
SCRIPT_MARKS = "\u200e\u200f\u202a\u202b\u202c\u202d\u202e"

# Letters that are meaningless as words (single char, punctuation etc.)
_WORD_PATTERN = re.compile(r"[\w\u0600-\u06FF]+")

# Urdu characters (Arabic script blocks used by Urdu).
URDU_CHARS = re.compile(r"[\u0600-\u06FF]")

# Common free/under-rated stopwords incl. Roman Urdu particles
STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "is", "are", "was", "were", "be", "been", "to", "of", "in",
    "on", "at", "for", "with", "from", "by", "i", "me", "my", "we", "our", "you", "your", "he", "she",
    "it", "they", "them", "his", "her", "its", "this", "that", "these", "those", "have", "has", "had",
    "do", "does", "did", "will", "would", "shall", "should", "can", "could", "may", "might", "not",
    "no", "so", "very", "just", "like", "don't", "dont", "i'm", "im", "you're", "there", "about",
    "what", "which", "who", "when", "where", "why", "how", "all", "some", "any", "more", "most",
    "other", "only", "also",
    # Roman Urdu particles
    "hai", "hain", "hona", "tha", "the", "thi", "ka", "ki", "ke", "ko", "me", "mien", "se", "par",
    "aur", "ya", "kyun", "kya", "kahan", "kaise", "bahut", "bhi", "hua", "hue", "ho", "hu", "nahi",
    "nhi", "ab", "abhi", "to", "jo", "jab", "phir", "wala", "wale", "apna", "aap", "tum", "main",
    "mujhe", "mera", "mere", "apni", "acha", "accha", "theek", "thk", "ok", "okay", "hmm", "haan",
    "nai", "bhai", "bro", "yaar",
}

POSITIVE_WORDS = {"love", "like", "great", "nice", "awesome", "cool", "good", "happy", "best",
                  "enjoy", "amazing", "excellent", "fantastic"}
NEGATIVE_WORDS = {"hate", "don't", "dont", "bad", "sad", "angry", "terrible", "awful", "worst",
                  "boring", "annoyed", "upset", "cry"}

ROMAN_URDU_WORDS = {
    "hai", "hain", "kya", "kyun", "kahan", "kaise", "acha", "accha", "nahi", "nhi", "abhi", "sab",
    "aap", "tum", "mera", "tere", "apna", "bhi", "wala", "wale", "bahut", "theek", "tha", "thi",
    "aur", "ya", "mujhe", "main", "ho", "hu", "milen", "chala", "gaya", "karo", "karte", "raha",
}


def strip_dir_marks(text: str) -> str:
    return text.translate({ord(c): None for c in SCRIPT_MARKS})


def normalize_whitespace(text: str) -> str:
    """Trim + collapse runs of whitespace. Direction marks are removed."""
    if not text:
        return ""
    return " ".join(strip_dir_marks(text).split())


def tokenize_words(text: str) -> list[str]:
    """Lowercase word tokens (handles English + Urdu script)."""
    return _WORD_PATTERN.findall(text.casefold())


def meaningful_words(text: str) -> list[str]:
    """Word tokens minus stopwords and pure numbers."""
    words = []
    for w in tokenize_words(text):
        if w in STOPWORDS or w.isdigit():
            continue
        words.append(w)
    return words


def top_tokens(texts: Sequence[str], n: int = 10) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(meaningful_words(text))
    return [w for w, _c in counter.most_common(n)]


def top_phrases(texts: Sequence[str], n: int = 5) -> list[str]:
    """Most frequent word bigrams across texts."""
    counter: Counter[str] = Counter()
    for text in texts:
        words = tokenize_words(text)
        for i in range(len(words) - 1):
            if words[i] in STOPWORDS or words[i + 1] in STOPWORDS:
                continue
            counter[f"{words[i]} {words[i+1]}"] += 1
    return [p for p, _c in counter.most_common(n)]


def count_emoji(text: str) -> int:
    return len(EMOJI_PATTERN.findall(text))


def common_emojis(texts: Sequence[str], n: int = 8) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(EMOJI_PATTERN.findall(text))
    return [e for e, _c in counter.most_common(n)]


def has_urdu_script(text: str) -> bool:
    return bool(URDU_CHARS.search(text))


def is_roman_urdu(text: str) -> bool:
    words = tokenize_words(text)
    if not words:
        return False
    hits = sum(1 for w in words if w in ROMAN_URDU_WORDS)
    return hits >= 2 or (hits == 1 and len(words) <= 4)


def detect_language(text: str) -> tuple[str, float]:
    """Best-effort language guess.

    Returns (language, confidence in [0, 1]) where language is one of
    english | urdu | roman-urdu | unknown.
    """
    if has_urdu_script(text):
        return "urdu", 0.9
    if not text.strip():
        return "unknown", 0.0
    if is_roman_urdu(text):
        return "roman-urdu", 0.7
    words = tokenize_words(text)
    recognizable = sum(1 for w in words if re.fullmatch(r"[a-z]+", w))
    if words and recognizable / len(words) >= 0.5:
        return "english", 0.8
    return "english", 0.5


def detect_tone(texts: Sequence[str]) -> str:
    """Very light sentiment heuristic used only to label communication tone."""
    positive = sum(1 for t in texts if any(w in t.casefold() for w in POSITIVE_WORDS))
    negative = sum(1 for t in texts if any(w in t.casefold() for w in NEGATIVE_WORDS))
    emoji_happy = sum(1 for t in texts if any(e in t for e in ("😀", "😂", "😍", "🥰", "🙂", "😄", "🎉")))
    if positive + emoji_happy > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"


def is_repeat_chars(text: str) -> bool:
    """Heuristic for spammy repetition like 'aaaaaaaa' or 'hahahaha'."""
    runs = [len(g) for g in re.findall(r"(.)\1{3,}", text.casefold())]
    return any(run >= 5 for run in runs)