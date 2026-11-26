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
