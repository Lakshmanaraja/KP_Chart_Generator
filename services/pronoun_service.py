"""Turn generic pronoun pairs into natural, gender-aware report wording."""
from __future__ import annotations

import re
from typing import Optional


def _pair(first: str, second: str) -> str:
    """Match either order, with 'or' or a slash and flexible spacing."""
    alternatives = (
        rf"{first}\s*(?:/|\s+or\s+)\s*{second}",
        rf"{second}\s*(?:/|\s+or\s+)\s*{first}",
    )
    return rf"(?<![A-Za-z])(?:{'|'.join(alternatives)})(?![A-Za-z])"


# Longer/more specific forms come first so 'his or hers' is not read as
# 'his or her'. Standalone pronouns are deliberately untouched: they may refer
# to somebody other than the report subject.
_PAIRS = (
    (_pair("himself", "herself"), "himself", "herself", "themselves"),
    (_pair("his", "hers"), "his", "hers", "theirs"),
    (_pair("his", "her"), "his", "her", "their"),
    (_pair("he", "she"), "he", "she", "they"),
    (_pair("him", "her"), "him", "her", "them"),
)
_COMPILED = tuple((re.compile(pattern, re.IGNORECASE), male, female, neutral)
                  for pattern, male, female, neutral in _PAIRS)


def _match_case(source: str, replacement: str) -> str:
    letters = "".join(character for character in source if character.isalpha())
    if letters and letters.isupper():
        return replacement.upper()
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _neutral_agreement(text: str) -> str:
    """Keep common singular-template verbs grammatical after 'they'."""
    replacements = {
        "isn't": "aren't", "wasn't": "weren't", "hasn't": "haven't", "doesn't": "don't",
        "is": "are", "was": "were", "has": "have", "does": "do",
        "goes": "go", "needs": "need", "wants": "want", "likes": "like",
        "feels": "feel", "seems": "seem", "appears": "appear", "becomes": "become",
        "shows": "show", "takes": "take", "makes": "make", "finds": "find",
        "gives": "give", "enjoys": "enjoy", "prefers": "prefer", "learns": "learn",
        "grows": "grow", "develops": "develop", "values": "value", "seeks": "seek",
        "loves": "love", "dislikes": "dislike", "avoids": "avoid", "requires": "require",
        "responds": "respond", "tends": "tend",
    }
    verbs = "|".join(re.escape(verb) for verb in replacements)
    pattern = re.compile(rf"\b(they)(\s+)({verbs})\b", re.IGNORECASE)

    def replace(match: re.Match) -> str:
        they, whitespace, verb = match.groups()
        replacement = replacements[verb.lower()]
        if they.isupper():
            replacement = replacement.upper()
        return f"{they}{whitespace}{replacement}"

    result = pattern.sub(replace, text)
    coordinated = re.compile(
        rf"(\bthey\b[^.!?]{{0,160}}?\b(?:and|or|but|yet)\s+(?:[a-z'-]+\s+){{0,2}})({verbs})\b",
        re.IGNORECASE,
    )

    def replace_coordinated(match: re.Match) -> str:
        lead, verb = match.groups()
        replacement = replacements[verb.lower()]
        if lead.isupper():
            replacement = replacement.upper()
        return f"{lead}{replacement}"

    return coordinated.sub(replace_coordinated, result)


def personalize_pronouns(text: str, gender: Optional[str] = None) -> str:
    """Replace generic pronoun pairs, defaulting to singular they/their/them.

    Male/boy and female/girl values are accepted case-insensitively. Unknown,
    blank or omitted values use neutral wording rather than failing a report.
    """
    normalized = str(gender or "").strip().lower()
    index = 0 if normalized in {"male", "m", "boy", "man"} else 1 if normalized in {"female", "f", "girl", "woman"} else 2
    result = str(text or "")
    for pattern, male, female, neutral in _COMPILED:
        replacement = (male, female, neutral)[index]
        result = pattern.sub(lambda match: _match_case(match.group(0), replacement), result)
    return _neutral_agreement(result) if index == 2 else result
