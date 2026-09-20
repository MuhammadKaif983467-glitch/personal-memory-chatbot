"""Lexical similarity for offline / mock AI providers.

Deterministic hash embeddings (utils/embeddings.py) are stable but have no
semantics, so vector cosine can rank unrelated memories above genuinely
relevant ones. When no real embedding model is available the retrieval service
falls back to lexical similarity, which combines:

  * stemming-aware token overlap (prefer/prefers match),
  * character bigram overlap for partial-word matches (football/footballs).

Both halves stay in [0, 1] so the result is comparable to a cosine score.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[\w\u0600-\u06FF]+")

_SUFFIXES = (
    ("ing", 3),
    ("ies", 3),
    ("es", 2),
    ("ed", 2),
    ("s", 1),
)


def _stem(token: str) -> str:
    if len(token) <= 4:
        return token
    for suffix, cut in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: len(token) - len(suffix)]
    return token


def _tokens(text: str) -> set[str]:
    return {_stem(t) for t in _TOKEN.findall(text.casefold())}


def _bigrams(text: str) -> set[str]:
    compact = "".join(_TOKEN.findall(text.casefold()))
    return {compact[i : i + 2] for i in range(max(0, len(compact) - 1))}


def lexical_similarity(a: str, b: str) -> float:
    tokens_a, tokens_b = _tokens(a), _tokens(b)
    if not tokens_a or not tokens_b:
        return 0.0
    token_overlap = len(tokens_a & tokens_b) / max(len(tokens_a), len(tokens_b))

    grams_a, grams_b = _bigrams(a), _bigrams(b)
    if not grams_a or not grams_b:
        gram_overlap = 0.0
    else:
        gram_overlap = len(grams_a & grams_b) / max(len(grams_a), len(grams_b))

    return round(0.6 * token_overlap + 0.4 * gram_overlap, 4)


_STOPWORDS = {
    "what", "who", "when", "where", "why", "how", "do", "does", "did", "is",
    "are", "am", "was", "were", "be", "been", "the", "a", "an", "of", "to",
    "in", "on", "at", "for", "and", "or", "but", "my", "me", "i", "you",
    "your", "it", "its", "this", "that", "these", "those", "about", "tell",
    "know", "please", "can", "could", "would", "should", "has", "have", "had",
    "with", "from", "there", "here", "any", "much", "many", "some", "get",
}

# Small, curated synonym groups so the offline provider can match intent words
# (e.g. "drink") to concrete values ("chai", "coffee") without a real model.
_SYNONYM_GROUPS = [
    {"like", "likes", "love", "loves", "prefer", "prefers", "favorite", "enjoy", "enjoys", "fond"},
    {"drink", "drinks", "beverage", "coffee", "chai", "tea", "water", "juice", "pepsi", "coke", "cola", "latte", "soda"},
    {"age", "old", "years", "year", "born", "birthday", "aged"},
    {"job", "work", "works", "working", "profession", "occupation", "career", "doctor", "engineer", "teacher", "lawyer", "business", "employed"},
    {"study", "studies", "studied", "university", "college", "school", "student", "degree", "major", "education", "graduated"},
    {"brother", "sister", "mother", "father", "parent", "parents", "family", "sibling", "son", "daughter", "wife", "husband", "sibling"},
    {"sport", "sports", "football", "cricket", "gym", "exercise", "play", "playing", "game", "match"},
    {"live", "lives", "living", "city", "home", "house", "hometown", "karachi", "lahore", "islamabad", "reside"},
    {"food", "eat", "eats", "eating", "meal", "meals", "dish", "cuisine", "hungry"},
    {"travel", "trip", "visit", "vacation", "tour", "holiday"},
    {"name", "called", "named"},
]

_WORD_TO_GROUP: dict[str, frozenset[str]] = {}
for _group in _SYNONYM_GROUPS:
    _stems = frozenset(_stem(word) for word in _group)
    for _stemmed in _stems:
        _WORD_TO_GROUP.setdefault(_stemmed, _stems)


def _content_tokens(text: str) -> set[str]:
    return {token for token in _tokens(text) if token not in _STOPWORDS and len(token) > 1}


def keyword_relevance(question: str, text: str) -> float:
    """Fraction of meaningful question terms matched, with synonym expansion.

    "What do I like to drink?" matches "Ali prefers chai over coffee" because
    like->prefer and drink->chai/coffee. Returns a value in [0, 1].
    """
    question_terms = _content_tokens(question)
    if not question_terms:
        return 0.0
    text_terms = _tokens(text)
    if not text_terms:
        return 0.0

    hits = 0
    for term in question_terms:
        variants = _WORD_TO_GROUP.get(term, frozenset({term})) | {term}
        if text_terms & variants:
            hits += 1
    return round(hits / len(question_terms), 4)


def best_relevance(question: str, text: str) -> float:
    """Strongest of lexical overlap and synonym-aware keyword matching."""
    return max(lexical_similarity(question, text), keyword_relevance(question, text))