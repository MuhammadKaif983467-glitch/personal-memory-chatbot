"""Deterministic embedding fallback for mock/local AI providers.

Produces fixed-dimension float vectors from text so retrieval, ranking and the
whole pipeline can run offline (tests included) without an external API.
Not meaningful for real semantic search, but stable and fast.

Two tricks make partial matches reliable for the offline/mock providers:

* light stemming (football/footballs, prefer/prefers, drink/drinking) so
  inflected variants overlap,
* multi-probe hashing: each token energizes K fixed buckets, so a shared word
  always boosts similarity strongly while unrelated words rarely collide.
"""

from __future__ import annotations

import hashlib
import math
import re

from numpy import float32, zeros

DEFAULT_DIM = 384
_PROBES = 4

_TOKEN = re.compile(r"[\w\u0600-\u06FF]+")

_SUFFIXES = (
    ("ing", 3),
    ("ies", 3),
    ("es", 2),
    ("ed", 2),
    ("s", 1),
)


def _stem(token: str) -> str:
    if len(token) <= 4 or not token.islower():
        return token
    for suffix, cut in _SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: len(token) - len(suffix)]
    return token


def hash_embedding(text: str, dim: int = DEFAULT_DIM) -> list:
    """Map text to a deterministic unit-length vector in ``dim`` space."""
    vector = zeros(dim, dtype=float32)
    tokens = [_stem(t) for t in _TOKEN.findall(text.casefold())]
    if not tokens:
        return vector.tolist()
    for token in tokens:
        digest = hashlib.sha256(f"emb:{token}".encode("utf-8")).digest()
        for probe in range(_PROBES):
            seed = (int.from_bytes(digest[probe * 2 : probe * 2 + 2], "big") << 8) + probe
            index = seed % dim
            sign = 1.0 if (digest[probe] % 2 == 0) else -1.0
            vector[index] += sign
    norm = float(math.sqrt(float((vector**2).sum()))) or 1.0
    return (vector / norm).tolist()