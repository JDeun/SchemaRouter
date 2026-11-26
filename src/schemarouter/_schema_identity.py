"""Canonical declared-name normalization shared by paper and lexical research paths."""

from __future__ import annotations

import re
import unicodedata

_HALFWIDTH_KATAKANA_RE = re.compile(r"[\uFF66-\uFF9F]+")
_FULLWIDTH_ASCII_IDENTIFIER_RE = re.compile(r"[０-９Ａ-Ｚａ-ｚ＿]+")


def _locale_lexical_text(text: str) -> str:
    """Compose canonical Unicode, then fold only Japanese halfwidth kana.

    Korean NFD Jamo and NFC Hangul must search the same declared aliases.
    Do not apply global NFKC: unrelated compatibility symbols and units are
    not interchangeable capability names or numerical evidence.
    """
    canonical = unicodedata.normalize("NFC", text)
    kana_folded = _HALFWIDTH_KATAKANA_RE.sub(
        lambda match: unicodedata.normalize("NFKC", match.group()),
        canonical,
    )
    # Fullwidth ASCII letters/digits/underscore occur in Japanese tool
    # names and requests. Fold only those exact compatibility characters,
    # not all NFKC symbols: measurement units or circled numbers must never
    # gain a new capability identity by incidental normalization.
    identifier_folded = _FULLWIDTH_ASCII_IDENTIFIER_RE.sub(
        lambda match: unicodedata.normalize("NFKC", match.group()),
        kana_folded,
    )
    # Mixed-width input such as "カﾞ" is fullwidth KA followed by a
    # halfwidth dakuten. Folding the mark leaves a combining mark; compose
    # again to recover the same declared "ガ" lexical identity.
    return unicodedata.normalize("NFC", identifier_folded)


def _normalize(text: str) -> str:
    return "".join(ch.lower() for ch in _locale_lexical_text(text) if ch.isalnum())


# Match normalized Korean syllables and Japanese kana/kanji as lexical
# spans so explicitly declared multilingual aliases can be retrieved.
# Canonical Unicode equivalence is not a translation of tool metadata.
_TOKEN_RE = re.compile(
    r"[A-Za-z0-9_]+|[가-힣]+|[ぁ-ゖ]+|[ァ-ヺー]+|[一-鿿々〆]+"
)

_KOREAN_PARTICLE_SUFFIXES = (
    "에서",
    "에게",
    "으로",
    "까지",
    "부터",
    "처럼",
    "보다",
    "을",
    "를",
    "이",
    "가",
    "은",
    "는",
    "의",
    "에",
    "로",
    "와",
    "과",
)


def _tokens(text: str) -> set[str]:
    tokens = {
        token.lower() for token in _TOKEN_RE.findall(_locale_lexical_text(text))
    }
    expanded = set(tokens)
    for token in tokens:
        if not token or not all("가" <= char <= "힣" for char in token):
            continue
        for suffix in _KOREAN_PARTICLE_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix) + 1:
                expanded.add(token[: -len(suffix)])
                break
    return expanded
